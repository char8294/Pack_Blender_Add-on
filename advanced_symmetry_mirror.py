bl_info = {
    "name": "Advanced Symmetry Weight Mirror",
    "author": "Gemini CLI",
    "version": (1, 1),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > Mirror",
    "description": "Symmetrically mirror weights across X, Y, or Z with normalization and center-line support.",
    "category": "Mesh",
}

import bpy
import bmesh
import mathutils

# -------------------------------------------------------------------
#   Properties
# -------------------------------------------------------------------

class WeightMirrorProperties(bpy.types.PropertyGroup):
    show_bone_setup: bpy.props.BoolProperty(
        name="Show Bone Setup",
        description="Show/Hide bone naming settings",
        default=True
    )
    source_prefix: bpy.props.StringProperty(
        name="Negative Side (-)",
        description="Bones on the -X side (e.g. ' R ')",
        default="Bip001 R "
    )
    target_prefix: bpy.props.StringProperty(
        name="Positive Side (+)",
        description="Bones on the +X side (e.g. ' L ')",
        default="Bip001 L "
    )
    direction: bpy.props.EnumProperty(
        name="Source Side",
        items=[
            ('NEG_TO_POS', "- Negative (-X)", "Copy weights FROM Right side (-X) TO Left side (+X)"),
            ('POS_TO_NEG', "+ Positive (+X)", "Copy weights FROM Left side (+X) TO Right side (-X)"),
        ],
        description="Which side contains the correct weights to mirror FROM",
        default='NEG_TO_POS'
    )

# -------------------------------------------------------------------
#   Operator
# -------------------------------------------------------------------

class MESH_OT_symmetry_mirror_advanced(bpy.types.Operator):
    """Symmetrically mirror vertex weights across X-axis with normalization"""
    bl_idname = "mesh.symmetry_mirror_advanced"
    bl_label = "Apply Skin Mirror"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        props = context.scene.weight_mirror_tool
        
        # Save original mode
        original_mode = obj.mode
        
        # We need to be in Object mode to access vertex groups and selection reliably
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
            
        try:
            self.mirror_logic(obj, props)
        except Exception as e:
            self.report({'ERROR'}, f"Mirror failed: {str(e)}")
            bpy.ops.object.mode_set(mode=original_mode)
            return {'CANCELLED'}

        # Restore original mode
        bpy.ops.object.mode_set(mode=original_mode)
        self.report({'INFO'}, "Skin mirror applied successfully.")
        return {'FINISHED'}

    def mirror_logic(self, obj, props):
        mesh = obj.data
        vgs = obj.vertex_groups
        src_pre = props.source_prefix
        tgt_pre = props.target_prefix
        axis_idx = 0 # Hardcoded to X axis
        
        # dir_mult=1.0 means POS side is source. 
        # But we want NEG side as source by default (Right side).
        dir_mult = 1.0 if props.direction == 'POS_TO_NEG' else -1.0
        
        # 1. Identify processing targets (selected vertices or all)
        selected_verts = [v for v in mesh.vertices if v.select]
        process_indices = [v.index for v in (selected_verts if selected_verts else mesh.vertices)]
        
        # 2. Build KDTree for full mesh
        kd = mathutils.kdtree.KDTree(len(mesh.vertices))
        for i, v in enumerate(mesh.vertices):
            kd.insert(v.co, i)
        kd.balance()

        processed_indices = set()
        
        for v_idx in process_indices:
            if v_idx in processed_indices:
                continue
                
            v = mesh.vertices[v_idx]
            
            # Find mirror counterpart
            mirror_co = v.co.copy()
            mirror_co[axis_idx] = -v.co[axis_idx]
            co_mirror, mirror_idx, dist = kd.find(mirror_co)
            
            if dist > 0.001:
                continue 

            v_mirror = mesh.vertices[mirror_idx]
            coord_val = v.co[axis_idx]
            
            # Logic check:
            # If Source Side is NEG_TO_POS: 
            #   coord < -0.0001 -> Source Side
            #   coord >  0.0001 -> Target Side
            # If Source Side is POS_TO_NEG:
            #   coord >  0.0001 -> Source Side
            #   coord < -0.0001 -> Target Side
            
            if props.direction == 'NEG_TO_POS':
                is_source_side = coord_val < -0.0001
                is_target_side = coord_val > 0.0001
            else: # POS_TO_NEG
                is_source_side = coord_val > 0.0001
                is_target_side = coord_val < -0.0001
                
            is_center = abs(coord_val) < 0.0005
            
            if is_center:
                v_src_ptr = v
                v_tgt_ptr = v
            elif is_source_side:
                v_src_ptr = v
                v_tgt_ptr = v_mirror
            else: # Vertex is on Target side (or other)
                v_src_ptr = v_mirror
                v_tgt_ptr = v

            # --- DEFINE BONE MAPPING BASED ON DIRECTION ---
            # If Source Side is NEG_TO_POS: R bones on -X (Src) map to L bones on +X (Tgt)
            # If Source Side is POS_TO_NEG: L bones on +X (Src) map to R bones on -X (Tgt)
            if props.direction == 'NEG_TO_POS':
                local_pre, mirror_pre = src_pre, tgt_pre
            else:
                local_pre, mirror_pre = tgt_pre, src_pre

            src_weights = {g.group: g.weight for g in v_src_ptr.groups if g.weight > 1e-6}

            if is_center:
                # --- CENTER SYNC ---
                for g in list(v.groups):
                    vgs[g.group].remove([v.index])
                
                new_weights = {}
                for g_idx, w in src_weights.items():
                    name = vgs[g_idx].name
                    if local_pre in name:
                        new_weights[name] = w
                        m_name = name.replace(local_pre, mirror_pre, 1)
                        if m_name in vgs:
                            new_weights[m_name] = w
                    elif mirror_pre in name:
                        l_name = name.replace(mirror_pre, local_pre, 1)
                        if l_name in vgs and l_name not in new_weights:
                            new_weights[l_name] = w
                            new_weights[name] = w
                        else:
                            new_weights[name] = w
                    else:
                        new_weights[name] = w
                
                total = sum(new_weights.values())
                if total > 1e-7:
                    for name, w in new_weights.items():
                        vgs[name].add([v.index], w / total, 'REPLACE')
                processed_indices.add(v.index)

            else:
                # --- SYMMETRIC MIRROR ---
                # 1. Update Target Vertex
                for g in list(v_tgt_ptr.groups):
                    vgs[g.group].remove([v_tgt_ptr.index])
                
                new_tgt_weights = {}
                for g_idx, w in src_weights.items():
                    name = vgs[g_idx].name
                    if local_pre in name:
                        m_name = name.replace(local_pre, mirror_pre, 1)
                        if m_name in vgs:
                            new_tgt_weights[m_name] = w
                    elif mirror_pre in name:
                        # If mirror bone exists on source side, it shouldn't be moved to target side as is
                        continue 
                    else:
                        new_tgt_weights[name] = w
                
                t_total = sum(new_tgt_weights.values())
                if t_total > 1e-7:
                    for name, w in new_tgt_weights.items():
                        vgs[name].add([v_tgt_ptr.index], w / t_total, 'REPLACE')

                # 2. Clean Source Vertex (remove mirror bones that shouldn't be here)
                for g in list(v_src_ptr.groups):
                    if mirror_pre in vgs[g.group].name:
                        vgs[g.group].remove([v_src_ptr.index])
                
                s_final_weights = {vgs[g.group].name: g.weight for g in v_src_ptr.groups if g.weight > 1e-6}
                s_total = sum(s_final_weights.values())
                if s_total > 1e-7:
                    for name, w in s_final_weights.items():
                        vgs[name].add([v_src_ptr.index], w / s_total, 'REPLACE')

                processed_indices.add(v_src_ptr.index)
                processed_indices.add(v_tgt_ptr.index)

# -------------------------------------------------------------------
#   UI Panel
# -------------------------------------------------------------------

class VIEW3D_PT_weight_mirror(bpy.types.Panel):
    """Weight Mirror Panel in the Sidebar"""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Skin Mirror' 
    bl_label = "Symmetry Mirror (X-Axis)"

    def draw(self, context):
        layout = self.layout
        props = context.scene.weight_mirror_tool
        
        # 1. Collapsible Bone Setup
        row = layout.row(align=True)
        row.prop(props, "show_bone_setup", 
                 icon="TRIA_DOWN" if props.show_bone_setup else "TRIA_RIGHT", 
                 icon_only=True, emboss=False)
        row.label(text="Bone Naming", icon='BONE_DATA')
        
        if props.show_bone_setup:
            box = layout.box()
            col = box.column(align=True)
            col.prop(props, "source_prefix", text="Right Side (-X)")
            col.prop(props, "target_prefix", text="Left Side (+X)")
        
        layout.separator()

        # 2. Mirror Setup
        box = layout.box()
        box.label(text="Mirror Direction", icon='MOD_MIRROR')
        box.prop(props, "direction", text="Source Side")
        
        layout.separator()
        
        # 3. Action
        active_obj = context.active_object
        if active_obj and active_obj.type == 'MESH':
            row = layout.row()
            row.scale_y = 1.3 # Smaller button
            row.operator("mesh.symmetry_mirror_advanced", icon='MOD_MIRROR', text="Apply Skin Mirror")
        else:
            layout.label(text="Please select a Mesh Object", icon='ERROR')

# -------------------------------------------------------------------
#   Registration
# -------------------------------------------------------------------

classes = (
    WeightMirrorProperties,
    MESH_OT_symmetry_mirror_advanced,
    VIEW3D_PT_weight_mirror,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.weight_mirror_tool = bpy.props.PointerProperty(type=WeightMirrorProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.register_class(cls)
    del bpy.types.Scene.weight_mirror_tool

if __name__ == "__main__":
    register()
