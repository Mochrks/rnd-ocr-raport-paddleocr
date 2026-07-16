from app.fuzzy.base_matcher import fuzzy_match


RELIGIONS = [
    "ISLAM",
    "KRISTEN",
    "KATOLIK",
    "HINDU",
    "BUDDHA",
    "KONGHUCU"
]


def match_religion(value):

    return fuzzy_match(
        value=value,
        choices=RELIGIONS,
        score_cutoff=65
    )