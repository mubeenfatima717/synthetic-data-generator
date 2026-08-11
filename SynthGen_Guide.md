# SynthGen Pro

**User Guide & Configuration**

*Synthetic dataset generation, camera & lighting randomization, and YOLO / COCO annotation export for Blender.*

---

## Overview

SynthGen Pro is a synthetic dataset generator for Blender that automatically randomizes scene elements, renders images, and exports 2D bounding box annotations (YOLO/COCO formats) for training computer vision models.

---

## 🚀 Quick Start (3 Steps)

1. **Activate the Add-on:** Install the `.zip` file in Blender (Edit > Preferences > Add-ons). Enter your license key and click Activate.
2. **Load your JSON:** Open the SynthGen panel in your 3D Viewport Sidebar (N-Key). Select your target Camera and load your configuration JSON file.
3. **Generate:** Click Generate Dataset. The viewport will update, render, and save your dataset to your export folder automatically.

---

## 📁 Using the Blender Template File (.blend)

Before modifying your JSON settings, open the provided template `.blend` file included in your purchase:

- **Keep the defaults:** The template contains the pre-configured camera, compositor nodes, and world lighting trees required by the code.
- **Add your objects:** Import or link your custom 3D model into this file.
- **Check your naming:**
  - Your target object must match the name in your JSON configuration (e.g., `"Lantern"`).
  - Any scene lights you want randomized must start with the prefix `"Target"` (e.g., `"TargetLight"`, `"TargetSun"`).

---

## ⚙️ JSON Configuration Structure

Your generation pipeline is controlled by your JSON configuration file. Below is the structure of the settings:

```json
{
  "render_configuration": {
    "engine": "CYCLES",          // Render engine: "CYCLES" (best quality) or "BLENDER_EEVEE" (fastest)
    "device": "GPU",             // Set to "GPU" to use your graphics card, or "CPU"
    "resolution": [680, 680],    // The X and Y pixel dimensions of your output images
    "samples": 128,              // Lower samples = faster renders; Higher samples = cleaner images
    "denoising": false           // Set to true to enable Blender's denoiser
  }
}
```

---

## 📏 How to Set Up Your Camera & Location Ranges (The Exact Math)

To prevent your objects from sliding out of the camera's view or rendering completely clipped off, use this step-by-step math guide to configure your JSON ranges.

### Step 1: Get Your Object Size (S)

- Select your target object in Blender.
- Press the N key to open the sidebar and click the Item tab.
- Read the largest of the three values in the Dimensions panel (e.g., 2.0 meters for a large cube, or 0.3 meters for a lantern). This is your Object Width (S).

### Step 2: Calculate the Minimum Camera Radius (R min)

To keep the object inside your frame, the minimum camera radius must be larger than twice the maximum movement offset plus the width of the object:

> **Min Camera Radius (R) > (2 × Max Object Move Offset) + Object Width**

#### Where to find these in your JSON:

- **Max Object Move Offset (X):** The maximum absolute value inside your `"location_range"` (X or Y axis).
- **Object Width (S):** The dimension of your object measured in Step 1.

#### Example Calculation:

If your object is a 2.0-meter cube (S = 2.0) and your `"location_range"` allows it to move up to 0.5 meters to the side (X = 0.5):

```
Min Camera Radius > (2 × 0.5) + 2.0 = 1.0 + 2.0 = 3.0 meters
```

**Setup:** In your JSON, set the first value of `"camera_radius_range"` to at least 3.1 (e.g., `[3.1, 4.5]`).

#### How to force "Slightly Out of Frame" (Clipped) Images:

If you are training AI and want the object to partially slide off the screen edges, reverse the formula:

- Set your `"location_range"` higher than the safety math (e.g., `[-1.0, 1.0]` shift with a camera radius of 3.0).

### Step 3: Calculate the Camera Height Range (H)

The camera height range controls the downward tilt angle of your camera. To capture optimal side and top perspectives, we aim for viewing angles between 14° (low angle) and 45° (high angle).

Apply these pre-calculated multipliers to your Minimum Camera Radius (R min) calculated in Step 2:

> **Min Height = 0.25 × R min          Max Height = 1.0 × R min**

#### Example Calculation (Using the 3.0 m Radius from Step 2):

- Min Height: 0.25 × 3.0 = 0.75 meters
- Max Height: 1.0 × 3.0 = 3.0 meters

**Setup:** In your JSON, write: `"camera_height_range": [0.75, 3.0]`.

---

## 🌐 Complete Reference Guide to All Ranges

### 1. Object Location (`location_range`)

Controls the bounding box boundary in meters within which the object randomly teleports from the scene origin (0, 0, 0).

- **X & Y:** Horizontal shift (left, right, forward, back). Keep these balanced (e.g., `[-0.2, 0.2]`).
- **Z:** Vertical height. If your object must sit flat on the ground, keep Z at `[0.0, 0.0]`. Use small ranges (e.g., `[0.0, 0.2]`) to let the object hover or sit on varying floor levels.

### 2. Object Rotation (`rotation_range`)

Controls the spin applied to your target object in degrees. Set this based on your object type:

**Type A: Free-Floating (Phones, Handheld Lanterns, Drones)**

Let it rotate completely on all axes:

```json
"x": [-180.0, 180.0], "y": [-180.0, 180.0], "z": [-180.0, 180.0]
```

**Type B: Ground-Bound (Cars, Chairs, Pedestrians)**

Must stay flat on the ground. Lock X and Y to prevent clipping, and only randomize the Z-axis (Yaw):

```json
"x": [0.0, 0.0], "y": [0.0, 0.0], "z": [-180.0, 180.0]
```

**Type C: Ground Wobble (Boxes or Bottles on uneven ground)**

Allow slight tilts on X and Y, with full rotation on Z:

```json
"x": [-5.0, 5.0], "y": [-5.0, 5.0], "z": [-180.0, 180.0]
```

### 3. Lighting Power (`light_intensity_range`)

Controls the random brightness (in Watts/Suns) applied to active scene lights starting with the name "Target".

- **Usage:** `[300.0, 1500.0]`.
- **Adjustment:** If your rendered frames appear completely white or washed out, lower these numbers. If they are too dark, raise them.

### 4. Material Shuffling (`material_shuffling`)

Controls texture swapping and random color overlays.

- `texture_assets_path`: Absolute path to a folder on your computer filled with `.png` or `.jpg` textures to randomly wrap around your object.
- `hue_range`: `[0.0, 1.0]`. Dictates the color spectrum overlay. `[0.0, 1.0]` covers the full rainbow.
- `saturation_range`: `[0.2, 0.9]`. Controls color depth. 0.0 is completely grayscale, while 1.0 is highly saturated.
- `value_range`: `[0.3, 1.0]`. Controls brightness of the randomized color. 0.0 is pure black, while 1.0 is fully illuminated.

### 🌌 5. HDRI Environment Pool (`hdri_pool`)

Controls the sky environment maps used to light your scene.

- **What to do:** List the absolute file paths pointing to high-dynamic-range image files (`.exr` or `.hdr`) on your local hard drive.
- **Action:** Every frame, the engine randomly picks one file from this list, loads it as your Blender world environment, and scales the ambient background lighting.
- **Format requirement:** You must use double backslashes `\\` or single forward slashes `/` inside the JSON paths on Windows systems:

```json
"hdri_pool": [
  "C:\\path\\to\\textures\\grasslands_sunset_4k.exr",
  "C:/path/to/textures/wooden_studio_15_4k.exr"
]
```

---

## 📂 Outputs & Annotations

```json
"annotation_specification": {
  "format": "YOLO",                  // Output format: "YOLO" (.txt per image) or "COCO" (labels.json)
  "occlusion_threshold": 0.25,       // If more than 75% of the object is hidden, skip labeling it
  "target_objects": ["Lantern"],     // Must match the exact Blender Outliner name of your object
  "generate_binary_masks": true      // Creates black-and-white silhouette mask files for segmentation
}
```

- **YOLO output:** Saves one `.txt` coordinate file alongside every rendered image inside the `/labels` directory.
- **COCO output:** Automatically compiles all annotations into a single, structured `labels.json` manifest at the end of the run.

---

If you want custom dataset or custom pipeline contact me: https://www.linkedin.com/in/mubeen-fatima-66a276373/
