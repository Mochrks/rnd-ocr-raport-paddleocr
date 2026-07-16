from app.fuzzy.base_matcher import fuzzy_match


EDUCATIONS = [
    "TIDAK/BELUM SEKOLAH",
    "BELUM TAMAT SD/SEDERAJAT",
    "TAMAT SD/SEDERAJAT",
    "SLTP/SEDERAJAT",
    "SLTA/SEDERAJAT",
    "DIPLOMA I/II",
    "AKADEMI/DIPLOMA III/S.MUDA",
    "DIPLOMA IV/STRATA I (S1)",
    "STRATA II (S2)",
    "STRATA III (S3)"
]


def match_education(value):

    return fuzzy_match(
        value=value,
        choices=EDUCATIONS,
        score_cutoff=65
    )