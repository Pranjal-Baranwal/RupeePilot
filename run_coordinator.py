
import logging
import sys

from app.agents.coordinator_runtime import build_coordinator_agent
from app.config import configure_logging, validate_agent_seeds
from run_workers import build_worker_network


def main() -> int:
    configure_logging()
    logger = logging.getLogger("rupeepilot.coordinator")

    try:
        # Re-create the workers to calculate their persistent addresses.
        # This does not start a second worker network.
        _, workers = build_worker_network()

        specialist_addresses = {
            name: worker.address
            for name, worker in workers.items()
        }

        validate_agent_seeds()

        coordinator = build_coordinator_agent(
            specialist_addresses=specialist_addresses,
            port=8010,
            mailbox=True,
        )

    except (ValueError, RuntimeError) as exc:
        logger.error("Coordinator configuration failed: %s", exc)
        return 1

    logger.info("Coordinator configured successfully.")
    logger.info("Coordinator address: %s", coordinator.address)
    logger.info(
        "Specialist addresses derived from persistent agent seeds."
    )
    logger.info("Starting Coordinator with mailbox enabled.")

    try:
        coordinator.run()
    except KeyboardInterrupt:
        logger.info("Coordinator shutdown requested.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
