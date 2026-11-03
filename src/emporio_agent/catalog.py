import csv
import json
import unicodedata
from dataclasses import dataclass, field
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
    search_text: str = ""
    description: str = ""
    specs: dict = field(default_factory=dict)


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
                description=r["description"],
                specs=_spec_dict(r["specs"]),
                search_text=_normalize(
                    " ".join([r["name"], categories[int(r["category_id"])], *_spec_values(r["specs"])])
                ),
            )
            products[product.id] = product
        return cls(products)

    def search_products(
        self,
        query: str = "",
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 10,
    ) -> list[Product]:
        words = _normalize(query).split()
        if not words and category is None and min_price is None and max_price is None:
            return []
        wanted_category = _normalize(category) if category else None
        matches = [
            p
            for p in self._products.values()
            if all(w in p.search_text for w in words)
            and (wanted_category is None or wanted_category in _normalize(p.category))
            and (min_price is None or p.price >= min_price)
            and (max_price is None or p.price <= max_price)
        ]
        matches.sort(
            key=lambda p: (
                -sum(w in _normalize(p.name) for w in words),  # words found in the name first
                p.availability != "available",  # then sellable before unavailable
                p.discount_percent is None,  # then discounted before full price
                p.price,
            )
        )
        return matches[:limit]

    def suggest_alternatives(self, product_id: int, limit: int = 3) -> list[Product]:
        target = self.get_product(product_id)
        if target is None:
            return []
        candidates = [
            p
            for p in self._products.values()
            if p.id != target.id
            and p.category == target.category
            and p.availability == "available"
            and 0.7 * target.price <= p.price <= 1.3 * target.price
        ]
        candidates.sort(key=lambda p: (abs(p.price - target.price), p.price))
        return candidates[:limit]

    def get_product(self, product_id: int) -> Product | None:
        return self._products.get(product_id)


def _read(data_dir: Path, suffix: str) -> list[dict]:
    (path,) = Path(data_dir).glob(f"*{suffix}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _availability(status: str, stock: int) -> str:
    if status != "active":
        return status  # discontinued / coming_soon: status wins over the stock number
    return "available" if stock > 0 else "out_of_stock"


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(_singular(word) for word in plain.split())


def _singular(word: str) -> str:
    """Light pt-BR plural handling so 'violão' matches 'Violões' and 'baixos' matches 'baixo'."""
    if word.endswith(("oes", "aes")):
        return word[:-3] + "ao"
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def _spec_dict(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _spec_values(raw: str) -> list[str]:
    return [str(v) for v in _spec_dict(raw).values()]
