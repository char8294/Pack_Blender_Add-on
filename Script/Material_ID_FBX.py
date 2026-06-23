import bpy
import bmesh
import os

input_folder  = r"C:\Users\Smart Office\Desktop\Plugin\Python\Material_ID_FBX\Input"
output_folder = r"C:\Users\Smart Office\Desktop\Plugin\Python\Material_ID_FBX\Output"

def clear_scene():
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

def remove_empty_objects():
    empties = [obj for obj in bpy.data.objects if obj.type == 'EMPTY']
    for obj in empties:
        print(f"  🗑️ ลบ Empty: {obj.name}")
        bpy.data.objects.remove(obj, do_unlink=True)
    print(f"  ✅ ลบ Empty objects ทั้งหมด: {len(empties)} objects")

def remove_unused_bones(armature_obj, mesh_objects):
    used_bones = set()
    for mesh_obj in mesh_objects:
        for vg in mesh_obj.vertex_groups:
            for vert in mesh_obj.data.vertices:
                for g in vert.groups:
                    if g.group == vg.index and g.weight > 0:
                        used_bones.add(vg.name)
                        break
    
    print(f"  🦴 Bones ที่มี skin weight: {len(used_bones)}")
    
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    bones_to_remove = []
    for bone in armature_obj.data.edit_bones:
        if bone.name not in used_bones:
            bones_to_remove.append(bone.name)
    
    for bone_name in bones_to_remove:
        bone = armature_obj.data.edit_bones.get(bone_name)
        if bone:
            armature_obj.data.edit_bones.remove(bone)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"  ✅ ลบ bone ที่ไม่มี skin weight: {len(bones_to_remove)} bones")

def shade_smooth_and_clear_sharp(mesh_objects):
    for obj in mesh_objects:
        bpy.context.view_layer.objects.active = obj
        
        # Shade Smooth
        bpy.ops.object.shade_smooth()
        
        # Clear Sharp edges
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.mark_sharp(clear=True)
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Clear custom split normals
        if obj.data.has_custom_normals:
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        
        print(f"  ✅ Shade Smooth + Clear Sharp: {obj.name}")

# หาไฟล์ .fbx ทุกไฟล์รวมถึงใน subfolder
fbx_files = []
for root, dirs, files in os.walk(input_folder):
    for file in files:
        if file.lower().endswith(".fbx"):
            fbx_files.append(os.path.join(root, file))

print(f"พบไฟล์ทั้งหมด {len(fbx_files)} ไฟล์")

for input_path in fbx_files:
    relative_path = os.path.relpath(input_path, input_folder)
    output_path   = os.path.join(output_folder, relative_path)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"\n🔄 กำลังประมวลผล: {relative_path}")
    
    clear_scene()
    
    bpy.ops.import_scene.fbx(filepath=input_path)
    
    # ลบ Empty objects ทั้งหมด
    remove_empty_objects()
    
    # แยก mesh objects และ armature objects
    mesh_objects     = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    armature_objects = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    
    # ลบ bone ที่ไม่มี skin weight
    for armature_obj in armature_objects:
        remove_unused_bones(armature_obj, mesh_objects)
    
    for obj in mesh_objects:
        # หา SKIN_body
        skin_index = -1
        for i, slot in enumerate(obj.material_slots):
            if slot.material and "SKIN_body" in slot.material.name:
                skin_index = i
                break
        
        if skin_index == -1:
            print(f"  ⚠️ ไม่พบ SKIN_body ใน {obj.name}")
            continue
        
        if skin_index == 0:
            print(f"  ✅ SKIN_body อยู่ slot 0 แล้ว")
        else:
            # Step 1: แก้ face index ก่อนสลับ slot
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(obj.data)
            
            for face in bm.faces:
                if face.material_index == 0:
                    face.material_index = skin_index
                elif face.material_index == skin_index:
                    face.material_index = 0
            
            bmesh.update_edit_mesh(obj.data)
            bpy.ops.object.mode_set(mode='OBJECT')
            print(f"  ✅ Step1: แก้ face index สำเร็จ")
            
            # Step 2: สลับ material slot
            mat_0    = obj.material_slots[0].material
            mat_skin = obj.material_slots[skin_index].material
            obj.material_slots[0].material          = mat_skin
            obj.material_slots[skin_index].material = mat_0
            print(f"  ✅ Step2: ย้าย SKIN_body → slot 0")
        
        # Step 3: Sort Elements by Material
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.sort_elements(type='MATERIAL', elements={'FACE'})
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"  ✅ Step3: Sort Elements by Material")
    
    # Step 4: Shade Smooth + Clear Sharp
    shade_smooth_and_clear_sharp(mesh_objects)
    
    # Export FBX
    bpy.ops.export_scene.fbx(
        filepath=output_path,
        use_selection=False,
        add_leaf_bones=False
    )
    
    print(f"  💾 บันทึกแล้ว → {output_path}")

print("\n✅ เสร็จสิ้นทั้งหมด!")