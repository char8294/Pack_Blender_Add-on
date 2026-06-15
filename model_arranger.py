bl_info = {
    "name": "Model Arranger",
    "author": "Pack Blender Add-on",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Model Arranger",
    "description": "Arrange models in a grid layout using linked duplicates with smart labels.",
    "category": "Object",
}

import bpy
import math
from mathutils import Vector


# -------------------------------------------------------------------
#   Constants
# -------------------------------------------------------------------

COLLECTION_NAME = "ModelArranger_Output"


# -------------------------------------------------------------------
#   Helper Functions
# -------------------------------------------------------------------

def get_bbox_data(obj):
    """Calculate bounding-box data for *obj*.

    Returns a dict with local min/max/center and world-space
    axis-aligned dimensions (accounting for rotation & scale).
    """
    local_corners = [Vector(c) for c in obj.bound_box]

    local_min = Vector((
        min(c.x for c in local_corners),
        min(c.y for c in local_corners),
        min(c.z for c in local_corners),
    ))
    local_max = Vector((
        max(c.x for c in local_corners),
        max(c.y for c in local_corners),
        max(c.z for c in local_corners),
    ))
    local_center = (local_min + local_max) / 2

    # World-space AABB
    world_corners = [obj.matrix_world @ lc for lc in local_corners]
    world_min = Vector((
        min(c.x for c in world_corners),
        min(c.y for c in world_corners),
        min(c.z for c in world_corners),
    ))
    world_max = Vector((
        max(c.x for c in world_corners),
        max(c.y for c in world_corners),
        max(c.z for c in world_corners),
    ))

    return {
        'local_min': local_min,
        'local_max': local_max,
        'local_center': local_center,
        'world_dims': world_max - world_min,
    }


def calc_local_pivot(bbox, pivot_mode):
    """Return the pivot point in local space for the chosen *pivot_mode*.

    ``ORIGINAL`` returns (0, 0, 0) — the object keeps its existing origin.
    """
    if pivot_mode == 'ORIGINAL':
        return Vector((0.0, 0.0, 0.0))

    lmin = bbox['local_min']
    lmax = bbox['local_max']
    lcen = bbox['local_center']

    if pivot_mode == 'CENTER':
        return lcen.copy()
    elif pivot_mode == 'BOTTOM':
        return Vector((lcen.x, lcen.y, lmin.z))
    elif pivot_mode == 'TOP':
        return Vector((lcen.x, lcen.y, lmax.z))
    elif pivot_mode == 'LEFT':
        return Vector((lmin.x, lcen.y, lmin.z))
    elif pivot_mode == 'RIGHT':
        return Vector((lmax.x, lcen.y, lmin.z))
    return lcen.copy()


def calc_instance_world_bbox(inst_location, obj, rot_scale):
    """Compute the world-space AABB for an instance at *inst_location*
    that shares the same rotation/scale matrix as *obj*.

    This avoids a full ``view_layer.update()`` call.
    """
    world_corners = [
        inst_location + rot_scale @ Vector(c) for c in obj.bound_box
    ]
    w_min = Vector((
        min(c.x for c in world_corners),
        min(c.y for c in world_corners),
        min(c.z for c in world_corners),
    ))
    w_max = Vector((
        max(c.x for c in world_corners),
        max(c.y for c in world_corners),
        max(c.z for c in world_corners),
    ))
    return w_min, w_max


def get_or_create_collection(context, name=COLLECTION_NAME):
    """Return the output collection, creating it if it does not exist."""
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        context.scene.collection.children.link(col)
    elif col.name not in context.scene.collection.children:
        context.scene.collection.children.link(col)
    return col


def clear_collection(name=COLLECTION_NAME):
    """Remove every object inside the named collection, then delete the
    collection itself.  Shared mesh data is left untouched; orphaned
    text-curve data blocks are cleaned up.
    """
    col = bpy.data.collections.get(name)
    if col is None:
        return False

    # Collect text-curve data that may become orphaned
    curve_candidates = []
    for obj in col.objects:
        if obj.type == 'FONT' and obj.data is not None:
            curve_candidates.append(obj.data)

    # Remove all objects
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    # Clean up orphaned curves
    for curve in curve_candidates:
        if curve.users == 0:
            bpy.data.curves.remove(curve)

    bpy.data.collections.remove(col)
    return True


def create_label_text(collection, index, source_name, props,
                      inst_w_min, inst_w_max):
    """Create a floating text label above the bounding box of an instance.

    The label is **not** parented to the instance — it is placed at the
    correct world position directly.  This avoids matrix-inverse issues
    that caused misalignment in the previous version.
    """
    # Build label string
    parts = []
    if props.show_number:
        parts.append(f"#{index + 1}")
    if props.show_name:
        parts.append(source_name)

    if not parts:
        return None

    label_body = " — ".join(parts) if len(parts) > 1 else parts[0]

    # Create text-curve data
    text_data = bpy.data.curves.new(
        name=f"Label_{index}_{source_name}", type='FONT',
    )
    text_data.body = label_body
    text_data.align_x = 'CENTER'
    text_data.align_y = 'BOTTOM'

    # Auto-scale text relative to object size
    inst_dims = inst_w_max - inst_w_min
    max_dim = max(inst_dims.x, inst_dims.y, inst_dims.z, 0.5)
    text_data.size = max(0.15, min(max_dim * 0.10, 0.50))

    # Create text object
    text_obj = bpy.data.objects.new(
        name=f"Label_{index}_{source_name}",
        object_data=text_data,
    )
    collection.objects.link(text_obj)

    # Position: centred on X/Y of bounding box, above Z-max
    cx = (inst_w_min.x + inst_w_max.x) * 0.5
    cy = (inst_w_min.y + inst_w_max.y) * 0.5
    top_z = inst_w_max.z
    gap = 0.1 + text_data.size * 0.3

    # Rotate 90° around X so the text stands upright and faces front (-Y)
    text_obj.rotation_euler = (math.pi / 2, 0, 0)
    text_obj.location = Vector((cx, cy, top_z + gap))

    return text_obj


# -------------------------------------------------------------------
#   List-Item PropertyGroup
# -------------------------------------------------------------------

class ModelArrangerItem(bpy.types.PropertyGroup):
    """A single entry in the model arrangement list."""
    obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Object",
        description="Mesh object to include in the arrangement",
    )


# -------------------------------------------------------------------
#   Scene Properties
# -------------------------------------------------------------------

class ModelArrangerProperties(bpy.types.PropertyGroup):

    # -- Model list --------------------------------------------------
    model_list: bpy.props.CollectionProperty(type=ModelArrangerItem)
    model_list_index: bpy.props.IntProperty(
        name="Active Index", default=0,
    )
    source_collection: bpy.props.PointerProperty(
        type=bpy.types.Collection,
        name="Source Collection",
        description="Pick a collection to add all its mesh objects",
    )

    # -- Pivot -------------------------------------------------------
    pivot_mode: bpy.props.EnumProperty(
        name="Pivot",
        description="Reference point for positioning models in the grid",
        items=[
            ('ORIGINAL', "Original",
             "Keep the model's existing origin",          'OBJECT_ORIGIN',  0),
            ('CENTER',   "Center",
             "Bounding-box centre",                       'PIVOT_BOUNDBOX', 1),
            ('BOTTOM',   "Bottom",
             "Bounding-box bottom (Z min)",               'TRIA_DOWN',      2),
            ('TOP',      "Top",
             "Bounding-box top (Z max)",                  'TRIA_UP',        3),
            ('LEFT',     "Left",
             "Bounding-box left (-X)",                    'TRIA_LEFT',      4),
            ('RIGHT',    "Right",
             "Bounding-box right (+X)",                   'TRIA_RIGHT',     5),
        ],
        default='BOTTOM',
    )

    # -- Grid --------------------------------------------------------
    columns: bpy.props.IntProperty(
        name="Columns",
        description="Number of columns in the grid",
        default=5, min=1, max=100,
    )
    spacing: bpy.props.FloatProperty(
        name="Spacing",
        description="Gap between model edges (Blender units). "
                    "Type any value: 0.5, 1.0, 1.5, 2.0 …",
        default=1.0, min=0.0, soft_max=10.0,
        step=50, precision=2,
    )
    primary_axis: bpy.props.EnumProperty(
        name="Primary Axis",
        description="Direction in which columns are laid out",
        items=[
            ('X',    "X",   "Columns spread along +X (left → right)"),
            ('NX',  "-X",  "Columns spread along -X (right → left)"),
            ('Y',    "Y",   "Columns spread along +Y (front → back)"),
            ('NY',  "-Y",  "Columns spread along -Y (back → front)"),
            ('Z',    "Z",   "Columns stack along +Z (bottom → top)"),
            ('NZ',  "-Z",  "Columns stack along -Z (top → bottom)"),
        ],
        default='X',
    )

    # -- Labels ------------------------------------------------------
    show_name: bpy.props.BoolProperty(
        name="Show Model Name",
        description="Display the source object name above each instance",
        default=False,
    )
    show_number: bpy.props.BoolProperty(
        name="Show Model Number",
        description="Display the sequence number (#1, #2 …) above each instance",
        default=False,
    )


# -------------------------------------------------------------------
#   UIList
# -------------------------------------------------------------------

class MODELARR_UL_model_list(bpy.types.UIList):
    """Display list of objects queued for arrangement."""

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if item.obj:
                row = layout.row(align=True)
                row.label(text=f"{index + 1}.")
                row.label(text=item.obj.name, icon='MESH_DATA')
            else:
                layout.label(text="(Missing Object)", icon='ERROR')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='MESH_DATA')


# -------------------------------------------------------------------
#   List-Management Operators
# -------------------------------------------------------------------

class MODELARR_OT_list_add_selected(bpy.types.Operator):
    """Add every selected mesh object to the arrangement list"""
    bl_idname = "model_arranger.list_add_selected"
    bl_label = "Add Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        props = context.scene.model_arranger_props
        existing = {item.obj for item in props.model_list if item.obj}
        added = 0
        for obj in sorted(context.selected_objects, key=lambda o: o.name):
            if obj.type == 'MESH' and obj not in existing:
                new_item = props.model_list.add()
                new_item.obj = obj
                added += 1
        self.report({'INFO'}, f"Added {added} object(s) to list")
        return {'FINISHED'}


class MODELARR_OT_list_add_collection(bpy.types.Operator):
    """Add all mesh objects from the chosen collection to the list"""
    bl_idname = "model_arranger.list_add_collection"
    bl_label = "Add from Collection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.model_arranger_props.source_collection is not None

    def execute(self, context):
        props = context.scene.model_arranger_props
        src = props.source_collection
        if src is None:
            self.report({'WARNING'}, "No collection selected.")
            return {'CANCELLED'}

        existing = {item.obj for item in props.model_list if item.obj}
        added = 0
        for obj in sorted(src.all_objects, key=lambda o: o.name):
            if obj.type == 'MESH' and obj not in existing:
                new_item = props.model_list.add()
                new_item.obj = obj
                added += 1

        self.report({'INFO'},
                    f"Added {added} object(s) from \"{src.name}\"")
        return {'FINISHED'}


class MODELARR_OT_list_remove(bpy.types.Operator):
    """Remove the selected item from the list"""
    bl_idname = "model_arranger.list_remove"
    bl_label = "Remove"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.model_arranger_props.model_list) > 0

    def execute(self, context):
        props = context.scene.model_arranger_props
        props.model_list.remove(props.model_list_index)
        props.model_list_index = min(
            max(0, props.model_list_index),
            max(0, len(props.model_list) - 1),
        )
        return {'FINISHED'}


class MODELARR_OT_list_clear(bpy.types.Operator):
    """Remove all items from the list"""
    bl_idname = "model_arranger.list_clear"
    bl_label = "Clear List"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.model_arranger_props.model_list) > 0

    def execute(self, context):
        context.scene.model_arranger_props.model_list.clear()
        context.scene.model_arranger_props.model_list_index = 0
        self.report({'INFO'}, "List cleared.")
        return {'FINISHED'}


class MODELARR_OT_list_move(bpy.types.Operator):
    """Move the selected item up or down"""
    bl_idname = "model_arranger.list_move"
    bl_label = "Move Item"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=[('UP', "Up", ""), ('DOWN', "Down", "")],
    )

    @classmethod
    def poll(cls, context):
        return len(context.scene.model_arranger_props.model_list) > 1

    def execute(self, context):
        props = context.scene.model_arranger_props
        idx = props.model_list_index
        max_idx = len(props.model_list) - 1

        if self.direction == 'UP' and idx > 0:
            props.model_list.move(idx, idx - 1)
            props.model_list_index -= 1
        elif self.direction == 'DOWN' and idx < max_idx:
            props.model_list.move(idx, idx + 1)
            props.model_list_index += 1

        return {'FINISHED'}


# -------------------------------------------------------------------
#   Main Operators
# -------------------------------------------------------------------

class MODELARR_OT_arrange(bpy.types.Operator):
    """Create linked duplicates from the list and arrange them in a grid"""
    bl_idname = "model_arranger.arrange"
    bl_label = "Arrange Models"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.model_arranger_props
        return (context.mode == 'OBJECT'
                and len(props.model_list) > 0)

    def execute(self, context):
        props = context.scene.model_arranger_props

        # 1 — Gather valid objects from the list
        objects = []
        for item in props.model_list:
            if item.obj is not None and item.obj.type == 'MESH':
                objects.append(item.obj)

        if not objects:
            self.report({'WARNING'}, "No valid mesh objects in the list.")
            return {'CANCELLED'}

        # 2 — Clear any previous arrangement
        clear_collection(COLLECTION_NAME)

        # 3 — Create / get output collection
        collection = get_or_create_collection(context)

        # 4 — Pre-compute bounding-box data
        bbox_list = [get_bbox_data(obj) for obj in objects]

        # 5 — Determine uniform cell sizes
        max_dx = max(bd['world_dims'].x for bd in bbox_list)
        max_dy = max(bd['world_dims'].y for bd in bbox_list)
        max_dz = max(bd['world_dims'].z for bd in bbox_list)
        sp = props.spacing

        axis = props.primary_axis          # e.g. 'X', 'NX', 'Y', …
        base_axis = axis[-1]                # 'X', 'Y', or 'Z'
        sign = -1.0 if axis.startswith('N') else 1.0

        if base_axis == 'X':
            cell_col = max_dx + sp          # column step along X
            cell_row = max_dy + sp          # row step along Y
        elif base_axis == 'Y':
            cell_col = max_dy + sp          # column step along Y
            cell_row = max_dx + sp          # row step along X
        else:  # Z
            cell_col = max_dz + sp          # column step along Z
            cell_row = max_dx + sp          # row step along X

        columns = min(props.columns, len(objects))

        # 6 — Create instances, position them, add labels
        for i, (obj, bbox) in enumerate(zip(objects, bbox_list)):
            col_idx = i % columns
            row_idx = i // columns

            # Grid position (sign flips the column direction)
            if base_axis == 'X':
                gx = sign * col_idx * cell_col
                gy = -row_idx * cell_row
                gz = 0.0
            elif base_axis == 'Y':
                gx = row_idx * cell_row
                gy = sign * col_idx * cell_col
                gz = 0.0
            else:  # Z
                gx = row_idx * cell_row
                gy = 0.0
                gz = sign * col_idx * cell_col

            grid_pos = Vector((gx, gy, gz))

            # Pivot offset (local → world)
            local_pivot = calc_local_pivot(bbox, props.pivot_mode)
            rot_scale = obj.matrix_world.to_3x3()
            world_pivot_offset = rot_scale @ local_pivot

            # Linked duplicate (shares mesh data, copies transform)
            instance = obj.copy()
            collection.objects.link(instance)

            # Ensure instance is only in the output collection
            for c in list(instance.users_collection):
                if c != collection:
                    c.objects.unlink(instance)

            # Place instance so its pivot lands on grid_pos
            instance.location = grid_pos - world_pivot_offset

            # World AABB (computed without depsgraph update)
            inst_w_min, inst_w_max = calc_instance_world_bbox(
                instance.location, obj, rot_scale,
            )

            # Labels
            if props.show_name or props.show_number:
                create_label_text(
                    collection, i, obj.name, props,
                    inst_w_min, inst_w_max,
                )

        # 7 — Select new instances
        bpy.ops.object.select_all(action='DESELECT')
        for obj in collection.objects:
            obj.select_set(True)

        rows = math.ceil(len(objects) / columns)
        self.report(
            {'INFO'},
            f"Arranged {len(objects)} model(s) → {columns}×{rows} grid  |  "
            f"Collection: \"{COLLECTION_NAME}\"",
        )
        return {'FINISHED'}


class MODELARR_OT_clear_arranged(bpy.types.Operator):
    """Remove all arranged instances and their labels"""
    bl_idname = "model_arranger.clear_arranged"
    bl_label = "Clear Arranged"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bpy.data.collections.get(COLLECTION_NAME) is not None

    def execute(self, context):
        if clear_collection(COLLECTION_NAME):
            self.report({'INFO'},
                        f"Cleared collection \"{COLLECTION_NAME}\".")
        else:
            self.report({'WARNING'}, "Nothing to clear.")
        return {'FINISHED'}


# -------------------------------------------------------------------
#   UI Panel
# -------------------------------------------------------------------

class MODELARR_PT_main_panel(bpy.types.Panel):
    """Model Arranger — sidebar panel"""
    bl_label = "Model Arranger"
    bl_idname = "MODELARR_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Model Arranger"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.model_arranger_props
        list_len = len(props.model_list)

        # ── Model List ──────────────────────────────────────────────
        box = layout.box()
        box.label(text="Model List", icon='OUTLINER')

        row = box.row()
        row.template_list(
            "MODELARR_UL_model_list", "",
            props, "model_list",
            props, "model_list_index",
            rows=4,
        )

        # Side buttons: move up/down, remove
        side_col = row.column(align=True)
        side_col.operator("model_arranger.list_move",
                          text="", icon='TRIA_UP').direction = 'UP'
        side_col.operator("model_arranger.list_move",
                          text="", icon='TRIA_DOWN').direction = 'DOWN'
        side_col.separator()
        side_col.operator("model_arranger.list_remove",
                          text="", icon='X')

        # Add Selected / Clear List
        btn_row = box.row(align=True)
        btn_row.operator("model_arranger.list_add_selected",
                         text="Add Selected", icon='ADD')
        btn_row.operator("model_arranger.list_clear",
                         text="Clear List", icon='TRASH')

        # Add from Collection
        col_row = box.row(align=True)
        col_row.prop(props, "source_collection", text="")
        sub = col_row.row(align=True)
        sub.enabled = props.source_collection is not None
        sub.operator("model_arranger.list_add_collection",
                     text="", icon='ADD')

        # Count
        count_row = box.row()
        count_row.alignment = 'CENTER'
        count_row.label(text=f"{list_len} object(s) in list")

        layout.separator()

        # ── Pivot Point ─────────────────────────────────────────────
        box = layout.box()
        box.label(text="Pivot Point", icon='PIVOT_BOUNDBOX')
        box.prop(props, "pivot_mode", text="")

        layout.separator()

        # ── Grid Layout ─────────────────────────────────────────────
        box = layout.box()
        box.label(text="Grid Layout", icon='MESH_GRID')

        col = box.column(align=True)
        col.prop(props, "columns")
        col.prop(props, "spacing")

        axis_row = box.row(align=True)
        axis_row.label(text="Axis:")
        axis_row.prop(props, "primary_axis", expand=True)

        # Grid preview
        if list_len > 0:
            cols = min(props.columns, list_len)
            rows = math.ceil(list_len / cols) if cols > 0 else 0
            preview = box.row()
            preview.alignment = 'CENTER'
            preview.label(text=f"Result: {cols} col × {rows} row",
                          icon='INFO')

        layout.separator()

        # ── Labels ──────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Labels", icon='FONT_DATA')

        col = box.column(align=True)
        col.prop(props, "show_name", icon='OUTLINER_OB_FONT')
        col.prop(props, "show_number", icon='SEQUENCE')

        if props.show_name or props.show_number:
            parts = []
            if props.show_number:
                parts.append("#1")
            if props.show_name:
                parts.append("ModelName")
            example = " — ".join(parts)
            hint = box.row()
            hint.alignment = 'CENTER'
            hint.label(text=f'e.g.  "{example}"', icon='INFO')

        layout.separator()

        # ── Actions ─────────────────────────────────────────────────
        action_col = layout.column(align=True)

        arr_row = action_col.row(align=True)
        arr_row.scale_y = 1.5
        arr_row.operator("model_arranger.arrange",
                         text="Arrange Models", icon='SORTSIZE')
        arr_row.enabled = list_len > 0

        action_col.separator()

        clr_row = action_col.row(align=True)
        clr_row.scale_y = 1.2
        clr_row.operator("model_arranger.clear_arranged",
                         text="Clear Arranged", icon='TRASH')
        clr_row.enabled = (
            bpy.data.collections.get(COLLECTION_NAME) is not None
        )


# -------------------------------------------------------------------
#   Registration
# -------------------------------------------------------------------

classes = (
    ModelArrangerItem,
    ModelArrangerProperties,
    MODELARR_UL_model_list,
    MODELARR_OT_list_add_selected,
    MODELARR_OT_list_add_collection,
    MODELARR_OT_list_remove,
    MODELARR_OT_list_clear,
    MODELARR_OT_list_move,
    MODELARR_OT_arrange,
    MODELARR_OT_clear_arranged,
    MODELARR_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.model_arranger_props = bpy.props.PointerProperty(
        type=ModelArrangerProperties,
    )


def unregister():
    del bpy.types.Scene.model_arranger_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
