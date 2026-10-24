
from decimal import Decimal

from app.agents.coordinator import run_planning_workflow
from app.schemas.financial_models import FinancialProfile


def make_profile(**overrides) -> FinancialProfile:
    """Build the standard RupeePilot demo profile."""

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


def test_coordinator_returns_verified_recommendation():
    """The demo request should produce a verified budget adjustment."""

    result = run_planning_workflow(
        make_profile(),
        request_id="test_demo_001",
    )

    assert result.request_id == "test_demo_001"
    assert result.status == "verified"
    assert result.recommended_scenario is not None
    assert result.verification is not None
    assert result.verification.approved is True

    recommended = result.recommended_scenario

    assert recommended.adjustment.spending_reduction == Decimal("0")
    assert recommended.adjustment.savings_reduction == Decimal("4000")
    assert recommended.projected_closing_balance == Decimal("0")


def test_coordinator_does_not_authorize_extra_spending_cuts():
    """The Coordinator must respect the user's spending limit."""

    result = run_planning_workflow(
        make_profile(max_spending_cut=Decimal("500")),
        request_id="test_demo_002",
    )

    assert result.recommended_scenario is not None
    assert (
        result.recommended_scenario.adjustment.spending_reduction
        <= Decimal("500")
    )


def test_coordinator_reports_unresolved_shortfall():
    """If no permitted adjustment resolves the shortfall, disclose it."""

    profile = make_profile(
        planned_savings=Decimal("0"),
        unexpected_expenses=Decimal("12000"),
        max_spending_cut=Decimal("0"),
    )

    result = run_planning_workflow(
        profile,
        request_id="test_demo_003",
    )

    assert result.status == "verified_with_shortfall"
    assert result.recommended_scenario is not None
    assert (
        result.recommended_scenario.projected_closing_balance
        == Decimal("-2000")
    )
    assert "shortfall" in result.summary.lower()
