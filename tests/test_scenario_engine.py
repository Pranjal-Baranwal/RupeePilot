
from decimal import Decimal

import pytest

from app.schemas.financial_models import FinancialProfile
from app.services.scenario_engine import generate_budget_scenarios


def make_profile(**overrides) -> FinancialProfile:
    """Create a reusable test profile."""

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


def test_generates_scenarios_for_shortfall():
    """The engine should generate alternatives for the ₹4,000 shortfall."""

    result = generate_budget_scenarios(make_profile())

    assert result["success"] is True
    assert result["metrics"]["baseline_closing_balance"] == Decimal("-4000")
    assert result["metrics"]["returned_candidates"] > 0


def test_never_exceeds_authorized_spending_cut():
    """No scenario may cut more spending than the user permits."""

    profile = make_profile(max_spending_cut=Decimal("1000"))

    result = generate_budget_scenarios(profile)

    for scenario in result["scenarios"]:
        assert scenario.adjustment.spending_reduction <= Decimal("1000")
        assert scenario.adjustment.spending_reduction >= Decimal("0")


def test_savings_reduction_can_resolve_shortfall():
    """Reducing savings by ₹4,000 should bring the balance to zero."""

    result = generate_budget_scenarios(make_profile())

    matching = [
        scenario
        for scenario in result["scenarios"]
        if (
            scenario.adjustment.spending_reduction == Decimal("0")
            and scenario.adjustment.savings_reduction == Decimal("4000")
        )
    ]

    assert matching
    assert matching[0].projected_closing_balance == Decimal("0")
    assert matching[0].preserves_minimum_buffer is True


def test_savings_reduction_never_exceeds_contribution():
    """The engine must not reduce savings below zero."""

    result = generate_budget_scenarios(make_profile())

    for scenario in result["scenarios"]:
        assert (
            scenario.adjustment.savings_reduction
            <= Decimal("6000")
        )



def test_no_feasible_plan_is_reported():
    """A shortfall must be disclosed when no permitted adjustment can fix it."""

    profile = make_profile(
        planned_savings=Decimal("0"),
        max_spending_cut=Decimal("0"),
        unexpected_expenses=Decimal("12000"),
    )

    result = generate_budget_scenarios(profile)

    assert all(
        scenario.projected_closing_balance < Decimal("0")
        for scenario in result["scenarios"]
    )

    assert any(
        "No candidate avoids a negative balance"
        in warning
        for warning in result["warnings"]
    )


def test_rejects_invalid_scenario_limit():
    """The caller must request at least one candidate."""

    with pytest.raises(ValueError, match="at least 1"):
        generate_budget_scenarios(
            make_profile(),
            max_scenarios=0,
        )


def test_scenario_limit_is_respected():
    """The engine must not return more than the requested number."""

    result = generate_budget_scenarios(
        make_profile(),
        max_scenarios=2,
    )

    assert len(result["scenarios"]) <= 2
