
from decimal import Decimal

from app.schemas.financial_models import (
    BudgetAdjustment,
    FinancialProfile,
    PlanningScenario,
)


ZERO = Decimal("0")


def _project_balance(
    profile: FinancialProfile,
    spending_cut: Decimal,
    savings_cut: Decimal,
) -> Decimal:
    """Independently calculate the balance for a candidate plan."""

    return (
        profile.opening_balance
        + profile.monthly_income
        - profile.fixed_bills
        - (profile.regular_spending - spending_cut)
        - (profile.planned_savings - savings_cut)
        - profile.unexpected_expenses
    )


def _make_description(
    spending_cut: Decimal,
    savings_cut: Decimal,
) -> str:
    """Create a readable description of the proposed adjustments."""

    if spending_cut == ZERO and savings_cut == ZERO:
        return "Keep the existing budget unchanged."

    if spending_cut > ZERO and savings_cut == ZERO:
        return f"Reduce regular spending by ₹{spending_cut}."

    if spending_cut == ZERO and savings_cut > ZERO:
        return (
            "Reduce the planned savings contribution "
            f"by ₹{savings_cut} this month."
        )

    return (
        f"Reduce regular spending by ₹{spending_cut} "
        f"and planned savings by ₹{savings_cut}."
    )


def generate_budget_scenarios(
    profile: FinancialProfile,
    max_scenarios: int = 6,
) -> dict:
    """Generate and rank candidate budget plans.

    Ranking priorities:
    1. Cover fixed mandatory-bill totals.
    2. Avoid a negative projected balance.
    3. Preserve the requested cash buffer.
    4. Minimize total spending and savings adjustments.

    Spending cuts are limited by the user's authorized maximum.
    Savings cuts cannot exceed the planned savings contribution.
    """

    if max_scenarios < 1:
        raise ValueError("max_scenarios must be at least 1.")

    baseline_balance = _project_balance(
        profile,
        ZERO,
        ZERO,
    )

    maximum_spending_cut = min(
        profile.max_spending_cut,
        profile.regular_spending,
    )

    required_for_nonnegative = max(
        ZERO,
        -baseline_balance,
    )

    required_for_buffer = max(
        ZERO,
        profile.minimum_cash_buffer - baseline_balance,
    )

    # Consider no cut, the authorized maximum, and useful
    # spending reductions for reaching the balance targets.
    spending_options = {
        ZERO,
        maximum_spending_cut,
        min(maximum_spending_cut, required_for_nonnegative),
        min(maximum_spending_cut, required_for_buffer),
    }

    candidates = []
    seen_adjustments = set()

    for spending_cut in sorted(spending_options):
        remaining_for_nonnegative = max(
            ZERO,
            required_for_nonnegative - spending_cut,
        )

        remaining_for_buffer = max(
            ZERO,
            required_for_buffer - spending_cut,
        )

        savings_options = {
            ZERO,
            profile.planned_savings,
            min(
                profile.planned_savings,
                remaining_for_nonnegative,
            ),
            min(
                profile.planned_savings,
                remaining_for_buffer,
            ),
        }

        for savings_cut in sorted(savings_options):
            adjustment_key = (spending_cut, savings_cut)

            if adjustment_key in seen_adjustments:
                continue

            seen_adjustments.add(adjustment_key)

            closing_balance = _project_balance(
                profile,
                spending_cut,
                savings_cut,
            )

            preserves_buffer = (
                closing_balance >= profile.minimum_cash_buffer
            )

            # This checks aggregate monthly totals only.
            mandatory_bills_covered = (
                profile.opening_balance + profile.monthly_income
                >= profile.fixed_bills
            )

            tradeoffs = []

            if spending_cut > ZERO:
                tradeoffs.append(
                    "Less money remains available for regular spending."
                )

            if savings_cut > ZERO:
                tradeoffs.append(
                    "Savings progress will be slower this month."
                )

            if closing_balance < ZERO:
                tradeoffs.append(
                    "The plan still has a projected cash shortfall."
                )

            if not preserves_buffer:
                tradeoffs.append(
                    "The requested minimum cash buffer is not preserved."
                )

            if not mandatory_bills_covered:
                tradeoffs.append(
                    "Available monthly funds do not cover the "
                    "fixed-bill total."
                )

            candidates.append(
                PlanningScenario(
                    scenario_id="pending",
                    description=_make_description(
                        spending_cut,
                        savings_cut,
                    ),
                    adjustment=BudgetAdjustment(
                        spending_reduction=spending_cut,
                        savings_reduction=savings_cut,
                        reserve_used=ZERO,
                    ),
                    projected_closing_balance=closing_balance,
                    preserves_minimum_buffer=preserves_buffer,
                    mandatory_bills_covered=mandatory_bills_covered,
                    tradeoffs=tradeoffs,
                )
            )

    def ranking_key(
        scenario: PlanningScenario,
    ) -> tuple:
        """Return a transparent, deterministic ranking key."""

        balance = scenario.projected_closing_balance

        total_adjustment = (
            scenario.adjustment.spending_reduction
            + scenario.adjustment.savings_reduction
        )

        return (
            not scenario.mandatory_bills_covered,
            balance < ZERO,
            not scenario.preserves_minimum_buffer,
            max(ZERO, -balance),
            total_adjustment,
            scenario.adjustment.savings_reduction,
            scenario.adjustment.spending_reduction,
        )

    candidates.sort(key=ranking_key)

    # Assign IDs after sorting so they reflect ranked order.
    ranked_scenarios = []

    for index, scenario in enumerate(
        candidates[:max_scenarios],
        start=1,
    ):
        scenario.scenario_id = f"scenario_{index}"
        ranked_scenarios.append(scenario)

    warnings = []

    if not any(
        scenario.projected_closing_balance >= ZERO
        for scenario in candidates
    ):
        warnings.append(
            "No candidate avoids a negative balance within the "
            "authorized adjustment limits."
        )

    if not any(
        scenario.preserves_minimum_buffer
        for scenario in candidates
    ):
        warnings.append(
            "No candidate preserves the requested minimum cash buffer."
        )

    if maximum_spending_cut == ZERO:
        warnings.append(
            "No spending reduction was authorized by the user."
        )

    warnings.append(
        "This engine uses monthly aggregate totals and does not "
        "verify the timing of individual bill payments."
    )

    return {
        "success": True,
        "metrics": {
            "baseline_closing_balance": baseline_balance,
            "maximum_authorized_spending_cut": maximum_spending_cut,
            "total_candidates": len(candidates),
            "returned_candidates": len(ranked_scenarios),
        },
        "scenarios": ranked_scenarios,
        "warnings": warnings,
        "errors": [],
    }
