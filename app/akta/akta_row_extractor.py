def group_rows(raw_boxes, tolerance=15):

    boxes = sorted(
        raw_boxes,
        key=lambda x: x["y"]
    )

    rows = []

    for box in boxes:

        found = False

        for row in rows:

            if abs(
                    row[0]["y"] - box["y"]
            ) <= tolerance:

                row.append(box)
                found = True
                break

        if not found:

            rows.append(
                [box]
            )

    for row in rows:

        row.sort(
            key=lambda x: x["x"]
        )

    return rows


def join_rows(rows):

    result = []

    for row in rows:

        text = " ".join(
            item["text"]
            for item in row
        )

        result.append(
            text.strip()
        )

    return result