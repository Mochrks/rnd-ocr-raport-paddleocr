import os

import cv2
import numpy as np
import fitz

from paddleocr import PaddleOCR


ocr = PaddleOCR(
    use_angle_cls=True,
    lang="en",
)


# ============================================================
# KONSTANTA
# ============================================================

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
PDF_EXTENSION = ".pdf"
PDF_DPI = 200


# ============================================================
# DETEKSI TIPE FILE
# ============================================================

def is_pdf(file_path: str) -> bool:
    return os.path.splitext(file_path)[1].lower() == PDF_EXTENSION


# ============================================================
# KONVERSI PDF → GAMBAR (numpy array)
# ============================================================

def pdf_to_images(file_path: str, dpi: int = PDF_DPI) -> list[np.ndarray]:
    doc = fitz.open(file_path)
    images = []

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for page_num in range(len(doc)):
        page = doc[page_num]
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        img_array = np.frombuffer(pixmap.samples, dtype=np.uint8)
        img_array = img_array.reshape(pixmap.height, pixmap.width, pixmap.n)

        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        images.append(img_bgr)

    doc.close()
    return images


# ============================================================
# OCR CORE
# ============================================================

def extract_text(image_input) -> str:
    if isinstance(image_input, str):
        image = cv2.imread(image_input)
        if image is None:
            raise ValueError(f"Gagal membaca gambar: {image_input}")
    else:
        image = image_input

    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    try:
        result = ocr.ocr(image, cls=True)
    except TypeError:
        result = ocr.ocr(image)
    lines = []

    if not result:
        return ""
    first = result[0]
    if not first:
        return ""

    if isinstance(first, list):
        for line in first:
            if not line or len(line) < 2:
                continue
            text_data = line[1]
            if isinstance(text_data, (list, tuple)) and len(text_data) >= 2:
                lines.append(str(text_data[0]))
            elif isinstance(text_data, str):
                lines.append(text_data)
    elif isinstance(first, dict):
        texts = first.get("rec_texts", [])
        for t in texts:
            lines.append(str(t))

    return "\n".join(lines)


def extract_text_with_boxes(image_input) -> list[dict]:
    if isinstance(image_input, str):
        image = cv2.imread(image_input)
        if image is None:
            raise ValueError(f"Gagal membaca gambar: {image_input}")
    else:
        image = image_input

    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    try:
        result = ocr.ocr(image, cls=True)
    except TypeError:
        result = ocr.ocr(image)
    rows = []

    if not result:
        return rows
    first = result[0]
    if not first:
        return rows

    if isinstance(first, list):
        for line in first:
            if not line or len(line) < 2:
                continue
            poly = line[0]
            text_data = line[1]
            if not poly:
                continue

            try:
                x = min(float(point[0]) for point in poly if len(point) >= 2)
                y = min(float(point[1]) for point in poly if len(point) >= 2)
            except Exception:
                continue

            if isinstance(text_data, (list, tuple)) and len(text_data) >= 2:
                text = str(text_data[0])
                confidence = float(text_data[1])
            elif isinstance(text_data, str):
                text = text_data
                confidence = 0.5
            else:
                continue

            rows.append({
                "text": text,
                "x": x,
                "y": y,
                "confidence": confidence,
            })
    elif isinstance(first, dict):
        texts = first.get("rec_texts", [])
        scores = first.get("rec_scores", [])
        boxes = first.get("rec_boxes", first.get("dt_polys", []))

        has_boxes = False
        if boxes is not None:
            try:
                has_boxes = len(boxes) > 0
            except Exception:
                has_boxes = True

        n = min(len(texts), len(scores), len(boxes)) if has_boxes else min(len(texts), len(scores))
        for i in range(n):
            try:
                text = str(texts[i])
                confidence = float(scores[i])

                if has_boxes:
                    bbox = boxes[i]
                    if hasattr(bbox, "tolist"):
                        bbox = bbox.tolist()
                    if bbox and hasattr(bbox[0], "__iter__") and not isinstance(bbox[0], str):
                        xs = [float(p[0]) for p in bbox if len(p) >= 2]
                        ys = [float(p[1]) for p in bbox if len(p) >= 2]
                        x = min(xs) if xs else 0.0
                        y = min(ys) if ys else 0.0
                    elif bbox and len(bbox) >= 2:
                        x = float(bbox[0])
                        y = float(bbox[1])
                    else:
                        x, y = i * 100.0, 0.0
                else:
                    x, y = i * 100.0, 0.0

                rows.append({
                    "text": text,
                    "x": x,
                    "y": y,
                    "confidence": confidence,
                })
            except Exception:
                continue

    rows.sort(key=lambda d: (d["y"], d["x"]))
    return rows


# ============================================================
# ENTRY POINT TERPADU: FILE PATH (gambar atau PDF)
# ============================================================

def extract_boxes_from_file(
    file_path,
    page_mode: str = "first",
    y_offset_per_page: int = 2000,
) -> list[dict]:
    if isinstance(file_path, np.ndarray):
        return extract_text_with_boxes(file_path)

    if is_pdf(file_path):
        images = pdf_to_images(file_path)

        if not images:
            return []

        if page_mode == "first":
            return extract_text_with_boxes(images[0])

        all_boxes = []
        current_y_offset = 0

        for page_img in images:
            page_boxes = extract_text_with_boxes(page_img)
            for box in page_boxes:
                box = box.copy()
                box["y"] = box["y"] + current_y_offset
                all_boxes.append(box)
            current_y_offset += y_offset_per_page

        return all_boxes

    return extract_text_with_boxes(file_path)


def extract_text_from_image(image_input):
    return extract_text(image_input)