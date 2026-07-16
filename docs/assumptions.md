# Assumptions

The Computer Vision pipeline design in this documentation relies on the following assumptions. If any of these do not hold in a real deployment, the corresponding pipeline stage may need to be redesigned or hardened.

## 1. Fixed Camera Position
The camera is assumed to be mounted in a fixed position with a stable field of view (e.g. CCTV or a fixed industrial camera). The target object (display, meter, etc.) is expected to appear in a consistent, predictable region of the frame, simplifying detection and reducing the need for continuous re-calibration.

## 2. Sufficient and Consistent Lighting
The environment is assumed to have adequate, reasonably consistent lighting for the camera sensor to capture a usable image. Extreme low-light, glare, or rapidly changing lighting conditions are not the primary design target, though preprocessing (CLAHE, denoising) provides some tolerance.

## 3. Trained Model Availability
It is assumed that the object detection and OCR models have already been trained (or fine-tuned) on representative data for the target use case, and that these trained model artifacts are available and deployable at inference time. Model training/retraining is out of scope for this pipeline design.

## 4. Continuous Video Stream
The camera is assumed to provide a continuous, stable video stream (rather than intermittent or corrupted frames), allowing the frame capture and buffering stages to operate on a predictable, steady flow of data.

## 5. Stable Network Connectivity
Where the pipeline depends on network-connected components (e.g. streaming to a remote server, pushing data to a dashboard/API/database, or sending alerts), stable network connectivity is assumed. Temporary network interruptions are not the primary focus of this design, though the frame buffer/queue provides some short-term resilience.

## 6. Single Object / Region of Interest per Frame
The pipeline assumes there is generally one primary region of interest (e.g. one display or meter) to detect and read per frame. Scenarios with many simultaneous regions of interest may require additional scaling considerations.

## 7. Acceptable Processing Latency
Near-real-time processing is assumed to be sufficient for the use case; the pipeline is not assumed to require hard real-time (millisecond-level) guarantees unless otherwise specified by business requirements.
