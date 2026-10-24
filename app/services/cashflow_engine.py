
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


ZERO = Decimal("0")


@dataclass(frozen=True)
class CashflowEvent:
    """A dated financial event.

    Positive amount = money received.
    Negative amount = money paid.
    """

    event_date: date
    description: str
    amount: Decimal


def forecast_cashflow(
    opening_balance: Decimal,
    events: list[CashflowEvent],
    start_date: date,
    end_date: date,
) -> dict:
    """Forecast daily balances from explicitly dated cash events.

    All known expected inflows and outflows must be provided as events.
    Events outside the forecast period are rejected rather than silently
    ignored. The opening balance is the balance before start-date events.
    """

    if opening_balance < ZERO:
        raise ValueError("Opening balance cannot be negative.")

    if start_date > end_date:
        raise ValueError("start_date must not be after end_date.")

    grouped_events = defaultdict(list)

    for event in events:
        if not isinstance(event.amount, Decimal):
            raise TypeError(
                "Event amounts must use Decimal, not float or int."
            )

        if not event.description.strip():
            raise ValueError("Event description cannot be empty.")

        if not start_date <= event.event_date <= end_date:
            raise ValueError(
                f"Event '{event.description}' dated "
                f"{event.event_date} is outside the forecast period."
            )

        grouped_events[event.event_date].append(event)

    balance = opening_balance
    lowest_balance = opening_balance
    lowest_balance_date = start_date
    daily_balances = []
    negative_balance_dates = []

    current_date = start_date

    while current_date <= end_date:
        opening_daily_balance = balance
        inflows = ZERO
        outflows = ZERO
        daily_events = []

        # Stable ordering makes the forecast reproducible.
        day_events = sorted(
            grouped_events[current_date],
            key=lambda event: event.description,
        )

        for event in day_events:
            if event.amount >= ZERO:
                inflows += event.amount
            else:
                outflows += -event.amount

            balance += event.amount

            daily_events.append({
                "description": event.description,
                "amount": event.amount,
            })

        if balance < lowest_balance:
            lowest_balance = balance
            lowest_balance_date = current_date

        if balance < ZERO:
            negative_balance_dates.append({
                "date": current_date.isoformat(),
                "closing_balance": balance,
            })

        daily_balances.append({
            "date": current_date.isoformat(),
            "opening_balance": opening_daily_balance,
            "inflows": inflows,
            "outflows": outflows,
            "closing_balance": balance,
            "events": daily_events,
        })

        current_date += timedelta(days=1)

    warnings = []

    if negative_balance_dates:
        warnings.append(
            "The projected balance becomes negative on one or "
            "more days during the forecast period."
        )

    warnings.append(
        "Forecast accuracy depends on the completeness and timing "
        "of the supplied cash-flow events."
    )

    return {
        "success": True,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "opening_balance": opening_balance,
        "ending_balance": balance,
        "lowest_balance": lowest_balance,
        "lowest_balance_date": lowest_balance_date.isoformat(),
        "negative_balance_dates": negative_balance_dates,
        "daily_balances": daily_balances,
        "warnings": warnings,
    }
