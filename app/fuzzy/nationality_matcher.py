from app.fuzzy.base_matcher import fuzzy_match


NATIONALITIES = [
    "WNI",
    "WNA"
]


def match_nationality(value):

    if not value:
        return None

    value = value.upper()

    # Fast path
    if "WNI" in value:
        return "WNI"

    if "WNA" in value:
        return "WNA"

    # Fallback OCR rusak
    return fuzzy_match(
        value=value,
        choices=NATIONALITIES,
        score_cutoff=75
    )