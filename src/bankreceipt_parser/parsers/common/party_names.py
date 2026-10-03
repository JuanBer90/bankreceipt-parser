"""Person-name normalization helpers for receipt parsers."""


def natural_name_from_single_comma(raw: str) -> str:
    """
    When a printed name uses a single comma as ``<surnames>, <given names>``,
    return ``<given names> <surnames>``. Otherwise return the input unchanged.
    """
    text = raw.strip()
    if "," not in text:
        return text
    if text.count(",") != 1:
        return text
    left, right = text.split(",", 1)
    if not left.strip() or not right.strip():
        return text
    return f"{right.strip()} {left.strip()}"
