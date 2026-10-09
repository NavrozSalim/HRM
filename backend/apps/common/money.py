from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")
ONE = Decimal("1")
HALF = Decimal("0.50")


def D(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def hours(minutes) -> Decimal:
    return (D(minutes) / Decimal("60")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def json_safe(value):
    if isinstance(value, Decimal):
        return format(money(value), "f")
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
