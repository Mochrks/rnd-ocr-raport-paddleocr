from app.services.fuzzy.base_matcher import fuzzy_match


BLOOD_TYPES = [
    "TIDAK TAHU",
    "AB",
    "A",
    "B",
    "O"
]


def match_blood_type(value):

    if not value:
        return None

    value = value.upper()

    # OCR sering membaca O menjadi 0
    value = value.replace("0", "O")

    # Prioritaskan substring
    if "TIDAK TAHU" in value:
        return "TIDAK TAHU"

    if "AB" in value:
        return "AB"

    # Tokenisasi agar BAJAWA tidak dianggap A
    tokens = value.replace("/", " ").split()

    if "A" in tokens:
        return "A"

    if "B" in tokens:
        return "B"

    if "O" in tokens:
        return "O"

    # Fallback jika OCR jelek
    return fuzzy_match(
        value=value,
        choices=BLOOD_TYPES,
        score_cutoff=70
    )
