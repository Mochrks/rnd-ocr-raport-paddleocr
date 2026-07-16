import re


def validate_nik(nik):

    if nik is None:
        return None

    nik = nik.replace(" ", "")

    if re.fullmatch(r'\d{16}', nik):
        return nik

    return None