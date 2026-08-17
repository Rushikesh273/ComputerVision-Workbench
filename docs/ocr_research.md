# OCR Research — Why Standard OCR Struggles on Industrial Digital Displays

## 1. What is OCR?

Optical Character Recognition (OCR) is the process of converting an image containing text — a scanned document, a photo, a video frame — into machine-readable, editable text. Modern OCR is almost entirely deep-learning based: a pipeline of neural networks that first find *where* text is in an image, then figure out *what* that text says.

## 2. OCR Detection vs. OCR Recognition

These are two distinct sub-tasks that almost every modern OCR engine splits into separate stages:

- **Detection** answers "where is the text?" It takes a full image and outputs bounding boxes (or polygons) around regions that contain text — without knowing yet what the characters actually are. This is a localization/segmentation problem, structurally similar to object detection (which is why detectors like DBNet borrow ideas from general-purpose segmentation networks).
- **Recognition** answers "what does the text say?" It takes a *cropped* text region (already located by the detector) and outputs a character/word string. This is a sequence-prediction problem, not a localization one.

Splitting the problem this way lets each stage specialize — detection cares about shapes and edges at the image level, recognition cares about character sequences at the crop level — and lets engines mix and match different detector/recognizer combinations.

## 3. How OCR Engines Identify Characters (General Pipeline)

At a high level, most modern OCR systems follow this pipeline:

1. **Preprocessing** — grayscale conversion, noise reduction, binarization/thresholding, sometimes skew/rotation correction.
2. **Text detection** — a neural network scans the image and proposes regions likely to contain text.
3. **Region cropping and normalization** — each detected region is cropped, straightened, and resized to a fixed height so the recognizer sees consistent input.
4. **Feature extraction** — a CNN backbone converts each cropped region into a sequence of feature vectors (essentially "sliding" left to right across the crop).
5. **Sequence modeling** — a recurrent network (LSTM) or transformer processes that feature sequence, modeling how characters relate to their neighbors.
6. **Decoding** — the sequence of per-position character probabilities is collapsed into an actual text string, usually with **CTC (Connectionist Temporal Classification)**, which handles the fact that a fixed-width feature sequence needs to align to a variable-length text output without needing character-by-character position labels during training.
7. **Post-processing** — optional dictionary/language-model correction, confidence scoring.

Character *identification* itself, then, isn't template matching — it's the CNN+sequence-model combination learning to map visual patterns (strokes, curves, gaps) to character classes, trained on large labeled datasets.

## 4. Engine Architectures at a High Level

### Tesseract
Tesseract has two recognition modes: a legacy pattern-matching classifier (pre-v4), and — since Tesseract 4 — a modern **LSTM-based neural network engine**, which is now the default and far more accurate. It processes one text line at a time, running the cropped line through an LSTM sequence recognizer (`LSTMRecognizer`) rather than segmenting individual characters up front. Its network structure is defined via Tesseract's own VGSL (Variable Graph Specification Language) rather than a fixed architecture. Tesseract does **not** ship its own general-purpose scene-text *detector* — it's built primarily for document images with an assumed page/line layout, using its own layout analysis to find lines rather than a deep-learning detection network like the other two engines below.

### EasyOCR
EasyOCR is a two-stage pipeline: **CRAFT** (Character Region Awareness for Text Detection) for detection, and a **CRNN** (Convolutional Recurrent Neural Network) for recognition. CRAFT is distinctive in that it works at the *character* level — it predicts a "region score" for individual character locations and an "affinity score" for the gaps between them, then groups characters into words/lines from those two score maps rather than predicting word-level boxes directly. The recognizer (CRNN) then takes each cropped, grayscale region through a CNN feature extractor (commonly ResNet), a bidirectional LSTM for sequence modeling, and CTC decoding to produce the final string.

### PaddleOCR
PaddleOCR (PP-OCR) uses a three-stage pipeline: a **DB (Differentiable Binarization) detector** finds text regions as polygons; a lightweight **direction/orientation classifier** rotates each cropped region upright; and a **recognizer** reads the corrected crop. The recognizer has evolved across PaddleOCR versions — early versions used CRNN, but from PP-OCRv3 onward it shifted to **SVTR** (Scene Text Recognition with a single Visual Transformer), a transformer-based recognizer combined with a lightweight CNN backbone (LCNet), which is faster and smaller than the CRNN+LSTM approach while matching or beating its accuracy. Decoding is still primarily CTC-based, with an optional attention-based branch used during training for extra supervision.

### Comparison Table

| | Tesseract | EasyOCR | PaddleOCR |
|---|---|---|---|
| Detection stage | Traditional layout analysis (page/line segmentation), not a learned scene-text detector | CRAFT — character-level region + affinity maps | DBNet — polygon-based text region segmentation |
| Recognition stage | LSTM sequence recognizer (line-level) | CRNN: CNN + BiLSTM + CTC | Evolved from CRNN to SVTR (transformer) + CTC |
| Best suited for | Clean, scanned documents; structured page layouts | Natural/scene text, multiple languages, arbitrary orientation | Production/edge deployment; lightweight + multilingual |
| Handles rotated/curved text | Poorly — assumes fairly regular line layout | Well — CRAFT + rotation handling built in | Well — dedicated orientation classifier stage |
| Relative speed/size | Lightweight, CPU-friendly | Heavier (PyTorch, ResNet+LSTM) | Optimized for small model size, fast inference |
| Segmentation-free? | Yes — line-level LSTM avoids character segmentation | Yes — CTC-based, no explicit character segmentation | Yes — CTC/attention-based, no explicit character segmentation |

All three share one important trait relevant to this project: **none of them were designed or trained with seven-segment/LED/LCD displays as a target domain.** Their training data is overwhelmingly natural scene text and printed documents — ordinary typefaces with continuous strokes — which matters a great deal for Section 6 below.

## 5. Digital Displays — What Makes Them Visually Different from Printed Text

### Seven-segment displays
A seven-segment display forms each digit from seven straight-line segments (labeled conventionally a–g) arranged in a figure-eight pattern, lit or unlit in combination to form digits 0–9 (and a limited set of letters). Structurally, this is fundamentally different from a printed digit's continuous, curved stroke — a "0" on a seven-segment display is six straight lit segments forming a rectangle-ish loop, not a smooth oval.

### LED displays
LED (Light-Emitting Diode) displays are usually the physical implementation of a seven-segment (or dot-matrix) layout: each segment is one or more LEDs. Key visual properties: high brightness/contrast against a dark background, a tendency to **bloom or halo** in photos (the lit segment appears wider/brighter than its physical size, especially in a slightly overexposed or long-exposure shot), and — critically for this project — **flicker**, since many LED displays are pulse-width-modulated (rapidly switched on/off faster than the eye perceives) for brightness control. A camera with a fast shutter can catch the display mid-off-cycle.

### LCD displays
LCD (Liquid Crystal Display) segments work by blocking/passing light rather than emitting it, so contrast depends heavily on ambient lighting, viewing angle, and backlight condition. LCDs are prone to **low contrast** under poor lighting, glare/reflection off the glass or plastic cover, and contrast shifts when viewed off-angle (a real issue for factory cameras mounted at a fixed, not-necessarily-perpendicular angle to the meter).

### Seven-segment digit structure, decimal points, and negative signs
- Each digit occupies a fixed segment "slot" — unlike printed text, digit width and segment thickness are usually uniform across the whole display, which is actually a potential *advantage* for a purpose-built reader (predictable geometry) but not something a general OCR engine is designed to exploit.
- A **decimal point** is typically a single small square/round segment, often physically tiny relative to the digit height — easy to miss entirely under blur, low resolution, or aggressive binarization thresholds that treat it as noise.
- A **negative sign** is usually a single horizontal segment, sometimes in its own dedicated position on the display, sometimes reusing part of a segment pattern. It's visually just a short horizontal line — trivially confusable with a dash, an underscore, a dust speck, or dropped entirely by a detector that expects "text" to look like connected character shapes.
- **Different digit shapes**: several digits share almost all their segments (e.g., 8 uses all seven segments; 6, 9, and 8 differ by only one or two segments each), so a partially occluded or low-confidence read can easily flip one digit into a visually adjacent one (8↔6, 8↔9, 5↔6, 3↔9 are classic seven-segment confusions).

## 6. Why a Standard OCR Engine Might Fail on "12.50"

Each condition below attacks a different assumption that Tesseract/EasyOCR/PaddleOCR's training data implicitly makes about what "text" looks like:

- **Blurry** — All three recognizers rely on a CNN extracting sharp edge/stroke features. Blur softens segment edges into gradients, which is especially damaging for seven-segment characters since segments are already just thin rectangles — a blurred segment can lose its rectangular shape entirely and get read as a blob, merging adjacent segments (e.g., a blurred "1" and a blurred "." might merge into what looks like nothing recognizable, or the decimal point can disappear into blur noise entirely, silently turning "12.50" into "1250").
- **Flickering** — If the display is mid-refresh or mid-PWM-cycle when the photo/frame is captured, some segments may be partially or fully unlit in that exact frame, even though the true reading is stable. The OCR engine has no way to know this is a temporal artifact rather than the actual displayed value — it will confidently recognize whatever partial/missing segment pattern is in that single frame, potentially reading "12.50" as "12.5" (dot lost) or "17.50" (a segment of "2" dropped, making it look like "7").
- **Low contrast** — Detection stages (CRAFT, DBNet) rely on a strong edge/intensity difference between text and background to segment "text" regions in the first place. A washed-out LCD under poor lighting may not clear the contrast threshold the detector was trained on, so the whole display region — or just the fainter decimal point — may never even get *detected* as containing text, regardless of how good the recognizer is downstream.
- **Reflected** — Glare on an LCD's glass surface creates bright specular highlights that can be misread as bright "on" segments where there are none, or can wash out real segments underneath the glare, effectively adding false segments or deleting real ones. Reflections can also mimic edges that confuse the detector into drawing a bounding box around the glare instead of the actual digits.
- **Slightly rotated** — None of these engines expect perfectly axis-aligned text as a hard requirement, but recognition accuracy for CRNN/SVTR-style models drops as skew increases, because the "read left to right across a fixed-height crop" assumption starts breaking down — a rotated decimal point can end up vertically offset from the digit baseline it belongs to, making it ambiguous whether it's associated with the "2" or the "5", or get cropped out of the recognition window entirely if the detector's box doesn't fully compensate for the rotation.
- **Partially occluded** — If a wire, finger, glare, or dirt obscures even one segment, a whole digit can flip into a different valid digit (an occluded top-right segment can turn an "8" into a "6", per the digit-confusion table in Section 5). Occlusion can also hide the negative sign or decimal point entirely — both being small, single-segment glyphs — silently turning "12.50" into "1250" or, worse, sign-flipping a negative reading into a positive one with no visual cue in the output that anything was missed.

**The common thread:** none of these are exotic edge cases from the perspective of a factory floor — flicker, glare, and slightly-off camera angles are the *normal* operating conditions for a fixed industrial camera. But they're all outside the training distribution these three engines were built and tuned on (clean documents and natural scene text), and seven-segment glyphs in particular have almost no redundant stroke information to fall back on when a segment or two goes missing — a real letter "o" surviving a small ink smudge still looks like an "o"; a seven-segment "8" losing one segment to occlusion becomes a completely different, still-perfectly-valid digit.

## 7. Relevance to This Project

This is the underlying justification for testing multiple OCR engines (Tesseract, PaddleOCR, EasyOCR, plus the additional engines already in use — mmocr, easyocr, fastocr, parseq) against the cropped display regions produced by the YOLO detector, rather than assuming any single general-purpose engine will handle industrial seven-segment readings reliably out of the box. It also motivates preprocessing steps worth testing downstream (contrast enhancement, deflicker/multi-frame averaging, glare masking, and possibly a purpose-trained seven-segment recognizer instead of a general OCR engine) — covered in later stages of the pipeline.

## References

- Tesseract architecture and LSTM engine: [tesseract-ocr/tesseract on DeepWiki](https://deepwiki.com/tesseract-ocr/tesseract), [tessdoc — Neural nets in Tesseract 4.00](https://tesseract-ocr.github.io/tessdoc/tess4/NeuralNetsInTesseract4.00.html)
- EasyOCR architecture (CRAFT + CRNN): [JaidedAI/EasyOCR on DeepWiki](https://deepwiki.com/JaidedAI/EasyOCR), [EasyOCR PyPI project description](https://pypi.org/project/easyocr/1.1.9/)
- PaddleOCR pipeline (DB + SVTR): [PaddleOCR overview — EmergentMind](https://www.emergentmind.com/topics/paddleocr), [PaddleOCR Usage Tutorial](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html)
