
from decimal import Decimal

from app.schemas.financial_models import (
    BudgetAdjustment,
    FinancialProfile,
    PlanningScenario,
)


ZERO = Decimal("0")


def _calculate_closing_balance(
    profile: FinancialProfile,
    spending_reduction: Decimal,
    savings_reduction: Decimal,
) -> Decimal:
    """Calculate the closing balance for a proposed budget."""

    adjusted_spending = (
        profile.regular_spending - spending_reduction
    )

    adjusted_savings = (
        profile.planned_savings - savings_reduction
    )

    return (
        profile.opening_balance
        + profile.monthly_income
        - profile.fixed_bills
        - adjusted_spending
        - adjusted_savings
        - profile.unexpected_expenses
    )


def generate_scenarios(
    profile: FinancialProfile,
    max_scenarios: int = 6,
) -> dict:
    """Generate and rank budget alternatives using deterministic rules.

    Only spending reductions explicitly authorized by the user
    are considered. Savings reductions cannot exceed the planned
    savings contribution.
    """

    if max_scenarios < 1:
        raise ValueError("max_scenarios must be at least 1.")

    baseline_balance = _calculate_closing_balance(
        profile,
        ZERO,
        ZERO,
    )

    # The amount required to reach the user's minimum buffer.
    required_adjustment = max(
        profile.minimum_cash_buffer - baseline_balance,
        ZERO,
    )

    # Never cut more spending than the user has authorized or
    # more than the total regular spending.
    maximum_spending_cut = min(
        profile.max_spending_cut,
        profile.regular_spending,
    )

    # Candidate spending reductions.
    spending_options = {
        ZERO,
        maximum_spending_cut,
        min(maximum_spending_cut, required_adjustment),
    }

    scenarios = []

    for spending_cut in sorted(spending_options):
        # Determine how much savings would need to be reduced
        # after applying this particular spending adjustment.
        remaining_required = max(
            profile.minimum_cash_buffer
            - baseline_balance
            - spending_cut,
            ZERO,
        )

        savings_options = {
            ZERO,
            profile.planned_savings,
            min(
                profile.planned_savings,
                remaining_required,
            ),
            min(
                profile.planned_savings,
                required_adjustment,
            ),
        }

        for savings_cut in sorted(savings_options):
            # Avoid duplicate or invalid adjustments.
            if spending_cut < ZERO:
                continue

            if savings_cut < ZERO:
                continue

            if spending_cut > maximum_spending_cut:
                continue

            if savings_cut > profile.planned_savings:
                continue

            closing_balance = _calculate_closing_balance(
                profile,
                spending_cut,
                savings_cut,
            )

            preserves_buffer = (
                closing_balance >= profile.minimum_cash_buffer
            )

            feasible = closing_balance >= ZERO

            # With monthly aggregate figures, we can check whether
            # total available money covers the fixed-bill total.
            mandatory_bills_covered = (
                profile.opening_balance + profile.monthly_income
                >= profile.fixed_bills
            )

            if spending_cut == ZERO and savings_cut == ZERO:
                description = "Keep the existing budget unchanged."

            elif spending_cut > ZERO and savings_cut == ZERO:
                description = (
                    f"Reduce regular spending by "
                    f"₹{spending_cut}."
                )

            elif spending_cut == ZERO and savings_cut > ZERO:
                description = (
                    f"Reduce the planned savings contribution "
                    f"by ₹{savings_cut} this month."
                )

            else:
                description = (
                    f"Reduce regular spending by ₹{spending_cut} "
                    f"and planned savings by ₹{savings_cut}."
                )

            tradeoffs = []

            if spending_cut > ZERO:
                tradeoffs.append(
                    "Less money is available for regular spending."
                )

            if savings_cut > ZERO:
                tradeoffs.append(
                    "Savings progress will be slower this month."
                )

            if not feasible:
                tradeoffs.append(
                    "The plan still has a negative projected balance."
                )

            if not preserves_buffer:
                tradeoffs.append(
                    "The requested minimum cash buffer is not preserved."
                )

            scenarios.append(
                PlanningScenario(
                    scenario_id=f"scenario_{len(scenarios) + 1}",
                    description=description,
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

    # Rank first by feasibility, then buffer preservation.
    # Among plans with the same status, prefer smaller adjustments
    # and then smaller savings reductions.
    scenarios.sort(
        key=lambda scenario: (
            not (
                scenario.projected_closing_balance >= ZERO
            ),
            not scenario.preserves_minimum_buffer,
            (
                ZERO
                if scenario.projected_closing_balance >= ZERO
                else -scenario.projected_closing_balance
            ),
            (
                scenario.adjustment.spending_reduction
                + scenario.adjustment.savings_reduction
            ),
            scenario.adjustment.savings_reduction,
        )
    )

    # Assign stable identifiers after ranking.
    ranked_scenarios = []

    for index, scenario in enumerate(
        scenarios[:max_scenarios],
        start=1,
    ):
        scenario.scenario_id = f"scenario_{index}"
        ranked_scenarios.append(scenario)

    warnings = []

    if not any(
        scenario.projected_closing_balance >= ZERO
        for scenario in scenarios
    ):
        warnings.append(
            "No candidate avoids a negative closing balance "
            "within the authorized adjustment limits."
        )

    if not any(
        scenario.preserves_minimum_buffer
        for scenario in scenarios
    ):
        warnings.append(
            "No candidate preserves the requested minimum "
            "cash buffer."
        )

    if maximum_spending_cut == ZERO:
        warnings.append(
            "Spending reductions were not authorized, so no "
            "spending cuts were used."
        )

    warnings.append(
        "This is a monthly aggregate forecast. Individual bill "
        "payment dates have not been modeled."
    )

    return {
        "agent_name": "scenario",
        "success": True,
        "metrics": {
            "baseline_closing_balance": baseline_balance,
            "required_adjustment": required_adjustment,
            "maximum_authorized_spending_cut": maximum_spending_cut,
            "scenario_count": len(ranked_scenarios),
        },
        "scenarios": ranked_scenarios,
        "warnings": warnings,
        "errors": [],
    }
