
import logging
import os
from pathlib import Path

from dotenv import load_dotenv


# Project root: rupeepilot/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load environment variables from the project's .env file.
load_dotenv(PROJECT_ROOT / ".env")


def get_env(name: str, default: str = "") -> str:
    """Read an environment variable and trim surrounding whitespace."""
    return os.getenv(name, default).strip()


# Application settings
APP_ENV = get_env("RUPEEPILOT_ENV", "development")
LOG_LEVEL = get_env("LOG_LEVEL", "INFO").upper()

# ASI:One settings
ASI_ONE_API_KEY = get_env("ASI_ONE_API_KEY")
ASI_ONE_BASE_URL = get_env(
    "ASI_ONE_BASE_URL",
    "https://api.asi1.ai/v1",
)
ASI_ONE_MODEL = get_env("ASI_ONE_MODEL", "asi1")

# Persistent seeds for the seven agents.
AGENT_SEEDS = {
    "coordinator": get_env("COORDINATOR_SEED"),
    "expense": get_env("EXPENSE_AGENT_SEED"),
    "cashflow": get_env("CASHFLOW_AGENT_SEED"),
    "bills": get_env("BILLS_AGENT_SEED"),
    "goal": get_env("GOAL_AGENT_SEED"),
    "scenario": get_env("SCENARIO_AGENT_SEED"),
    "verification": get_env("VERIFICATION_AGENT_SEED"),
}


def configure_logging() -> None:
    """Configure consistent application-wide logging."""
    level = getattr(logging, LOG_LEVEL, logging.INFO)

    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def validate_agent_seeds() -> None:
    """Ensure all seven agents have distinct, non-empty seeds."""
    missing = [
        name
        for name, seed in AGENT_SEEDS.items()
        if not seed
    ]

    if missing:
        raise ValueError(
            "Missing agent seeds in .env: "
            + ", ".join(missing)
        )

    if len(set(AGENT_SEEDS.values())) != len(AGENT_SEEDS):
        raise ValueError(
            "Every agent must have a unique seed."
        )


def validate_asi_config() -> None:
    """Require an API key only when an LLM feature is needed."""
    if not ASI_ONE_API_KEY:
        raise ValueError(
            "ASI_ONE_API_KEY is missing from .env."
        )
