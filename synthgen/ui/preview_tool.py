import bpy
import gpu
import json
import os
from gpu_extras.batch import batch_for_shader
from .. import core

# Global handles to keep preview data safe from garbage collection
_draw_handle = None
_preview_targets = []
_preview_camera = None
_preview_anno = None

def get_2d_uniform_shader():
    """Returns the correct shader name based on Blender Version"""
    if bpy.app.version >= (4, 0, 0):
        return gpu.shader.from_builtin('UNIFORM_COLOR')
    else:
        return gpu.shader.from_builtin('2D_UNIFORM_COLOR')
    
class SYNTHGEN_OT_DrawVisualBox(bpy.types.Operator):
    """Draw a 2D Bounding Box overlay in the 3D Viewport"""
    bl_idname = "synthgen.draw_visual_box"
    bl_label = "Toggle BBox Overlay"
    
    def execute(self, context):
        global _draw_handle, _preview_targets, _preview_camera, _preview_anno
        
        # TOGGLE OFF: If already drawing, stop it immediately and clean up
        if _draw_handle is not None:
            self.stop_drawing(context)
            self.report({'INFO'}, "BBox Overlay Stopped.")
            return {'FINISHED'}
            
        # TOGGLE ON: Validate inputs and start drawing
        props = context.scene.synthgen_props
        if not props.target_camera:
            self.report({'ERROR'}, "Select a camera first.")
            return {'CANCELLED'}

        if not props.json_path or not os.path.exists(bpy.path.abspath(props.json_path)):
            self.report({'ERROR'}, "Select a valid JSON config file first.")
            return {'CANCELLED'}

        # Initialize and cache globally to prevent garbage collection
        _preview_anno = core.BoundingBoxGenerator(props.target_camera.name, context.scene.name)
        _preview_camera = props.target_camera
        
        # Load targets from JSON
        try:
            abs_json_path = bpy.path.abspath(props.json_path)
            with open(abs_json_path, 'r') as f:
                config = json.load(f)
            _preview_targets = config.get("annotation_specification", {}).get("target_objects", [])
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load preview targets: {e}")
            return {'CANCELLED'}
        
        # Add the viewport drawing callback (no frozen arguments passed)
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback, (), 'WINDOW', 'POST_PIXEL')
        
        # Force redraw the 3D viewport so the blue box appears instantly
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
                
        self.report({'INFO'}, "BBox Overlay Started.")
        return {'FINISHED'}

    def stop_drawing(self, context):
        global _draw_handle, _preview_targets, _preview_camera, _preview_anno
        if _draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
            _draw_handle = None
            _preview_targets = []
            _preview_camera = None
            _preview_anno = None
            
            # Force redraw viewport to clear the box instantly
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

def draw_callback():
    """The function that handles the actual GPU drawing of the rectangle"""
    global _preview_targets, _preview_camera, _preview_anno
    
    if not _preview_targets or not _preview_camera or not _preview_anno:
        return
        
    context = bpy.context
    
    # Ensure active context is the main 3D Viewport window
    if not context.space_data or context.space_data.type != 'VIEW_3D':
        return
        
    region = context.region
    rv3d = context.space_data.region_3d
    if not rv3d:
        return
        
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from mathutils import Vector

    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(3.0)

    # 1. Fetch the evaluated dependency graph for this frame
    depsgraph = context.evaluated_depsgraph_get()

    for obj_name in _preview_targets:
        obj = bpy.data.objects.get(obj_name)
        if not obj: continue
        
        # 2. Get the evaluated version of the object
        obj_eval = obj.evaluated_get(depsgraph)
        matrix = obj_eval.matrix_world
        
        # 3. Project the actual evaluated mesh vertices instead of the 8 bounding box corners
        coords_2d = []
        mesh = None
        try:
            mesh = obj_eval.to_mesh()
            for vert in mesh.vertices:
                world_coord = matrix @ vert.co
                pos_2d = location_3d_to_region_2d(region, rv3d, world_coord)
                if pos_2d:
                    coords_2d.append(pos_2d)
        except Exception as e:
            print(f"Preview Error: {e}")
            continue
        finally:
            # Critical Cleanup: Free the temporary mesh from RAM to prevent leaks
            if mesh is not None:
                obj_eval.to_mesh_clear()
                
        if not coords_2d:
            continue
            
        x_coords = [p.x for p in coords_2d]
        y_coords = [p.y for p in coords_2d]
        
        px_min_x, px_max_x = min(x_coords), max(x_coords)
        px_min_y, px_max_y = min(y_coords), max(y_coords)

        # Dimension switching based on Blender Version
        if bpy.app.version >= (4, 0, 0):
            # Blender 4.0/5.0+ UNIFORM_COLOR expects 3D coordinates (x, y, 0.0)
            coords = [
                (px_min_x, px_min_y, 0.0), (px_max_x, px_min_y, 0.0),
                (px_max_x, px_min_y, 0.0), (px_max_x, px_max_y, 0.0),
                (px_max_x, px_max_y, 0.0), (px_min_x, px_max_y, 0.0),
                (px_min_x, px_max_y, 0.0), (px_min_x, px_min_y, 0.0)
            ]
        else:
            # Blender 3.6 and older 2D_UNIFORM_COLOR expects 2D coordinates (x, y)
            coords = [
                (px_min_x, px_min_y), (px_max_x, px_min_y),
                (px_max_x, px_min_y), (px_max_x, px_max_y),
                (px_max_x, px_max_y), (px_min_x, px_max_y),
                (px_min_x, px_max_y), (px_min_x, px_min_y)
            ]

        shader = get_2d_uniform_shader()
        batch = batch_for_shader(shader, 'LINES', {"pos": coords})
        
        shader.bind()
        shader.uniform_float("color", (0.0, 0.5, 1.0, 1.0)) # Bright Neon Blue
        batch.draw(shader)

    gpu.state.blend_set('NONE')
        
"""
def draw_callback(self, context):
    #The function that handles the actual GPU drawing of the rectangle
    props = context.scene.synthgen_props
    
    # Iterate through the targets loaded dynamically from your JSON config
    for obj_name in getattr(self, "target_names", []):
        obj = bpy.data.objects.get(obj_name)
        if not obj: continue
        
        bbox = self.anno.get_2d_bbox(obj)
        if not bbox: continue
        
        # Convert 0-1 normalized coords to actual Screen Pixels
        width = context.region.width
        height = context.region.height
        
        x_min, y_min, x_max, y_max = bbox
        px_min_x, px_max_x = x_min * width, x_max * width
        px_min_y, px_max_y = y_min * height, y_max * height

        # Define coordinates for a hollow rectangle
        coords = [
            (px_min_x, px_min_y), (px_max_x, px_min_y),
            (px_max_x, px_min_y), (px_max_x, px_max_y),
            (px_max_x, px_max_y), (px_min_x, px_max_y),
            (px_min_x, px_max_y), (px_min_x, px_min_y)
        ]

        shader = get_2d_uniform_shader()
        batch = batch_for_shader(shader, 'LINES', {"pos": coords})
        
        shader.bind()
        shader.uniform_float("color", (0.0, 1.0, 0.0, 1.0)) # Bright Green
        batch.draw(shader)
        """