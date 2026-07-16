from app.fuzzy.base_matcher import fuzzy_match


MARITAL_STATUSES = [
    "BELUM KAWIN",
    "KAWIN",
    "KAWIN TERCATAT",
    "CERAI HIDUP",
    "CERAI MATI",
    "KAWIN BELUM TERCATAT"
]


def match_marital_status(value):

    return fuzzy_match(
        value=value,
        choices=MARITAL_STATUSES,
        score_cutoff=60
    )