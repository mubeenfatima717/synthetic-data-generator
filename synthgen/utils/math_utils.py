import bpy
from bpy_extras.object_utils import world_to_camera_view

def get_vertex_projections(obj, scene, camera , depsgraph=None):
    """
    Projects every vertex of the 3D mesh into 2D camera space (0.0 to 1.0).
    
    Returns: 
        List of (x, y) tuples if vertices are in front of camera.
        Empty list if object is entirely behind the camera.
    """
    # Validation: Ensure working with valid objects
    if obj is None or camera is None:
        return []
    
    # Ensure the object has geometry (Mesh, Curve, Surface, or Font)
    if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
        return []
    
    # Ensure the camera is actually a camera
    if camera.type != 'CAMERA':
        return []
    
    # 1. Get the 'Evaluated' version of the object (handles modifiers like Subsurf)
    # If a depsgraph is passed (from the main loop), use it for performance
    if depsgraph is None:
     depsgraph = bpy.context.evaluated_depsgraph_get()# get dependency graph i.e. how objects depend on each other (modifiers, constraints, etc.)
    
    obj_eval = obj.evaluated_get(depsgraph)# get the evaluated version of the object (after modifiers are applied) 
    matrix = obj_eval.matrix_world         #Gets the object's World Matrix

    coords_2d = []
    mesh = None

    #try-finally block to guarantee memory cleanup 
    # even if a crash occurs during the vertex loop.
    mesh = None
    try:
        mesh = obj_eval.to_mesh()
        
        # 3. Projection Loop
        for vert in mesh.vertices:
            # Convert local vertex to world space
            world_coord = matrix @ vert.co
            
            # Project to 2D space (returns x, y, z where z is depth)
            # (0,0) is bottom-left, (1,1) is top-right
            coords = world_to_camera_view(scene, camera, world_coord)
            
            # Only keep points that are in front of the camera (z > 0)
            # Also filter points that are strictly outside the 0-1 range (optional)
            if coords.z > 0:
                coords_2d.append((coords.x, coords.y))
                
    except Exception as e:
        print(f"Error projecting object {obj.name}: {e}")
        return []
        
    finally:
        # 4. Critical Cleanup: Free the temporary mesh from RAM
        if mesh is not None:
            obj_eval.to_mesh_clear()
    
    return coords_2d

def calculate_bounds(points):
    """
    Finds the extreme boundaries (Min/Max) of a set of 2D points.
    
    Returns: 
        Tuple (x_min, y_min, x_max, y_max)
        None if no points exist.
    """
    if not points:
        return None

    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]

    return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))

def clamp_to_unit_square(bbox):
    """
    Ensures the bounding box does not exceed the image boundaries (0.0 to 1.0).
    
    Returns:
        Cleaned Tuple (x_min, y_min, x_max, y_max)
    """
    if not bbox:
        return None

    x_min, y_min, x_max, y_max = bbox

    # Clamp values to [0.0, 1.0] range
    c_x_min = max(0.0, min(1.0, x_min))
    c_y_min = max(0.0, min(1.0, y_min))
    c_x_max = max(0.0, min(1.0, x_max))
    c_y_max = max(0.0, min(1.0, y_max))

    # Safety Check: If the box was clamped so much it has no area, it's off-screen
    if c_x_min >= c_x_max or c_y_min >= c_y_max:
        return None

    return (c_x_min, c_y_min, c_x_max, c_y_max)