from app.services.fuzzy.base_matcher import fuzzy_match


FAMILY_RELATIONS = [
    "KEPALA KELUARGA",
    "SUAMI",
    "ISTRI",
    "ANAK",
    "MENANTU",
    "CUCU",
    "ORANG TUA",
    "MERTUA",
    "FAMILI LAIN",
    "PEMBANTU",
    "LAINNYA"
]


def match_family_relation(value):

    return fuzzy_match(
        value=value,
        choices=FAMILY_RELATIONS,
        score_cutoff=60
    )
