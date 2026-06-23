"""
Batch FBX Re-Export with Shade Smooth — Blender 5
==================================================
- Clear scene ก่อนเริ่มทุกครั้ง
- Import/Export ใช้ค่า default เหมือน RunOnBlender.py
- Shade Smooth + Clear Custom Split Normals ทุก mesh
- ไม่แตะ transform / scale ใดๆ
"""

import bpy
import os

# ─── CONFIG ──────────────────────────────────────────────────────────────────
INPUT_DIR  = r"C:\Users\Smart Office\Desktop\Plugin\Python\ReExport_NPC\Input"
OUTPUT_DIR = r"C:\Users\Smart Office\Desktop\Plugin\Python\ReExport_NPC\Output"
# ─────────────────────────────────────────────────────────────────────────────


def clear_scene():
    """ลบทุกอย่างใน scene อย่างละเอียด"""
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for armature in bpy.data.armatures:
        bpy.data.armatures.remove(armature)
    for texture in bpy.data.textures:
        bpy.data.textures.remove(texture)
    for image in bpy.data.images:
        bpy.data.images.remove(image)
    for action in bpy.data.actions:
        bpy.data.actions.remove(action)
    for collection in bpy.data.collections:
        bpy.data.collections.remove(collection)
    print("  🧹 Clear scene สำเร็จ")


def apply_shade_smooth():
    """Shade Smooth + Clear Custom Split Normals ทุก mesh ใน scene"""
    mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    for obj in mesh_objects:
        bpy.context.view_layer.objects.active = obj

        # Shade Smooth
        bpy.ops.object.shade_smooth()

        # Clear Sharp edges + Custom Split Normals (ต้องอยู่ใน Edit Mode)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.mark_sharp(clear=True)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Clear custom split normals (ถ้ามี) — ทำให้ Shade Smooth มีผลจริง
        if obj.data.has_custom_normals:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
            print(f"  ✅ Shade Smooth + Clear Custom Normals: {obj.name}")
        else:
            print(f"  ✅ Shade Smooth: {obj.name}")


def collect_fbx_files(root_dir):
    """คืน list ของ abs_path ทุกไฟล์ .fbx ใต้ root_dir"""
    results = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.lower().endswith(".fbx"):
                results.append(os.path.join(dirpath, fname))
    return results


def main():
    print("=" * 60)
    print("Batch FBX Re-Export with Shade Smooth")
    print(f"Input  : {INPUT_DIR}")
    print(f"Output : {OUTPUT_DIR}")
    print("=" * 60)

    # ── Clear scene ก่อนเริ่มงานทั้งหมด ──
    print("\n🧹 Clear scene ก่อนเริ่ม...")
    clear_scene()

    fbx_files = collect_fbx_files(INPUT_DIR)

    if not fbx_files:
        print("[WARN] ไม่พบไฟล์ .fbx ใน Input folder เลย")
        return

    total   = len(fbx_files)
    success = 0
    failed  = []

    print(f"พบไฟล์ทั้งหมด {total} ไฟล์\n")

    for i, input_path in enumerate(fbx_files, 1):
        relative_path = os.path.relpath(input_path, INPUT_DIR)
        output_path   = os.path.join(OUTPUT_DIR, relative_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        print(f"[{i}/{total}] 🔄 กำลังประมวลผล: {relative_path}")

        try:
            # Clear scene ก่อน import ทุกไฟล์
            clear_scene()

            # Import — default settings
            bpy.ops.import_scene.fbx(filepath=input_path)

            # Shade Smooth + Clear Custom Split Normals
            apply_shade_smooth()

            # Export — default settings + add_leaf_bones=False
            bpy.ops.export_scene.fbx(
                filepath       = output_path,
                use_selection  = False,
                add_leaf_bones = False,
            )

            print(f"  💾 บันทึกแล้ว → {output_path}")
            success += 1

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed.append((input_path, str(e)))

    print("\n" + "=" * 60)
    print(f"✅ เสร็จสิ้น — {success}/{total} ไฟล์สำเร็จ")
    if failed:
        print(f"❌ ล้มเหลว ({len(failed)}):")
        for path, err in failed:
            print(f"  {path}\n    → {err}")
    print("=" * 60)


main()
