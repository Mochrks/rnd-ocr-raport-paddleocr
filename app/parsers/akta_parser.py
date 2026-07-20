from app.akta.old_akta_parser import parse_old_akta
from app.akta.new_akta_parser import parse_new_akta


def parse_akta(raw_boxes):

    text = " ".join(
        item["text"]
        for item in raw_boxes
    ).upper()

    if (
            "STBLD" in text
            or "ISTIMEWA" in text
            or "1920 NO" in text
            or "1920NO" in text
    ):

        return parse_old_akta(
            raw_boxes
        )

    return parse_new_akta(
        raw_boxes
    )