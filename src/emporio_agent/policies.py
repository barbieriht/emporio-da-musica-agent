from dataclasses import dataclass
import unicodedata
from decimal import Decimal
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from emporio_agent.money import decimal, round_money

# (largest n of the tier, minimum parcela in R$) from the manual's payment rules
_TIERS = [(3, 50.0), (6, 80.0), (12, 100.0)]


@dataclass(frozen=True)
class Installment:
    n: int
    value: float


STORE_TZ = ZoneInfo("America/Campo_Grande")

# weekday (Mon=0) -> (opens, closes), from the published hours; Sunday is closed
_HOURS = {
    **{d: (time(9), time(18)) for d in range(5)},
    5: (time(9), time(13)),
}

# national fixed-date holidays; movable ones (Carnaval, Sexta-feira Santa, Corpus Christi)
# and local ones are not covered: the agent tells customers to confirm those
_HOLIDAYS = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência do Brasil",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (12, 25): "Natal",
}


_WEEKDAYS_PT = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]


@dataclass(frozen=True)
class StoreStatus:
    is_open: bool
    next_open: datetime | None  # None while open
    holiday: str | None = None  # name of the national holiday, when today is one


@dataclass(frozen=True)
class PaymentOptions:
    pix_price: float | None  # None when the price is already promotional (no stacking)
    installments: list[Installment]
    combined_payment_allowed: bool  # e.g. PIX + card, from R$ 2.000 (assumption: inclusive)


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
                options.append(Installment(n, round_money(decimal(price) / n)))
            else:
                break
        return options

    def payment_options(self, price: float, is_promotional: bool) -> PaymentOptions:
        return PaymentOptions(
            pix_price=None if is_promotional else round_money(decimal(price) * Decimal('0.95')),
            installments=self.installment_options(price),
            combined_payment_allowed=price >= 2000,
        )

    def shipping_quote(self, order_total: float, city: str) -> ShippingQuote:
        if _plain(city) == "campo grande":
            return ShippingQuote(0 if order_total >= 500 else 35.0, "1 a 3 dias úteis")
        return ShippingQuote(
            None, "PAC 5 a 12 dias úteis; SEDEX 2 a 5 dias úteis; Jadlog 3 a 8 dias úteis"
        )

    def store_status(self, now: datetime) -> StoreStatus:
        local = now.astimezone(STORE_TZ) if now.tzinfo else now.replace(tzinfo=STORE_TZ)
        holiday = _HOLIDAYS.get((local.month, local.day))
        hours = None if holiday else _HOURS.get(local.weekday())
        if hours and hours[0] <= local.time() < hours[1]:
            return StoreStatus(True, None)
        for offset in range(0, 8):
            day = local.date() + timedelta(days=offset)
            opens = _opening_time(day)
            if opens and opens > local.replace(tzinfo=None):
                return StoreStatus(False, opens.replace(tzinfo=STORE_TZ), holiday)
        raise AssertionError("store never opens")  # unreachable: opens every Mon-Sat

    def after_hours_notice(self, now: datetime) -> str | None:
        status = self.store_status(now)
        if status.is_open:
            return None
        reopens = (
            f"{_WEEKDAYS_PT[status.next_open.weekday()]}, "
            f"{status.next_open:%d/%m}, às {status.next_open:%H:%M}"
        )
        if status.holiday:
            head = f"Hoje é feriado nacional ({status.holiday}) e a loja está fechada. Reabre em {reopens}."
        else:
            head = f"A loja está fechada agora e reabre em {reopens}."
        return f"🕘 {head} Mas posso te ajudar por aqui mesmo!"


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _opening_time(day: date) -> datetime | None:
    if (day.month, day.day) in _HOLIDAYS or day.weekday() not in _HOURS:
        return None
    return datetime.combine(day, _HOURS[day.weekday()][0])
