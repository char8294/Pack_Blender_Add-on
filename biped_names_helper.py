bl_info = {
    "name": "Biped Names Helper",
    "author": "Gemini CLI",
    "version": (1, 2),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Biped Names",
    "description": "Temporarily renames Biped bones/VGs to .L/.R for symmetry and mirroring weights",
    "category": "Animation",
}

import bpy
import json

def get_all_fcurves(action):
    """Get all F-Curves from an action, supporting both Legacy and Layered (5.1+) API."""
    fcurves = []
    # Layered Action (Blender 5.1+)
    if hasattr(action, 'is_action_layered') and action.is_action_layered:
        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, 'channelbags'):
                    for cb in strip.channelbags:
                        fcurves.extend(cb.fcurves)
    # Legacy Action (Blender 4.x and earlier)
    elif hasattr(action, 'fcurves'):
        fcurves.extend(action.fcurves)
    return fcurves

def rename_action_paths(mapping):
    """
    Rename bone data_paths and F-Curve group names in ALL actions in the blend file.
    mapping: dict of {new_name: old_name}
    Called AFTER bones are renamed, converts old_name -> new_name in paths and groups.
    """
    if not mapping:
        return
    path_pairs = []
    name_pairs = {}  # old_name -> new_name for group renaming
    for new_name, old_name in mapping.items():
        path_pairs.append(('pose.bones["' + old_name + '"]', 'pose.bones["' + new_name + '"]'))
        name_pairs[old_name] = new_name

    for action in bpy.data.actions:
        for fc in get_all_fcurves(action):
            # Rename data_path
            for old_path, new_path in path_pairs:
                if old_path in fc.data_path:
                    fc.data_path = fc.data_path.replace(old_path, new_path)
            # Rename F-Curve group name
            if fc.group and fc.group.name in name_pairs:
                fc.group.name = name_pairs[fc.group.name]

def restore_action_paths(mapping):
    """
    Restore bone data_paths and F-Curve group names in ALL actions.
    mapping: dict of {new_name: old_name}
    Called BEFORE bones are restored, converts new_name -> old_name in paths and groups.
    """
    if not mapping:
        return
    path_pairs = []
    name_pairs = {}  # new_name -> old_name for group restoring
    for new_name, old_name in mapping.items():
        path_pairs.append(('pose.bones["' + new_name + '"]', 'pose.bones["' + old_name + '"]'))
        name_pairs[new_name] = old_name

    for action in bpy.data.actions:
        for fc in get_all_fcurves(action):
            # Restore data_path
            for cur_path, orig_path in path_pairs:
                if cur_path in fc.data_path:
                    fc.data_path = fc.data_path.replace(cur_path, orig_path)
            # Restore F-Curve group name
            if fc.group and fc.group.name in name_pairs:
                fc.group.name = name_pairs[fc.group.name]

def rename_to_standard(obj):
    if not obj: return
    mapping = {}
    
    # Handle Armature Bones
    if obj.type == 'ARMATURE':
        for bone in obj.data.bones:
            old_name = bone.name
            new_name = None
            if " L " in old_name:
                new_name = old_name.replace(" L ", " ") + ".L"
            elif " R " in old_name:
                new_name = old_name.replace(" R ", " ") + ".R"
            
            if new_name:
                mapping[new_name] = old_name
                bone.name = new_name
        
        if mapping:
            # Store mapping in the armature data block
            obj.data["biped_name_mapping"] = json.dumps(mapping)
            # Update F-Curve paths in ALL actions
            rename_action_paths(mapping)
                
    # Handle Mesh Vertex Groups
    if obj.type == 'MESH':
        for vg in obj.vertex_groups:
            old_name = vg.name
            new_name = None
            if " L " in old_name:
                new_name = old_name.replace(" L ", " ") + ".L"
            elif " R " in old_name:
                new_name = old_name.replace(" R ", " ") + ".R"
            
            if new_name:
                mapping[new_name] = old_name
                try:
                    vg.name = new_name
                except:
                    # If collision happens (Blender auto-renamed it), just skip
                    pass
        
        if mapping:
            # Store mapping in the mesh object
            obj["biped_vg_mapping"] = json.dumps(mapping)

def restore_original_names(obj):
    if not obj: return
    
    # Handle Armature Bones
    if obj.type == 'ARMATURE' and "biped_name_mapping" in obj.data:
        try:
            mapping = json.loads(obj.data["biped_name_mapping"])
            # Restore F-Curve paths in ALL actions BEFORE restoring bone names
            restore_action_paths(mapping)
            for new_name, old_name in mapping.items():
                if new_name in obj.data.bones:
                    obj.data.bones[new_name].name = old_name
            del obj.data["biped_name_mapping"]
        except:
            pass
                
    # Handle Mesh Vertex Groups
    if obj.type == 'MESH' and "biped_vg_mapping" in obj:
        try:
            mapping = json.loads(obj["biped_vg_mapping"])
            for new_name, old_name in mapping.items():
                if new_name in obj.vertex_groups:
                    try:
                        obj.vertex_groups[new_name].name = old_name
                    except:
                        pass
            del obj["biped_vg_mapping"]
        except:
            pass

class BIPED_OT_setup_mirror(bpy.types.Operator):
    bl_idname = "biped.setup_mirror"
    bl_label = "Setup Symmetry Names"
    bl_description = "Convert ' L '/' R ' to '.L'/'.R' and save original names"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armatures = set()
        meshes = set()
        
        for obj in context.selected_objects:
            if obj.type == 'ARMATURE': armatures.add(obj)
            elif obj.type == 'MESH': meshes.add(obj)
            
            if obj.parent and obj.parent.type == 'ARMATURE':
                armatures.add(obj.parent)
            for child in obj.children:
                if child.type == 'MESH':
                    meshes.add(child)
                    
        # Process Armatures FIRST
        for arm in armatures:
            rename_to_standard(arm)
        # Process Meshes SECOND
        for mesh in meshes:
            rename_to_standard(mesh)
            
        return {'FINISHED'}

class BIPED_OT_restore_names(bpy.types.Operator):
    bl_idname = "biped.restore_names"
    bl_label = "Restore Original Names"
    bl_description = "Restore names from saved properties and clean up"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armatures = set()
        meshes = set()
        
        for obj in context.selected_objects:
            if obj.type == 'ARMATURE': armatures.add(obj)
            elif obj.type == 'MESH': meshes.add(obj)
            
            if obj.parent and obj.parent.type == 'ARMATURE':
                armatures.add(obj.parent)
            for child in obj.children:
                if child.type == 'MESH':
                    meshes.add(child)
                    
        # Process Armatures FIRST
        for arm in armatures:
            restore_original_names(arm)
        # Process Meshes SECOND
        for mesh in meshes:
            restore_original_names(mesh)
            
        return {'FINISHED'}

class BIPED_PT_panel(bpy.types.Panel):
    bl_label = "Biped Names Helper"
    bl_idname = "BIPED_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Biped Names'

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("biped.setup_mirror", icon='MOD_MIRROR')
        col.operator("biped.restore_names", icon='LOOP_BACK')

def register():
    bpy.utils.register_class(BIPED_OT_setup_mirror)
    bpy.utils.register_class(BIPED_OT_restore_names)
    bpy.utils.register_class(BIPED_PT_panel)

def unregister():
    bpy.utils.unregister_class(BIPED_OT_setup_mirror)
    bpy.utils.unregister_class(BIPED_OT_restore_names)
    bpy.utils.unregister_class(BIPED_PT_panel)

if __name__ == "__main__":
    register()
