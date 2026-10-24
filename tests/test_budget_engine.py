
from decimal import Decimal

from app.schemas.financial_models import FinancialProfile
from app.services.budget_engine import calculate_budget


def make_profile(**overrides) -> FinancialProfile:
    """Build a reusable financial profile for tests."""

    values = {
        "monthly_income": Decimal("28000"),
        "fixed_bills": Decimal("10000"),
        "regular_spending": Decimal("8000"),
        "planned_savings": Decimal("6000"),
        "unexpected_expenses": Decimal("8000"),
        "opening_balance": Decimal("0"),
    }

    values.update(overrides)

    return FinancialProfile(**values)


def test_budget_with_shortfall():
    """The sample profile should produce a ₹4,000 shortfall."""

    profile = make_profile()

    result = calculate_budget(profile)

    assert result.total_income == Decimal("28000")
    assert result.total_outflows == Decimal("32000")
    assert result.projected_closing_balance == Decimal("-4000")
    assert result.shortfall == Decimal("4000")
    assert result.is_feasible is False


def test_budget_with_positive_balance():
    """A profile with lower outflows should remain feasible."""

    profile = make_profile(
        unexpected_expenses=Decimal("0"),
    )

    result = calculate_budget(profile)

    assert result.total_outflows == Decimal("24000")
    assert result.projected_closing_balance == Decimal("4000")
    assert result.shortfall == Decimal("0")
    assert result.is_feasible is True


def test_opening_balance_is_included():
    """Opening cash affects closing balance, not monthly income."""

    profile = make_profile(
        opening_balance=Decimal("5000"),
    )

    result = calculate_budget(profile)

    assert result.total_income == Decimal("28000")
    assert result.total_outflows == Decimal("32000")
    assert result.projected_closing_balance == Decimal("1000")
    assert result.shortfall == Decimal("0")
    assert result.is_feasible is True


def test_zero_balance_is_feasible():
    """A closing balance of exactly zero is feasible."""

    profile = make_profile(
        regular_spending=Decimal("4000"),
        unexpected_expenses=Decimal("8000"),
    )

    result = calculate_budget(profile)

    assert result.projected_closing_balance == Decimal("0")
    assert result.shortfall == Decimal("0")
    assert result.is_feasible is True
