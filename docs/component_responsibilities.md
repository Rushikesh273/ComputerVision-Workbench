# Component Responsibility Table

This table summarizes each component in the Computer Vision pipeline, its responsibility, and the data it consumes and produces.

| Component | Responsibility | Input | Output |
|---|---|---|---|
| **Camera** | Captures live video of the target scene (e.g. a display, meter, or industrial area) continuously or on trigger. | Physical scene / light | Raw video stream (analog or digital signal) |
| **Frame Capture** | Grabs individual frames from the continuous video stream at a defined rate (FPS) so downstream components can work on discrete images. | Raw video stream | Individual raw image frame (BGR/RGB matrix) + timestamp |
| **Frame Buffer / Queue** | Temporarily holds captured frames so that capture (fast, constant rate) is decoupled from processing (slower, variable rate), preventing frame loss or blocking. | Raw image frame + timestamp | Queued frame + metadata (frame ID, timestamp) |
| **Preprocessing** | Cleans and normalizes the raw frame — resize, grayscale conversion, CLAHE (contrast enhancement), denoising, perspective/lens correction — so the AI model receives consistent, high-quality input. | Queued raw frame | Cleaned / normalized image frame |
| **Object Detection Model** | Locates the region of interest within the frame (e.g. the display, meter, or object to be read), returning its position so later stages can crop and focus on it. | Preprocessed frame | Bounding box(es) + confidence score |
| **OCR Model** | Reads the digits, text, or value from the cropped region of interest identified by the detection model. | Cropped ROI image | Recognized text / value + confidence score |
| **Post-processing** | Filters noisy or low-confidence predictions and stabilizes the reading using confidence thresholding, non-max suppression, tracking, or temporal voting across multiple frames. | Raw OCR/detection output + confidence score | Filtered, stabilized reading |
| **Business Logic / Validation** | Applies domain rules, threshold checks, and compliance logic to the stabilized reading to decide if it is valid, actionable, or should trigger an alert. | Filtered, stabilized reading | Validated result + status/flag |
| **Output Layer (Dashboard / API / Alerts / Database / Reports)** | Delivers the validated result to its final destination(s) — visual dashboard, downstream API consumers, real-time alerts, persistent storage, or periodic reports. | Validated result + status/flag | Displayed/stored/transmitted output (UI update, API response, alert notification, DB record, report file) |
