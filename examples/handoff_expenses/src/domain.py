"""Pure input validation for expenses."""
import datetime
import re


class InvalidInput(ValueError):
    pass


class Conflict(Exception):
    pass


def validate_expense(amount, category, day):
    if re.fullmatch(r'[0-9]+', amount) is None:
        raise InvalidInput()
    try:
        value = int(amount)
    except ValueError:
        raise InvalidInput() from None
    # SQLite INTEGER uses signed 64-bit storage.
    if not 0 < value <= 9223372036854775807:
        raise InvalidInput()
    if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', day) is None:
        raise InvalidInput()
    try:
        datetime.date.fromisoformat(day)
    except ValueError:
        raise InvalidInput() from None
    return value, category, day


def validate_month(month):
    if re.fullmatch(r'[0-9]{4}-[0-9]{2}', month) is None:
        raise InvalidInput()
    try:
        datetime.date.fromisoformat(month + '-01')
    except ValueError:
        raise InvalidInput() from None
    return month
