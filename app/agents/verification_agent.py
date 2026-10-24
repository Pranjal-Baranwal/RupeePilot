
from decimal import Decimal

from app.schemas.financial_models import (
    FinancialProfile,
    PlanningScenario,
    VerificationReport,
)


ZERO = Decimal("0")


def verify_scenario(
    profile: FinancialProfile,
    candidate: PlanningScenario,
) -> dict:
    """Independently verify a proposed financial scenario.

    The verifier recalculates the closing balance from the original
    profile and checks the adjustment limits and reported constraints.
    It does not trust the candidate's calculated balance.
    """

    adjustment = candidate.adjustment
    discrepancies = []
    warnings = []
    checks_passed = []

    spending_cut = adjustment.spending_reduction
    savings_cut = adjustment.savings_reduction

    # Check 1: Spending reduction must be authorized.
    maximum_allowed_cut = min(
        profile.max_spending_cut,
        profile.regular_spending,
    )

    if spending_cut < ZERO or spending_cut > maximum_allowed_cut:
        discrepancies.append(
            "The proposed spending reduction exceeds the "
            "user-authorized limit."
        )
    else:
        checks_passed.append(
            "Spending reduction is within the authorized limit."
        )

    # Check 2: Savings reduction must be valid.
    if savings_cut < ZERO or savings_cut > profile.planned_savings:
        discrepancies.append(
            "The proposed savings reduction is outside the "
            "available planned savings contribution."
        )
    else:
        checks_passed.append(
            "Savings reduction is within the planned contribution."
        )

    # Check 3: Adjustments must not exceed their original categories.
    if spending_cut > profile.regular_spending:
        discrepancies.append(
            "Spending reduction exceeds regular spending."
        )

    adjusted_spending = profile.regular_spending - spending_cut
    adjusted_savings = profile.planned_savings - savings_cut

    if adjusted_spending < ZERO or adjusted_savings < ZERO:
        discrepancies.append(
            "The proposed plan produces a negative spending "
            "or savings category."
        )

    # Check 4: Independently recalculate the closing balance.
    # Do not use the candidate's reported balance in this equation.
    corrected_balance = (
        profile.opening_balance
        + profile.monthly_income
        - profile.fixed_bills
        - adjusted_spending
        - adjusted_savings
        - profile.unexpected_expenses
    )

    if candidate.projected_closing_balance != corrected_balance:
        discrepancies.append(
            "Reported closing balance does not match the "
            f"independent calculation. Reported: "
            f"{candidate.projected_closing_balance}; "
            f"calculated: {corrected_balance}."
        )
    else:
        checks_passed.append(
            "Projected closing balance matches independent arithmetic."
        )

    # Check 5: Validate the minimum cash buffer claim.
    expected_buffer_status = (
        corrected_balance >= profile.minimum_cash_buffer
    )

    if (
        candidate.preserves_minimum_buffer
        != expected_buffer_status
    ):
        discrepancies.append(
            "The reported minimum cash-buffer status is incorrect."
        )
    else:
        checks_passed.append(
            "Minimum cash-buffer status is consistent with the balance."
        )

    # Check 6: Check the aggregate mandatory-bill coverage claim.
    # This is a monthly-total check, not a due-date forecast.
    expected_bills_covered = (
        profile.opening_balance + profile.monthly_income
        >= profile.fixed_bills
    )

    if candidate.mandatory_bills_covered != expected_bills_covered:
        discrepancies.append(
            "The reported mandatory-bill coverage status is incorrect."
        )
    else:
        checks_passed.append(
            "Mandatory-bill coverage claim matches the aggregate totals."
        )

    if corrected_balance < ZERO:
        warnings.append(
            "The independently calculated closing balance is negative."
        )

    if not expected_buffer_status:
        warnings.append(
            "The proposed plan does not preserve the requested "
            "minimum cash buffer."
        )

    if adjustment.reserve_used != ZERO:
        warnings.append(
            "The reserve-used field is not included as an additional "
            "cash source in this monthly calculation. The opening "
            "balance is already included."
        )

    report = VerificationReport(
        approved=len(discrepancies) == 0,
        checks_passed=checks_passed,
        discrepancies=discrepancies,
        warnings=warnings,
    )

    return {
        "agent_name": "verification",
        "success": True,
        "approved": report.approved,
        "corrected_balance": corrected_balance,
        "report": report,
        "metrics": {
            "corrected_balance": corrected_balance,
            "checks_passed": len(checks_passed),
            "discrepancy_count": len(discrepancies),
        },
        "warnings": warnings,
        "errors": discrepancies,
    }
