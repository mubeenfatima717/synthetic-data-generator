import bpy
from . import n_panel
from . import preview_tool

# List all classes in clean registration order
classes = (
    n_panel.SynthGenSettings,
    n_panel.SYNTHGEN_OT_RunGenerator,
    n_panel.SYNTHGEN_OT_StopGenerator,
    n_panel.SYNTHGEN_PT_MainPanel,
    preview_tool.SYNTHGEN_OT_DrawVisualBox,
    n_panel.SYNTHGEN_OT_ActivateLicense,
    n_panel.SYNTHGEN_OT_DeactivateLicense,
    n_panel.SynthGenAddonPreferences
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register the properties to the Scene
    bpy.types.Scene.synthgen_props = bpy.props.PointerProperty(type=n_panel.SynthGenSettings)

def unregister():
    # Unregister in reverse order
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.synthgen_props