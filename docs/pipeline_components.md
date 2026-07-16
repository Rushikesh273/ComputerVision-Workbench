# Pipeline Components — Detailed Breakdown

This document details each component of the Computer Vision pipeline: what it is, why it's required, its inputs/outputs, and the common techniques or algorithms associated with it.

---

## 1. Camera

**What is it?**
The physical (or virtual/IP) device that captures the visual scene — e.g. a CCTV camera or a fixed industrial camera.

**Why is it required?**
It is the sole source of visual data for the entire pipeline. No downstream component can compensate for a poorly positioned, poorly configured, or malfunctioning camera.

- **Input:** Physical scene / ambient light
- **Output:** Raw video stream (analog or digital signal)
- **Common considerations:** Resolution, frame rate, field of view, lens type, mounting position, lighting conditions, day/night (IR) capability

---

## 2. Frame Capture

**What is it?**
The component that grabs individual, discrete frames from the continuous video stream.

**Why is it required?**
AI models operate on single images, not continuous streams. This stage converts the stream into a sequence of processable frames and typically timestamps/tags each one for traceability.

- **Input:** Raw video stream
- **Output:** Individual raw image frame (BGR/RGB pixel matrix) + timestamp/metadata
- **Common techniques:** OpenCV `VideoCapture`, GStreamer pipelines, RTSP frame grabbing, frame-rate sampling/skipping, frame buffering/queueing

---

## 3. Image Preprocessing

**What is it?**
A set of transformations applied to a raw frame to clean and normalize it before it's fed to the AI model.

**Why is it required?**
Raw camera footage is inherently variable — noisy, unevenly lit, or captured at an angle. Preprocessing reduces this variability, which directly improves downstream model accuracy and consistency.

- **Input:** Raw image frame
- **Output:** Cleaned, normalized image frame
- **Common techniques/algorithms:**
  - **Resize** — standardizes image dimensions to match model input requirements
  - **Grayscale conversion** — reduces data dimensionality when color isn't informative
  - **CLAHE (Contrast Limited Adaptive Histogram Equalization)** — enhances local contrast, especially useful in uneven lighting
  - **Thresholding** — converts grayscale images to binary (black/white) for tasks like OCR pre-processing
  - **Denoising** — removes sensor/compression noise (e.g. Gaussian blur, median filtering, non-local means)
  - **Perspective correction** — warps a skewed view (e.g. an angled camera shot of a flat display) into a front-on view

---

## 4. AI Model

**What is it?**
The core inference component that extracts meaning from the preprocessed image. The specific model type depends on the use case.

**Why is it required?**
This is where raw pixels are converted into structured, meaningful information (what's in the image, where it is, or what it says).

- **Input:** Preprocessed image frame (or a cropped region of interest)
- **Output:** Structured predictions — labels, bounding boxes, masks, text, or keypoints, each typically with a confidence score
- **Common model types:**
  - **Classification** — assigns a single label to the whole image (e.g. "defective" vs "normal")
  - **Object Detection** — locates and labels one or more objects with bounding boxes (e.g. YOLO, Faster R-CNN, SSD)
  - **Segmentation** — classifies image at the pixel level (e.g. U-Net, Mask R-CNN)
  - **OCR (Optical Character Recognition)** — reads text/digits from an image region (e.g. Tesseract, EasyOCR, custom CRNN models)
  - **Pose Estimation** — detects keypoints/joints of a body or object (e.g. OpenPose, MediaPipe Pose)

---

## 5. Post-processing

**What is it?**
A set of techniques that clean up and stabilize the raw model output before it's used for decision-making.

**Why is it required?**
A single frame's model prediction can be noisy, low-confidence, or momentarily wrong even if the model is generally accurate. Post-processing turns raw, noisy predictions into a stable, trustworthy result.

- **Input:** Raw model predictions + confidence scores
- **Output:** Filtered, stabilized reading
- **Common techniques/algorithms:**
  - **Confidence Thresholding** — discards predictions below a minimum confidence score
  - **NMS (Non-Max Suppression)** — removes duplicate/overlapping bounding boxes for the same object
  - **Tracking** — maintains object identity across frames (e.g. SORT, DeepSORT, Kalman filters)
  - **Temporal Voting** — aggregates predictions across multiple consecutive frames (e.g. majority vote) to reduce the impact of a single erroneous frame

---

## 6. Business Logic / Validation

**What is it?**
The layer that applies domain-specific rules to the stabilized reading to determine what it means for the business.

**Why is it required?**
A technically "correct" reading isn't inherently actionable — it needs to be interpreted against business rules (is this value in range? does it indicate a violation?) to become a decision.

- **Input:** Filtered, stabilized reading
- **Output:** Validated result + status/flag (e.g. pass/fail, alert/no-alert)
- **Common techniques:**
  - **Rule Engine** — configurable if/then business rules applied to the reading
  - **Threshold Checks** — comparing the reading against min/max acceptable values
  - **Compliance Verification** — checking the reading against regulatory or contractual requirements

---

## 7. Output

**What is it?**
The final delivery layer that routes the validated result to its destination(s).

**Why is it required?**
A validated result only creates value once it reaches a human or system that can act on it — an operator dashboard, an automated system via API, an alerting channel, a persistent data store, or a report.

- **Input:** Validated result + status/flag
- **Output:** Delivered output in the destination's native form
- **Common destinations:**
  - **Dashboard** — real-time visual display for human operators
  - **API** — programmatic endpoint for other systems to consume the result
  - **Alerts** — push notifications, SMS, email, or alarms for anomalies/violations
  - **Database** — persistent storage for historical records and auditing
  - **Reports** — periodic (daily/weekly) aggregated summaries

---
