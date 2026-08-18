"""
easyocr_engine.py
==================
EasyOCR wrapper exposing the shared OCR interface used by every engine in
ocr/: a single run_ocr(image_path) -> str function

EasyOCR pipeline: CRAFT (detection) -> CRNN (recognition) -> CTC decode.
"""

import easyocr

_reader = None  # lazy-loaded singleton -- loading the model is slow, do it once


def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def run_ocr(image_path):
    """Returns the recognized text as a single string (empty string if none found)."""
    reader = get_reader()
    results = reader.readtext(image_path, detail=0)  # detail=0 -> just the text strings
    return " ".join(results).strip()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python easyocr_engine.py <image_path>")
    else:
        print(run_ocr(sys.argv[1]))
