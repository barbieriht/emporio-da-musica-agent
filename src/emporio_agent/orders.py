import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from emporio_agent.catalog import Catalog


@dataclass(frozen=True)
class OrderItem:
    name: str
    quantity: int


@dataclass
class Verification:
    """Per-session memory of the phone that passed verification."""

    phone: str | None = None
    verified_at: datetime | None = None
    last_used_at: datetime | None = None


@dataclass(frozen=True)
class LookupResult:
    # found | invalid_phone | invalid_order | verification_needed | not_verified
    status: str
    order: "Order | None" = None
    expired: bool = False


@dataclass(frozen=True)
class Order:
    id: int
    status: str
    order_date: date
    total: float
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    cancel_reason: str | None
    customer_first_name: str
    items: list[OrderItem]


class Orders:
    def __init__(self, orders: dict[int, Order], phones: dict[int, str]):
        self._orders = orders
        self._phones = phones  # order id -> owner's phone digits

    @classmethod
    def from_csv_dir(cls, data_dir: Path, catalog: Catalog) -> "Orders":
        customers = {int(r["customer_id"]): r for r in _read(data_dir, "customers.csv")}
        items: dict[int, list[OrderItem]] = {}
        for r in _read(data_dir, "order_items.csv"):
            product = catalog.get_product(int(r["product_id"]))
            name = product.name if product else f"Produto {r['product_id']}"
            items.setdefault(int(r["order_id"]), []).append(OrderItem(name, int(r["quantity"])))
        orders, phones = {}, {}
        for r in _read(data_dir, "orders.csv"):
            oid = int(r["order_id"])
            customer = customers[int(r["customer_id"])]
            orders[oid] = Order(
                id=oid,
                status=r["status"],
                order_date=date.fromisoformat(r["order_date"]),
                total=float(r["total_brl"]),
                payment_method=r["payment_method"],
                tracking_code=r["tracking_code"] or None,
                estimated_delivery=date.fromisoformat(r["estimated_delivery"]) if r["estimated_delivery"] else None,
                cancel_reason=r["notes"] or None,
                customer_first_name=customer["name"].split()[0],
                items=items.get(oid, []),
            )
            phones[oid] = _digits_without_country_code(customer["phone"])
        return cls(orders, phones)

    def lookup(self, order_id: int, phone: str | None, verification: Verification, now: datetime) -> LookupResult:
        if not isinstance(order_id, int) or order_id <= 0:
            return LookupResult("invalid_order")
        if phone and phone.strip():
            digits = _digits_without_country_code(phone)
            if len(digits) not in (10, 11):
                return LookupResult("invalid_phone")
            order = self.get_order(order_id, phone)
            if order is None:
                return LookupResult("not_verified")  # failed attempts are never remembered
            verification.phone, verification.verified_at, verification.last_used_at = digits, now, now
            return LookupResult("found", order)
        if verification.phone is None:
            return LookupResult("verification_needed")
        if not _still_valid(verification, now):
            verification.phone = verification.verified_at = verification.last_used_at = None
            return LookupResult("verification_needed", expired=True)
        order = self._orders.get(order_id)
        if order is None or self._phones[order_id] != verification.phone:
            return LookupResult("not_verified")
        verification.last_used_at = now
        return LookupResult("found", order)

    def get_order(self, order_id: int, phone: str) -> Order | None:
        order = self._orders.get(order_id)
        if order is None or _digits_without_country_code(phone) != self._phones[order_id]:
            return None
        return order


IDLE_LIMIT = timedelta(minutes=10)  # since the last use
ABSOLUTE_LIMIT = timedelta(minutes=30)  # since the phone was last typed by the customer


def _still_valid(verification: Verification, now: datetime) -> bool:
    return now - verification.last_used_at <= IDLE_LIMIT and now - verification.verified_at <= ABSOLUTE_LIMIT


def _digits(text: str) -> str:
    return "".join(c for c in text if c.isdigit())


def _digits_without_country_code(phone: str) -> str:
    digits = _digits(phone)
    return digits[2:] if len(digits) == 13 and digits.startswith("55") else digits


def _read(data_dir: Path, suffix: str) -> list[dict]:
    (path,) = Path(data_dir).glob(f"*{suffix}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
