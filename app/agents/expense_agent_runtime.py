
import json
from typing import Any

from uagents import Agent, Context

from app.agents.expense_agent import analyze_expenses
from app.agents.network_messages import AgentTask, AgentTaskResult
from app.config import AGENT_SEEDS
from app.schemas.financial_models import FinancialProfile


DEFAULT_PORT = 8011
AGENT_NAME = "rupeepilot-expense"


def build_expense_agent(
    seed: str | None = None,
    port: int = DEFAULT_PORT,
) -> Agent:
    """Build the Expense Agent and register its message handler.

    Pass the persistent expense-agent seed from configuration.
    A separate port is used so this agent can run alongside the
    other local agents.
    """

    resolved_seed = (
        seed or AGENT_SEEDS["expense"]
    ).strip()

    if not resolved_seed:
        raise ValueError(
            "EXPENSE_AGENT_SEED is missing. "
            "Configure it in your .env file before starting "
            "the agent network."
        )

    if not 1024 <= port <= 65535:
        raise ValueError("port must be between 1024 and 65535.")

    agent = Agent(
        name=AGENT_NAME,
        seed=resolved_seed,
        port=port,
        endpoint=[
            f"http://127.0.0.1:{port}/submit"
        ],
    )

    @agent.on_event("startup")
    async def on_startup(ctx: Context) -> None:
        ctx.logger.info(
            "Expense Agent started. Address: %s",
            ctx.agent.address,
        )
        ctx.logger.info(
            "Expense Agent listening on port %s.",
            port,
        )

    @agent.on_message(model=AgentTask)
    async def handle_expense_task(
        ctx: Context,
        sender: str,
        msg: AgentTask,
    ) -> None:
        """Receive a task, analyze the profile, and reply."""

        ctx.logger.info(
            "Received task %s from %s",
            msg.request_id,
            sender,
        )

        if msg.task_type != "expense":
            await ctx.send(
                sender,
                AgentTaskResult(
                    request_id=msg.request_id,
                    agent_name="expense",
                    success=False,
                    error=(
                        "Unsupported task type. "
                        "Expected 'expense'."
                    ),
                ),
            )
            return

        try:
            payload: Any = json.loads(msg.payload_json)

            if not isinstance(payload, dict):
                raise ValueError(
                    "Task payload must be a JSON object."
                )

            # Accept either {"profile": {...}} or a profile object.
            profile_data = payload.get("profile", payload)

            if not isinstance(profile_data, dict):
                raise ValueError(
                    "The profile must be a JSON object."
                )

            profile = FinancialProfile.model_validate(
                profile_data
            )

            analysis = analyze_expenses(profile)

            # Decimal values are serialized as strings to preserve
            # exact monetary amounts across the network.
            result_json = json.dumps(
                analysis,
                default=str,
                separators=(",", ":"),
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="expense",
                success=True,
                result_json=result_json,
            )

            ctx.logger.info(
                "Expense analysis completed for request %s.",
                msg.request_id,
            )

        except Exception as exc:
            ctx.logger.exception(
                "Expense analysis failed for request %s.",
                msg.request_id,
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="expense",
                success=False,
                error=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        await ctx.send(sender, response)

    return agent