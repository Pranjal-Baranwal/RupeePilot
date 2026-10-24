
import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from uagents import Agent, Context

from app.agents.scenario_agent import generate_scenarios
from app.agents.network_messages import AgentTask, AgentTaskResult
from app.config import AGENT_SEEDS
from app.schemas.financial_models import FinancialProfile


DEFAULT_PORT = 8015
AGENT_NAME = "rupeepilot-scenario"


def _json_default(value: Any) -> Any:
    """Serialize financial and Pydantic values without losing precision."""

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")

    raise TypeError(
        f"Unsupported JSON value: {type(value).__name__}"
    )


def build_scenario_agent(
    seed: str | None = None,
    port: int = DEFAULT_PORT,
) -> Agent:
    """Build the Scenario Agent and register its message handler."""

    resolved_seed = (
        seed or AGENT_SEEDS["scenario"]
    ).strip()

    if not resolved_seed:
        raise ValueError(
            "SCENARIO_AGENT_SEED is missing. "
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
            "Scenario Agent started. Address: %s",
            ctx.agent.address,
        )
        ctx.logger.info(
            "Scenario Agent listening on port %s.",
            port,
        )

    @agent.on_message(model=AgentTask)
    async def handle_scenario_task(
        ctx: Context,
        sender: str,
        msg: AgentTask,
    ) -> None:
        """Generate and rank candidate budget scenarios."""

        ctx.logger.info(
            "Received scenario task %s from %s",
            msg.request_id,
            sender,
        )

        if msg.task_type != "scenario":
            await ctx.send(
                sender,
                AgentTaskResult(
                    request_id=msg.request_id,
                    agent_name="scenario",
                    success=False,
                    error=(
                        "Unsupported task type. "
                        "Expected 'scenario'."
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

            if not isinstance(profile_data, dict):
                raise ValueError(
                    "The payload must contain a 'profile' object."
                )

            profile = FinancialProfile.model_validate(
                profile_data
            )

            max_scenarios = payload.get("max_scenarios", 6)

            if (
                not isinstance(max_scenarios, int)
                or isinstance(max_scenarios, bool)
                or max_scenarios < 1
                or max_scenarios > 20
            ):
                raise ValueError(
                    "'max_scenarios' must be an integer "
                    "between 1 and 20."
                )

            analysis = generate_scenarios(
                profile,
                max_scenarios=max_scenarios,
            )

            result_json = json.dumps(
                analysis,
                default=_json_default,
                separators=(",", ":"),
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="scenario",
                success=True,
                result_json=result_json,
            )

            ctx.logger.info(
                "Generated %s scenarios for request %s.",
                analysis["metrics"]["scenario_count"],
                msg.request_id,
            )

        except Exception as exc:
            ctx.logger.exception(
                "Scenario generation failed for request %s.",
                msg.request_id,
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="scenario",
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        await ctx.send(sender, response)

    return agent
