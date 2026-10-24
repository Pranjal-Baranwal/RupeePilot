
from decimal import Decimal

from app.schemas.financial_models import (
    PlanningResult,
    PlanningScenario,
)


def format_inr(amount: Decimal) -> str:
    """Format a rupee amount using the Indian numbering system."""

    rounded = Decimal(amount).quantize(Decimal("0.01"))
    negative = rounded < 0
    absolute = abs(rounded)

    whole, _, fraction = f"{absolute:.2f}".partition(".")

    # Indian grouping: 1,23,45,678 rather than 12,345,678.
    if len(whole) > 3:
        last_three = whole[-3:]
        remaining = whole[:-3]
        groups = []

        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]

        if remaining:
            groups.insert(0, remaining)

        whole = ",".join(groups + [last_three])

    if absolute == absolute.to_integral_value():
        formatted = whole
    else:
        formatted = f"{whole}.{fraction}"

    sign = "-" if negative else ""

    return f"{sign}₹{formatted}"


def _format_scenario(
    scenario: PlanningScenario,
    number: int | None = None,
) -> str:
    """Format one candidate scenario for display."""

    prefix = f"{number}. " if number is not None else ""

    lines = [
        f"{prefix}{scenario.description}",
        (
            "   Projected closing balance: "
            f"{format_inr(scenario.projected_closing_balance)}"
        ),
        (
            "   Spending reduction: "
            f"{format_inr(scenario.adjustment.spending_reduction)}"
        ),
        (
            "   Savings reduction: "
            f"{format_inr(scenario.adjustment.savings_reduction)}"
        ),
    ]

    if scenario.tradeoffs:
        lines.append(
            "   Trade-offs: " + "; ".join(scenario.tradeoffs)
        )

    return "\n".join(lines)


def build_explanation(
    result: PlanningResult,
    max_alternatives: int = 3,
) -> str:
    """Build a readable explanation from a structured planning result.

    This function only formats existing results. It does not calculate
    financial figures, change recommendations, or override verification.
    """

    if max_alternatives < 0:
        raise ValueError("max_alternatives cannot be negative.")

    lines = [
        "RupeePilot — Your Financial Plan",
        "=" * 34,
        "",
        result.summary,
        "",
        f"Planning status: {result.status.replace('_', ' ').title()}",
    ]

    # Verification status is taken directly from the verifier's report.
    if result.verification is not None:
        if result.verification.approved:
            lines.append(
                "Independent verification: PASSED"
            )

            lines.append(
                "Checks passed: "
                f"{len(result.verification.checks_passed)}"
            )
        else:
            lines.append(
                "Independent verification: FAILED"
            )

    # Never display a rejected plan as the recommendation.
    if result.recommended_scenario is None:
        lines.extend([
            "",
            "Recommendation",
            "No verified recommendation is available.",
        ])

        if result.verification and result.verification.discrepancies:
            lines.append("")
            lines.append("Verification issues:")

            for issue in result.verification.discrepancies:
                lines.append(f"- {issue}")

    else:
        lines.extend([
            "",
            "Recommended plan",
            _format_scenario(result.recommended_scenario),
        ])

        if result.alternatives and max_alternatives > 0:
            lines.extend([
                "",
                "Alternative verified plans",
            ])

            for index, scenario in enumerate(
                result.alternatives[:max_alternatives],
                start=1,
            ):
                lines.append(_format_scenario(scenario, index))

    if result.verification and result.verification.warnings:
        lines.extend(["", "Verification warnings"])

        for warning in result.verification.warnings:
            lines.append(f"- {warning}")

    if result.assumptions:
        lines.extend(["", "Assumptions and limitations"])

        for assumption in result.assumptions:
            lines.append(f"- {assumption}")

    lines.extend([
        "",
        "Note: This is a planning aid, not a guarantee of future "
        "cash availability. Results depend on the accuracy and "
        "completeness of the supplied financial information.",
    ])

    return "\n".join(lines)