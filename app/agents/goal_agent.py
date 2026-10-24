
from datetime import date
from decimal import Decimal, ROUND_CEILING

from app.schemas.financial_models import SavingsGoal


def analyze_goals(
    goals: list[SavingsGoal],
    proposed_contributions: dict[str, Decimal] | None = None,
    reference_date: date | None = None,
) -> dict:
    """Analyze savings progress and the effect of contribution changes.

    proposed_contributions optionally maps each goal's name to its
    proposed monthly contribution. Goals not present in the mapping
    retain their original monthly contribution.
    """

    proposed_contributions = proposed_contributions or {}
    today = reference_date or date.today()

    results = []
    warnings = []

    for goal in goals:
        remaining = max(
            goal.target_amount - goal.current_amount,
            Decimal("0"),
        )

        contribution = proposed_contributions.get(
            goal.name,
            goal.monthly_contribution,
        )

        if contribution < 0:
            raise ValueError(
                f"Contribution for '{goal.name}' cannot be negative."
            )

        if remaining == 0:
            months_to_goal = 0
        elif contribution > 0:
            months_to_goal = int(
                (
                    remaining / contribution
                ).to_integral_value(rounding=ROUND_CEILING)
            )
        else:
            months_to_goal = None
            warnings.append(
                f"'{goal.name}' has a remaining target but no "
                "monthly contribution."
            )

        required_monthly_contribution = None
        months_until_deadline = None
        deadline_feasible = None

        if goal.target_date is not None:
            months_until_deadline = (
                (goal.target_date.year - today.year) * 12
                + goal.target_date.month
                - today.month
            )

            if goal.target_date.day < today.day:
                months_until_deadline -= 1

            months_until_deadline = max(
                months_until_deadline,
                0,
            )

            if remaining == 0:
                required_monthly_contribution = Decimal("0")
                deadline_feasible = True
            elif months_until_deadline > 0:
                required_monthly_contribution = (
                    remaining / Decimal(months_until_deadline)
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_CEILING,
                )

                deadline_feasible = (
                    contribution >= required_monthly_contribution
                )
            else:
                required_monthly_contribution = remaining
                deadline_feasible = False

            if not deadline_feasible:
                warnings.append(
                    f"'{goal.name}' may miss its target date "
                    "at the proposed contribution level."
                )

        results.append({
            "goal_name": goal.name,
            "target_amount": goal.target_amount,
            "current_amount": goal.current_amount,
            "remaining_amount": remaining,
            "original_monthly_contribution":
                goal.monthly_contribution,
            "proposed_monthly_contribution": contribution,
            "months_to_goal": months_to_goal,
            "target_date": (
                goal.target_date.isoformat()
                if goal.target_date else None
            ),
            "months_until_deadline": months_until_deadline,
            "required_monthly_contribution":
                required_monthly_contribution,
            "deadline_feasible": deadline_feasible,
        })

    return {
        "agent_name": "goal",
        "success": True,
        "metrics": {
            "goal_count": len(goals),
            "goals": results,
        },
        "warnings": warnings,
        "errors": [],
    }
