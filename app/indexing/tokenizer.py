import unicodedata


def tokenize(text: str | None) -> list[str]:
    """Normalize text and return deterministic Unicode letter/number tokens."""
    if not text:
        return []

    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens: list[str] = []
    current: list[str] = []

    for character in normalized:
        category = unicodedata.category(character)
        is_letter_or_number = category[0] in {"L", "N"}
        is_combining_mark = category[0] == "M" and bool(current)
        if is_letter_or_number or is_combining_mark:
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current.clear()

    if current:
        tokens.append("".join(current))
    return tokens
