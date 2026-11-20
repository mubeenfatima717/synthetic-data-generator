import bpy
import os

class RenderController:
    def __init__(self, json_data):
        """
        Initializes the controller with hardware, file paths, and mask configuration.
        """
        # --- PRESERVED FROM YOUR INITIAL CODE ---
        self.settings = json_data.get("render_configuration", {})
        self.annotation_settings = json_data.get("annotation_specification", {})
        
        relative_path = json_data.get("output_management", {}).get("export_path", "//renders/")
        self.output_path = bpy.path.abspath(relative_path)
        
        # Ensure the main export directory exists
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        # ----------------------------------------
        
        # Read parameters for the binary mask generation
        self.generate_masks = self.annotation_settings.get("generate_binary_masks", False)
        self.target_objects = self.annotation_settings.get("target_objects", [])
            
        # If mask generation is enabled, create a subfolder for masks
        if self.generate_masks:
            self.mask_output_path = os.path.join(self.output_path, "masks")
            if not os.path.exists(self.mask_output_path):
                os.makedirs(self.mask_output_path)

    def setup_engine(self):
        """
        Switches Blender engine, sets hardware device, configures resolution,
        and builds the compositor nodes for Cryptomatte masks if enabled.
        """
        scene = bpy.context.scene
        render = scene.render
        
        # --- PRESERVED FROM YOUR INITIAL CODE ---
        # 1. Set the Engine (CYCLES or BLENDER_EEVEE)
        render.engine = self.settings.get("engine", "CYCLES")
        
        # 2. Hardware Configuration (Only for Cycles)
        if render.engine == 'CYCLES':
            scene.cycles.device = self.settings.get("device", "GPU")
            # Refresh devices to ensure GPU is activated
            if scene.cycles.device == 'GPU':
                prefs = bpy.context.preferences.addons['cycles'].preferences
                prefs.get_devices()
                # Set the first available compute device type (CUDA, OPTIX, etc.)
                for type in ('OPTIX', 'CUDA', 'OPENCL'):
                    try:
                        prefs.compute_device_type = type
                        break
                    except:
                        continue
                for device in prefs.devices:
                    device.use = True
                    
        # 3. Set Resolution
        res = self.settings.get("resolution", [1920, 1080])
        render.resolution_x = res[0]
        render.resolution_y = res[1]
        render.resolution_percentage = 100
        
        # 4. Samples and Denoising
        if render.engine == 'CYCLES':
            scene.cycles.samples = self.settings.get("samples", 128)
            scene.cycles.use_denoising = self.settings.get("denoising", True)
        # ----------------------------------------
            
        # 5. Configure the Compositor Tree
        self.setup_compositor()

    def setup_compositor(self):
        """
        Configures the post-processing node network to output Cryptomatte masks.
        Fully compatible with both Blender 5.x (new compositing APIs) and Blender 4.x/3.x.
        """
        scene = bpy.context.scene
        view_layer = bpy.context.view_layer
        
        # Check if the active running Blender is version 5.0 or newer
        is_blender_5 = bpy.app.version >= (5, 0, 0)
        
        # If mask generation is disabled, reset to standard rendering
        if not self.generate_masks:
            scene.render.use_compositing = False
            view_layer.use_pass_cryptomatte_object = False
            return
            
        # Enable rendering compositor
        scene.render.use_compositing = True
        
        # 1. Enable Object Cryptomatte pass on the active View Layer
        view_layer.use_pass_cryptomatte_object = True
        
        # 2. Retrieve or create the compositor node tree (Backwards compatible)
        if is_blender_5:
            # Blender 5.x API
            if not scene.compositing_node_group:
                scene.compositing_node_group = bpy.data.node_groups.new(
                    name="Compositing Nodes", type="CompositorNodeTree"
                )
            tree = scene.compositing_node_group
        else:
            # Blender 4.x and older API
            scene.use_nodes = True
            tree = scene.node_tree
            
        # Clear existing nodes to build a clean post-processing pipeline
        tree.nodes.clear()
        
        # 3. Create Render Layers Node (Raw inputs)
        rl_node = tree.nodes.new('CompositorNodeRLayers')
        rl_node.location = (-300, 200)
        
        # 4. Create Composite Output Node (Backwards compatible)
        if is_blender_5:
            # In Blender 5.0, standard Composite node is NodeGroupOutput
            comp_node = tree.nodes.new('NodeGroupOutput')
            comp_node.location = (400, 200)
            # Safely ensure a Color Output socket exists on the tree interface
            try:
                if len(tree.interface.items_tree) == 0:
                    tree.interface.new_socket(name="Output", in_out='OUTPUT', socket_type='NodeSocketColor')
            except Exception as e:
                print(f"[DEBUG] NodeGroupOutput socket fallback: {e}")
            # Connect Render Layers Image -> Group Output Node
            try:
                tree.links.new(rl_node.outputs['Image'], comp_node.inputs[0])
            except Exception as e:
                print(f"[DEBUG] Failed linking standard color output: {e}")
        else:
            # Legacy Composite Node
            comp_node = tree.nodes.new('CompositorNodeComposite')
            comp_node.location = (400, 200)
            tree.links.new(rl_node.outputs['Image'], comp_node.inputs['Image'])
        
        # 5. Create File Output Node (Saves our mask files)
        file_out = tree.nodes.new('CompositorNodeOutputFile')
        file_out.location = (400, -100)
        
        # Backwards compatible output directory setup
        if hasattr(file_out, "directory"):
            # CRITICAL: Blender requires a trailing slash! We replace backslashes and force a slash.
            formatted_path = self.mask_output_path.replace("\\", "/")
            if not formatted_path.endswith("/"):
                formatted_path += "/"
            
            file_out.directory = formatted_path  # Blender 5.x
            file_out.file_name = ""  # Clear the base name so we only use custom slot names
        else:
            # For older Blender 4.x/3.x, force a trailing slash as well
            formatted_path = self.mask_output_path.replace("\\", "/")
            if not formatted_path.endswith("/"):
                formatted_path += "/"
            file_out.base_path = formatted_path  # Blender 4.x/3.x
        
        # Unlocks PNG format in Blender 5.x by switching from Multilayer EXR to Image mode
        if hasattr(file_out.format, "media_type"):
            file_out.format.media_type = 'IMAGE'
        
        # Configure output format to BW (Grayscale) PNG for ultra-lightweight mask files
        file_out.format.file_format = 'PNG'
        file_out.format.color_mode = 'BW'
        
        # Clear default slots
        if hasattr(file_out, "file_output_items"):
            file_out.file_output_items.clear()  # Blender 5.x
        else:
            file_out.file_slots.clear()  # Blender 4.x/3.x
        
        # 6. Add Cryptomatte Nodes for each target object
        y_offset = 0
        for obj_name in self.target_objects:
            # Create a CryptomatteV2 node
            crypto_node = tree.nodes.new('CompositorNodeCryptomatteV2')
            crypto_node.location = (100, y_offset)
            crypto_node.matte_id = obj_name  # Select this specific object name
            
            # CRITICAL: Append '####' so single-frame renders successfully write sequence files to disk
            slot_name = f"mask_{obj_name}_####"
            
            # Add slot and connect wires (Backwards compatible)
            if hasattr(file_out, "file_output_items"):
                # Blender 5.x API
                # Create a 'FLOAT' socket (grey) to match Cryptomatte's Matte output (resolves conversion error!)
                new_item = file_out.file_output_items.new('FLOAT', slot_name)
                
                # Link 1: Render Layers Image -> Cryptomatte Image
                tree.links.new(rl_node.outputs['Image'], crypto_node.inputs['Image'])
                # Link 2: Cryptomatte Matte -> File Output Input (Looked up safely by unique item name!)
                tree.links.new(crypto_node.outputs['Matte'], file_out.inputs[new_item.name])
            else:
                # Blender 4.x and older API
                file_out.file_slots.new(slot_name)
                
                # Link 1: Render Layers Image -> Cryptomatte Image
                tree.links.new(rl_node.outputs['Image'], crypto_node.inputs['Image'])
                # Link 2: Cryptomatte Matte -> File Output Slot
                tree.links.new(crypto_node.outputs['Matte'], file_out.inputs[slot_name])
            
            y_offset -= 250

    def render_frame(self, frame_index):
        """
        Sets the frame index, output file name, and triggers the render.
        Returns: The absolute file path of the saved color image.
        """
        scene = bpy.context.scene
        
        # --- PRESERVED FROM YOUR INITIAL CODE ---
        # Format the color image file name (e.g., img_0001.png)
        file_name = f"img_{str(frame_index).zfill(4)}.png"
        full_path = os.path.join(self.output_path, file_name)
        # Set Blender's internal output path for the colored frame
        scene.render.filepath = full_path
        # ----------------------------------------
        
        # Sync Blender's timeline to frame_index.
        # This is critical so the File Output node names the masks (e.g., mask_Lantern_0001.png) correctly.
        scene.frame_set(frame_index)
        
        # Force dependency graph evaluation so the compositor updates context correctly
        bpy.context.view_layer.update()
        
        # Execute Render (write_still=True writes both the color render and the compositor files to disk)
        bpy.ops.render.render(write_still=True)
        
        return full_path