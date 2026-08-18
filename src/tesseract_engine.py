"""
tesseract_engine.py
====================
Tesseract wrapper exposing the shared OCR interface used by every engine in
ocr/: a single run_ocr(image_path) -> str function, so compare_engines.py
can call all three engines identically.

Tesseract pipeline: page/line layout analysis -> LSTM line recognizer.

Requires the Tesseract OCR *binary* installed separately from the pytesseract
pip package (pytesseract is just a Python wrapper around it):
    Windows: https://github.com/UB-Mannheim/tesseract/wiki
    Linux:   sudo apt install tesseract-ocr
"""

import pytesseract
from PIL import Image

# Set this if tesseract.exe isn't on PATH (common on Windows):
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --psm 7 = treat the image as a single line of text (matches a cropped display).
# The digit/decimal/minus whitelist steers Tesseract away from misreading
# segments as letters, since a seven-segment display only ever shows these.
TESSERACT_CONFIG = "--psm 7 -c tessedit_char_whitelist=0123456789.-"


def run_ocr(image_path):
    """Returns the recognized text as a single string (empty string if none found)."""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
    return text.strip()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tesseract_engine.py <image_path>")
    else:
        print(run_ocr(sys.argv[1]))
