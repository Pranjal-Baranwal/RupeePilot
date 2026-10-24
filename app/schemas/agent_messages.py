
from decimal import Decimal
from typing import Any, Optional

from pydantic import Field

from app.schemas.financial_models import (
    StrictModel,
    FinancialProfile,
    BudgetAdjustment,
    PlanningScenario,
    VerificationReport,
)


class PlanningRequest(StrictModel):
    """Coordinator -> specialist agent."""

    request_id: str
    profile: FinancialProfile
    bills: list[dict[str, Any]] = Field(default_factory=list)
    goals: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisResult(StrictModel):
    """Specialist agent -> Coordinator."""

    request_id: str
    agent_name: str
    success: bool
    metrics: dict[str, Decimal | int | float | str | bool | None] = (
        Field(default_factory=dict)
    )
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ScenarioRequest(StrictModel):
    """Coordinator -> Scenario Agent."""

    request_id: str
    profile: FinancialProfile
    analysis_results: list[AnalysisResult] = Field(
        default_factory=list
    )


class ScenarioResult(StrictModel):
    """Scenario Agent -> Coordinator."""

    request_id: str
    success: bool
    scenarios: list[PlanningScenario] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class VerificationRequest(StrictModel):
    """Coordinator -> Verification Agent."""

    request_id: str
    original_profile: FinancialProfile
    adjustment: BudgetAdjustment
    candidate: PlanningScenario


class VerificationResult(StrictModel):
    """Verification Agent -> Coordinator."""

    request_id: str
    agent_name: str = "verification"
    report: VerificationReport
    corrected_balance: Optional[Decimal] = None


class PlanningComplete(StrictModel):
    """Coordinator's completed planning result."""

    request_id: str
    success: bool
    response_text: str
    verification: Optional[VerificationReport] = None
    errors: list[str] = Field(default_factory=list)
