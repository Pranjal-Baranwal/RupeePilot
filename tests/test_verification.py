
from decimal import Decimal

from app.schemas.financial_models import (
    BudgetAdjustment,
    FinancialProfile,
    PlanningScenario,
)
from app.agents.verification_agent import verify_scenario


def make_profile(**overrides) -> FinancialProfile:
    """Create a reusable financial profile for verification tests."""

    values = {
        "monthly_income": Decimal("28000"),
        "opening_balance": Decimal("0"),
        "fixed_bills": Decimal("10000"),
        "regular_spending": Decimal("8000"),
        "planned_savings": Decimal("6000"),
        "unexpected_expenses": Decimal("8000"),
        "max_spending_cut": Decimal("0"),
        "minimum_cash_buffer": Decimal("0"),
    }

    values.update(overrides)

    return FinancialProfile(**values)


def make_scenario(
    profile: FinancialProfile,
    spending_cut: Decimal = Decimal("0"),
    savings_cut: Decimal = Decimal("4000"),
    reported_balance: Decimal | None = None,
    preserves_buffer: bool | None = None,
) -> PlanningScenario:
    """Construct a candidate scenario for testing."""

    actual_balance = (
        profile.opening_balance
        + profile.monthly_income
        - profile.fixed_bills
        - (profile.regular_spending - spending_cut)
        - (profile.planned_savings - savings_cut)
        - profile.unexpected_expenses
    )

    balance = (
        actual_balance
        if reported_balance is None
        else reported_balance
    )

    buffer_status = (
        balance >= profile.minimum_cash_buffer
        if preserves_buffer is None
        else preserves_buffer
    )

    bills_covered = (
        profile.opening_balance + profile.monthly_income
        >= profile.fixed_bills
    )

    return PlanningScenario(
        scenario_id="test_scenario",
        description="Test budget scenario",
        adjustment=BudgetAdjustment(
            spending_reduction=spending_cut,
            savings_reduction=savings_cut,
        ),
        projected_closing_balance=balance,
        preserves_minimum_buffer=buffer_status,
        mandatory_bills_covered=bills_covered,
    )


def test_valid_scenario_is_approved():
    """A mathematically correct, authorized adjustment should pass."""

    profile = make_profile()
    scenario = make_scenario(profile)

    result = verify_scenario(profile, scenario)

    assert result["success"] is True
    assert result["approved"] is True
    assert result["corrected_balance"] == Decimal("0")
    assert result["errors"] == []


def test_incorrect_reported_balance_is_rejected():
    """The verifier must reject an incorrect closing balance."""

    profile = make_profile()

    scenario = make_scenario(
        profile,
        reported_balance=Decimal("4000"),
    )

    result = verify_scenario(profile, scenario)

    assert result["approved"] is False
    assert result["corrected_balance"] == Decimal("0")
    assert any(
        "does not match the independent calculation"
        in error
        for error in result["errors"]
    )


def test_unauthorized_spending_cut_is_rejected():
    """A candidate cannot reduce spending without authorization."""

    profile = make_profile(
        max_spending_cut=Decimal("0"),
    )

    scenario = make_scenario(
        profile,
        spending_cut=Decimal("1000"),
        savings_cut=Decimal("3000"),
    )

    result = verify_scenario(profile, scenario)

    assert result["approved"] is False
    assert any(
        "exceeds the user-authorized limit" in error
        for error in result["errors"]
    )


def test_excessive_savings_reduction_is_rejected():
    """A candidate cannot reduce more savings than planned."""

    profile = make_profile()

    scenario = make_scenario(
        profile,
        savings_cut=Decimal("7000"),
    )

    result = verify_scenario(profile, scenario)

    assert result["approved"] is False
    assert any(
        "planned savings contribution" in error
        for error in result["errors"]
    )


def test_incorrect_cash_buffer_claim_is_rejected():
    """The candidate's buffer-preservation claim must be accurate."""

    profile = make_profile(
        minimum_cash_buffer=Decimal("1000"),
    )

    scenario = make_scenario(
        profile,
        preserves_buffer=True,
    )

    result = verify_scenario(profile, scenario)

    assert result["approved"] is False
    assert any(
        "cash-buffer status is incorrect" in error
        for error in result["errors"]
    )


def test_negative_balance_is_warned_about():
    """A mathematically correct shortfall should be disclosed."""

    profile = make_profile(
        planned_savings=Decimal("0"),
        unexpected_expenses=Decimal("12000"),
    )

    scenario = make_scenario(
        profile,
        savings_cut=Decimal("0"),
    )

    result = verify_scenario(profile, scenario)

    assert result["approved"] is True
    assert result["corrected_balance"] == Decimal("-2000")
    assert any(
        "closing balance is negative" in warning
        for warning in result["warnings"]
    )