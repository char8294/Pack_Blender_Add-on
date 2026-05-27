# CLEAN CUSTOM PROPERTIES SCRIPT
# Removes all metadata/custom properties from selected objects
# Useful for cleaning up imported models (e.g. from 3ds Max/Maya)

import bpy

def clear_custom_props():
    print("Cleaning Custom Properties...")
    count_obj = 0
    count_data = 0
    
    for obj in bpy.context.selected_objects:
        # 1. Clear Object-level properties
        keys = [k for k in obj.keys() if k != '_RNA_UI']
        for key in keys:
            del obj[key]
            count_obj += 1
            
        # 2. Clear Mesh-level properties
        if obj.data and hasattr(obj.data, "keys"):
            keys = [k for k in obj.data.keys() if k != '_RNA_UI']
            for key in keys:
                del obj.data[key]
                count_data += 1
                
    print(f"Finished! Removed {count_obj} object props and {count_data} data props.")

if __name__ == "__main__":
    clear_custom_props()
