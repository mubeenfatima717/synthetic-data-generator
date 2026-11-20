bl_info = {
    "name": "SynthGen Pro",
    "author": "Mubeen Fatima",
    "version": (1, 0),
    "blender": (5, 0, 0),  # Matches your Blender 5.0 environment
    "location": "View3D > Sidebar > SynthGen Tab",
    "description": "Professional Synthetic Data Generator for AI Training",
    "category": "Pipeline",
}

import bpy
from . import ui

def register():
    # Register all UI, Operators, and Preferences unconditionally 
    # so the Addon Preferences window is accessible to enter the key.
    ui.register()
    print("SynthGen Pro Registered Successfully.")

def unregister():
    # Safe unregistration
    try:
        ui.unregister()
        print("SynthGen Pro Unregistered.")
    except Exception as e:
        print(f"SynthGen Unregistration Warning: {e}")

if __name__ == "__main__":
    register()