import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from emporio_agent.catalog import Catalog


@dataclass(frozen=True)
class OrderItem:
    name: str
    quantity: int


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

    def get_order(self, order_id: int, phone: str) -> Order | None:
        order = self._orders.get(order_id)
        if order is None or _digits_without_country_code(phone) != self._phones[order_id]:
            return None
        return order


def _digits(text: str) -> str:
    return "".join(c for c in text if c.isdigit())


def _digits_without_country_code(phone: str) -> str:
    digits = _digits(phone)
    return digits[2:] if len(digits) == 13 and digits.startswith("55") else digits


def _read(data_dir: Path, suffix: str) -> list[dict]:
    (path,) = Path(data_dir).glob(f"*{suffix}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
