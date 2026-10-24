
from datetime import date
from decimal import Decimal

import pytest

from app.services.cashflow_engine import (
    CashflowEvent,
    forecast_cashflow,
)


def test_detects_temporary_cash_shortfall():
    """A bill due before salary can cause a temporary shortfall."""

    events = [
        CashflowEvent(
            date(2026, 10, 26),
            "Electricity bill",
            Decimal("-15000"),
        ),
        CashflowEvent(
            date(2026, 10, 27),
            "Salary received",
            Decimal("20000"),
        ),
        CashflowEvent(
            date(2026, 10, 28),
            "Groceries",
            Decimal("-7000"),
        ),
    ]

    result = forecast_cashflow(
        opening_balance=Decimal("5000"),
        events=events,
        start_date=date(2026, 10, 24),
        end_date=date(2026, 10, 30),
    )

    assert result["ending_balance"] == Decimal("3000")
    assert result["lowest_balance"] == Decimal("-10000")
    assert result["lowest_balance_date"] == "2026-10-26"

    assert len(result["negative_balance_dates"]) == 1
    assert (
        result["negative_balance_dates"][0]["date"]
        == "2026-10-26"
    )


def test_forecast_without_events():
    """The balance remains unchanged when no events are supplied."""

    result = forecast_cashflow(
        opening_balance=Decimal("5000"),
        events=[],
        start_date=date(2026, 10, 24),
        end_date=date(2026, 10, 26),
    )

    assert result["ending_balance"] == Decimal("5000")
    assert result["lowest_balance"] == Decimal("5000")
    assert result["negative_balance_dates"] == []
    assert len(result["daily_balances"]) == 3


def test_events_on_same_day_are_combined():
    """All events on a date contribute to that day's closing balance."""

    events = [
        CashflowEvent(
            date(2026, 10, 25),
            "Salary",
            Decimal("10000"),
        ),
        CashflowEvent(
            date(2026, 10, 25),
            "Bill",
            Decimal("-3000"),
        ),
    ]

    result = forecast_cashflow(
        opening_balance=Decimal("2000"),
        events=events,
        start_date=date(2026, 10, 25),
        end_date=date(2026, 10, 25),
    )

    assert len(result["daily_balances"]) == 1
    assert result["daily_balances"][0]["inflows"] == Decimal("10000")
    assert result["daily_balances"][0]["outflows"] == Decimal("3000")
    assert result["ending_balance"] == Decimal("9000")


def test_rejects_events_outside_forecast_period():
    """The engine must not silently ignore out-of-range events."""

    events = [
        CashflowEvent(
            date(2026, 10, 23),
            "Earlier payment",
            Decimal("-1000"),
        ),
    ]

    with pytest.raises(ValueError, match="outside the forecast period"):
        forecast_cashflow(
            opening_balance=Decimal("5000"),
            events=events,
            start_date=date(2026, 10, 24),
            end_date=date(2026, 10, 30),
        )


def test_rejects_invalid_date_range():
    """The forecast start date must not follow the end date."""

    with pytest.raises(
        ValueError,
        match="start_date must not be after end_date",
    ):
        forecast_cashflow(
            opening_balance=Decimal("5000"),
            events=[],
            start_date=date(2026, 10, 30),
            end_date=date(2026, 10, 24),
        )
