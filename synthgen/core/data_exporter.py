import json
import os
import bpy

class FormatPackager:
    def __init__(self, json_data):
        """
        Initializes the exporter with the format type and output location.
        """
        self.format_type = json_data["annotation_specification"].get("format", "YOLO")
        
        # 1. Grab the relative folder path you mentioned in your JSON
        relative_path = json_data["output_management"].get("export_path", "./output/")
        self.export_path = bpy.path.abspath(relative_path)
        
        # 2. UNCONDITIONALLY create the main folder you mentioned in your JSON (Fixes COCO/Manifest save errors)
        if not os.path.exists(self.export_path):
            os.makedirs(self.export_path)
        
        # 3. Create a 'labels' subdirectory within the export path (Only if using YOLO)
        self.labels_dir = os.path.join(self.export_path, "labels")
        if self.format_type == "YOLO":
            if not os.path.exists(self.labels_dir):
                os.makedirs(self.labels_dir)
                
        # 4. Setup COCO Data Structure (Only if using COCO)
        if self.format_type == "COCO":
            target_names = json_data.get("annotation_specification", {}).get("target_objects", [])
            
            # Standard COCO JSON Schema skeleton
            self.coco_data = {
                "info": {
                    "description": "Synthetic Dataset",
                    "year": 2026
                },
                "images": [],
                "annotations": [],
                "categories": []
            }
            self.coco_anno_id = 1 # Auto-incrementing ID for annotations
            
            # Automatically populate categories list based on your target objects
            for idx, name in enumerate(target_names):
                self.coco_data["categories"].append({
                    "id": idx,
                    "name": name,
                    "supercategory": "object"
                })

    def convert_to_yolo(self, class_id, bbox):
        #Takes: Raw bbox coordinates and image size.
        #Does: Calculates center_x, center_y, width, height (normalized 0-1).
        #Returns: A formatted string for a .txt file.
        """
        Converts (x_min, y_min, x_max, y_max) to YOLO format:
        [class_id] [center_x] [center_y] [width] [height]
        Note: BBox from annotator is already 0.0 to 1.0.
        """
        x_min, y_min, x_max, y_max = bbox

        # Calculate width and height
        width = x_max - x_min
        height = y_max - y_min

        # Calculate center point
        center_x = x_min + (width / 2)
        center_y = 1.0 - (y_min + (height / 2))

        # Format as string: "class x_center y_center width height"
        # Using 6 decimal places for precision
        yolo_string = f"{class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}"
        
        return yolo_string


    def save_label(self, label_data, filename):
        #Takes: The formatted string and the filename.
        #Does: Writes the string to a text file on the disk.
        #Returns: None.
        """
        Writes the formatted string to a .txt file.
        Example: img_0001.png -> img_0001.txt
        """
        # Change image extension to .txt
        base_name = os.path.splitext(filename)[0]
        label_filename = f"{base_name}.txt"
        full_path = os.path.join(self.labels_dir, label_filename)

        with open(full_path, "w") as f:
            f.write(label_data)

    # ==========================================================================
    # COCO CONVERSION & EXPORT
    # ==========================================================================
    def add_coco_frame(self, frame_id, filename, img_width, img_height, bboxes):
        """
        Accumulates frame metadata and converts bboxes into absolute pixel COCO values.
        
        Parameters:
            frame_id (int): Incremental ID of the frame.
            filename (str): Name of the saved image file (e.g. "img_0001.png").
            img_width (int): Pixel width of the image.
            img_height (int): Pixel height of the image.
            bboxes (list): List of tuples: (class_id, normalized_bbox)
        """
        # A. Append image dictionary
        self.coco_data["images"].append({
            "id": frame_id,
            "width": img_width,
            "height": img_height,
            "file_name": filename
        })
        
        # B. Convert and append annotations
        for class_id, bbox in bboxes:
            x_min_norm, y_min_norm, x_max_norm, y_max_norm = bbox
            
            # Convert normalized floats (0.0 to 1.0) back to absolute pixels
            x_min = x_min_norm * img_width
            x_max = x_max_norm * img_width
            y_min = (1.0 - y_max_norm) * img_height
            y_max = (1.0 - y_min_norm) * img_height
            
            # COCO bounding box format is: [x_min, y_min, width, height]
            width = x_max - x_min
            height = y_max - y_min
            area = width * height
            
            self.coco_data["annotations"].append({
                "id": self.coco_anno_id,
                "image_id": frame_id,
                "category_id": class_id,
                # Round coordinates to 2 decimal places to keep the file clean
                "bbox": [round(x_min, 2), round(y_min, 2), round(width, 2), round(height, 2)],
                "area": round(area, 2),
                "segmentation": [],
                "iscrowd": 0
            })
            self.coco_anno_id += 1

    def save_coco_manifest(self):
        """
        Writes the accumulated COCO data structure to a single labels.json file.
        """
        coco_path = os.path.join(self.export_path, "labels.json")
        with open(coco_path, "w") as f:
            json.dump(self.coco_data, f, indent=4)
        print(f"COCO dataset annotation successfully saved to: {coco_path}")


    def write_manifest(self, full_log):
        #Takes: A list/dict of all data generated in the session.
        #Does: Creates a manifest.json so the user knows exactly what settings were used for the whole batch.
        #Returns: None.
        """
        Writes a master JSON file containing all session metadata.
        This is used for dataset versioning and debugging.
        """
        manifest_path = os.path.join(self.export_path, "manifest.json")
        
        with open(manifest_path, "w") as f:
            json.dump(full_log, f, indent=4)