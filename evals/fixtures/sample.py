"""Small statistics helpers."""


def average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)


def last_or_none(items):
    return items[len(items) - 1] if items else None
