import bpy
import math
import os
import re
import json
import urllib.request
import urllib.error
from mathutils import Vector
from bpy.props import (
    EnumProperty,
    FloatProperty,
    PointerProperty,
    IntProperty,
    CollectionProperty,
    StringProperty,
)
from bpy.types import Panel, Operator, PropertyGroup, UIList

bl_info = {
    "name": "Turntable Camera",
    "author": "TEERA",
    "version": (1, 1, 8),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Turntable Tab",
    "description": "Turntable animation สำหรับโมเดล: กล้องหมุนรอบโมเดล หรือโมเดลหมุนบนที่ พร้อมพรีเซ็ตกล้องสำเร็จรูป",
    "category": "Animation",
}

# =====================================================================
#  GitHub Update Config
# =====================================================================

GITHUB_OWNER = "char8294"
GITHUB_REPO = "Pack_Blender_Add-on"
GITHUB_ADDON_FOLDER = "turntable_camera"
GITHUB_RAW_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}"
    f"/main/{GITHUB_ADDON_FOLDER}/__init__.py"
)
GITHUB_API_CONTENTS = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
    f"/contents/{GITHUB_ADDON_FOLDER}"
)
GITHUB_CHANGELOG_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}"
    f"/main/{GITHUB_ADDON_FOLDER}/CHANGELOG.md"
)

_update_info = {
    "checked": False,
    "has_update": False,
    "current_version": (0, 0, 0),
    "latest_version": (0, 0, 0),
    "error": "",
    "changelog": [],
}

# =====================================================================
#  Preset Data
# =====================================================================

PRESETS = {
    'PIXEL_ART': {
        'name': "Pixel Art / Retro",
        'fps': 12,
        'frames': 60,
        'desc': "กระตุกดิบๆ สไตล์ Stop Motion ยุคคลาสสิก",
    },
    'PS1': {
        'name': "PS1 / ยุค 90s",
        'fps': 15,
        'frames': 75,
        'desc': "หน่วงๆ เฟรมต่ำแบบเกมคอนโซลยุคแรก",
    },
    'MODERN_30': {
        'name': "Modern Smooth 30fps",
        'fps': 30,
        'frames': 150,
        'desc': "ลื่นไหล เนียนตา 30fps",
    },
    'MODERN_60': {
        'name': "Modern Smooth 60fps",
        'fps': 60,
        'frames': 300,
        'desc': "ลื่นไหลสุด เนียนตา 60fps",
    },
}


# =====================================================================
#  Properties
# =====================================================================

def _filter_mesh_armature(self, obj):
    """Filter สำหรับ PointerProperty — แสดงเฉพาะ MESH, ARMATURE, EMPTY, CURVE, SURFACE, META, FONT"""
    return obj.type in {'MESH', 'ARMATURE', 'EMPTY', 'CURVE', 'SURFACE', 'META', 'FONT'}


def _filter_camera(self, obj):
    """Filter สำหรับ PointerProperty — แสดงเฉพาะ CAMERA"""
    return obj.type == 'CAMERA'


# ── Rotation List Item ──

class TURNTABLE_RotationItem(PropertyGroup):
    """Item ในลิสต์สำหรับ Model Rotate — เป็นได้ทั้ง Object หรือ Collection"""
    item_type: EnumProperty(
        name="Type",
        items=[
            ('OBJECT', "Object", "หมุน Object เดี่ยว"),
            ('COLLECTION', "Collection", "หมุนทั้ง Collection เป็นกลุ่ม"),
        ],
        default='OBJECT',
    )

    target_object: PointerProperty(
        type=bpy.types.Object,
        name="Object",
        description="Object ที่จะหมุน",
    )

    collection_name: StringProperty(
        name="Collection",
        description="ชื่อ Collection ที่จะหมุน",
        default="",
    )


# ── Main Properties ──

class TURNTABLE_Properties(PropertyGroup):
    mode: EnumProperty(
        name="Mode",
        description="เลือกโหมดการหมุน",
        items=[
            ('CAMERA_ROTATE', "Camera Rotate", "กล้องหมุนรอบโมเดล (โมเดลเดียว)"),
            ('MODEL_ROTATE', "Model Rotate", "โมเดลหมุน กล้องอยู่กับที่ (โมเดลเยอะ)"),
        ],
        default='CAMERA_ROTATE',
    )

    preset: EnumProperty(
        name="Preset",
        description="เลือกพรีเซ็ตกล้อง",
        items=[
            ('PIXEL_ART', "Pixel Art / Retro", "12 fps · 60 frames — กระตุกดิบๆ Stop Motion"),
            ('PS1',       "PS1 / ยุค 90s",     "15 fps · 75 frames — หน่วงๆ คอนโซลยุคแรก"),
            ('MODERN_30', "Modern 30fps",      "30 fps · 150 frames — ลื่นไหล"),
            ('MODERN_60', "Modern 60fps",      "60 fps · 300 frames — ลื่นไหลสุด"),
        ],
        default='MODERN_30',
    )

    # ── Camera Orbit Settings ──

    target_object: PointerProperty(
        type=bpy.types.Object,
        name="Target",
        description="โมเดลที่กล้องจะหมุนรอบ",
        poll=_filter_mesh_armature,
    )

    camera_object: PointerProperty(
        type=bpy.types.Object,
        name="Camera",
        description="กล้องที่จะใช้ (ถ้าไม่เลือกจะสร้างใหม่)",
        poll=_filter_camera,
    )

    cam_distance: FloatProperty(
        name="Distance",
        description="ระยะห่างกล้องจากโมเดล",
        default=5.0,
        min=0.1,
        max=1000.0,
        unit='LENGTH',
    )

    cam_height: FloatProperty(
        name="Height",
        description="ความสูงกล้อง (จากจุดศูนย์กลางของ target)",
        default=1.5,
        min=-100.0,
        max=100.0,
        unit='LENGTH',
    )

    cam_tilt_x: FloatProperty(
        name="Tilt (X)",
        description="มุมก้ม/เงย ของกล้อง (มองขึ้น-ลง)",
        default=0.0,
        min=math.radians(-90),
        max=math.radians(90),
        subtype='ANGLE',
    )

    # ── Custom overrides ──

    custom_fps: IntProperty(
        name="FPS",
        description="Frame rate (จาก preset)",
        default=30,
        min=1,
        max=120,
    )

    custom_frames: IntProperty(
        name="Frames",
        description="จำนวนเฟรมที่หมุน 1 รอบ (จาก preset)",
        default=150,
        min=1,
        max=9999,
    )

    # ── Model Rotate List ──

    rotation_items: CollectionProperty(type=TURNTABLE_RotationItem)

    rotation_items_index: IntProperty(
        name="Active Rotation Item",
        default=0,
    )

    add_mode: EnumProperty(
        name="Add Mode",
        items=[
            ('OBJECT', "Object", "เพิ่ม selected objects เข้าลิสต์"),
            ('COLLECTION', "Collection", "เพิ่ม collections ของ selected objects เข้าลิสต์"),
        ],
        default='OBJECT',
    )


# =====================================================================
#  Helper Functions
# =====================================================================

def _set_fcurve_linear_interpolation(obj, data_path, index):
    """ตั้งค่า interpolation ของ F-Curve ที่กำหนดให้เป็น LINEAR โดยรองรับทั้ง Blender 5.0+ และเวอร์ชันเก่า"""
    if not obj.animation_data or not obj.animation_data.action:
        return

    action = obj.animation_data.action

    # 1. Blender 5.0+ Slotted Actions API
    if hasattr(action, "fcurve_ensure_for_datablock"):
        try:
            fc = action.fcurve_ensure_for_datablock(datablock=obj, data_path=data_path, index=index)
            if fc:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
                return
        except Exception:
            pass

    # 2. Blender 4.x/3.x Legacy API
    if hasattr(action, "fcurves"):
        for fc in action.fcurves:
            if fc.data_path == data_path and fc.array_index == index:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'


def _remove_fcurve(obj, data_path, index):
    """ลบ F-Curve สำหรับ property และ index ที่ระบุ โดยรองรับทั้ง Blender 5.0+ และเวอร์ชันเก่า"""
    if not obj.animation_data or not obj.animation_data.action:
        return False

    action = obj.animation_data.action
    removed = False

    # 1. Blender 5.0+ Slotted Actions API
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                try:
                    cb = strip.channelbag(obj.animation_data.action_slot, ensure=False)
                    if cb:
                        to_remove = [fc for fc in cb.fcurves if fc.data_path == data_path and fc.array_index == index]
                        for fc in to_remove:
                            cb.fcurves.remove(fc)
                            removed = True
                except Exception:
                    pass

    # 2. Blender 4.x/3.x Legacy API
    if hasattr(action, "fcurves"):
        to_remove = [fc for fc in action.fcurves if fc.data_path == data_path and fc.array_index == index]
        for fc in to_remove:
            action.fcurves.remove(fc)
            removed = True

    return removed


def _clean_empty_action(obj):
    """ตรวจสอบและลบ Action ที่ไม่มี F-Curves เพื่อประหยัดพื้นที่"""
    if not obj.animation_data or not obj.animation_data.action:
        return

    action = obj.animation_data.action
    has_fcurves = False

    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                try:
                    cb = strip.channelbag(obj.animation_data.action_slot, ensure=False)
                    if cb and len(cb.fcurves) > 0:
                        has_fcurves = True
                        break
                except Exception:
                    pass
            if has_fcurves:
                break
    elif hasattr(action, "fcurves"):
        if len(action.fcurves) > 0:
            has_fcurves = True

    if not has_fcurves:
        try:
            bpy.data.actions.remove(action)
        except Exception:
            pass
        obj.animation_data_clear()


def _apply_preset(props):
    """อัปเดต custom_fps / custom_frames ตาม preset ที่เลือก"""
    p = PRESETS.get(props.preset)
    if p:
        props.custom_fps = p['fps']
        props.custom_frames = p['frames']


def _get_or_create_camera(context, props):
    """คืน camera object — ใช้ตัวที่เลือก หรือสร้างใหม่"""
    if props.camera_object and props.camera_object.type == 'CAMERA':
        return props.camera_object

    cam_data = bpy.data.cameras.new("TurntableCam")
    cam_obj = bpy.data.objects.new("TurntableCam", cam_data)
    context.collection.objects.link(cam_obj)
    props.camera_object = cam_obj
    return cam_obj


def _find_turntable_empty(cam_obj):
    """หา Empty ที่เป็น turntable pivot ของกล้อง (ถ้ามี)"""
    if cam_obj.parent and cam_obj.parent.type == 'EMPTY':
        if cam_obj.parent.name.startswith("Turntable_Pivot"):
            return cam_obj.parent
    return None


def _clear_track_to(cam_obj):
    """ลบ Track To constraint ที่ชื่อ TurntableTrack (ถ้ามี)"""
    to_remove = [c for c in cam_obj.constraints if c.name == "TurntableTrack"]
    for c in to_remove:
        cam_obj.constraints.remove(c)


def _get_collection_center(collection):
    """คำนวณจุดศูนย์กลางของทุก object ใน Collection (รวม sub-collections)"""
    positions = []
    for obj in collection.all_objects:
        positions.append(obj.matrix_world.translation.copy())
    if not positions:
        return Vector((0, 0, 0))
    center = Vector((0, 0, 0))
    for p in positions:
        center += p
    center /= len(positions)
    return center


def _find_rotation_pivot(obj):
    """หา Turntable_Rot_Pivot ที่เป็น parent ของ object (ถ้ามี)"""
    if obj.parent and obj.parent.type == 'EMPTY':
        if obj.parent.name.startswith("Turntable_Rot_"):
            return obj.parent
    return None


def _rotate_single_object(obj, total_frames):
    """ใส่ keyframe rotation Z 360° ให้ object เดี่ยว"""
    _remove_fcurve(obj, "rotation_euler", 2)

    original_z = obj.rotation_euler.z
    obj.rotation_euler.z = original_z
    obj.keyframe_insert(data_path="rotation_euler", index=2, frame=1)

    obj.rotation_euler.z = original_z + math.radians(360)
    obj.keyframe_insert(data_path="rotation_euler", index=2, frame=total_frames + 1)

    _set_fcurve_linear_interpolation(obj, "rotation_euler", 2)


def _rotate_collection_as_group(context, collection, total_frames):
    """สร้าง Empty Pivot ตรงกลาง Collection แล้ว Parent ทุก object → หมุน Pivot"""
    # ── สร้างหรือใช้ Pivot Empty เดิม ──
    pivot_name = f"Turntable_Rot_{collection.name}"
    pivot = bpy.data.objects.get(pivot_name)

    if pivot is None:
        pivot = bpy.data.objects.new(pivot_name, None)
        pivot.empty_display_type = 'PLAIN_AXES'
        pivot.empty_display_size = 0.5
        # Link pivot เข้า collection ของมันเอง (ไม่ใช่ context.collection)
        collection.objects.link(pivot)

    # ── คำนวณ center จาก direct objects เท่านั้น (ไม่รวม pivot) ──
    positions = []
    for obj in collection.objects:
        if obj == pivot:
            continue
        positions.append(obj.matrix_world.translation.copy())
    if positions:
        center = Vector((0, 0, 0))
        for p in positions:
            center += p
        center /= len(positions)
    else:
        center = Vector((0, 0, 0))

    pivot.location = center
    pivot.rotation_euler = (0, 0, 0)

    # ── อัปเดต depsgraph เพื่อให้ matrix_world ของ pivot ถูกต้อง ──
    context.view_layer.update()

    # ── Parent เฉพาะ direct objects ของ collection นี้ → Pivot ──
    for obj in collection.objects:
        if obj == pivot:
            continue
        # ข้าม object ที่ถูก parent ไปยัง pivot ของ collection อื่นแล้ว
        if obj.parent is not None and obj.parent.name.startswith("Turntable_Rot_"):
            continue
        if obj.parent is None:
            # เก็บ world matrix เดิมของ object
            orig_matrix = obj.matrix_world.copy()
            obj.parent = pivot
            obj.matrix_parent_inverse = pivot.matrix_world.inverted()
            # คืนค่า world matrix เดิมเพื่อให้ object ไม่เคลื่อนที่
            obj.matrix_world = orig_matrix

    # ── ลบ animation เก่าของ Pivot ──
    if pivot.animation_data and pivot.animation_data.action:
        try:
            bpy.data.actions.remove(pivot.animation_data.action)
        except Exception:
            pass
        pivot.animation_data_clear()

    # ── Keyframe Pivot rotation Z ──
    pivot.rotation_euler = (0, 0, 0)
    pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=1)

    pivot.rotation_euler.z = math.radians(360)
    pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=total_frames + 1)

    _set_fcurve_linear_interpolation(pivot, "rotation_euler", 2)
    return pivot


def _clear_single_object_animation(obj):
    """ลบ rotation Z animation ของ object เดี่ยว"""
    if _remove_fcurve(obj, "rotation_euler", 2):
        _clean_empty_action(obj)
        return True
    return False


def _clear_collection_animation(collection):
    """ลบ Pivot Empty + unparent objects ของ collection"""
    pivot_name = f"Turntable_Rot_{collection.name}"
    pivot = bpy.data.objects.get(pivot_name)
    if pivot is None:
        return False

    # Unparent ทุก child
    for child in list(pivot.children):
        child_world = child.matrix_world.copy()
        child.parent = None
        child.matrix_world = child_world

    # ลบ Pivot
    bpy.data.objects.remove(pivot, do_unlink=True)
    return True


# =====================================================================
#  UIList
# =====================================================================

class TURNTABLE_UL_rotation_items(UIList):
    """UIList สำหรับแสดง Rotation Items (แบบรายชื่อ อ่านอย่างเดียว)"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            if item.item_type == 'OBJECT':
                obj = item.target_object
                if obj:
                    row.label(text=obj.name, icon='OBJECT_DATA')
                else:
                    row.label(text="(ไม่ได้เลือก Object)", icon='ERROR')
                row.label(text="Object", icon='BLANK1')
            else:
                col = bpy.data.collections.get(item.collection_name)
                if col:
                    row.label(text=col.name, icon='OUTLINER_COLLECTION')
                else:
                    row.label(text=item.collection_name or "(ไม่พบ Collection)", icon='ERROR')
                row.label(text="Collection", icon='BLANK1')

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OBJECT_DATA')


# =====================================================================
#  Operators
# =====================================================================

class TURNTABLE_OT_apply_preset(Operator):
    """โหลดค่า FPS / Frames จากพรีเซ็ตที่เลือก"""
    bl_idname = "turntable.apply_preset"
    bl_label = "Apply Preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.turntable_props
        _apply_preset(props)
        self.report({'INFO'}, f"Applied preset: {PRESETS[props.preset]['name']}")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────
#  Rotation List — Add / Remove Items
# ─────────────────────────────────────────────────────────────────────

class TURNTABLE_OT_add_selected(Operator):
    """เพิ่ม selected objects หรือ collections เข้าลิสต์ตาม Add Mode"""
    bl_idname = "turntable.add_selected"
    bl_label = "Add Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "turntable_props", None)
        if props and props.add_mode == 'COLLECTION':
            return True
        return len(context.selected_objects) > 0

    def execute(self, context):
        props = context.scene.turntable_props
        added = 0
        skipped = 0

        if props.add_mode == 'OBJECT':
            # ── Bulk add selected objects ──
            for obj in context.selected_objects:
                if obj.type == 'CAMERA':
                    continue
                # ตรวจซ้ำ
                already = any(
                    i.item_type == 'OBJECT' and i.target_object == obj
                    for i in props.rotation_items
                )
                if already:
                    skipped += 1
                    continue
                new_item = props.rotation_items.add()
                new_item.item_type = 'OBJECT'
                new_item.target_object = obj
                added += 1

            label = "objects"

        else:  # COLLECTION
            col_names = set()
            
            if len(context.selected_objects) > 0:
                # ── หา collections ที่ selected objects อยู่ ──
                for obj in context.selected_objects:
                    if obj.type == 'CAMERA':
                        continue
                    for col in bpy.data.collections:
                        if obj.name in col.objects:
                            col_names.add(col.name)
            else:
                # ── ถ้าไม่ได้เลือก object ให้ใช้ active collection จาก Outliner ──
                if context.collection and context.collection.name in bpy.data.collections:
                    col_names.add(context.collection.name)

            for col_name in sorted(col_names):
                # ตรวจซ้ำ
                already = any(
                    i.item_type == 'COLLECTION' and i.collection_name == col_name
                    for i in props.rotation_items
                )
                if already:
                    skipped += 1
                    continue
                new_item = props.rotation_items.add()
                new_item.item_type = 'COLLECTION'
                new_item.collection_name = col_name
                added += 1

            label = "collections"

        # อัปเดต active index
        if len(props.rotation_items) > 0:
            props.rotation_items_index = len(props.rotation_items) - 1

        if added == 0 and skipped == 0:
            self.report({'WARNING'}, "ไม่มีอะไรให้เพิ่ม — เลือก objects ก่อน")
            return {'CANCELLED'}

        msg = f"เพิ่ม {added} {label}"
        if skipped > 0:
            msg += f" (ข้าม {skipped} ซ้ำ)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class TURNTABLE_OT_remove_rotation_item(Operator):
    """ลบ item ที่เลือกออกจากลิสต์"""
    bl_idname = "turntable.remove_rotation_item"
    bl_label = "Remove Item"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.turntable_props
        return len(props.rotation_items) > 0

    def execute(self, context):
        props = context.scene.turntable_props
        idx = props.rotation_items_index

        if idx < 0 or idx >= len(props.rotation_items):
            return {'CANCELLED'}

        item = props.rotation_items[idx]
        name = ""
        if item.item_type == 'OBJECT' and item.target_object:
            name = item.target_object.name
        elif item.item_type == 'COLLECTION':
            name = item.collection_name

        props.rotation_items.remove(idx)
        props.rotation_items_index = min(idx, len(props.rotation_items) - 1)

        self.report({'INFO'}, f"ลบ '{name}' ออกจากลิสต์")
        return {'FINISHED'}


class TURNTABLE_OT_move_rotation_item(Operator):
    """ขยับรายการขึ้น/ลง"""
    bl_idname = "turntable.move_rotation_item"
    bl_label = "Move Item"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        items=[('UP', "Up", ""), ('DOWN', "Down", "")]
    )

    @classmethod
    def poll(cls, context):
        props = context.scene.turntable_props
        return len(props.rotation_items) > 1

    def execute(self, context):
        props = context.scene.turntable_props
        idx = props.rotation_items_index
        items = props.rotation_items

        if self.direction == 'UP' and idx > 0:
            items.move(idx, idx - 1)
            props.rotation_items_index -= 1
        elif self.direction == 'DOWN' and idx < len(items) - 1:
            items.move(idx, idx + 1)
            props.rotation_items_index += 1

        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────
#  Camera Orbit — Step 1: Create / Update Camera
# ─────────────────────────────────────────────────────────────────────

class TURNTABLE_OT_create_camera(Operator):
    """สร้าง/อัพเดทกล้อง — วางตำแหน่งตาม Distance, Height, Tilt(X) และชี้ไปที่ Target"""
    bl_idname = "turntable.create_camera"
    bl_label = "Create / Update Camera"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.turntable_props
        return props.target_object is not None

    def execute(self, context):
        props = context.scene.turntable_props
        target = props.target_object

        if target is None:
            self.report({'ERROR'}, "กรุณาเลือก Target Object ก่อน")
            return {'CANCELLED'}

        cam_obj = _get_or_create_camera(context, props)

        # ── ตำแหน่งกล้อง ──
        target_loc = target.matrix_world.translation.copy()
        cam_obj.location.x = target_loc.x + props.cam_distance
        cam_obj.location.y = target_loc.y
        cam_obj.location.z = target_loc.z + props.cam_height

        # ── ลบ constraint เดิม แล้วเพิ่มใหม่ ──
        _clear_track_to(cam_obj)
        track = cam_obj.constraints.new('TRACK_TO')
        track.name = "TurntableTrack"
        track.target = target
        track.track_axis = 'TRACK_NEGATIVE_Z'
        track.up_axis = 'UP_Y'

        # ── Tilt (X) — เพิ่มมุมก้ม/เงยเพิ่มเติม ──
        cam_obj.rotation_euler = (props.cam_tilt_x, 0, 0)

        # ── ตั้งเป็น active camera ──
        context.scene.camera = cam_obj

        self.report({'INFO'}, f"กล้อง '{cam_obj.name}' พร้อมแล้ว — ชี้ไปที่ '{target.name}'")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────
#  Camera Orbit — Step 2: Start Turntable
# ─────────────────────────────────────────────────────────────────────

class TURNTABLE_OT_start_turntable(Operator):
    """ใส่ keyframe ให้กล้องหมุนรอบ Target Object 360°"""
    bl_idname = "turntable.start_turntable"
    bl_label = "Start Turntable"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.turntable_props
        return (props.target_object is not None and
                props.camera_object is not None)

    def execute(self, context):
        props = context.scene.turntable_props
        target = props.target_object
        cam_obj = props.camera_object
        scene = context.scene

        if target is None or cam_obj is None:
            self.report({'ERROR'}, "กรุณาสร้างกล้องก่อน (Create / Update Camera)")
            return {'CANCELLED'}

        total_frames = props.custom_frames
        fps = props.custom_fps
        target_loc = target.matrix_world.translation.copy()

        # ── สร้างหรือใช้ Empty Pivot ──
        pivot = _find_turntable_empty(cam_obj)
        if pivot is None:
            pivot = bpy.data.objects.new("Turntable_Pivot", None)
            pivot.empty_display_type = 'PLAIN_AXES'
            pivot.empty_display_size = 0.5
            context.collection.objects.link(pivot)

        pivot.location = target_loc
        pivot.rotation_euler = (0, 0, 0)

        # ── Parent กล้อง → Pivot (keep transform) ──
        cam_world = cam_obj.matrix_world.copy()
        cam_obj.parent = pivot
        cam_obj.matrix_world = cam_world

        # ── ลบ animation เก่าของ Pivot (ถ้ามี) ──
        if pivot.animation_data and pivot.animation_data.action:
            try:
                bpy.data.actions.remove(pivot.animation_data.action)
            except Exception:
                pass
            pivot.animation_data_clear()

        # ── Keyframe Pivot rotation Z ──
        pivot.rotation_euler = (0, 0, 0)
        pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=1)

        pivot.rotation_euler.z = math.radians(360)
        pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=total_frames + 1)

        # ── ตั้ง interpolation = LINEAR ──
        _set_fcurve_linear_interpolation(pivot, "rotation_euler", 2)

        # ── ตั้งค่า Scene ──
        scene.render.fps = fps
        scene.frame_start = 1
        scene.frame_end = total_frames
        scene.frame_current = 1

        self.report({'INFO'},
                    f"Turntable พร้อม! {total_frames} frames @ {fps} fps — "
                    f"กล้อง '{cam_obj.name}' หมุนรอบ '{target.name}'")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────
#  Model Rotate — หมุนจากลิสต์ (Object + Collection)
# ─────────────────────────────────────────────────────────────────────

class TURNTABLE_OT_rotate_models(Operator):
    """หมุนทุก item ในลิสต์ — Object หมุนเดี่ยว, Collection หมุนเป็นกลุ่ม"""
    bl_idname = "turntable.rotate_models"
    bl_label = "Rotate All"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.turntable_props
        return len(props.rotation_items) > 0

    def execute(self, context):
        props = context.scene.turntable_props
        scene = context.scene
        total_frames = props.custom_frames
        fps = props.custom_fps
        obj_count = 0
        col_count = 0

        for item in props.rotation_items:
            if item.item_type == 'OBJECT':
                obj = item.target_object
                if obj is None:
                    continue
                _rotate_single_object(obj, total_frames)
                obj_count += 1

            elif item.item_type == 'COLLECTION':
                col = bpy.data.collections.get(item.collection_name)
                if col is None:
                    continue
                _rotate_collection_as_group(context, col, total_frames)
                col_count += 1

        # ── ตั้งค่า Scene ──
        scene.render.fps = fps
        scene.frame_start = 1
        scene.frame_end = total_frames
        scene.frame_current = 1

        self.report({'INFO'},
                    f"หมุน {obj_count} objects + {col_count} collections — "
                    f"{total_frames} frames @ {fps} fps")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────
#  Clear Animation
# ─────────────────────────────────────────────────────────────────────

class TURNTABLE_OT_clear_animation(Operator):
    """ลบ turntable animation ที่สร้างไว้"""
    bl_idname = "turntable.clear_animation"
    bl_label = "Clear Animation"
    bl_options = {'REGISTER', 'UNDO'}

    clear_mode: EnumProperty(
        name="Clear Mode",
        items=[
            ('CAMERA', "Camera Rotate", "ลบ animation ของ Camera Rotate"),
            ('MODELS', "Model Rotate", "ลบ rotation animation ของลิสต์"),
        ],
        default='CAMERA',
    )

    def execute(self, context):
        props = context.scene.turntable_props

        if self.clear_mode == 'CAMERA':
            cam_obj = props.camera_object
            if cam_obj is None:
                self.report({'WARNING'}, "ไม่มีกล้องที่จะ clear")
                return {'CANCELLED'}

            # ── ลบ Pivot Empty + animation ──
            pivot = _find_turntable_empty(cam_obj)
            if pivot:
                cam_world = cam_obj.matrix_world.copy()
                cam_obj.parent = None
                cam_obj.matrix_world = cam_world
                bpy.data.objects.remove(pivot, do_unlink=True)

            # ── ลบ Track To constraint ──
            _clear_track_to(cam_obj)

            # ── ลบ animation ของกล้อง (ถ้ามี) ──
            if cam_obj.animation_data and cam_obj.animation_data.action:
                try:
                    bpy.data.actions.remove(cam_obj.animation_data.action)
                except Exception:
                    pass
                cam_obj.animation_data_clear()

            self.report({'INFO'}, f"ลบ Turntable animation ของกล้อง '{cam_obj.name}' แล้ว")

        else:  # MODELS
            obj_count = 0
            col_count = 0

            for item in props.rotation_items:
                if item.item_type == 'OBJECT':
                    obj = item.target_object
                    if obj and _clear_single_object_animation(obj):
                        obj_count += 1

                elif item.item_type == 'COLLECTION':
                    col = bpy.data.collections.get(item.collection_name)
                    if col and _clear_collection_animation(col):
                        col_count += 1

            self.report({'INFO'},
                        f"ลบ animation ของ {obj_count} objects + {col_count} collections แล้ว")

        return {'FINISHED'}


# =====================================================================
#  GitHub Update Operators
# =====================================================================


class TURNTABLE_OT_check_update(Operator):
    """ตรวจสอบอัปเดตจาก GitHub"""
    bl_idname = "turntable.check_update"
    bl_label = "Check for Updates"

    def execute(self, context):
        global _update_info
        _update_info["error"] = ""
        _update_info["current_version"] = bl_info["version"]

        try:
            req = urllib.request.Request(GITHUB_RAW_URL)
            req.add_header('User-Agent', 'Blender-Addon-Updater')

            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8')

            # Parse version from bl_info
            match = re.search(
                r'"version"\s*:\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
                content
            )
            if match:
                latest = (
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                )
                _update_info["latest_version"] = latest
            else:
                _update_info["error"] = "ไม่สามารถอ่านเวอร์ชันจาก GitHub ได้"
                _update_info["checked"] = True
                bpy.ops.turntable.update_popup('INVOKE_DEFAULT')
                return {'CANCELLED'}

            _update_info["has_update"] = latest > bl_info["version"]
            _update_info["checked"] = True

            # ถ้ามีอัปเดต ให้พยายามดึงข้อมูล CHANGELOG.md มาแสดงด้วย
            if _update_info["has_update"]:
                try:
                    req_cl = urllib.request.Request(GITHUB_CHANGELOG_URL)
                    req_cl.add_header('User-Agent', 'Blender-Addon-Updater')
                    with urllib.request.urlopen(req_cl, timeout=5) as res_cl:
                        cl_content = res_cl.read().decode('utf-8')
                        wrapped_lines = []
                        for line in cl_content.split('\n'):
                            line = line.strip()
                            if not line: continue
                            
                            is_first = True
                            while len(line) > 45:
                                split_at = line.rfind(' ', 0, 45)
                                if split_at <= 0:
                                    split_at = 45
                                
                                chunk = line[:split_at]
                                wrapped_lines.append(chunk if is_first else "  " + chunk)
                                line = line[split_at:].strip()
                                is_first = False
                                
                            if line:
                                wrapped_lines.append(line if is_first else "  " + line)

                        # เก็บข้อความเพื่อไม่ให้ล้น UI
                        _update_info["changelog"] = wrapped_lines[:15]
                except:
                    pass

        except urllib.error.URLError as e:
            _update_info["error"] = f"ไม่สามารถเชื่อมต่อ: {e.reason}"
            _update_info["checked"] = True
        except Exception as e:
            _update_info["error"] = str(e)
            _update_info["checked"] = True

        bpy.ops.turntable.update_popup('INVOKE_DEFAULT')
        return {'FINISHED'}


class TURNTABLE_OT_update_popup(Operator):
    """แสดงข้อมูลเวอร์ชันและอัปเดต"""
    bl_idname = "turntable.update_popup"
    bl_label = "Turntable Camera — Update"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        info = _update_info

        if info["error"]:
            layout.label(text="เกิดข้อผิดพลาด:", icon='ERROR')
            layout.label(text=info["error"])
            return

        if not info["checked"]:
            layout.label(text="ยังไม่ได้ตรวจสอบ", icon='INFO')
            return

        current = ".".join(str(v) for v in info["current_version"])
        latest = ".".join(str(v) for v in info["latest_version"])

        layout.label(text=f"เวอร์ชันปัจจุบัน:  v{current}", icon='PACKAGE')
        layout.label(text=f"เวอร์ชันล่าสุด:      v{latest}", icon='WORLD')

        layout.separator()

        if info["has_update"]:
            box = layout.box()
            box.label(text="มีเวอร์ชันใหม่!", icon='INFO')
            
            # แสดงสิ่งที่อัปเดต (ถ้ามี)
            if info.get("changelog"):
                box.separator()
                box.label(text="What's New:", icon='TEXT')
                col = box.column(align=True)
                for line in info["changelog"]:
                    col.label(text=line)
                box.separator()

            # อธิบายให้ผู้ใช้ทราบว่าอัปเดตเสร็จต้องทำอะไรต่อ
            box.label(text="* เมื่อกด Update Now เสร็จแล้ว", icon='ERROR')
            box.label(text="  โปรด Restart Blender หรือกด F3 พิมพ์ Reload Scripts")
            
            row = box.row()
            row.operator("turntable.do_update",
                         text="Update Now",
                         icon='IMPORT')
        else:
            layout.label(text="เวอร์ชันล่าสุดแล้ว ✓", icon='CHECKMARK')

    def execute(self, context):
        return {'FINISHED'}


class TURNTABLE_OT_do_update(Operator):
    """ดาวน์โหลดและติดตั้งอัปเดตจาก GitHub"""
    bl_idname = "turntable.do_update"
    bl_label = "Update Add-on"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            # ดึงรายการไฟล์จาก GitHub API
            req = urllib.request.Request(GITHUB_API_CONTENTS)
            req.add_header('User-Agent', 'Blender-Addon-Updater')

            with urllib.request.urlopen(req, timeout=15) as response:
                files = json.loads(response.read().decode('utf-8'))

            # หา path ที่ add-on ติดตั้งอยู่
            addon_path = os.path.join(
                bpy.utils.user_resource('SCRIPTS'),
                "addons",
                GITHUB_ADDON_FOLDER,
            )
            os.makedirs(addon_path, exist_ok=True)

            updated_count = 0
            for file_info in files:
                if file_info.get("type") != "file":
                    continue

                file_name = file_info["name"]
                download_url = file_info.get("download_url")
                if not download_url:
                    continue

                req = urllib.request.Request(download_url)
                req.add_header('User-Agent', 'Blender-Addon-Updater')

                with urllib.request.urlopen(req, timeout=15) as response:
                    content = response.read()

                file_path = os.path.join(addon_path, file_name)
                with open(file_path, 'wb') as f:
                    f.write(content)
                updated_count += 1

            self.report(
                {'INFO'},
                f"อัปเดตเสร็จ! ({updated_count} ไฟล์) กรุณา Restart Blender หรือกด F3 พิมพ์ Reload Scripts"
            )

        except Exception as e:
            self.report({'ERROR'}, f"อัปเดตล้มเหลว: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


# =====================================================================
#  UI Panel
# =====================================================================


class TURNTABLE_PT_main_panel(Panel):
    bl_label = "Turntable Camera"
    bl_idname = "TURNTABLE_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Turntable"

    def draw(self, context):
        layout = self.layout
        props = context.scene.turntable_props

        # ── Mode ──
        row = layout.row(align=True)
        row.prop(props, "mode", text="Mode")
        row.operator("turntable.check_update", text="", icon='WORLD')
        layout.separator()

        # ── Preset ──
        box = layout.box()
        box.label(text="Preset", icon='PRESET')
        split = box.split(factor=0.75, align=True)
        split.prop(props, "preset", text="")
        split.operator("turntable.apply_preset", text="Apply")
        box.separator(factor=0.5)

        # แสดง FPS / Frames (แก้ไขได้)
        row = box.row(align=True)
        row.prop(props, "custom_fps", text="FPS")
        row.prop(props, "custom_frames", text="Frames")

        # แสดง info ของ preset
        preset_data = PRESETS.get(props.preset)
        if preset_data:
            box.label(text=preset_data['desc'], icon='INFO')

        layout.separator()

        # ── Camera Rotate Mode ──
        if props.mode == 'CAMERA_ROTATE':
            box = layout.box()
            box.label(text="Camera Rotate Settings", icon='OUTLINER_OB_CAMERA')

            box.prop(props, "target_object", text="Target", icon='OBJECT_DATA')
            box.prop(props, "camera_object", text="Camera", icon='CAMERA_DATA')
            box.separator(factor=0.5)

            col = box.column(align=True)
            col.prop(props, "cam_distance", text="Distance")
            col.prop(props, "cam_height", text="Height")
            col.prop(props, "cam_tilt_x", text="Tilt (X)")

            box.separator(factor=0.5)

            # Step 1: Create Camera
            row = box.row(align=True)
            row.scale_y = 1.4
            row.operator("turntable.create_camera",
                         text="Create / Update Camera",
                         icon='OUTLINER_OB_CAMERA')

            # Step 2: Start Turntable
            row = box.row(align=True)
            row.scale_y = 1.4
            can_start = (props.target_object is not None and
                         props.camera_object is not None)
            row.enabled = can_start
            row.operator("turntable.start_turntable",
                         text="Start Turntable",
                         icon='PLAY')

            # Clear
            box.separator(factor=0.5)
            row = box.row()
            op = row.operator("turntable.clear_animation",
                              text="Clear Animation",
                              icon='TRASH')
            op.clear_mode = 'CAMERA'

        # ── Model Rotate Mode ──
        else:
            box = layout.box()
            box.label(text="Model Rotate Settings", icon='OBJECT_DATA')

            # ── Add Mode ──
            row = box.row(align=True)
            row.prop(props, "add_mode", expand=True)

            box.separator(factor=0.5)

            # ── UIList ──
            row = box.row()
            row.template_list(
                "TURNTABLE_UL_rotation_items", "",
                props, "rotation_items",
                props, "rotation_items_index",
                rows=4,
            )

            # ── ปุ่มข้างลิสต์ ──
            col = row.column(align=True)
            col.operator("turntable.add_selected", icon='ADD', text="")
            col.operator("turntable.remove_rotation_item", icon='REMOVE', text="")
            col.separator()
            op_up = col.operator("turntable.move_rotation_item", icon='TRIA_UP', text="")
            op_up.direction = 'UP'
            op_down = col.operator("turntable.move_rotation_item", icon='TRIA_DOWN', text="")
            op_down.direction = 'DOWN'

            box.separator(factor=0.5)

            # ── Info ──
            item_count = len(props.rotation_items)
            obj_count = sum(1 for i in props.rotation_items if i.item_type == 'OBJECT')
            col_count = sum(1 for i in props.rotation_items if i.item_type == 'COLLECTION')
            box.label(text=f"Items: {item_count}  (Objects: {obj_count} / Collections: {col_count})",
                      icon='INFO')

            box.separator(factor=0.5)

            # ── Rotate All ──
            row = box.row(align=True)
            row.scale_y = 1.4
            row.enabled = item_count > 0
            row.operator("turntable.rotate_models",
                         text="Rotate All",
                         icon='PLAY')

            # ── Clear ──
            box.separator(factor=0.5)
            row = box.row()
            row.enabled = item_count > 0
            op = row.operator("turntable.clear_animation",
                              text="Clear All Animation",
                              icon='TRASH')
            op.clear_mode = 'MODELS'


# =====================================================================
#  Registration
# =====================================================================

classes = (
    TURNTABLE_RotationItem,
    TURNTABLE_Properties,
    TURNTABLE_UL_rotation_items,
    TURNTABLE_OT_apply_preset,
    TURNTABLE_OT_add_selected,
    TURNTABLE_OT_remove_rotation_item,
    TURNTABLE_OT_move_rotation_item,
    TURNTABLE_OT_create_camera,
    TURNTABLE_OT_start_turntable,
    TURNTABLE_OT_rotate_models,
    TURNTABLE_OT_clear_animation,
    TURNTABLE_OT_check_update,
    TURNTABLE_OT_update_popup,
    TURNTABLE_OT_do_update,
    TURNTABLE_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.turntable_props = PointerProperty(type=TURNTABLE_Properties)


def unregister():
    del bpy.types.Scene.turntable_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
