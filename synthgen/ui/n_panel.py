import bpy
import json
import os
from .. import core
from ..utils import license_check

# ==============================================================================
# 1. DATA STORAGE
# ==============================================================================
class SynthGenSettings(bpy.types.PropertyGroup):
    json_path: bpy.props.StringProperty(name="JSON Config", subtype='FILE_PATH')
    target_camera: bpy.props.PointerProperty(name="Camera", type=bpy.types.Object, poll=lambda self, obj: obj.type == 'CAMERA')
    
    current_frame: bpy.props.IntProperty(name="Current Frame", default=0)
    total_frames: bpy.props.IntProperty(name="Total Frames", default=0)
    is_running: bpy.props.BoolProperty(name="Is Running", default=False)
    stop_requested: bpy.props.BoolProperty(name="Stop Requested", default=False)

# ==============================================================================
# 2. MODAL RUN OPERATOR
# ==============================================================================
class SYNTHGEN_OT_RunGenerator(bpy.types.Operator):
    bl_idname = "synthgen.run_generator"
    bl_label = "Generate Dataset"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    rand = None
    rend = None
    anno = None
    expt = None
    config = None
    target_objects = []
    session_log = {}

    def modal(self, context, event):
        props = context.scene.synthgen_props

        # Handle Forceful Stop Requests (ESC key or Stop UI Button)
        if event.type in {'ESC'} or props.stop_requested:
            self.cancel(context)
            self.report({'INFO'}, "Generation Forcefully Stopped.")
            return {'CANCELLED'}

        # Timer-based loop (Processes exactly one frame per timer tick)
        if event.type == 'TIMER':
            if props.current_frame < props.total_frames:
                i = props.current_frame
                filename = f"img_{str(i + 1).zfill(4)}.png"
                
                # 1. Randomize scene lights, locations, and materials
                self.rand.apply_lighting_randomization()
                for obj in self.target_objects:
                    self.rand.apply_random_transform(obj)
                    self.rand.shuffle_materials(obj)
                
                # 2. Randomize camera position
                if props.target_camera:
                    self.rand.randomize_camera(props.target_camera)
                
                # 3. Force Blender to evaluate the new positions
                context.view_layer.update()
                
                # 4. Render the current frame (uses a 1-based index)
                image_path = self.rend.render_frame(i + 1)
                
                # 5. Extract bounding boxes and log metadata
                frame_bboxes = []
                frame_log_entry = {
                    "frame_id": i + 1,
                    "filename": filename,
                    "annotations": []
                }
                
                for class_id, obj in enumerate(self.target_objects):
                    bbox = self.anno.get_2d_bbox(obj)
                    if bbox:
                        frame_bboxes.append((class_id, bbox))
                        frame_log_entry["annotations"].append({
                            "class_name": obj.name,
                            "class_id": class_id,
                            "bbox_normalized": [round(c, 4) for c in bbox]
                        })
                
                # 6. Export annotations to the selected format
                if self.expt.format_type == "YOLO":
                    yolo_lines = []
                    for class_id, bbox in frame_bboxes:
                        yolo_line = self.expt.convert_to_yolo(class_id, bbox)
                        yolo_lines.append(yolo_line)
                    
                    if yolo_lines:
                        self.expt.save_label("\n".join(yolo_lines), os.path.basename(image_path))
                        
                elif self.expt.format_type == "COCO":
                    res_x, res_y = self.config.get("render_configuration", {}).get("resolution", [1920, 1080])
                    self.expt.add_coco_frame(
                        frame_id=i + 1,
                        filename=os.path.basename(image_path),
                        img_width=res_x,
                        img_height=res_y,
                        bboxes=frame_bboxes
                    )
                
                self.session_log["frames"].append(frame_log_entry)
                props.current_frame += 1
                return {'RUNNING_MODAL'}
            else:
                self.cancel(context)
                self.report({'INFO'}, "Generation Complete.")
                return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        props = context.scene.synthgen_props
        
        if not props.target_camera:
            self.report({'ERROR'}, "Please select a Camera in the panel first.")
            return {'CANCELLED'}
            
        if not props.json_path or not os.path.exists(bpy.path.abspath(props.json_path)):
            self.report({'ERROR'}, "Please specify a valid JSON configuration file.")
            return {'CANCELLED'}
        
        try:
            abs_json_path = bpy.path.abspath(props.json_path)
            with open(abs_json_path, 'r') as f:
                self.config = json.load(f)
            
            self.rand = core.RandomizerEngine(self.config)
            self.rend = core.RenderController(self.config)
            self.anno = core.BoundingBoxGenerator(props.target_camera.name, context.scene.name)
            self.expt = core.FormatPackager(self.config)
            self.target_objects = self.rand.target_objects
            
            self.rend.setup_engine()
            
            props.total_frames = self.config.get("randomization_parameters", {}).get("total_images", 10)
            props.current_frame = 0
            props.is_running = True
            props.stop_requested = False

            res_x, res_y = self.config.get("render_configuration", {}).get("resolution", [1920, 1080])
            self.session_log = {
                "dataset_format": self.expt.format_type,
                "total_images_generated": props.total_frames,
                "resolution": [res_x, res_y],
                "frames": []
            }

            self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        except Exception as e:
            self.report({'ERROR'}, f"Initialization Failed: {str(e)}")
            return {'CANCELLED'}

    def cancel(self, context):
        props = context.scene.synthgen_props
        props.is_running = False
        
        if self.expt and self.expt.format_type == "COCO":
            try:
                self.expt.save_coco_manifest()
            except Exception as e:
                print(f"Error saving COCO data on cancel: {e}")
        
        if self.expt and hasattr(self, "session_log") and self.session_log:
            try:
                if self.config.get("output_management", {}).get("save_log", True):
                    self.expt.write_manifest(self.session_log)
                    print("Master manifest.json metadata saved successfully.")
            except Exception as e:
                print(f"Error saving manifest.json: {e}")
                
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)

# ==============================================================================
# 3. STOP OPERATOR
# ==============================================================================
class SYNTHGEN_OT_StopGenerator(bpy.types.Operator):
    bl_idname = "synthgen.stop_generator"
    bl_label = "STOP"
    
    def execute(self, context):
        context.scene.synthgen_props.stop_requested = True
        return {'FINISHED'}

# ==============================================================================
# 4. MAIN N-PANEL UI
# ==============================================================================
class SYNTHGEN_PT_MainPanel(bpy.types.Panel):
    bl_label = "SynthGen"
    bl_idname = "SYNTHGEN_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SynthGen"

    def draw(self, context):
        layout = self.layout
        props = context.scene.synthgen_props
        
        # 1. LICENSE ENFORCEMENT CHECK
        from ..utils import license_check
        if not license_check.verify_active_license():
            box = layout.box()
            box.alert = True
            box.label(text="License Inactive", icon='ERROR')
            box.label(text="Please activate your license in Addon Preferences.")
            box.label(text="Go to: Edit > Preferences > Add-ons")
            return

        # 2. MAIN FUNCTIONAL UI
        if not props.is_running:
            col = layout.column(align=True)
            col.label(text="Setup Config:", icon='SETTINGS')
            col.prop(props, "json_path", text="")
            col.prop(props, "target_camera")
            layout.separator()
            
            col = layout.column(align=True)
            col.label(text="Calibration Tools:", icon='VIEWZOOM')
            row = col.row(align=True)
            # Use 'HIDE_OFF' to prevent Blender 5.0 icon crashes
            row.operator("synthgen.draw_visual_box", text="Show BBox Overlay", icon='HIDE_OFF')
            layout.separator()
            
            col = layout.column()
            col.scale_y = 1.5
            col.operator("synthgen.run_generator", text="GENERATE DATASET", icon='PLAY')
        else:
            box = layout.box()
            box.label(text=f"Progress: {props.current_frame} / {props.total_frames}")
            progress = props.current_frame / props.total_frames
            box.progress(text="Rendering...", factor=progress)
            box.operator("synthgen.stop_generator", icon='CANCEL', text="STOP")

# ==============================================================================
# 5. ADDON PREFERENCES & ACTIVATION OPERATORS
# ==============================================================================
class SYNTHGEN_OT_ActivateLicense(bpy.types.Operator):
    """Send key to online verification server and activate local license"""
    bl_idname = "synthgen.activate_license"
    bl_label = "Activate License"
    
    def execute(self, context):
        addon_name = __package__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        
        
        success, msg = license_check.activate_license_online(prefs.license_key)
        
        if success:
            self.report({'INFO'}, msg)
        else:
            self.report({'ERROR'}, msg)
        return {'FINISHED'}


class SYNTHGEN_OT_DeactivateLicense(bpy.types.Operator):
    """Remove local license key cache"""
    bl_idname = "synthgen.deactivate_license"
    bl_label = "Deactivate License"
    
    def execute(self, context):
        from ..utils import license_check
        success, msg = license_check.deactivate_license()
        
        if success:
            self.report({'INFO'}, msg)
        else:
            self.report({'ERROR'}, msg)
        return {'FINISHED'}


class SynthGenAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__.split('.')[0]

    license_key: bpy.props.StringProperty(
        name="License Key",
        description="Paste your Gumroad or Blender Market purchase license key here",
        default=""
    )

    def draw(self, context):
        layout = self.layout
        from ..utils import license_check
        is_active = license_check.verify_active_license()

        box = layout.box()
        if is_active:
            box.label(text="License State: ACTIVE (Activated)", icon='CHECKBOX_HLT')
            box.operator("synthgen.deactivate_license", text="Deactivate License", icon='REMOVE')
        else:
            box.label(text="License State: INACTIVE (Unlicensed)", icon='CHECKBOX_DEHLT')
            box.prop(self, "license_key")
            box.operator("synthgen.activate_license", text="Activate License", icon='FILE_TICK')