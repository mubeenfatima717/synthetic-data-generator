import bpy
from ..utils import math_utils

class BoundingBoxGenerator:
    def __init__(self, camera_name, scene_name):
        """
        Connects the annotator to the specific camera and scene.
        """
        self.scene = bpy.data.scenes.get(scene_name)
        self.camera = bpy.data.objects.get(camera_name)
        
        # Defensive Check: If names are wrong, stop immediately with a clear message
        if not self.camera or not self.scene:
            raise ValueError(f"Annotator Error: Camera '{camera_name}' or Scene '{scene_name}' not found.")

    def get_2d_bbox(self, obj, depsgraph=None):
        """
        Orchestrates the 3-step process of generating a bounding box.
        1. Project Vertices -> 2. Calculate Bounds -> 3. Clamp for AI.
        """
        # Defensive Check: Ensure object exists and is visible
        if obj is None or obj.hide_render:
            return None

        try:
            if depsgraph is None:
                depsgraph = bpy.context.evaluated_depsgraph_get() 
            # Step 1: Get 2D points from Math Utils
            points = math_utils.get_vertex_projections(obj, self.scene, self.camera,depsgraph)
            
            # Step 2: Get raw min/max boundaries
            raw_box = math_utils.calculate_bounds(points)
            
            # Step 3: Clamp to 0.0-1.0 range (YOLO standard)
            final_box = math_utils.clamp_to_unit_square(raw_box)
            
            return final_box

        except Exception as e:
            # If a specific object has bad geometry, log it but don't crash the render
            print(f"Annotator Warning: Skipping {obj.name} due to error: {e}")
            return None

    def check_occlusion(self, obj, depsgraph=None):
        """
        Determines if the object is hidden by other geometry using a Raycast.
        Returns: 1.0 (Visible) or 0.0 (Occluded).
        """
        if not obj:
            return 0.0

        # Get the evaluated dependency graph (needed for Raycasting modifiers)
        if depsgraph is None:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        
        # Origin: Camera position
        origin = self.camera.matrix_world.translation
        
        # Destination: Object center
        destination = obj.matrix_world.translation
        direction = destination - origin

        # Cast ray from camera to object center
        hit, location, normal, index, hit_obj, matrix = self.scene.ray_cast(depsgraph, origin, direction)

        # If the ray hits the object we are looking for, it is visible
        if hit and hit_obj == obj:
            return 1.0
            
        return 0.0