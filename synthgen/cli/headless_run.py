import bpy
import sys
import json
import os

# Adding the current directory to sys.path so we can import our core
# This ensures that 'from .. import core' works even in headless mode
dir_path = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(dir_path)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import core  # Importing our unified gateway

class HeadlessRunner:
    def __init__(self):
        self.config_path = self.parse_arguments()
        self.config = self.load_config()

    def parse_arguments(self):
        """
        Parses command line arguments. 
        Blender uses '--' to separate Blender args from Python args.
        Example: blender -b -P headless_run.py -- --config my_cfg.json
        """
        if "--config" in sys.argv:
            index = sys.argv.index("--config") + 1
            if index < len(sys.argv):
                return sys.argv[index]
        
        print("ERROR: No configuration file provided. Use --config <path>")
        sys.exit(1)

    def load_config(self):
        """Loads and validates the JSON configuration."""
        if not os.path.exists(self.config_path):
            print(f"ERROR: Config file not found at {self.config_path}")
            sys.exit(1)
        
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def execute(self):
        """
        The main production loop. No Timers, No UI, 100% CPU/GPU utilization.
        Now aligned with the updated randomizer, annotator, renderer, and exporters.
        """
        # SECURITY CHECK: Import and enforce your license check in headless mode
        try:
            from utils import license_check
            if not license_check.verify_active_license():
                print("CRITICAL ERROR: Invalid or missing license. Headless execution blocked.")
                sys.exit(1)
        except ImportError:
            print("CRITICAL ERROR: Licensing utility module 'utils.license_check' not found.")
            sys.exit(1)

        print("--- SynthGen Pro: Starting Headless Production ---")
        
        try:
            # 1. Setup Core Engine
            cam_name = "Camera"  # Look for the default active scene camera
            scene_name = bpy.context.scene.name
            
            rand = core.RandomizerEngine(self.config)
            rend = core.RenderController(self.config)
            anno = core.BoundingBoxGenerator(cam_name, scene_name)
            expt = core.FormatPackager(self.config)
            
            rend.setup_engine()
            
            total_images = self.config["randomization_parameters"].get("total_images", 10)
            target_objects = rand.target_objects
            
            # STABILITY FIX: Use safe dict get methods with fallbacks
            res_x, res_y = self.config.get("render_configuration", {}).get("resolution", [1920, 1080])
            
            # Setup metadata logging
            session_log = {
                "dataset_format": expt.format_type,
                "total_images_generated": total_images,
                "resolution": [res_x, res_y],
                "frames": []
            }
            
            # 2. Production Loop
            for i in range(total_images):
                frame_id = i + 1
                filename = f"img_{str(frame_id).zfill(4)}.png"
                
                # A. Randomize Environment & Lights
                rand.apply_lighting_randomization()
                
                # B. Randomize Object Transforms & Materials
                for obj in target_objects:
                    rand.apply_random_transform(obj)
                    rand.shuffle_materials(obj)
                
                # C. Randomize Camera Position
                cam = bpy.data.objects.get(cam_name)
                if cam:
                    rand.randomize_camera(cam)
                
                # D. Update View Layer (Crucial for correct bounding boxes)
                bpy.context.view_layer.update()
                
                # E. Calculate Bounding Boxes
                frame_bboxes = []
                frame_log_entry = {
                    "frame_id": frame_id,
                    "filename": filename,
                    "annotations": []
                }
                
                # Use enumerate to correctly map class_id (0, 1, etc.) to each object
                for class_id, obj in enumerate(target_objects):
                    bbox = anno.get_2d_bbox(obj)
                    if bbox:
                        frame_bboxes.append((class_id, bbox))
                        frame_log_entry["annotations"].append({
                            "class_name": obj.name,
                            "class_id": class_id,
                            "bbox_normalized": bbox
                        })
                
                # F. Render Frame
                image_path = rend.render_frame(frame_id)
                image_filename = os.path.basename(image_path)
                
                # G. Export Annotations based on chosen format
                if expt.format_type == "YOLO":
                    yolo_lines = []
                    for class_id, bbox in frame_bboxes:
                        yolo_str = expt.convert_to_yolo(class_id, bbox)
                        yolo_lines.append(yolo_str)
                    
                    if yolo_lines:
                        expt.save_label("\n".join(yolo_lines), image_filename)
                        
                elif expt.format_type == "COCO":
                    expt.add_coco_frame(
                        frame_id=frame_id,
                        filename=image_filename,
                        img_width=res_x,
                        img_height=res_y,
                        bboxes=frame_bboxes
                    )
                
                session_log["frames"].append(frame_log_entry)
                
                # Progress Reporting for Terminal
                percent = (frame_id / total_images) * 100
                print(f"[PROGRESS] {frame_id}/{total_images} rendered ({percent:.1f}%)")

            # 3. Post-Production Finalization
            if expt.format_type == "COCO":
                expt.save_coco_manifest()
                
            # Write master session log
            if self.config["output_management"].get("save_log", True):
                expt.write_manifest(session_log)

            print("--- Production Complete: All Data Saved ---")

        except Exception as e:
            print(f"CRITICAL ERROR during execution: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    runner = HeadlessRunner()
    runner.execute()