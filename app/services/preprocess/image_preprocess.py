import cv2
import numpy as np


def preprocess_image(image_path: str) -> np.ndarray:
    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(f"Gagal membaca gambar: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    upscaled = cv2.resize(
        gray,
        None,
        fx=2,
        fy=2,
        interpolation=cv2.INTER_CUBIC,
    )

    return upscaled