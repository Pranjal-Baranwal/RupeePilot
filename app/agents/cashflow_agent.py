
from app.schemas.financial_models import FinancialProfile


def analyze_cashflow(profile: FinancialProfile) -> dict:
    """Calculate the projected monthly cash position deterministically."""

    total_available = (
        profile.opening_balance + profile.monthly_income
    )

    total_outflows = (
        profile.fixed_bills
        + profile.regular_spending
        + profile.planned_savings
        + profile.unexpected_expenses
    )

    projected_balance = total_available - total_outflows

    shortfall = max(
        profile.minimum_cash_buffer - projected_balance,
        0,
    )

    warnings = []

    if projected_balance < 0:
        warnings.append(
            "Projected closing balance is negative."
        )

    if projected_balance < profile.minimum_cash_buffer:
        warnings.append(
            "Projected balance is below the requested cash buffer."
        )

    warnings.append(
        "This is a monthly summary; payment dates and daily "
        "balance movements have not been modeled yet."
    )

    return {
        "agent_name": "cashflow",
        "success": True,
        "metrics": {
            "total_available": total_available,
            "total_outflows": total_outflows,
            "projected_closing_balance": projected_balance,
            "minimum_cash_buffer": profile.minimum_cash_buffer,
            "shortfall_to_buffer": shortfall,
        },
        "warnings": warnings,
        "errors": [],
    }
