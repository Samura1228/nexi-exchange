def format_amount(value) -> str:
    """Format a number removing unnecessary trailing zeros.

    Examples:
        0.50000000 → '0.5'
        0.0004798  → '0.0004798'
        4.0        → '4'
        100.00     → '100'
    """
    if value is None:
        return "0"
    # Convert to float then format with enough precision, strip trailing zeros
    formatted = f"{float(value):.10f}".rstrip("0").rstrip(".")
    return formatted