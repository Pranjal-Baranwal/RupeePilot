
from decimal import Decimal

from app.schemas.financial_models import (
    ExpenseCategory,
    FinancialProfile,
)


def analyze_expenses(profile: FinancialProfile) -> dict:
    """Analyze the user's budget without assuming spending is reducible."""

    committed_outflows = (
        profile.fixed_bills
        + profile.regular_spending
        + profile.planned_savings
    )

    remaining_before_unexpected = (
        profile.monthly_income
        + profile.opening_balance
        - committed_outflows
    )

    remaining_after_unexpected = (
        remaining_before_unexpected
        - profile.unexpected_expenses
    )

    warnings = []

    if profile.regular_spending > 0:
        warnings.append(
            "The discretionary portion of regular spending "
            "has not been identified."
        )

    if profile.max_spending_cut == 0:
        warnings.append(
            "No spending reduction has been authorized."
        )

    if remaining_after_unexpected < 0:
        warnings.append(
            "The current budget has a projected shortfall."
        )

    return {
        "agent_name": "expense",
        "success": True,
        "metrics": {
            "monthly_income": profile.monthly_income,
            "fixed_bills": profile.fixed_bills,
            "regular_spending": profile.regular_spending,
            "planned_savings": profile.planned_savings,
            "unexpected_expenses": profile.unexpected_expenses,
            "committed_outflows": committed_outflows,
            "remaining_before_unexpected": remaining_before_unexpected,
            "remaining_after_unexpected": remaining_after_unexpected,
            "maximum_authorized_spending_cut": profile.max_spending_cut,
        },
        "warnings": warnings,
        "errors": [],
    }
