
import logging
import sys

from uagents import Agent, Bureau

from app.agents.bills_agent_runtime import build_bills_agent
from app.agents.cashflow_agent_runtime import build_cashflow_agent
from app.agents.expense_agent_runtime import build_expense_agent
from app.agents.goal_agent_runtime import build_goal_agent
from app.agents.scenario_agent_runtime import build_scenario_agent
from app.agents.verification_agent_runtime import (
    build_verification_agent,
)
from app.config import configure_logging, validate_agent_seeds


def build_worker_network() -> tuple[Bureau, dict[str, Agent]]:
    """Build the six internal specialists."""

    validate_agent_seeds()

    workers = {
        "expense": build_expense_agent(port=8011),
        "cashflow": build_cashflow_agent(port=8012),
        "bills": build_bills_agent(port=8013),
        "goal": build_goal_agent(port=8014),
        "scenario": build_scenario_agent(port=8015),
        "verification": build_verification_agent(port=8016),
    }

    # The Bureau exposes a single local submission endpoint.
    # Its agents share this endpoint for message routing.
    bureau = Bureau(
        port=8000,
        endpoint="http://127.0.0.1:8000/submit",
    )

    for worker in workers.values():
        bureau.add(worker)

    return bureau, workers


def main() -> int:
    configure_logging()
    logger = logging.getLogger("rupeepilot.workers")

    try:
        bureau, workers = build_worker_network()
    except (ValueError, RuntimeError) as exc:
        logger.error("Could not configure worker network: %s", exc)
        return 1

    logger.info("RupeePilot specialist network configured.")

    for name, worker in workers.items():
        logger.info("%s address: %s", name, worker.address)

    logger.info("Starting six specialist agents.")
    logger.info("Press Ctrl+C to stop.")

    try:
        bureau.run()
    except KeyboardInterrupt:
        logger.info("Worker network stopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
