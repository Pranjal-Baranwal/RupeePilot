
import json
from datetime import date
from typing import Any

from uagents import Agent, Context

from app.agents.bills_agent import analyze_bills
from app.agents.network_messages import AgentTask, AgentTaskResult
from app.config import AGENT_SEEDS
from app.schemas.financial_models import Bill


DEFAULT_PORT = 8013
AGENT_NAME = "rupeepilot-bills"


def build_bills_agent(
    seed: str | None = None,
    port: int = DEFAULT_PORT,
) -> Agent:
    """Build the Bills Agent and register its message handler."""

    resolved_seed = (
        seed or AGENT_SEEDS["bills"]
    ).strip()

    if not resolved_seed:
        raise ValueError(
            "BILLS_AGENT_SEED is missing. "
            "Configure it in your .env file before starting "
            "the agent network."
        )

    if not 1024 <= port <= 65535:
        raise ValueError(
            "port must be between 1024 and 65535."
        )

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
            f"Bills Agent started. Address: {ctx.agent.address}"
        )
        ctx.logger.info(
            f"Bills Agent listening on port {port}."
        )

    @agent.on_message(model=AgentTask)
    async def handle_bills_task(
        ctx: Context,
        sender: str,
        msg: AgentTask,
    ) -> None:
        """Analyze individual bills and respond to the sender."""

        ctx.logger.info(
            f"Received bills task {msg.request_id} from {sender}"
        )

        if msg.task_type != "bills":
            await ctx.send(
                sender,
                AgentTaskResult(
                    request_id=msg.request_id,
                    agent_name="bills",
                    success=False,
                    error=(
                        "Unsupported task type. "
                        "Expected 'bills'."
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

            bills_data = payload.get("bills", [])

            if not isinstance(bills_data, list):
                raise ValueError(
                    "'bills' must be a JSON array."
                )

            bills = [
                Bill.model_validate(item)
                for item in bills_data
            ]

            raw_reference_date = payload.get("reference_date")

            if raw_reference_date is None:
                reference_date = date.today()
            else:
                reference_date = date.fromisoformat(
                    raw_reference_date
                )

            horizon_days = payload.get("horizon_days", 7)

            if (
                not isinstance(horizon_days, int)
                or isinstance(horizon_days, bool)
                or horizon_days < 0
            ):
                raise ValueError(
                    "'horizon_days' must be a non-negative integer."
                )

            analysis = analyze_bills(
                bills,
                reference_date=reference_date,
                horizon_days=horizon_days,
            )

            # Serialize Decimal amounts without converting them
            # to imprecise floating-point numbers.
            result_json = json.dumps(
                analysis,
                default=str,
                separators=(",", ":"),
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="bills",
                success=True,
                result_json=result_json,
            )

            ctx.logger.info(
                f"Bills analysis completed for {msg.request_id}."
            )

        except Exception as exc:
            ctx.logger.exception(
                f"Bills analysis failed for {msg.request_id}."
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="bills",
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        await ctx.send(sender, response)

    return agent
