# SynthGen Pro: Automated 3D-to-AI Dataset Generation Pipeline

[![Blender Version](https://img.shields.io/badge/Blender-3.6%20--%205.0%20LTS-orange.svg)](https://www.blender.org)
[![Dataset Format](https://img.shields.io/badge/Format-YOLO%20%7C%20COCO-blue.svg)](#dataset-outputs)
[![Output](https://img.shields.io/badge/Output-Transparent%20PNGs-green.svg)](#dataset-outputs)

An automated synthetic data generation pipeline built in Blender to generate custom, high-fidelity training datasets for computer vision and object detection models. 

By eliminating the manual data labeling bottleneck, this pipeline produces mathematically verified, pre-annotated transparent image sets across diverse physical and environmental conditions
---

## 📺 Pipeline Demonstration

https://github.com/user-attachments/assets/e44be4f7-708c-49e9-b8c4-d54bf67531e8

.
---

## ⚙️ Core Pipeline Features

* **Real-Time Viewport Bounding Box Tracking:** Features a highly visual, viewport-space projection system to verify 2D bounding boxes dynamically as objects rotate and scale [1.1.1].
* **Robust Domain Randomization:** Automatically shuffles the object's 3D pose, surface material properties (metallic, roughness, hue, saturation), and lighting intensities on every single frame to ensure high real-world model generalization [1.1.7].
* **Transparent Background Outputs:** Renders target assets directly as transparent PNGs with alpha-channels. This allows machine learning pipelines to composite the objects onto thousands of diverse backgrounds, completely eliminating background bias during training .
* **Multi-Format Export Engine:** Automatically formats and writes bounding box annotations into industry-standard YOLO text files or structured COCO JSON databases on the fly.
* **Mathematical Verification (QA):** Includes a separate verification script that parses the generated annotation coordinates and overlays bounding boxes onto the rendered transparent images to ensure zero coordinate drift.

---

## 📊 Dataset Outputs (Example: Spray Paint Bottle)

Every frame is rendered in high resolution with corresponding label files containing mathematically exact coordinates.

### YOLO Format (.txt)
Individual text files matching each image frame, formatted as:
`<class_id> <center_x> <center_y> <width> <height>` (normalized 0.0 to 1.0) 

```text``
0 0.356283 0.494649 0.323300 0.094563

COCO Format (labels.json)
A single, centralized relational database containing all images, categories, and absolute pixel bounding boxes
{
    "images": [
        {
            "id": 1,
            "width": 1920,
            "height": 1080,
            "file_name": "img_0001.png"
        }
    ],
    "annotations": [
        {
            "id": 1,
            "image_id": 1,
            "category_id": 0,
            "bbox": [864.0, 324.0, 192.0, 216.0],
            "area": 41472.0,
            "segmentation": [],
            "iscrowd": 0
        }
    ],
    "categories": [
        {
            "id": 0,
            "name": "spray_paint_bottles_4k",
            "supercategory": "object"
        }
    ]
}

💼 Dataset-as-a-Service (DaaS) Offerings

We provide complete, custom synthetic dataset generation tailored specifically to your physical products, warehouse items, or industrial components

How the Service Works:

Send Us Your 3D Assets: Provide your CAD files, photogrammetry meshes, or standard 3D models.
Specify Your Parameters: Define your target resolutions, sample sizes, and desired label formats (YOLO/COCO).
Receive Production-Ready Data: We run your assets through our domain-randomized pipeline and deliver thousands of                                           transparent, pre-annotated frames ready to plug directly into your training loops.

📩 Request a Free Sample Dataset

We will generate a free, 50-frame sample dataset of your specific 3D asset so your engineering team can test and verify the coordinate alignment in your own training pipeline.
Contact Person: Mubeen Fatima
Email: contact.synthgen@gmail.com
