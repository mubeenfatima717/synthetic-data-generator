import os
import bpy
import random
import math
from mathutils import Vector
import mathutils

class RandomizerEngine:
    def __init__(self,   json_data = None):
        if json_data is None:
            json_data = {}
        #It iterates through json_data["annotation_specification"]["target_objects"], finds those objects in bpy.data.objects, and stores them in self.target_objects
        """
        Initializes the engine with the configuration.
        The json_data is the full dictionary loaded from your schema.json.
        """
        # Extract only the randomization section
        self.config_data = json_data.get("randomization_parameters", {})
        
        # Extract target object names from the annotation section to get Blender references
        target_names = json_data.get("annotation_specification", {}).get("target_objects", [])
        self.texture_deck = []
        # Convert names to actual Blender Object references
        self.target_objects = []
        for name in target_names:
            obj = bpy.data.objects.get(name)
            if obj:
                self.target_objects.append(obj)
            else:
                print(f"Warning: Object '{name}' not found in Blender scene.")
        
    def apply_random_transform(self, obj):
        #Takes: A Blender Object.
        #Does: Pulls min/max values from config and sets a new Location/Rotation/Scale for that object.
        #Returns: None
        """
        Pulls min/max values from config and sets a new Location and Rotation.
        """
        if not obj:
            print("Warning: No valid object passed to apply_random_transform. Skipping.")
            return
        loc_cfg = self.config_data.get("location_range", {"x": [0,0], "y": [0,0], "z": [0,0]})
        rot_cfg = self.config_data.get("rotation_range", {"x": [0,0], "y": [0,0], "z": [0,0]})

        # Apply Location
        obj.location.x = random.uniform(loc_cfg["x"][0], loc_cfg["x"][1])
        obj.location.y = random.uniform(loc_cfg["y"][0], loc_cfg["y"][1])
        obj.location.z = random.uniform(loc_cfg["z"][0], loc_cfg["z"][1])

        # Apply Rotation (Converting degrees to radians for Blender)
        obj.rotation_mode = 'XYZ'
        obj.rotation_euler.x = math.radians(random.uniform(rot_cfg["x"][0], rot_cfg["x"][1]))
        obj.rotation_euler.y = math.radians(random.uniform(rot_cfg["y"][0], rot_cfg["y"][1]))
        obj.rotation_euler.z = math.radians(random.uniform(rot_cfg["z"][0], rot_cfg["z"][1]))

    def randomize_camera(self, camera_obj):
        # CAMERA ORBITS THE CENTER
        r_range = self.config_data.get("camera_radius_range", [5, 8])
        h_range = self.config_data.get("camera_height_range", [2, 4])
        
        radius = random.uniform(r_range[0], r_range[1])
        height = random.uniform(h_range[0], h_range[1])
        angle = random.uniform(0, math.pi * 2)

        camera_obj.location.x = radius * math.cos(angle)
        camera_obj.location.y = radius * math.sin(angle)
        camera_obj.location.z = height

        # CRITICAL: Force Blender to recognize the new camera location 
        # before calculating the rotation/look-at vector.
        bpy.context.view_layer.update()

        # Point at the actual object, not just the world origin
        if self.target_objects:
         # Point at the first target object's current world position
         target_pos = self.target_objects[0].matrix_world.to_translation()
        else:
         target_pos = Vector((0.0, 0.0, 0.0))
        direction = target_pos-camera_obj.location
        camera_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        
    def apply_lighting_randomization(self):
        """
        Randomizes world strength and lamp power based on JSON ranges.
        Also picks and loads a random HDRI from the hdri_pool.
        """
        # Pull range from JSON (e.g., [200.0, 1000.0])
        light_range = self.config_data.get("light_intensity_range", [200.0, 1000.0])
        new_intensity = random.uniform(light_range[0], light_range[1])

        # 1. World / HDRI Randomization
        if bpy.context.scene.world and bpy.context.scene.world.use_nodes:
            node_tree = bpy.context.scene.world.node_tree
            nodes = node_tree.nodes
            links = node_tree.links
            
            # --- LOAD RANDOM HDRI FROM POOL ---
            hdri_list = self.config_data.get("hdri_pool", [])
            if hdri_list:
                # Pick a random path from your JSON list
                random_hdri_path = random.choice(hdri_list)
                # Resolve the relative '//' path into an absolute path on your computer
                abs_hdri_path = bpy.path.abspath(random_hdri_path)
                
                # Check to make sure the file exists before attempting to load it
                if os.path.exists(abs_hdri_path):
                    # Load the image into Blender's memory
                    new_img = bpy.data.images.load(abs_hdri_path, check_existing=True)
                    
                    # Find or create the Environment Texture node
                    env_node = next((n for n in nodes if n.type == 'TEX_ENVIRONMENT'), None)
                    if not env_node:
                        env_node = nodes.new(type='ShaderNodeTexEnvironment')
                    
                    # Assign the randomly chosen image to the node
                    env_node.image = new_img
                    
                    # Find the Background node so we can connect them
                    background_node = next((n for n in nodes if n.type == 'BACKGROUND'), None)
                    if background_node:
                        # Link Color output of Environment node to Color input of Background node
                        if not any(link.from_node == env_node for link in links):
                            links.new(env_node.outputs['Color'], background_node.inputs['Color'])
                else:
                    print(f"Warning: HDRI file not found at {abs_hdri_path}. Please check your folder path.")

            # --- ADJUST WORLD STRENGTH ---
            background_node = next((n for n in nodes if n.type == 'BACKGROUND'), None)
            if background_node:
                # Map your JSON values to a 0.1 - 1.5 range for the background
                world_strength = (new_intensity / light_range[1]) * 1.5
                background_node.inputs[1].default_value = world_strength

        # 2. Lamp Randomization (Only objects starting with "Target")
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT' and obj.name.startswith("Target"):
                if obj.data.type == 'SUN':
                    # Suns are massive; we scale the intensity down for them
                    obj.data.energy = new_intensity / 100.0
                else:
                    # Point/Spot/Area lights use the raw JSON intensity
                    obj.data.energy = new_intensity

    def shuffle_materials(self, obj):
       #Takes: A Blender Object.
       #Does: Accesses the object's material nodes and shuffles Hue/Saturation/Value or swaps the texture.
       #Returns: None
        """
        Accesses the object's material nodes and shuffles Hue/Saturation/Value.
        Assumes the material uses a Hue/Saturation node or Principled BSDF.
        """
        if not hasattr(obj.data, "materials") or not obj.data.materials:
            return
            
        mat_cfg = self.config_data.get("material_shuffling", {})
        tex_path = mat_cfg.get("texture_assets_path", "")
        
        # Pre-check for textures in the folder
        valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp')
        texture_files = []
        if tex_path and os.path.exists(tex_path):
            texture_files = [f for f in os.listdir(tex_path) if f.lower().endswith(valid_extensions)]

        # Your original loop logic using enumerate
        for i, mat in enumerate(obj.data.materials):
            if mat is None: continue
        
            # STABILITY FIX: Ensure material is unique to this object
            if mat.users > 1:
                mat = mat.copy()
                obj.data.materials[i] = mat

            if not mat.use_nodes: continue
            
            # Target the Principled BSDF using your preferred type search
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
            
            if bsdf:
                # --- 1. NEW TEXTURE LOGIC (Integrated) ---
                if texture_files:
                    # Find or create the Image Texture node
                    tex_node = next((n for n in nodes if n.type == 'TEX_IMAGE'), None)
                    if not tex_node:
                        tex_node = nodes.new(type='ShaderNodeTexImage')
                    
                    # Ensure texture is linked to the Base Color input
                    if not any(link.to_node == bsdf and link.to_socket == bsdf.inputs[0] for link in links):
                        links.new(tex_node.outputs[0], bsdf.inputs[0])
                    
                    # Pick and load image from your path
                    if not self.texture_deck:
                        self.texture_deck = texture_files.copy()
                        random.shuffle(self.texture_deck)
                    
                    # Draw (pop) the next texture from our shuffled deck
                    random_img_name = self.texture_deck.pop()
                    full_path = os.path.join(tex_path, random_img_name)
                    new_img = bpy.data.images.load(full_path, check_existing=True)
                    tex_node.image = new_img

                # --- 2. ORIGINAL COLOR LOGIC (Untouched) ---
                h = random.uniform(mat_cfg.get("hue_range", [0,1])[0], mat_cfg.get("hue_range", [0,1])[1])
                s = random.uniform(mat_cfg.get("saturation_range", [0,1])[0], mat_cfg.get("saturation_range", [0,1])[1])
                v = random.uniform(mat_cfg.get("value_range", [0,1])[0], mat_cfg.get("value_range", [0,1])[1])
                
                # Use mathutils.Color for sRGB HSV
                color = mathutils.Color()
                color.hsv = (h, s, v) 
                
                # Apply standard Gamma correction (Power of 2.2) for Linear RGB
                linear_rgb = [pow(c, 2.2) for c in color]
                bsdf.inputs[0].default_value = (linear_rgb[0], linear_rgb[1], linear_rgb[2], 1.0)
