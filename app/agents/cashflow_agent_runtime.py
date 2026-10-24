
import json
from typing import Any

from uagents import Agent, Context

from app.agents.cashflow_agent import analyze_cashflow
from app.agents.network_messages import AgentTask, AgentTaskResult
from app.config import AGENT_SEEDS
from app.schemas.financial_models import FinancialProfile


DEFAULT_PORT = 8012
AGENT_NAME = "rupeepilot-cashflow"


def build_cashflow_agent(
    seed: str | None = None,
    port: int = DEFAULT_PORT,
) -> Agent:
    """Construct the Cash-Flow Agent and register its handler."""

    resolved_seed = (
        seed or AGENT_SEEDS["cashflow"]
    ).strip()

    if not resolved_seed:
        raise ValueError(
            "CASHFLOW_AGENT_SEED is missing. "
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
            "Cash-Flow Agent started. Address: %s",
            ctx.agent.address,
        )
        ctx.logger.info(
            "Cash-Flow Agent listening on port %s.",
            port,
        )

    @agent.on_message(model=AgentTask)
    async def handle_cashflow_task(
        ctx: Context,
        sender: str,
        msg: AgentTask,
    ) -> None:
        """Analyze a financial profile and return a structured result."""

        ctx.logger.info(
            "Received task %s from %s",
            msg.request_id,
            sender,
        )

        if msg.task_type != "cashflow":
            await ctx.send(
                sender,
                AgentTaskResult(
                    request_id=msg.request_id,
                    agent_name="cashflow",
                    success=False,
                    error=(
                        "Unsupported task type. "
                        "Expected 'cashflow'."
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

            profile_data = payload.get("profile", payload)

            if not isinstance(profile_data, dict):
                raise ValueError(
                    "The profile must be a JSON object."
                )

            profile = FinancialProfile.model_validate(
                profile_data
            )

            analysis = analyze_cashflow(profile)

            # Preserve Decimal precision when serializing amounts.
            result_json = json.dumps(
                analysis,
                default=str,
                separators=(",", ":"),
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="cashflow",
                success=True,
                result_json=result_json,
            )

            ctx.logger.info(
                "Cash-flow analysis completed for request %s.",
                msg.request_id,
            )

        except Exception as exc:
            ctx.logger.exception(
                "Cash-flow analysis failed for request %s.",
                msg.request_id,
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="cashflow",
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        await ctx.send(sender, response)

    return agent
