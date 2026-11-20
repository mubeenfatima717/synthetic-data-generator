import os
import json
import urllib.request
import urllib.parse
import urllib.error
import bpy
import mathutils

# Replace this with your actual Gumroad Product ID or Permalink
# (Found in your Gumroad Product Dashboard -> Share/Settings)
GUMROAD_PRODUCT_ID = "synthgen-blender"

def get_license_file_path():
    """Gets the path to the hidden license key cache file inside Blender's user config folder."""
    pref_dir = bpy.utils.user_resource('CONFIG')
    return os.path.join(pref_dir, "synthgen_pro_license.txt")

def check_dependencies():
    """
    Verify that required modules are present.
    Return True if dependencies are safe, False if something is missing.
    """
    try:
        
        return True
    except ImportError:
        return False

def verify_active_license():
    """
    Checks if a valid license has already been activated and cached on this machine.
    Runs quickly and offline on Blender startup to prevent lag.
    """
    license_file = get_license_file_path()
    if os.path.exists(license_file):
        return True
    return False

def activate_license_online(license_key):
    """
    Sends a web request to Gumroad's API to verify if the key is valid.
    If valid, caches it locally for offline verification on startup.
    Returns: Tuple (Success (bool), Message (str))
    """
    url = "https://api.gumroad.com/v2/licenses/verify"
    
    # Strip any accidental leading/trailing spaces
    license_key = license_key.strip()
    if not license_key:
        return False, "License key cannot be empty."

    #  ==========================================================================
    # DEVELOPER BYPASS (For testing your UI and activation flow locally)
    # ==========================================================================
    if license_key == "DEV-TEST-KEY":
        license_file = get_license_file_path()
        with open(license_file, "w") as f:
            f.write(license_key)
        return True, "Dev Mode Activation Successful! UI Unlocked."
    # =========================================================================

    # Prepare data payload for Gumroad API
    data = urllib.parse.urlencode({
        "product_id": GUMROAD_PRODUCT_ID,
        "license_key": license_key,
        "increment_uses_count": "true"  # Increments active seat count on Gumroad
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        # Timeout after 8 seconds so we don't freeze Blender if the user's internet is slow
        with urllib.request.urlopen(req, timeout=8) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            
            # Check if the API call succeeded
            if res_data.get("success", False):
                purchase_info = res_data.get("purchase", {})
                
                # Check that the purchase is active (not refunded or disputed)
                if not purchase_info.get("refunded", False) and not purchase_info.get("disputed", False):
                    
                    # --- SEAT LIMIT MATHS ---
                    uses_count = res_data.get("uses", 1)
                    variant_name = purchase_info.get("variants", "")

                    # Define seat limits based on variant chosen during checkout
                    if "Team License" in variant_name:
                        max_seats = 5
                    else:
                        max_seats = 1  # Default fallback for Single User

                    # If the number of uses exceeds their allowed seats, block activation
                    if uses_count > max_seats:
                        return False, f"Activation Failed: Max seat limit reached ({uses_count}/{max_seats})."
                    # -------------------------

                    # Save (cache) the valid key locally on the user's computer
                    license_file = get_license_file_path()
                    with open(license_file, "w") as f:
                        f.write(license_key)
                    return True, "Activation Successful!"
                else:
                    return False, "Activation Failed: This purchase was refunded or disputed."
            else:
                return False, "Activation Failed: Invalid license key."
                
    except urllib.error.URLError as e:
        return False, f"Connection Error: Could not reach verification server. ({e.reason})"
    except Exception as e:
        return False, f"Unexpected Error: {str(e)}"

def deactivate_license():
    """Deletes the local license cache file from the user's computer."""
    license_file = get_license_file_path()
    if os.path.exists(license_file):
        try:
            os.remove(license_file)
            return True, "License successfully deactivated."
        except Exception as e:
            return False, f"Deactivation Error: {str(e)}"
    return False, "No active license found to deactivate."