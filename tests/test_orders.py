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


# ---------------------------------------------------------------------------
# lookup(): format validation and session-remembered verification
# ---------------------------------------------------------------------------
from datetime import datetime, timedelta

from emporio_agent.orders import Verification

T0 = datetime(2026, 11, 3, 10, 0)
ANA = "(67) 99654-7821"        # owns order 8
THIAGO = "(67) 98321-6543"     # owns orders 2 and 20


def test_a_malformed_phone_is_rejected_before_any_lookup(orders):
    for typed in ("7821", "abc", "99654-78", "123456789012345"):
        result = orders.lookup(8, typed, Verification(), T0)
        assert result.status == "invalid_phone", typed
        assert result.order is None


@pytest.mark.parametrize("order_id", [0, -3])
def test_an_order_number_must_be_a_positive_integer(orders, order_id):
    assert orders.lookup(order_id, ANA, Verification(), T0).status == "invalid_order"


def test_without_a_phone_and_without_a_verification_the_agent_must_ask(orders):
    result = orders.lookup(8, None, Verification(), T0)

    assert result.status == "verification_needed"
    assert result.expired is False
    assert result.order is None


def test_lookup_with_the_right_phone_finds_the_order(orders):
    result = orders.lookup(8, ANA, Verification(), T0)

    assert result.status == "found"
    assert result.order.id == 8


def test_a_verified_phone_unlocks_the_other_orders_of_the_same_customer(orders):
    verification = Verification()
    orders.lookup(2, THIAGO, verification, T0)

    result = orders.lookup(20, None, verification, T0 + timedelta(minutes=5))

    assert result.status == "found"
    assert result.order.id == 20


def test_a_verified_phone_never_unlocks_someone_elses_order(orders):
    verification = Verification()
    orders.lookup(2, THIAGO, verification, T0)

    result = orders.lookup(8, None, verification, T0 + timedelta(minutes=1))  # Ana's order

    assert result.status == "not_verified"
    assert result.order is None


def test_a_wrong_phone_is_never_remembered(orders):
    verification = Verification()

    assert orders.lookup(8, "(67) 90000-0000", verification, T0).status == "not_verified"
    assert orders.lookup(8, None, verification, T0 + timedelta(minutes=1)).status == "verification_needed"


def test_a_failed_attempt_keeps_the_existing_verification(orders):
    verification = Verification()
    orders.lookup(2, THIAGO, verification, T0)

    assert orders.lookup(8, "(67) 90000-0000", verification, T0 + timedelta(minutes=1)).status == "not_verified"
    assert orders.lookup(20, None, verification, T0 + timedelta(minutes=2)).status == "found"


def test_an_unknown_order_with_a_remembered_phone_is_a_generic_failure(orders):
    verification = Verification()
    orders.lookup(2, THIAGO, verification, T0)

    assert orders.lookup(9999, None, verification, T0 + timedelta(minutes=1)).status == "not_verified"


def minutes(n):
    return T0 + timedelta(minutes=n)


def verified_at_t0(orders):
    verification = Verification()
    orders.lookup(2, THIAGO, verification, T0)
    return verification


def test_the_verification_lasts_10_minutes_after_the_last_use(orders):
    verification = verified_at_t0(orders)

    assert orders.lookup(20, None, verification, minutes(10)).status == "found"


def test_after_10_idle_minutes_the_agent_must_ask_again(orders):
    verification = verified_at_t0(orders)

    result = orders.lookup(20, None, verification, minutes(10) + timedelta(seconds=1))

    assert (result.status, result.expired) == ("verification_needed", True)


def test_each_use_renews_the_idle_limit_but_never_beyond_30_minutes_in_total(orders):
    verification = verified_at_t0(orders)

    for minute in (9, 18, 27):
        assert orders.lookup(20, None, verification, minutes(minute)).status == "found"
    assert orders.lookup(20, None, verification, minutes(30)).status == "found"

    late = orders.lookup(20, None, verification, minutes(30) + timedelta(seconds=1))
    assert (late.status, late.expired) == ("verification_needed", True)


def test_once_expired_the_stored_phone_is_gone_until_the_customer_verifies_again(orders):
    verification = verified_at_t0(orders)
    orders.lookup(20, None, verification, minutes(11))  # expired

    assert orders.lookup(20, None, verification, minutes(12)).status == "verification_needed"
    assert orders.lookup(20, THIAGO, verification, minutes(13)).status == "found"
    assert orders.lookup(2, None, verification, minutes(14)).status == "found"


def test_giving_the_phone_again_restarts_the_30_minute_cap(orders):
    verification = Verification()
    for minute in (0, 9, 18, 27):
        orders.lookup(2, THIAGO, verification, minutes(minute))

    assert orders.lookup(20, None, verification, minutes(36)).status == "found"  # 36 min after the first, 9 after the last
