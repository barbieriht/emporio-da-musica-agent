from dataclasses import dataclass
import unicodedata
from pathlib import Path

# (largest n of the tier, minimum parcela in R$) from the manual's payment rules
_TIERS = [(3, 50.0), (6, 80.0), (12, 100.0)]


@dataclass(frozen=True)
class Installment:
    n: int
    value: float


@dataclass(frozen=True)
class ShippingQuote:
    fee: float | None  # None: depends on the destination CEP
    delivery_time: str


class Policies:
    def __init__(self, sections: dict[str, str]):
        self._sections = sections

    @classmethod
    def from_dir(cls, directory: Path) -> "Policies":
        return cls({p.stem: p.read_text(encoding="utf-8") for p in sorted(Path(directory).glob("*.md"))})

    def topics(self) -> list[str]:
        return list(self._sections)

    def lookup(self, topic: str) -> str | None:
        return self._sections.get(topic)

    def installment_options(self, price: float) -> list[Installment]:
        options = []
        for n in range(1, 13):
            minimum = next(m for top, m in _TIERS if n <= top)
            if n == 1 or price / n >= minimum:
                options.append(Installment(n, round(price / n, 2)))
            else:
                break
        return options

    def shipping_quote(self, order_total: float, city: str) -> ShippingQuote:
        if _plain(city) == "campo grande":
            return ShippingQuote(0 if order_total >= 500 else 35.0, "1 a 3 dias úteis")
        return ShippingQuote(
            None, "PAC 5 a 12 dias úteis; SEDEX 2 a 5 dias úteis; Jadlog 3 a 8 dias úteis"
        )


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in decomposed if not unicodedata.combining(c))
