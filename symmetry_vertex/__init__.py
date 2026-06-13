bl_info = {
    "name": "Symmetry Vertex",
    "author": "ChatGPT (GPT-5 Thinking)",
    "version": (1, 6, 0),
    "blender": (4, 5, 0),
    "location": "Edit > Mesh > Symmetry Vertex",
    "description": "Make vertices symmetrical; UV follows move (Correct Face Attributes + Keep Connected).",
    "category": "Mesh",
}

import bpy
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

# ---------- helpers ----------
def mirror_vec(v: Vector, axis: str):
    if axis == 'X': return Vector((-v.x,  v.y,  v.z))
    if axis == 'Y': return Vector(( v.x, -v.y,  v.z))
    return Vector(( v.x,  v.y, -v.z))

def axis_value(v: Vector, axis: str):
    return v.x if axis == 'X' else (v.y if axis == 'Y' else v.z)

def set_axis_value(v: Vector, axis: str, value: float):
    if axis == 'X': v.x = value
    elif axis == 'Y': v.y = value
    else: v.z = value

def side_sign(v: Vector, axis: str, eps: float):
    a = axis_value(v, axis)
    if a >  eps: return  1
    if a < -eps: return -1
    return 0

# ---------- operator ----------
class MESH_OT_symmetry_vertex(bpy.types.Operator):
    bl_idname = "mesh.symmetry_vertex"
    bl_label = "Symmetry Vertex"
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[('X',"X","Mirror across X=0"),
               ('Y',"Y","Mirror across Y=0"),
               ('Z',"Z","Mirror across Z=0")],
        default='X'
    )
    mode: bpy.props.EnumProperty(
        name="Vertex Mode",
        items=[
            ('NEG_TO_POS', "Copy - → +", "Copy negative side to positive side"),
            ('POS_TO_NEG', "Copy + → -", "Copy positive side to negative side"),
            ('AVERAGE',    "Average both", "Average both sides"),
        ],
        default='NEG_TO_POS'
    )
    seam_epsilon: bpy.props.FloatProperty(
        name="Seam Epsilon", min=0.0, soft_max=0.01, default=0.0
    )
    search_radius: bpy.props.FloatProperty(
        name="Pair Search Radius", min=0.0, default=0.50, soft_max=0.5
    )
    selected_only: bpy.props.BoolProperty(
        name="Selected Only", default=False
    )
    use_cfa_for_uv: bpy.props.BoolProperty(
        name="Correct Face Attributes",
        default=False
    )
    keep_connected: bpy.props.BoolProperty(
        name="Keep Connected",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "axis")
        col.prop(self, "mode")
        col.separator()
        col.prop(self, "seam_epsilon")
        col.prop(self, "search_radius")
        col.separator()
        col.prop(self, "selected_only")
        col.separator()
        col.prop(self, "use_cfa_for_uv")
        sub = col.column(align=True); sub.enabled = self.use_cfa_for_uv
        sub.prop(self, "keep_connected")

    def invoke(self, context, event): return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a Mesh")
            return {'CANCELLED'}

        enter_edit = False
        if context.mode != 'EDIT_MESH':
            enter_edit = True
            bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        use_selection = self.selected_only and any(v.select for v in bm.verts)
        verts = [v for v in bm.verts if (v.select if use_selection else True)]

        moved_pairs, seam_snaps, unmatched = self.apply_symmetry_bmesh(
            context, bm, verts, self.axis, self.mode,
            self.seam_epsilon, self.search_radius,
            self.use_cfa_for_uv, self.keep_connected
        )

        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        if enter_edit: bpy.ops.object.mode_set(mode='OBJECT')

        self.report({'INFO'}, f"Symmetry done. Pairs: {moved_pairs}, Seam snapped: {seam_snaps}, Unmatched: {unmatched}")
        return {'FINISHED'}

    # ---------- core ----------
    def apply_symmetry_bmesh(self, context, bm, verts, axis, mode, seam_eps, radius,
                             use_cfa_for_uv, keep_connected):
        neg, pos, seam = [], [], []
        for v in verts:
            s = side_sign(v.co, axis, seam_eps)
            (neg if s < 0 else pos if s > 0 else seam).append(v)

        for v in seam: set_axis_value(v.co, axis, 0.0)

        if mode == 'NEG_TO_POS':   src_side, dst_side = neg, pos
        elif mode == 'POS_TO_NEG': src_side, dst_side = pos, neg
        else:                      src_side, dst_side = neg, pos

        kd = KDTree(len(dst_side)); index_map = {}
        for i, v in enumerate(dst_side): kd.insert(v.co, i); index_map[i] = v
        kd.balance()

        ts = context.tool_settings
        old_cfa = ts.use_transform_correct_face_attributes
        old_keep = getattr(ts, "use_transform_correct_keep_connected", False)

        if use_cfa_for_uv:
            ts.use_transform_correct_face_attributes = True
            if hasattr(ts, "use_transform_correct_keep_connected"):
                ts.use_transform_correct_keep_connected = bool(keep_connected)

        def flush_sel():
            bmesh.update_edit_mesh(context.active_object.data, loop_triangles=False, destructive=False)

        orig_sel = [v for v in bm.verts if v.select]
        moved_pairs, unmatched = 0, 0
        taken_dst = set()

        for vs in src_side:
            loc, idx, dist = kd.find(mirror_vec(vs.co, axis))
            if idx is None or dist > radius or idx in taken_dst:
                unmatched += 1; continue
            vd = index_map[idx]
            target = mirror_vec(vs.co, axis)
            if abs(axis_value(target, axis)) <= seam_eps: set_axis_value(target, axis, 0.0)

            if use_cfa_for_uv:
                delta = target - vd.co
                if delta.length > 0.0:
                    for v in bm.verts: v.select = False
                    vd.select = True; flush_sel()
                    bpy.ops.transform.translate(
                        value=(delta.x, delta.y, delta.z),
                        orient_type='GLOBAL',
                        use_proportional_edit=False
                    )
            else:
                vd.co = target

            taken_dst.add(idx); moved_pairs += 1

        if use_cfa_for_uv:
            for v in bm.verts: v.select = False
            for v in orig_sel:
                if v.is_valid: v.select = True
            bmesh.update_edit_mesh(context.active_object.data, loop_triangles=False, destructive=False)
            ts.use_transform_correct_face_attributes = old_cfa
            if hasattr(ts, "use_transform_correct_keep_connected"):
                ts.use_transform_correct_keep_connected = old_keep

        seam_snaps = len(seam)
        return moved_pairs, seam_snaps, unmatched

# ---------- menu integration ----------
def menu_func(self, context):
    self.layout.operator(MESH_OT_symmetry_vertex.bl_idname, text="Symmetry Vertex")

classes = (MESH_OT_symmetry_vertex,)

def register():
    for c in classes: bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_edit_mesh.append(menu_func)

def unregister():
    for c in reversed(classes): bpy.utils.unregister_class(c)
    bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func)

if __name__ == "__main__":
    register()
