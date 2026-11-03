from datetime import date
from pathlib import Path

import pytest

from emporio_agent.catalog import Catalog
from emporio_agent.orders import Orders

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def orders():
    return Orders.from_csv_dir(DATA_DIR, Catalog.from_csv_dir(DATA_DIR))


def test_owner_sees_the_status_tracking_and_delivery_of_a_shipped_order(orders):
    order = orders.get_order(8, phone="(67) 99654-7821")  # Ana Carolina Ferreira

    assert order.status == "shipped"
    assert order.tracking_code == "BRJL5544332BR"
    assert order.estimated_delivery == date(2026, 2, 28)
    assert order.total == 349.9
    assert order.payment_method == "debit"
    assert order.customer_first_name == "Ana"
    assert [(i.name, i.quantity) for i in order.items] == [("Kala KA-C Concert Mogno", 1)]


def test_someone_elses_phone_reveals_nothing(orders):
    assert orders.get_order(8, phone="(67) 99812-3456") is None  # Lucas's phone, Ana's order


def test_unknown_order_and_wrong_phone_are_indistinguishable(orders):
    assert orders.get_order(9999, phone="(67) 99654-7821") is None
    assert orders.get_order(8, phone="(67) 90000-0000") is None


@pytest.mark.parametrize(
    "typed",
    ["67996547821", "(67)99654-7821", "67 99654 7821", "+55 67 99654-7821", "5567996547821"],
)
def test_phone_formatting_does_not_matter(orders, typed):
    assert orders.get_order(8, phone=typed).id == 8


@pytest.mark.parametrize("typed", ["", "   ", "abc", "7821"])
def test_empty_or_partial_phone_never_matches(orders, typed):
    assert orders.get_order(8, phone=typed) is None


def test_pending_order_has_no_tracking_or_delivery_estimate(orders):
    order = orders.get_order(13, phone="(67) 99456-7890")  # Fernanda Ribeiro Souza

    assert order.status == "pending"
    assert order.tracking_code is None
    assert order.estimated_delivery is None
    assert order.cancel_reason is None


def test_cancelled_order_explains_why(orders):
    order = orders.get_order(17, phone="(67) 98109-8765")  # Matheus Ramos Correia

    assert order.status == "cancelled"
    assert order.cancel_reason == "Pedido cancelado pelo cliente antes do processamento"


def test_order_with_several_items_lists_them_all(orders):
    order = orders.get_order(15, phone="(67) 99901-2345")  # Aline Borges Monteiro

    assert [i.name for i in order.items] == ["Yamaha C70 Nylon Natural", "Taylor 214ce Elétrico Aço Natural"]


def test_the_total_is_the_recorded_one_not_the_sum_of_current_prices(orders):
    order = orders.get_order(20, phone="(67) 98321-6543")  # Thiago Barbosa Lima

    assert order.total == 1400.0  # items at today's prices sum to 1488
