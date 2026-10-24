
import json
from datetime import date
from decimal import Decimal
from typing import Any

from uagents import Agent, Context

from app.agents.goal_agent import analyze_goals
from app.agents.network_messages import AgentTask, AgentTaskResult
from app.config import AGENT_SEEDS
from app.schemas.financial_models import SavingsGoal


DEFAULT_PORT = 8014
AGENT_NAME = "rupeepilot-goal"


def build_goal_agent(
    seed: str | None = None,
    port: int = DEFAULT_PORT,
) -> Agent:
    """Build the Goal Agent and register its message handler."""

    resolved_seed = (
        seed or AGENT_SEEDS["goal"]
    ).strip()

    if not resolved_seed:
        raise ValueError(
            "GOAL_AGENT_SEED is missing. "
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
            "Goal Agent started. Address: %s",
            ctx.agent.address,
        )
        ctx.logger.info(
            "Goal Agent listening on port %s.",
            port,
        )

    @agent.on_message(model=AgentTask)
    async def handle_goal_task(
        ctx: Context,
        sender: str,
        msg: AgentTask,
    ) -> None:
        """Analyze savings goals and return a structured response."""

        ctx.logger.info(
            "Received goal task %s from %s",
            msg.request_id,
            sender,
        )

        if msg.task_type != "goal":
            await ctx.send(
                sender,
                AgentTaskResult(
                    request_id=msg.request_id,
                    agent_name="goal",
                    success=False,
                    error=(
                        "Unsupported task type. "
                        "Expected 'goal'."
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

            goals_data = payload.get("goals", [])

            if not isinstance(goals_data, list):
                raise ValueError(
                    "'goals' must be a JSON array."
                )

            goals = [
                SavingsGoal.model_validate(item)
                for item in goals_data
            ]

            contributions_data = payload.get(
                "proposed_contributions",
                {},
            )

            if not isinstance(contributions_data, dict):
                raise ValueError(
                    "'proposed_contributions' must be a JSON object."
                )

            proposed_contributions: dict[str, Decimal] = {}

            for goal_name, amount in contributions_data.items():
                if not isinstance(goal_name, str):
                    raise ValueError(
                        "Contribution goal names must be strings."
                    )

                if isinstance(amount, bool):
                    raise ValueError(
                        "Contribution amounts must be numeric."
                    )

                contribution = Decimal(str(amount))

                if not contribution.is_finite():
                    raise ValueError(
                        f"Contribution for '{goal_name}' "
                        "must be a finite number."
                    )

                if contribution < Decimal("0"):
                    raise ValueError(
                        f"Contribution for '{goal_name}' "
                        "cannot be negative."
                    )

                proposed_contributions[goal_name] = contribution

            raw_reference_date = payload.get("reference_date")

            if raw_reference_date is None:
                reference_date = date.today()
            elif isinstance(raw_reference_date, str):
                reference_date = date.fromisoformat(
                    raw_reference_date
                )
            else:
                raise ValueError(
                    "'reference_date' must be an ISO date string."
                )

            analysis = analyze_goals(
                goals,
                proposed_contributions=proposed_contributions,
                reference_date=reference_date,
            )

            result_json = json.dumps(
                analysis,
                default=str,
                separators=(",", ":"),
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="goal",
                success=True,
                result_json=result_json,
            )

            ctx.logger.info(
                "Goal analysis completed for request %s.",
                msg.request_id,
            )

        except Exception as exc:
            ctx.logger.exception(
                "Goal analysis failed for request %s.",
                msg.request_id,
            )

            response = AgentTaskResult(
                request_id=msg.request_id,
                agent_name="goal",
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        await ctx.send(sender, response)

    return agent
