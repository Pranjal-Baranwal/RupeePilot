
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.agents.expense_agent import analyze_expenses
from app.agents.cashflow_agent import analyze_cashflow
from app.agents.bills_agent import analyze_bills
from app.agents.goal_agent import analyze_goals
from app.agents.scenario_agent import generate_scenarios
from app.agents.verification_agent import verify_scenario

from app.schemas.financial_models import (
    Bill,
    FinancialProfile,
    PlanningResult,
    PlanningScenario,
    SavingsGoal,
    VerificationReport,
)


ZERO = Decimal("0")


def _rank_scenario(
    scenario: PlanningScenario,
) -> tuple:
    """Rank candidates using explicit, deterministic priorities."""

    balance = scenario.projected_closing_balance

    total_adjustment = (
        scenario.adjustment.spending_reduction
        + scenario.adjustment.savings_reduction
    )

    # Mandatory bill coverage comes first.
    # Prefer a non-negative balance, then buffer preservation.
    # Among feasible plans, prefer the smallest adjustment.
    if balance >= ZERO:
        return (
            not scenario.mandatory_bills_covered,
            0,
            not scenario.preserves_minimum_buffer,
            total_adjustment,
            scenario.adjustment.savings_reduction,
            scenario.adjustment.spending_reduction,
            -balance,
        )

    # If no candidate avoids a shortfall, prefer the smallest
    # shortfall before comparing the remaining trade-offs.
    return (
        not scenario.mandatory_bills_covered,
        1,
        -balance,
        not scenario.preserves_minimum_buffer,
        total_adjustment,
        scenario.adjustment.savings_reduction,
        scenario.adjustment.spending_reduction,
    )


def _collect_warnings(*results: dict) -> list[str]:
    """Collect unique warnings from specialist analyses."""

    warnings = []

    for result in results:
        for warning in result.get("warnings", []):
            if warning not in warnings:
                warnings.append(warning)

    return warnings


def run_planning_workflow(
    profile: FinancialProfile,
    bills: list[Bill] | None = None,
    goals: list[SavingsGoal] | None = None,
    request_id: str | None = None,
    reference_date: date | None = None,
) -> PlanningResult:
    """Run the local financial planning workflow.

    The specialist agents analyze the profile, the Scenario Agent
    generates alternatives, and the Verification Agent checks every
    candidate before it can become a recommendation.
    """

    request_id = request_id or str(uuid4())
    bills = bills or []
    goals = goals or []

    # Stage 1: Collect independent specialist analyses.
    expense_result = analyze_expenses(profile)

    cashflow_result = analyze_cashflow(profile)

    bills_result = analyze_bills(
        bills,
        reference_date=reference_date,
    )

    goals_result = analyze_goals(
        goals,
        reference_date=reference_date,
    )

    # Stage 2: Generate candidate financial plans.
    scenario_result = generate_scenarios(profile)

    candidates: list[PlanningScenario] = (
        scenario_result.get("scenarios", [])
    )

    # Stage 3: Verify each candidate independently.
    verified_candidates = []

    verification_warnings = []
    verification_failures = []

    for candidate in candidates:
        verification_result = verify_scenario(
            profile,
            candidate,
        )

        report = verification_result["report"]

        if verification_result["approved"]:
            verified_candidates.append(
                (candidate, report)
            )
        else:
            verification_failures.extend(
                report.discrepancies
            )

        verification_warnings.extend(report.warnings)

    # Stage 4: Build the assumptions and warnings.
    assumptions = [
        "The forecast uses monthly aggregate financial figures.",
        "The closing-balance calculation does not model the timing "
        "of individual payments or income deposits.",
    ]

    if not bills:
        assumptions.append(
            "No individual bills were supplied. Mandatory-bill "
            "coverage is checked using the profile's fixed-bill total."
        )

    if not goals:
        assumptions.append(
            "No individual savings goals were supplied, so "
            "goal-specific deadlines cannot be assessed."
        )

    all_warnings = _collect_warnings(
        expense_result,
        cashflow_result,
        bills_result,
        goals_result,
        scenario_result,
    )

    for warning in verification_warnings:
        if warning not in all_warnings:
            all_warnings.append(warning)

    for warning in all_warnings:
        if warning not in assumptions:
            assumptions.append(warning)

    # Stage 5: Do not recommend an unverified candidate.
    if not verified_candidates:
        discrepancies = list(dict.fromkeys(verification_failures))

        if not discrepancies:
            discrepancies = [
                "No candidate passed independent verification."
            ]

        report = VerificationReport(
            approved=False,
            checks_passed=[],
            discrepancies=discrepancies,
            warnings=all_warnings,
        )

        return PlanningResult(
            request_id=request_id,
            status="verification_failed",
            summary=(
                "No budget scenario passed independent verification. "
                "A verified recommendation cannot be provided."
            ),
            recommended_scenario=None,
            alternatives=[],
            verification=report,
            assumptions=assumptions,
        )

    # Stage 6: Rank only independently verified candidates.
    verified_candidates.sort(
        key=lambda item: _rank_scenario(item[0])
    )

    recommended_scenario, verification_report = (
        verified_candidates[0]
    )

    alternatives = [
        scenario
        for scenario, _ in verified_candidates[1:]
    ]

    balance = (
        recommended_scenario.projected_closing_balance
    )

    if balance < ZERO:
        status = "verified_with_shortfall"

        summary = (
            f"The best independently verified candidate is: "
            f"{recommended_scenario.description} "
            f"The projected closing balance is -₹{-balance}; "
            f"the plan still has a shortfall of ₹{-balance}."
        )

    elif (
        balance < profile.minimum_cash_buffer
    ):
        status = "verified_below_buffer"

        summary = (
            f"Recommended plan: {recommended_scenario.description} "
            f"The projected closing balance is ₹{balance}, "
            f"but the requested cash buffer of "
            f"₹{profile.minimum_cash_buffer} is not preserved."
        )

    else:
        status = "verified"

        summary = (
            f"Recommended plan: {recommended_scenario.description} "
            f"The independently verified projected closing "
            f"balance is ₹{balance}."
        )

    return PlanningResult(
        request_id=request_id,
        status=status,
        summary=summary,
        recommended_scenario=recommended_scenario,
        alternatives=alternatives,
        verification=verification_report,
        assumptions=assumptions,
    )
