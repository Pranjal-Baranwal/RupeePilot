
from decimal import Decimal

from app.schemas.financial_models import (
    BudgetSummary,
    FinancialProfile,
)


ZERO = Decimal("0")


def calculate_budget(
    profile: FinancialProfile,
) -> BudgetSummary:
    """Calculate the user's monthly budget deterministically.

    Opening balance is included in the closing-balance calculation,
    but it is not counted as monthly income.

    Planned savings contributions are treated as budget outflows.
    """

    total_income = profile.monthly_income

    total_outflows = (
        profile.fixed_bills
        + profile.regular_spending
        + profile.planned_savings
        + profile.unexpected_expenses
    )

    projected_closing_balance = (
        profile.opening_balance
        + total_income
        - total_outflows
    )

    shortfall = max(
        ZERO,
        -projected_closing_balance,
    )

    return BudgetSummary(
        total_income=total_income,
        total_outflows=total_outflows,
        projected_closing_balance=projected_closing_balance,
        shortfall=shortfall,
        is_feasible=projected_closing_balance >= ZERO,
    )
