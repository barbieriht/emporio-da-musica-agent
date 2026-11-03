"""Finds monetary values and dates in a reply and checks them against known evidence texts."""
import re
from decimal import Decimal, InvalidOperation

# R$ followed by one of: thousands separated by dot/space/nbsp (1.000 | 1 000) with optional ,cents;
# a decimal (599,90 | 599.90); or a plain integer. The trailing (?!\d) keeps a sentence-ending
# dot ("... R$ 1.000.") out of the number.
_MONEY = re.compile(
    r"R\$\s*(\d{1,3}(?:[.   ]\d{3})+(?:,\d{1,2})?|\d+[.,]\d{1,2}|\d+)(?!\d)"
)
_DATE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?(?![\d/])")


def _parse_money(raw: str) -> Decimal | None:
    digits = re.sub(r"[\s  ]", "", raw)
    if "," in digits:
        digits = digits.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", digits):
        digits = digits.replace(".", "")  # 1.000 -> 1000
    try:
        return Decimal(digits).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None  # not a number we can judge; never crash the conversation


def money_values(text: str) -> set[Decimal]:
    return {v for v in map(_parse_money, _MONEY.findall(text)) if v is not None}


def dates(text: str) -> set[tuple[int, int, int | None]]:
    found = set()
    for day, month, year in _DATE.findall(text):
        if 1 <= int(day) <= 31 and 1 <= int(month) <= 12:
            full_year = None if not year else (int(year) if len(year) == 4 else 2000 + int(year))
            found.add((int(day), int(month), full_year))
    return found


def unsupported(reply: str, evidence: str) -> list[str]:
    """Values and dates written in `reply` that never appear in `evidence`."""
    known_money = money_values(evidence)
    known_dates = dates(evidence)
    problems = []
    for match in _MONEY.finditer(reply):
        value = _parse_money(match.group(1))
        if value is not None and value not in known_money:
            problems.append(match.group(0).strip())
    for match in _DATE.finditer(reply):
        found = dates(match.group(0))
        if not found:
            continue
        (day, month, year) = next(iter(found))
        if not any(d == day and m == month and (year is None or y is None or y == year) for d, m, y in known_dates):
            problems.append(match.group(0))
    return problems
