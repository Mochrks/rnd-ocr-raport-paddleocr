from app.services.fuzzy.base_matcher import fuzzy_match


GENDERS = [
    "LAKI-LAKI",
    "PEREMPUAN"
]


def match_gender(value):

    if not value:
        return None

    value = value.upper()

    # Fast path
    if "LAKI-LAKI" in value:
        return "LAKI-LAKI"

    if "PEREMPUAN" in value:
        return "PEREMPUAN"

    # Fallback untuk OCR yang rusak
    return fuzzy_match(
        value=value,
        choices=GENDERS,
        score_cutoff=60
    )
