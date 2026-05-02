def round_per_million(value: float) -> float:
    """Round a per-million price to 6 decimal places, eliminating floating-point noise."""
    return round(value, 6)
