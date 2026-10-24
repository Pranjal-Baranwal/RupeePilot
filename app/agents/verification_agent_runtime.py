
import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from uagents import Agent, Context

from app.agents.network_messages import AgentTask, AgentTaskResult
from app.agents.verification_agent import verify_scenario
from app.config import AGENT_SEEDS
from app.schemas.financial_models import (
    FinancialProfile,
    PlanningScenario,
)


DEFAULT_PORT = 8016
AGENT_NAME = "rupeepilot-verification"


def _json_default(value: Any) -> Any:
    """Serialize model and monetary values without losing precision."""

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")

    raise TypeError(
        f"Unsupported JSON value: {type(value).__name__}"
    )


def build_verification_agent(
    seed: str | None = None,
    port: int = DEFAULT_PORT,
) -> Agent:
    """Build the Verification Agent and register its message handler."""

    resolved_seed = (
        seed or AGENT_SEEDS["verification"]
    ).strip()

    if not resolved_seed:
        raise ValueError(
            "VERIFICATION_AGENT_SEED is missing. "
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
            "Verification Agent started. Address: %s",
            ctx.agent.address,
        )
        ctx.logger.info(
            "Verification Agent listening on port %s.",
            port,
        )

    @agent.on_message(model=AgentTask)
    async def handle_verification_task(
        ctx: Context,
        sender: str,
        msg: AgentTask,
    ) -> None:
        """Verify a candidate and return a structured report."""

        ctx.logger.info(
            "Received verification task %s from %s",
            msg.request_id,
            sender,
        )

        if msg.task_type != "verification":
            await ctx.send(
                sender,
                AgentTaskResult(
                    request_id=msg.request_id,
                    agent_name="verification",
                    success=False,
                    error=(
                        "Unsupported task type. "
                        "Expected 'verification'."
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

            profile_data = payload.get("profile")
            candidate_data = payload.get("candidate")

            if not isinstance(profile_data, dict):
                raise ValueError(
                    "The payload must contain a 'profile' object."
                )

            if not isinstance(candidate_data, dict):
                raise ValueError(
                    "The payload must contain a 'candidate' object."
                )

            profile = FinancialProfile.model_validate(
                profile_data
            )

            candidate = PlanningScenario.model_validate(
                candidate_data
            )

            # Independently recalculate and check the proposed plan.
            verification = verify_scenario(
                profile,
                candidate,
            )

            result_json = json.dumps(
                verification,
                default=_json_default,
                separators=(",", ":"),
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="verification",
                success=True,
                result_json=result_json,
            )

            ctx.logger.info(
                "Verification completed for request %s. Approved: %s",
                msg.request_id,
                verification["approved"],
            )

        except Exception as exc:
            ctx.logger.exception(
                "Verification failed for request %s.",
                msg.request_id,
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="verification",
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        await ctx.send(sender, response)

    return agent
