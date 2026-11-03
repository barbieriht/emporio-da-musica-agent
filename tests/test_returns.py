from datetime import date
from pathlib import Path

import pytest

from emporio_agent.catalog import Catalog
from emporio_agent.orders import Orders
from emporio_agent.returns import assess_return

DATA_DIR = Path(__file__).parent.parent / "data"

# customers' phones (from the CSV) used to load the orders
PHONES = {7: "(67) 99789-0123", 8: "(67) 99654-7821", 13: "(67) 99456-7890", 17: "(67) 98109-8765"}


@pytest.fixture(scope="module")
def order():
    orders = Orders.from_csv_dir(DATA_DIR, Catalog.from_csv_dir(DATA_DIR))

    def load(order_id):
        return orders.get_order(order_id, PHONES[order_id])

    return load


def test_arrependimento_inside_the_window(order):
    # order 7: delivered, estimated delivery 2026-02-17 => 7 days end on 2026-02-24
    result = assess_return(order(7), "arrependimento", today=date(2026, 2, 20))

    assert result.outcome == "eligible"
    assert result.deadline == date(2026, 2, 24)
    assert result.days_left == 4


@pytest.mark.parametrize("reason", ["arrependimento", "preferencia"])
def test_the_seventh_day_is_still_inside_and_the_eighth_is_outside(order, reason):
    last_day = assess_return(order(7), reason, today=date(2026, 2, 24))
    after = assess_return(order(7), reason, today=date(2026, 2, 25))

    assert (last_day.outcome, last_day.days_left) == ("eligible", 0)
    assert after.outcome == "expired"
    assert after.deadline == date(2026, 2, 24)


def test_defect_exchange_runs_30_days_from_receipt(order):
    last_day = assess_return(order(7), "defeito", today=date(2026, 3, 19))

    assert (last_day.outcome, last_day.deadline, last_day.days_left) == ("eligible", date(2026, 3, 19), 0)


def test_after_30_days_a_defect_falls_back_to_the_legal_warranty_until_day_90(order):
    result = assess_return(order(7), "defeito", today=date(2026, 3, 20))

    assert result.outcome == "expired"
    assert result.in_legal_warranty is True
    assert result.legal_warranty_until == date(2026, 5, 18)


def test_the_legal_warranty_ends_after_90_days(order):
    assert assess_return(order(7), "defeito", today=date(2026, 5, 18)).in_legal_warranty is True
    assert assess_return(order(7), "defeito", today=date(2026, 5, 19)).in_legal_warranty is False


def test_arrependimento_has_no_warranty_fallback(order):
    result = assess_return(order(7), "arrependimento", today=date(2026, 3, 1))

    assert result.legal_warranty_until is None


@pytest.mark.parametrize("reason", ["arrependimento", "preferencia", "defeito"])
def test_a_shipped_order_has_not_started_its_window_yet(order, reason):
    # order 8: shipped, estimated delivery 2026-02-28
    result = assess_return(order(8), reason, today=date(2026, 2, 20))

    assert result.outcome == "not_received_yet"
    assert result.starts_on == date(2026, 2, 28)
    assert result.deadline is None


def test_an_order_that_has_not_shipped_has_nothing_to_return(order):
    assert assess_return(order(13), "arrependimento", today=date(2026, 3, 20)).outcome == "not_shipped"  # pending


def test_a_cancelled_order_has_nothing_to_return(order):
    assert assess_return(order(17), "arrependimento", today=date(2026, 3, 20)).outcome == "cancelled"
