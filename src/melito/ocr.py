"""OCR module — Tesseract with Ancient Greek (grc) recognition.

Uses Tesseract's LSTM engine with the tessdata_best grc model for
polytonic Ancient Greek character recognition. The preprocessed images
are clean single-column upright text, so Tesseract's built-in page
segmentation (PSM 6) handles layout detection well.
"""

import pytesseract
from PIL import Image


TESSERACT_LANG = "grc"
# OEM 3 = LSTM only; PSM 6 = assume uniform block of text
TESSERACT_CONFIG = "--oem 3 --psm 6"


def check_tesseract_lang(lang: str = TESSERACT_LANG) -> None:
    """Verify the required Tesseract language pack is installed."""
    available = pytesseract.get_languages()
    if lang not in available:
        tessdata = "/opt/homebrew/share/tessdata"
        raise RuntimeError(
            f"Tesseract language '{lang}' not found. Install it:\n"
            f"  curl -L -o {tessdata}/{lang}.traineddata \\\n"
            f"    https://github.com/tesseract-ocr/tessdata_best/raw/main/{lang}.traineddata\n"
            f"Available languages: {', '.join(available)}"
        )


def ocr_image(image: Image.Image) -> list[str]:
    """Run Tesseract OCR on a preprocessed page image.

    Returns a list of recognized text lines.
    """
    text = pytesseract.image_to_string(
        image, lang=TESSERACT_LANG, config=TESSERACT_CONFIG
    )
    return text.strip().split("\n")
