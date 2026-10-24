
from datetime import date, timedelta

from app.schemas.financial_models import Bill, BillPriority


def analyze_bills(
    bills: list[Bill],
    reference_date: date | None = None,
    horizon_days: int = 7,
) -> dict:
    """Analyze unpaid bills and flag those due soon or overdue."""

    if horizon_days < 0:
        raise ValueError("horizon_days cannot be negative.")

    today = reference_date or date.today()
    horizon_end = today + timedelta(days=horizon_days)

    unpaid_bills = [bill for bill in bills if not bill.paid]

    mandatory_bills = [
        bill for bill in unpaid_bills
        if bill.priority == BillPriority.MANDATORY
    ]

    flexible_bills = [
        bill for bill in unpaid_bills
        if bill.priority == BillPriority.FLEXIBLE
    ]

    due_soon = [
        bill for bill in unpaid_bills
        if today <= bill.due_date <= horizon_end
    ]

    overdue = [
        bill for bill in unpaid_bills
        if bill.due_date < today
    ]

    warnings = []

    if overdue:
        warnings.append(
            f"{len(overdue)} unpaid bill(s) are overdue."
        )

    if due_soon:
        warnings.append(
            f"{len(due_soon)} unpaid bill(s) are due "
            f"within {horizon_days} days."
        )

    if not bills:
        warnings.append(
            "No individual bills were provided; "
            "the fixed-bill total cannot be assigned due dates."
        )

    return {
        "agent_name": "bills",
        "success": True,
        "metrics": {
            "unpaid_bill_count": len(unpaid_bills),
            "mandatory_bill_count": len(mandatory_bills),
            "flexible_bill_count": len(flexible_bills),
            "mandatory_total": sum(
                (bill.amount for bill in mandatory_bills),
                start=0,
            ),
            "unpaid_total": sum(
                (bill.amount for bill in unpaid_bills),
                start=0,
            ),
            "due_soon": [
                {
                    "name": bill.name,
                    "amount": bill.amount,
                    "due_date": bill.due_date.isoformat(),
                    "priority": bill.priority.value,
                }
                for bill in due_soon
            ],
            "overdue": [
                {
                    "name": bill.name,
                    "amount": bill.amount,
                    "due_date": bill.due_date.isoformat(),
                }
                for bill in overdue
            ],
        },
        "warnings": warnings,
        "errors": [],
    }
