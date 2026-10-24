
import argparse
import logging
import sys

from uagents import Agent, Bureau

from app.agents.bills_agent_runtime import build_bills_agent
from app.agents.cashflow_agent_runtime import build_cashflow_agent
from app.agents.coordinator_runtime import build_coordinator_agent
from app.agents.expense_agent_runtime import build_expense_agent
from app.agents.goal_agent_runtime import build_goal_agent
from app.agents.scenario_agent_runtime import build_scenario_agent
from app.agents.verification_agent_runtime import (
    build_verification_agent,
)
from app.config import AGENT_SEEDS, configure_logging, validate_agent_seeds


LOGGER = logging.getLogger("rupeepilot.network")


def build_network(
    mailbox: bool = False,
) -> tuple[Bureau, dict[str, Agent], Agent]:
    """Construct the six specialists and the Coordinator."""

    # Fail early if a seed is missing or reused.
    validate_agent_seeds()

    # Build the six independent specialist agents.
    specialists: dict[str, Agent] = {
        "expense": build_expense_agent(port=8011),
        "cashflow": build_cashflow_agent(port=8012),
        "bills": build_bills_agent(port=8013),
        "goal": build_goal_agent(port=8014),
        "scenario": build_scenario_agent(port=8015),
        "verification": build_verification_agent(port=8016),
    }

    # The Coordinator needs the actual addresses of its specialists.
    specialist_addresses = {
        name: agent.address
        for name, agent in specialists.items()
    }

    coordinator = build_coordinator_agent(
        specialist_addresses=specialist_addresses,
        port=8010,
        mailbox=mailbox,
    )

    # Register all seven agents with the local Bureau.
    bureau = Bureau()

    bureau.add(coordinator)

    for agent in specialists.values():
        bureau.add(agent)

    return bureau, specialists, coordinator


def main() -> int:
    """Start the complete RupeePilot agent network."""

    parser = argparse.ArgumentParser(
        description="Start the RupeePilot seven-agent network."
    )

    parser.add_argument(
        "--mailbox",
        action="store_true",
        help=(
            "Enable mailbox mode for the Coordinator. "
            "Use this when preparing the Agentverse connection."
        ),
    )

    args = parser.parse_args()

    configure_logging()

    try:
        bureau, specialists, coordinator = build_network(
            mailbox=args.mailbox,
        )

    except (ValueError, RuntimeError) as exc:
        LOGGER.error("Network configuration failed: %s", exc)
        LOGGER.error(
            "Check .env and ensure every agent has a unique, "
            "persistent seed."
        )
        return 1

    LOGGER.info("RupeePilot network configuration completed.")
    LOGGER.info(
        "Coordinator address: %s",
        coordinator.address,
    )

    for name, agent in specialists.items():
        LOGGER.info(
            "%s agent address: %s",
            name.capitalize(),
            agent.address,
        )

    LOGGER.info("Starting all seven agents through Bureau.")
    LOGGER.info("Press Ctrl+C to stop the network.")

    try:
        bureau.run()
    except KeyboardInterrupt:
        LOGGER.info("RupeePilot network shutdown requested.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
