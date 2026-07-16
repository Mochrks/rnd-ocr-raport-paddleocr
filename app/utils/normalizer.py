import re


_SYMBOL_REPLACEMENTS = {
    "\u201c": "",
    "\u201d": "",
    "\"": "",
    "\u2018": "",
    "\u2019": "",
    "`": "",
    "\u2014": "-",
    "\u2013": "-",
    "|": "I",
    "\\": "/",
    "\t": " ",
    "\n": " ",
    "\r": " ",
}

_OCR_TYPO_REPLACEMENTS = {
    "JENISKELAMIN": "JENIS KELAMIN",
    "GOLDARAH": "GOL DARAH",
    "GOL.DARAH": "GOL DARAH",
    "GOL. DARAH": "GOL DARAH",
    "KELDESA": "KEL/DESA",
    "RTRW": "RT/RW",
    "RTIRW": "RT/RW",
    "TEMPATTGL": "TEMPAT/TGL",
    "TEMPAT/TGLLAHIR": "TEMPAT/TGL LAHIR",
    "TEMPAT/TGL.LAHIR": "TEMPAT/TGL LAHIR",
    "LAKILAKI": "LAKI-LAKI",
    "LAKI LAKI": "LAKI-LAKI",
    "KARYAWANSWASTA": "KARYAWAN SWASTA",
    "PERENPUAN": "PEREMPUAN",
    "PEREPUAN": "PEREMPUAN",
    "KCLAHIRAN": "KELAHIRAN",
    "ANAKPERTAMA": "ANAK PERTAMA",
    "WISTERI": "ISTRI",
    "ISTERI": "ISTRI",
    "TEMYATA": "TERNYATA",
    "TEMYARA": "TERNYATA",
    "KELAMN": "KELAMIN",
    "JENIS KELAM": "JENIS KELAMIN",
    "DARI SUAMI DAN": "DARI SUAMI",
    "DANIBU": "DAN IBU",
    "PADATANGGAL": "PADA TANGGAL",
    "SATU.LAKI-LAKI": "SATU LAKI-LAKI",
    "KUTIPAN INI DIKELUARKAN": "KUTIPAN DIKELUARKAN",
    "KUTIPANINIDIKELUARKAN": "KUTIPAN DIKELUARKAN",
    "KUTIPAN INI": "KUTIPAN",
    "WESNBORN": "WES BORN",
    "THATIN": "THAT IN",
    "RIBUDUA": "RIBU DUA",
    "AY AH": "AYAH",
    "PEKERJEAN": "PEKERJAAN",
    "PEKERJCAN": "PEKERJAAN",
    "BERLAKUHINGGA": "BERLAKU HINGGA",
    "BERLAKU HINGGA:": "BERLAKU HINGGA",
    "STATUSPERKAWINAN": "STATUS PERKAWINAN",
    "KEWARGANEGARAAN:": "KEWARGANEGARAAN",
    "SEUMURHIDUP": "SEUMUR HIDUP",
    ".SEUMURHIDUP": "SEUMUR HIDUP",
    "SEUMUR HIDUP.": "SEUMUR HIDUP",
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.upper()
    for old, new in _SYMBOL_REPLACEMENTS.items():
        text = text.replace(old, new)
    for old, new in _OCR_TYPO_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s+([.,])", r"\1", text)
    return text.strip()


def normalize_text_safe(text) -> str | None:
    if text is None:
        return None
    result = normalize_text(text)
    return result if result else None