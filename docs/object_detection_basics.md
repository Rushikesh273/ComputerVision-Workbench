# Object Detection Basics

Before starting on the actual model, I spent time understanding what object detection is and how YOLO works.

## Classification, Detection, and Segmentation

Classification just gives one label for the whole image, like saying "this image has a display in it" without saying where. Detection goes further and finds where the object is too, by drawing a bounding box around it and giving it a label and a confidence score. Segmentation is even more detailed and outlines the exact pixels of the object instead of just a box. For this project I don't need segmentation's level of detail, detection is enough since I just need to locate the display before reading it.

## Core Components of Detection

Every detection has a few basic parts. The bounding box is the rectangle showing where the object is. The class is what the object is labeled as. The confidence score is how sure the model is, between 0 and 1, and anything below a set threshold (like 0.5) usually gets ignored as unreliable. IoU (Intersection over Union) is how much two boxes overlap, calculated as the overlapping area divided by the combined area of both boxes. It's used to check if a predicted box is close enough to the actual box to be counted correct, and also to remove duplicate boxes when the model predicts more than one box for the same object.

## YOLO

YOLO stands for "You Only Look Once." What makes it different from older detection methods is that it predicts all the boxes and classes in one single pass through the network, instead of first proposing regions and then classifying each one separately. It does this by dividing the image into a grid, and each grid cell predicts whether an object's center is inside it, along with the box coordinates and class. YOLOv8-nano is just the smallest version of YOLOv8, with fewer parameters so it runs faster and uses less memory, at the cost of being a bit less accurate than the bigger versions. A lightweight model like nano makes sense for something like real-time CCTV footage because the feed needs to be processed continuously and usually without a lot of GPU power, so the speed matters more than squeezing out a bit of extra accuracy, especially for a simple task like finding one display in a frame.

## Evaluation Metrics

For evaluating how good a detection model is, there are a few metrics. Precision is how many of the model's predictions were actually correct. Recall is how many of the real objects the model actually managed to find. IoU is used again here as the cutoff for deciding if a prediction counts as correct. mAP@50 measures accuracy while only requiring 50% overlap with the true box, which is a fairly easy bar. mAP@50-95 is stricter, it averages accuracy across overlap requirements from 50% up to 95%, so it rewards models that get the box placement really precise, not just roughly right.

## YOLO Dataset Format

YOLO expects data in a specific format to train on. Every image needs a matching label file with the same name, just a .txt instead of .jpg. Inside that file, each line represents one object as class_id, x_center, y_center, width, height, and all of these numbers are normalized between 0 and 1 based on the image size, not actual pixel values. There's also a data.yaml file that lists out the class names and points to where the training and validation images are. 
