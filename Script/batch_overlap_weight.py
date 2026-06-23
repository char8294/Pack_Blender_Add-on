"""
batch_overlap_weight.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
วางไฟล์นี้ในโฟลเดอร์ที่มีโครงสร้างดังนี้:

  📁 (root)
  ├── batch_overlap_weight.py   ← ไฟล์นี้
  ├── 📁 SkinVolume
  │     └── SkinVolume.fbx
  ├── 📁 InputFBX
  │     ├── charA.fbx
  │     ├── charB.fbx
  │     └── ...
  └── 📁 OutputFBX
        └── (ผลลัพธ์จะถูก export มาที่นี่)

ไม่ต้องแก้ไข config ใดๆ ทั้งสิ้น
ไม่มีการ Apply Scale หรือแก้ไข Transform ใดๆ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import bpy
import os
from mathutils.bvhtree import BVHTree
from mathutils import Vector

# ── Resolve paths relative to this script file ───────────
# __file__ ใช้ไม่ได้ใน Blender Text Editor
# ดึง path จาก Text block ที่กำลัง run อยู่แทน
def _get_script_dir() -> str:
    # วิธี 1: ดึงจาก Text block ที่ active อยู่ใน Text Editor
    for area in bpy.context.screen.areas:
        if area.type == 'TEXT_EDITOR':
            text = area.spaces.active.text
            if text and text.filepath:
                return os.path.dirname(os.path.abspath(text.filepath))

    # วิธี 2: วนหา Text block ใน bpy.data.texts ที่มี filepath
    for text in bpy.data.texts:
        if text.filepath:
            return os.path.dirname(os.path.abspath(text.filepath))

    # วิธี 3: fallback — ใช้ที่อยู่ของ .blend file (ถ้า save แล้ว)
    blend_path = bpy.data.filepath
    if blend_path:
        return os.path.dirname(os.path.abspath(blend_path))

    raise RuntimeError(
        "❌ ไม่สามารถหา Script Directory ได้\n"
        "   วิธีแก้: Save script ลงดิสก์ก่อน แล้วกด Run Script\n"
        "   (Text Editor → ไอคอน Save หรือ Alt+S)"
    )

_SCRIPT_DIR = _get_script_dir()

FOLDER_INPUT     = os.path.join(_SCRIPT_DIR, "InputFBX")
FOLDER_OUTPUT    = os.path.join(_SCRIPT_DIR, "OutputFBX")
SKIN_VOLUME_PATH = os.path.join(_SCRIPT_DIR, "SkinVolume", "SkinVolume.fbx")

# ══════════════════════════════════════════════════════════
#  ⚙️  CONFIG (ไม่จำเป็นต้องแก้)
# ══════════════════════════════════════════════════════════
ARMATURE_NAME       = "Bip001"
SKIN_VOLUME_KEYWORD = "SkinVolume"
TARGET_VG_NAME      = "Bip001 Neck"
WEIGHT_VALUE        = 1.0
# ══════════════════════════════════════════════════════════


# ────────────────────────────────────────────────────────
#  UTILITIES
# ────────────────────────────────────────────────────────

def find_mesh_by_armature(armature_name: str):
    """คืน list ของ Mesh Object ที่มี Armature Modifier ชี้ไปยัง armature_name"""
    arm_obj = bpy.data.objects.get(armature_name)
    if arm_obj is None:
        # Blender อาจเติม .001 ต่อท้ายหลัง import ซ้ำ — ค้นหา fallback
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE' and ARMATURE_NAME in obj.name:
                arm_obj = obj
                break
    if arm_obj is None:
        return []

    results = []
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == arm_obj:
                results.append(obj)
                break
    return results, arm_obj


def find_skin_volume_obj(keyword: str):
    """ค้นหา Object ที่ชื่อมี keyword (case-insensitive)"""
    kw = keyword.lower()
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and kw in obj.name.lower():
            return obj
    return None


def is_inside_mesh(point: Vector, bvh: BVHTree) -> bool:
    """
    Ray Casting Odd-Even Rule
    ยิง ray แกน +Z นับ face ชน — จำนวนคี่ = อยู่ภายใน
    """
    direction = Vector((0.0, 0.0, 1.0))
    origin    = point.copy()
    hits      = 0
    while True:
        loc, _, idx, _ = bvh.ray_cast(origin, direction)
        if idx is None:
            break
        hits  += 1
        origin = loc + direction * 1e-5
    return (hits % 2) == 1


def auto_normalize(obj, changed_vg_name: str):
    """
    Auto Normalize weights:
    สำหรับทุก vertex ที่มี weight ใน changed_vg_name
    ลด weight group อื่นตามสัดส่วน ให้ผลรวม = 1.0
    ไม่แตะ Transform / Scale ใดๆ
    """
    vgs        = obj.vertex_groups
    target_vg  = vgs.get(changed_vg_name)
    if target_vg is None:
        return
    target_idx = target_vg.index

    for v in obj.data.vertices:
        target_w   = 0.0
        has_target = False
        for g in v.groups:
            if g.group == target_idx:
                target_w   = g.weight
                has_target = True
                break
        if not has_target or target_w == 0.0:
            continue

        others       = [(g.group, g.weight) for g in v.groups if g.group != target_idx]
        other_total  = sum(w for _, w in others)
        if other_total == 0.0:
            continue

        remaining = max(0.0, 1.0 - target_w)
        scale     = remaining / other_total

        for gidx, gw in others:
            for vg in vgs:
                if vg.index == gidx:
                    vg.add([v.index], gw * scale, 'REPLACE')
                    break


# ────────────────────────────────────────────────────────
#  CORE PROCESS
# ────────────────────────────────────────────────────────

def process_weight(obj_a, bvh):
    """Set weight + Auto Normalize สำหรับ 1 Mesh Object"""
    # สร้าง Vertex Group ถ้ายังไม่มี
    vg = obj_a.vertex_groups.get(TARGET_VG_NAME)
    if vg is None:
        vg = obj_a.vertex_groups.new(name=TARGET_VG_NAME)

    mat_a          = obj_a.matrix_world
    inside_indices = []

    for v in obj_a.data.vertices:
        if is_inside_mesh(mat_a @ v.co, bvh):
            inside_indices.append(v.index)

    if inside_indices:
        vg.add(inside_indices, WEIGHT_VALUE, 'REPLACE')
        auto_normalize(obj_a, TARGET_VG_NAME)
        print(f"      ✅ {len(inside_indices)} vertices → weight {WEIGHT_VALUE} (normalized)")
    else:
        print(f"      ⚠️  ไม่มี vertex อยู่ใน SkinVolume")

    obj_a.data.update()


def get_objects_from_armature(arm_obj):
    """คืน set ของ Object ทั้งหมดที่เกี่ยวข้องกับ Armature (arm + meshes)"""
    related = {arm_obj}
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == arm_obj:
                related.add(obj)
                break
    return related


def clear_scene_except(keep_objects: set):
    """ลบ Object ทุกตัวที่ไม่อยู่ใน keep_objects พร้อม data block"""
    to_delete = [obj for obj in bpy.data.objects if obj not in keep_objects]
    for obj in to_delete:
        bpy.data.objects.remove(obj, do_unlink=True)

    # Purge orphan data
    bpy.ops.outliner.orphans_purge(do_recursive=True)


def export_fbx(arm_obj, mesh_objects, output_path: str):
    """
    Select เฉพาะ Armature + Mesh ที่เกี่ยวข้อง แล้ว Export FBX
    ไม่ใช้ Apply Transform ใดๆ
    """
    # Deselect ทั้งหมดก่อน
    bpy.ops.object.select_all(action='DESELECT')

    # Select เฉพาะ objects ที่ต้องการ export
    for obj in mesh_objects:
        obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj

    bpy.ops.export_scene.fbx(
        filepath            = output_path,
        use_selection       = True,
        apply_unit_scale    = False,
        apply_scale_options = 'FBX_SCALE_NONE',   # ไม่แตะ Scale เลย
        bake_space_transform= False,
        add_leaf_bones      = False,
        path_mode           = 'AUTO',
    )
    print(f"      💾 Export → {output_path}")


# ────────────────────────────────────────────────────────
#  MAIN BATCH LOOP
# ────────────────────────────────────────────────────────

def main():
    # ── ตรวจ folder ──────────────────────────────────────
    if not os.path.isdir(FOLDER_INPUT):
        raise FileNotFoundError(f"❌ ไม่พบ folder input: {FOLDER_INPUT}")
    if not os.path.isfile(SKIN_VOLUME_PATH):
        raise FileNotFoundError(f"❌ ไม่พบไฟล์: {SKIN_VOLUME_PATH}")
    os.makedirs(FOLDER_OUTPUT, exist_ok=True)

    # ── เก็บ Object เดิมทั้งหมดที่อยู่ใน Scene ──────────
    # (เพื่อจะได้รู้ว่า import มาใหม่อะไรบ้าง)

    # ── Import SkinVolume.fbx ครั้งเดียว ─────────────────
    print("📦 Import SkinVolume.fbx ...")
    before_import = set(bpy.data.objects[:])
    bpy.ops.import_scene.fbx(filepath=SKIN_VOLUME_PATH)
    after_import  = set(bpy.data.objects[:])

    skin_vol_obj = find_skin_volume_obj(SKIN_VOLUME_KEYWORD)
    if skin_vol_obj is None:
        raise ValueError(
            f"❌ Import SkinVolume สำเร็จแต่ไม่พบ Object ที่ชื่อมี '{SKIN_VOLUME_KEYWORD}'\n"
            f"   Object ที่ import มา: {[o.name for o in (after_import - before_import)]}"
        )
    print(f"   ✅ SkinVolume Object: '{skin_vol_obj.name}'")

    # Objects ของ SkinVolume ทั้งหมด (อาจมีหลายชิ้น)
    skin_vol_objects = after_import - before_import

    # ── สร้าง BVHTree จาก SkinVolume ─────────────────────
    depsgraph      = bpy.context.evaluated_depsgraph_get()
    skin_vol_eval  = skin_vol_obj.evaluated_get(depsgraph)
    bvh            = BVHTree.FromObject(skin_vol_eval, depsgraph)
    skin_vol_eval.to_mesh_clear()
    print(f"   ✅ BVHTree สร้างแล้ว\n")

    # ── รวบรวมไฟล์ FBX ใน input folder ──────────────────
    fbx_files = sorted([
        f for f in os.listdir(FOLDER_INPUT)
        if f.lower().endswith('.fbx')
    ])
    if not fbx_files:
        print(f"⚠️  ไม่พบไฟล์ .fbx ใน {FOLDER_INPUT}")
        return

    print(f"📂 พบ {len(fbx_files)} ไฟล์ใน input folder\n")
    print("=" * 60)

    # ── วนทุกไฟล์ FBX ────────────────────────────────────
    for i, fbx_filename in enumerate(fbx_files, 1):
        fbx_path = os.path.join(FOLDER_INPUT, fbx_filename)
        print(f"[{i}/{len(fbx_files)}] 📄 {fbx_filename}")

        # ── Import FBX ────────────────────────────────────
        before = set(bpy.data.objects[:])
        bpy.ops.import_scene.fbx(filepath=fbx_path)
        after  = set(bpy.data.objects[:])
        new_objects = after - before
        print(f"   Import Objects: {[o.name for o in new_objects]}")

        # ── ค้นหา Mesh ที่ผูกกับ Bip001 ──────────────────
        result = find_mesh_by_armature(ARMATURE_NAME)

        if not result or not result[0]:
            print(f"   ⚠️  ไม่พบ Mesh ที่ผูกกับ Armature '{ARMATURE_NAME}' — ข้ามไฟล์นี้")
            # Clear objects ที่ import มาใหม่
            clear_scene_except(skin_vol_objects)
            print()
            continue

        mesh_list, arm_obj = result
        print(f"   🦴 Armature: '{arm_obj.name}'")
        print(f"   🧊 Mesh(es): {[o.name for o in mesh_list]}")

        # ── Refresh depsgraph ─────────────────────────────
        depsgraph = bpy.context.evaluated_depsgraph_get()

        # ── Process Weight ทุก Mesh ───────────────────────
        for mesh_obj in mesh_list:
            print(f"   ⚙️  Processing '{mesh_obj.name}' ...")
            process_weight(mesh_obj, bvh)

        # ── ตั้งชื่อ Output FBX จากชื่อ Mesh แรก ─────────
        # ถ้ามีหลาย Mesh ใช้ชื่อ Mesh แรก (body mesh มักเป็นตัวหลัก)
        export_name = mesh_list[0].name
        # ตัด suffix ที่ Blender เติมให้ เช่น ".001"
        if '.' in export_name:
            base, suffix = export_name.rsplit('.', 1)
            if suffix.isdigit():
                export_name = base

        output_path = os.path.join(FOLDER_OUTPUT, export_name + ".fbx")

        # ── Export ────────────────────────────────────────
        export_fbx(arm_obj, mesh_list, output_path)

        # ── Clear Scene (เก็บแค่ SkinVolume) ─────────────
        clear_scene_except(skin_vol_objects)
        print(f"   🗑️  Scene cleared\n")

    print("=" * 60)
    print(f"🎉 Batch เสร็จสมบูรณ์! Export ไปที่: {FOLDER_OUTPUT}")


# ── Entry Point ───────────────────────────────────────────
if __name__ == "__main__":
    main()
