from rapidfuzz import process, fuzz
import re


def fuzzy_match(value, choices, score_cutoff=75):
    if not value:
        return None

    value = value.upper().strip()

    # Safeguard: jika tidak ada karakter huruf sama sekali, langsung return None
    # Mencegah string kosong / hanya angka / spasi cocok secara fuzzy
    if not re.search(r"[A-Z]", value):
        return None

    # Coba exact match dengan letter-boundary lookaround
    # Sort dari yang terpanjang dulu agar "KAWIN BELUM TERCATAT" tidak kalah dengan "KAWIN"
    sorted_choices = sorted(choices, key=len, reverse=True)
    for choice in sorted_choices:
        pattern = r"(?<![A-Z])" + re.escape(choice.upper()) + r"(?![A-Z])"
        if re.search(pattern, value):
            return choice

    cleaned = re.sub(r"\d+", " ", value)

    # Pisahkan choice pendek vs panjang, pakai scorer & cutoff berbeda
    long_choices = [c for c in choices if len(c) >= 7]
    short_choices = [c for c in choices if len(c) < 7]

    # Untuk choice panjang, partial_ratio relatif aman
    if long_choices:
        result = process.extractOne(
            query=cleaned, choices=long_choices,
            scorer=fuzz.partial_ratio, score_cutoff=score_cutoff
        )
        if result:
            return result[0]

    # Untuk choice pendek, JANGAN pakai partial_ratio terhadap full text.
    # Bandingkan token-per-token saja, dengan token_sort_ratio/ratio,
    # dan syaratkan panjang token mendekati panjang choice.
    if short_choices:
        tokens = re.findall(r"[A-Z/-]+", cleaned)
        for token in tokens:
            if abs(len(token) - max(len(c) for c in short_choices)) > 3:
                continue  # skip token yang panjangnya jauh beda
            result = process.extractOne(
                query=token, choices=short_choices,
                scorer=fuzz.ratio, score_cutoff=max(score_cutoff, 80)
            )
            if result:
                return result[0]

    return None