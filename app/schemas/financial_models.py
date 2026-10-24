
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class StrictModel(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class ExpenseCategory(str, Enum):
    ESSENTIAL = "essential"
    DISCRETIONARY = "discretionary"
    SAVINGS = "savings"
    OTHER = "other"


class BillPriority(str, Enum):
    MANDATORY = "mandatory"
    IMPORTANT = "important"
    FLEXIBLE = "flexible"


class FinancialProfile(StrictModel):
    """A user's financial information for one planning period."""

    currency: str = "INR"
    monthly_income: Decimal = Field(ge=0)
    opening_balance: Decimal = Field(default=Decimal("0"), ge=0)
    fixed_bills: Decimal = Field(ge=0)
    regular_spending: Decimal = Field(ge=0)
    planned_savings: Decimal = Field(default=Decimal("0"), ge=0)
    unexpected_expenses: Decimal = Field(default=Decimal("0"), ge=0)

    # User-approved maximum spending reduction.
    max_spending_cut: Decimal = Field(default=Decimal("0"), ge=0)

    # Optional minimum balance the plan should preserve.
    minimum_cash_buffer: Decimal = Field(default=Decimal("0"), ge=0)


class Bill(StrictModel):
    """A bill with a due date and priority."""

    name: str = Field(min_length=1)
    amount: Decimal = Field(ge=0)
    due_date: date
    priority: BillPriority = BillPriority.MANDATORY
    paid: bool = False


class SavingsGoal(StrictModel):
    """A user's savings target."""

    name: str = Field(min_length=1)
    target_amount: Decimal = Field(gt=0)
    current_amount: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_contribution: Decimal = Field(default=Decimal("0"), ge=0)
    target_date: Optional[date] = None


class BudgetSummary(StrictModel):
    """Deterministic budget calculation results."""

    total_income: Decimal
    total_outflows: Decimal
    projected_closing_balance: Decimal
    shortfall: Decimal
    is_feasible: bool


class BudgetAdjustment(StrictModel):
    """Changes proposed to the original budget."""

    spending_reduction: Decimal = Field(default=Decimal("0"), ge=0)
    savings_reduction: Decimal = Field(default=Decimal("0"), ge=0)
    reserve_used: Decimal = Field(default=Decimal("0"), ge=0)


class PlanningScenario(StrictModel):
    """One candidate plan for handling a financial situation."""

    scenario_id: str
    description: str
    adjustment: BudgetAdjustment
    projected_closing_balance: Decimal
    preserves_minimum_buffer: bool
    mandatory_bills_covered: bool
    tradeoffs: list[str] = Field(default_factory=list)


class VerificationReport(StrictModel):
    """Independent verification of a candidate plan."""

    approved: bool
    checks_passed: list[str] = Field(default_factory=list)
    discrepancies: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PlanningResult(StrictModel):
    """Final result returned by the planning workflow."""

    request_id: str
    status: str
    summary: str
    recommended_scenario: Optional[PlanningScenario] = None
    alternatives: list[PlanningScenario] = Field(default_factory=list)
    verification: Optional[VerificationReport] = None
    assumptions: list[str] = Field(default_factory=list)
