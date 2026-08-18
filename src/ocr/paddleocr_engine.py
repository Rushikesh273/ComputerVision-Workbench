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

_ocr = None

def get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(
            lang="en",
            device="cpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )
    return _ocr

def run_ocr(image_path):
    ocr = get_ocr()
    try:
        result = ocr.predict(image_path)   # 3.x preferred
    except AttributeError:
        result = ocr.ocr(image_path)       # 2.x fallback

    texts = []
    for res in result or []:
        if res is None:
            continue
        if hasattr(res, "rec_texts"):
            texts.extend(str(t) for t in res.rec_texts if t)
        elif isinstance(res, dict) and "rec_texts" in res:
            texts.extend(str(t) for t in res["rec_texts"] if t)
    return " ".join(texts).strip()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python paddleocr_engine.py <image_path>")
    else:
        print(run_ocr(sys.argv[1]))
