import csv

from pathlib import Path

from rapidfuzz import fuzz


class PostalCodeService:

    def __init__(self):

        self._postal_data = {}

        csv_path = (
            Path(__file__)
            .parent.parent
            / "infrastructure"
            / "data"
            / "postal_code_data.csv"
        )

        with open(
            csv_path,
            mode="r",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                postal_code = row["postal_code"].strip()

                item = {
                    "postal_code": postal_code,
                    "urban": row["urban"].strip().upper(),
                    "sub_district": row["sub_district"].strip().upper(),
                    "city": row["city"].strip().upper()
                }

                self._postal_data.setdefault(
                    postal_code,
                    []
                ).append(item)

    def find_by_postal_code(
        self,
        postal_code: str
    ):

        if postal_code is None:
            return []

        return self._postal_data.get(
            postal_code.strip(),
            []
        )

    def enrich(
        self,
        postal_code: str,
        urban: str = None,
        sub_district: str = None,
        city: str = None
    ):

        candidates = self.find_by_postal_code(
            postal_code
        )

        if not candidates:
            return None

        # hanya ada satu lokasi
        if len(candidates) == 1:
            return candidates[0]

        best_candidate = None
        best_score = -1

        for candidate in candidates:

            score = 0

            if urban:
                score += fuzz.ratio(
                    urban.upper(),
                    candidate["urban"]
                )

            if sub_district:
                score += fuzz.ratio(
                    sub_district.upper(),
                    candidate["sub_district"]
                )

            if city:
                score += fuzz.ratio(
                    city.upper(),
                    candidate["city"]
                )

            if score > best_score:

                best_score = score
                best_candidate = candidate

        if best_candidate:
            return best_candidate

        return None


postal_code_service = PostalCodeService()