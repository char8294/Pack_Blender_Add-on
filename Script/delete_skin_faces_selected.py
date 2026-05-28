# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh

def delete_faces_and_remove_material(material_prefix):
    deleted_total = 0
    objects_modified = 0
    
    # Process only selected mesh objects
    for obj in bpy.context.selected_objects:
        if obj.type != 'MESH':
            continue
            
        # Find material indices for the target material prefix (case-insensitive)
        mat_indices = [i for i, slot in enumerate(obj.material_slots) 
                       if slot.material and slot.material.name.lower().startswith(material_prefix.lower())]
        
        if not mat_indices:
            continue
            
        print(f"Processing object: {obj.name}")
        objects_modified += 1
        
        # 1. Delete faces using the material
        # Ensure object is active and in edit mode
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Use bmesh for deletion
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        
        faces_to_delete = [f for f in bm.faces if f.material_index in mat_indices]
        count = len(faces_to_delete)
        
        if count > 0:
            bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')
            bmesh.update_edit_mesh(me)
            deleted_total += count
            print(f"- Deleted {count} faces from {obj.name}")
            
        # Return to object mode to modify material slots
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 2. Remove the material slots
        # We iterate backwards to avoid index shifting issues when popping
        for i in reversed(range(len(obj.material_slots))):
            slot = obj.material_slots[i]
            if slot.material and slot.material.name.lower().startswith(material_prefix.lower()):
                mat_name = slot.material.name
                obj.active_material_index = i
                bpy.ops.object.material_slot_remove()
                print(f"- Removed material slot '{mat_name}' from {obj.name}")
        
    print(f"\nSummary:")
    print(f"- Objects processed: {objects_modified}")
    print(f"- Total faces deleted: {deleted_total}")

# Run the function
if __name__ == "__main__":
    delete_faces_and_remove_material("SKIN_body")
