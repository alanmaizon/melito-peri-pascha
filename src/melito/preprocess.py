"""Image preprocessing for scholarly edition pages.

Handles rotation, grayscale conversion, contrast enhancement,
adaptive thresholding, and deskewing. No automatic cropping —
manual trimming of headers, footnotes, and margins is preferred
to avoid accidentally cutting Greek text.
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def load_image(path: Path) -> np.ndarray:
    """Load an image as a BGR numpy array."""
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    return img


def orient_page(img: np.ndarray) -> np.ndarray:
    """Ensure the page is in standard reading orientation.

    Uses Tesseract OSD (orientation and script detection) to
    determine if rotation is needed, then applies the correction.
    """
    import pytesseract
    from PIL import Image as PILImage

    gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    pil = PILImage.fromarray(gray)

    try:
        osd = pytesseract.image_to_osd(pil, output_type=pytesseract.Output.DICT)
        angle = osd.get("rotate", 0)
    except pytesseract.TesseractError:
        return img

    if angle == 90:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif angle == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

    return img


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def enhance_contrast(gray: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """Apply CLAHE (adaptive histogram equalization) for local contrast."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    return clahe.apply(gray)


def adaptive_threshold(gray: np.ndarray, block_size: int = 31, c: int = 10) -> np.ndarray:
    """Binarize with adaptive thresholding (white text background, black ink)."""
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
    )


def deskew(gray: np.ndarray) -> np.ndarray:
    """Correct small rotational skew using minAreaRect on detected contours."""
    coords = np.column_stack(np.where(gray < 128))
    if len(coords) < 100:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.3:
        return gray
    h, w = gray.shape
    center = (w // 2, h // 2)
    mat = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, mat, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)


def preprocess(
    path: Path,
    *,
    debug_dir: Path | None = None,
) -> Image.Image:
    """Full preprocessing pipeline: load → rotate → gray → enhance → binarize.

    Returns a PIL Image suitable for Tesseract OCR.
    """
    img = load_image(path)
    img = orient_page(img)
    gray = to_grayscale(img)
    gray = enhance_contrast(gray)
    gray = deskew(gray)
    binary = adaptive_threshold(gray)

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        stem = path.stem
        cv2.imwrite(str(debug_dir / f"{stem}_preprocessed.png"), binary)

    return Image.fromarray(binary)
