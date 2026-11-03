from decimal import ROUND_HALF_UP, Decimal


def round_money(value: Decimal) -> float:
    """Commercial rounding (half up) to cents, avoiding binary-float artifacts."""
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def decimal(value: float) -> Decimal:
    return Decimal(str(value))
