"""
paddleocr_engine.py
====================
PaddleOCR wrapper exposing the shared OCR interface used by every engine in
ocr/: a single run_ocr(image_path) -> str function

PaddleOCR pipeline: DBNet (detection) -> orientation classifier -> SVTR (recognition).

Uses the PaddleOCR 3.x API (use_textline_orientation, no show_log/cls args --
those are 2.x-only and were removed). enable_mkldnn=False works around a
known PaddlePaddle 3.3.x CPU bug where the default oneDNN backend throws:
    NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
    [pir::ArrayAttribute<pir::DoubleAttribute>]
on many Windows/CPU setups (PaddlePaddle/Paddle#77340). If this ever gets
fixed upstream, mkldnn can be re-enabled for a speed boost.
"""

from paddleocr import PaddleOCR

_ocr = None  # lazy-loaded singleton -- loading the model is slow, do it once


def get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_textline_orientation=True, lang="en", enable_mkldnn=False)
    return _ocr


def run_ocr(image_path):
    """Returns the recognized text as a single string (empty string if none found)."""
    ocr = get_ocr()
    result = ocr.ocr(image_path)  # PaddleOCR 3.x: no cls= argument anymore

    texts = []
    for res in result:
        # PaddleOCR 3.x result items are dict-like, with a "rec_texts" key
        # holding every recognized text string for that image.
        rec_texts = res.get("rec_texts") if hasattr(res, "get") else getattr(res, "rec_texts", None)
        if rec_texts:
            texts.extend(rec_texts)
    return " ".join(texts).strip()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python paddleocr_engine.py <image_path>")
    else:
        print(run_ocr(sys.argv[1]))
