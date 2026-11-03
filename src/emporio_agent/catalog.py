import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category: str
    list_price: float
    price: float
    discount_percent: int | None
    availability: str


class Catalog:
    def __init__(self, products: dict[int, Product]):
        self._products = products

    @classmethod
    def from_csv_dir(cls, data_dir: Path) -> "Catalog":
        categories = {
            int(r["category_id"]): r["name"] for r in _read(data_dir, "categories.csv")
        }
        discounts: dict[int, int] = {}
        for r in _read(data_dir, "promotions.csv"):
            if r["is_active"] == "1":
                pid = int(r["product_id"])
                discounts[pid] = max(discounts.get(pid, 0), int(r["discount_percent"]))
        products = {}
        for r in _read(data_dir, "products.csv"):
            price = float(r["price_brl"])
            pid = int(r["product_id"])
            discount = discounts.get(pid)
            product = Product(
                id=pid,
                name=r["name"],
                category=categories[int(r["category_id"])],
                list_price=price,
                price=round(price * (100 - discount) / 100, 2) if discount else price,
                discount_percent=discount,
                availability=_availability(r["status"], int(r["stock_quantity"])),
            )
            products[product.id] = product
        return cls(products)

    def get_product(self, product_id: int) -> Product:
        return self._products[product_id]


def _read(data_dir: Path, suffix: str) -> list[dict]:
    (path,) = Path(data_dir).glob(f"*{suffix}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _availability(status: str, stock: int) -> str:
    if status != "active":
        return status  # discontinued / coming_soon: status wins over the stock number
    return "available" if stock > 0 else "out_of_stock"
