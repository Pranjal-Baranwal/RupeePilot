
import json
import logging
import secrets
import sys
from decimal import Decimal
from pathlib import Path

# Ensure the project root is importable when this file
# is launched directly from the tests directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from uagents import Agent, Context

from app.agents.network_messages import AgentTask, AgentTaskResult
from app.schemas.financial_models import FinancialProfile
from run_network import build_network



logging.basicConfig(level=logging.INFO)

REQUEST_ID = "rupeepilot-live-smoke-expense"


def main() -> None:
    # Build all seven application agents in one Bureau.
    bureau, specialists, coordinator = build_network()

    expense_agent = specialists["expense"]

    # A temporary probe agent tests real in-process messaging.
    probe = Agent(
        name="rupeepilot-smoke-probe",
        seed=f"rupeepilot-smoke-{secrets.token_hex(32)}",
        port=8017,
    )

    @probe.on_interval(period=3.0)
    async def send_test_task(ctx: Context) -> None:
        nonlocal task_sent

        if task_sent:
            return

        task_sent = True

        profile = FinancialProfile(
            monthly_income=Decimal("28000"),
            opening_balance=Decimal("0"),
            fixed_bills=Decimal("10000"),
            regular_spending=Decimal("8000"),
            planned_savings=Decimal("6000"),
            unexpected_expenses=Decimal("8000"),
            max_spending_cut=Decimal("0"),
            minimum_cash_buffer=Decimal("0"),
        )

        payload = json.dumps({
            "profile": profile.model_dump(mode="json")
        })

        await ctx.send(
            expense_agent.address,
            AgentTask(
                request_id=REQUEST_ID,
                task_type="expense",
                payload_json=payload,
            ),
        )

        ctx.logger.info(
            "SMOKE TEST: Sent expense task to %s",
            expense_agent.address,
        )

    @probe.on_message(model=AgentTaskResult)
    async def receive_result(
        ctx: Context,
        sender: str,
        msg: AgentTaskResult,
    ) -> None:
        if msg.request_id != REQUEST_ID:
            return

        if not msg.success:
            ctx.logger.error(
                "SMOKE TEST FAILED: %s",
                msg.error,
            )
            return

        result = json.loads(msg.result_json)

        actual_balance = Decimal(
            str(result["metrics"]["remaining_after_unexpected"])
        )

        expected_balance = Decimal("-4000")

        if (
            msg.agent_name == "expense"
            and actual_balance == expected_balance
        ):
            ctx.logger.info(
                "SMOKE TEST PASSED: Expense Agent received "
                "the message and returned the correct balance: %s",
                actual_balance,
            )
        else:
            ctx.logger.error(
                "SMOKE TEST FAILED: agent=%s, balance=%s",
                msg.agent_name,
                actual_balance,
            )

    task_sent = False

    bureau.add(probe)

    logging.info(
        "Starting seven-agent network plus temporary probe."
    )
    logging.info(
        "Coordinator address: %s",
        coordinator.address,
    )

    bureau.run()


if __name__ == "__main__":
    main()
