
import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from app.agents.coordinator import run_planning_workflow
from app.config import PROJECT_ROOT, configure_logging
from app.schemas.financial_models import (
    Bill,
    FinancialProfile,
    SavingsGoal,
)
from app.services.explanation_service import build_explanation
from app.storage.repository import PlanningRepository


LOGGER = logging.getLogger("rupeepilot")


def load_profile_file(
    file_path: Path,
) -> tuple[FinancialProfile, list[Bill], list[SavingsGoal], date]:
    """Load and validate a financial profile from a JSON file."""

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Profile file does not exist: {file_path}"
        )

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            raise ValueError(
                "The JSON document must contain an object."
            )

        if "profile" not in data:
            raise ValueError(
                "The JSON document is missing the 'profile' section."
            )

        profile = FinancialProfile.model_validate(
            data["profile"]
        )

        bills_data = data.get("bills", [])
        goals_data = data.get("goals", [])

        if not isinstance(bills_data, list):
            raise ValueError("'bills' must be a JSON array.")

        if not isinstance(goals_data, list):
            raise ValueError("'goals' must be a JSON array.")

        bills = [
            Bill.model_validate(item)
            for item in bills_data
        ]

        goals = [
            SavingsGoal.model_validate(item)
            for item in goals_data
        ]

        reference_date = date.fromisoformat(
            data.get("reference_date", date.today().isoformat())
        )

        return profile, bills, goals, reference_date

    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(
            f"Invalid financial profile in {file_path}: {exc}"
        ) from exc


def main() -> int:
    """Run RupeePilot's local financial planning demonstration."""

    parser = argparse.ArgumentParser(
        description=(
            "RupeePilot — multi-agent financial planning demo"
        )
    )

    parser.add_argument(
        "--profile",
        type=Path,
        default=PROJECT_ROOT / "data" / "demo_profile.json",
        help="Path to the financial profile JSON file.",
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save the planning result to SQLite.",
    )

    args = parser.parse_args()

    configure_logging()

    try:
        profile, bills, goals, reference_date = load_profile_file(
            args.profile
        )

        LOGGER.info("Loaded financial profile.")
        LOGGER.info("Running the planning workflow.")

        result = run_planning_workflow(
            profile=profile,
            bills=bills,
            goals=goals,
            reference_date=reference_date,
        )

        print()
        print(build_explanation(result))
        print()

        if not args.no_save:
            repository = PlanningRepository()
            repository.save_result(result)

            print(
                "Planning result saved. Request ID: "
                f"{result.request_id}"
            )
        else:
            print("Database saving skipped.")

        return 0

    except (FileNotFoundError, ValueError, OSError) as exc:
        LOGGER.error("%s", exc)
        return 1

    except Exception:
        LOGGER.exception(
            "An unexpected error occurred during planning."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
