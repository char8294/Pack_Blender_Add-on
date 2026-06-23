import bpy
import os
import sys
import json
import re
import urllib.request
import urllib.error

bl_info = {
    "name": "Kenji Export",
    "author": "Gemini CLI",
    "version": (1, 3, 3),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Kenji Export Tab",
    "description": "Batch export meshes with pinned armature using Kenji Export (Better FBX).",
    "category": "Import-Export",
}

# =====================================================================
#  GitHub Update Config
# =====================================================================

GITHUB_OWNER = "char8294"
GITHUB_REPO = "Pack_Blender_Add-on"
GITHUB_ADDON_FOLDER = "kenji_export"
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

def get_preset_path():
    appdata = os.getenv('APPDATA')
    if not appdata:
        return ""
    base_path = os.path.join(appdata, "Blender Foundation", "Blender")
    version = f"{bpy.app.version[0]}.{bpy.app.version[1]}"
    preset_dir = os.path.join(base_path, version, "scripts", "presets", "operator", "better_export.fbx")
    return preset_dir

def get_presets(self, context):
    preset_dir = get_preset_path()
    items = [("NONE", "No Preset", "Do not use a specific preset")]
    if os.path.exists(preset_dir):
        for f in os.listdir(preset_dir):
            if f.endswith(".py"):
                name = f[:-3]
                items.append((name, name, f"Use {name} preset"))
    return items

class BATCH_FBX_MeshItem(bpy.types.PropertyGroup):
    obj: bpy.props.PointerProperty(type=bpy.types.Object, name="Mesh")

class BATCH_FBX_Properties(bpy.types.PropertyGroup):
    export_dir: bpy.props.StringProperty(
        name="Export Directory",
        description="Select folder to export files",
        default="",
        maxlen=1024,
        subtype='DIR_PATH'
    )
    preset_enum: bpy.props.EnumProperty(
        name="Preset",
        description="Select Better FBX preset to use",
        items=get_presets
    )
    target_armature: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Armature",
        description="Pin the armature to pair with the meshes",
        poll=lambda self, object: object.type == 'ARMATURE'
    )
    mesh_list: bpy.props.CollectionProperty(type=BATCH_FBX_MeshItem)
    mesh_list_index: bpy.props.IntProperty()
    force_shade_smooth: bpy.props.BoolProperty(
        name="Force Shade Smooth",
        description="Clear sharp edges/custom normals and apply smooth shading for the exported file only",
        default=False
    )
    restore_biped_names: bpy.props.BoolProperty(
        name="Restore Biped Names",
        description="Export with original Biped bone names (restore from biped_name_mapping)",
        default=False
    )

class BATCH_FBX_UL_mesh_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if item.obj:
                layout.label(text=item.obj.name, icon='MESH_DATA')
            else:
                layout.label(text="<Deleted Object>", icon='ERROR')

class BATCH_FBX_OT_add_meshes(bpy.types.Operator):
    bl_idname = "export.batch_better_fbx_add_mesh"
    bl_label = "Add Selected Meshes"
    bl_description = "Add currently selected meshes to the export list"
    
    def execute(self, context):
        props = context.scene.batch_better_fbx_props
        selected = context.selected_objects
        added = 0
        
        existing_objs = [item.obj for item in props.mesh_list if item.obj]
        
        for obj in selected:
            if obj.type == 'MESH' and obj not in existing_objs:
                item = props.mesh_list.add()
                item.obj = obj
                added += 1
                
        if added > 0:
            self.report({'INFO'}, f"Added {added} meshes to the list.")
        else:
            self.report({'WARNING'}, "No new meshes selected.")
            
        return {'FINISHED'}

class BATCH_FBX_OT_remove_mesh(bpy.types.Operator):
    bl_idname = "export.batch_better_fbx_remove_mesh"
    bl_label = "Remove Mesh"
    bl_description = "Remove the selected mesh from the export list"
    
    def execute(self, context):
        props = context.scene.batch_better_fbx_props
        index = props.mesh_list_index
        
        if len(props.mesh_list) > 0 and 0 <= index < len(props.mesh_list):
            props.mesh_list.remove(index)
            if props.mesh_list_index >= len(props.mesh_list):
                props.mesh_list_index = max(0, len(props.mesh_list) - 1)
                
        return {'FINISHED'}

class BATCH_FBX_OT_clear_meshes(bpy.types.Operator):
    bl_idname = "export.batch_better_fbx_clear_meshes"
    bl_label = "Clear List"
    bl_description = "Clear all meshes from the export list"
    
    def execute(self, context):
        props = context.scene.batch_better_fbx_props
        props.mesh_list.clear()
        return {'FINISHED'}

class BATCH_FBX_OT_export(bpy.types.Operator):
    bl_idname = "export.batch_better_fbx"
    bl_label = "Batch Export FBX"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.batch_better_fbx_props
        export_dir = bpy.path.abspath(props.export_dir)

        if not export_dir:
            self.report({'ERROR'}, "Please select an export directory.")
            return {'CANCELLED'}

        if not os.path.exists(export_dir):
            try:
                os.makedirs(export_dir)
            except Exception as e:
                self.report({'ERROR'}, f"Could not create directory: {str(e)}")
                return {'CANCELLED'}

        armature = props.target_armature
        if not armature:
            self.report({'ERROR'}, "Please pin a Target Armature.")
            return {'CANCELLED'}

        if len(props.mesh_list) == 0:
            self.report({'ERROR'}, "The export list is empty. Please add meshes.")
            return {'CANCELLED'}

        meshes = []
        for item in props.mesh_list:
            if item.obj and item.obj.type == 'MESH':
                meshes.append(item.obj)
                
        if not meshes:
            self.report({'ERROR'}, "Export list contains no valid meshes.")
            return {'CANCELLED'}

        preset_params = {}
        if props.preset_enum != "NONE":
            preset_path = os.path.join(get_preset_path(), props.preset_enum + ".py")
            if os.path.exists(preset_path):
                class MockOp:
                    pass
                mock_op = MockOp()
                try:
                    with open(preset_path, 'r') as f:
                        code = f.read()
                        code = code.replace("op = bpy.context.active_operator", "op = mock_op")
                        exec(code, {"bpy": bpy, "mock_op": mock_op})
                        for attr in dir(mock_op):
                            if not attr.startswith("__") and attr != "filepath":
                                preset_params[attr] = getattr(mock_op, attr)
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to load preset: {str(e)}")

        original_active = context.view_layer.objects.active
        original_selected = list(context.selected_objects)
        force_smooth = props.force_shade_smooth
        restore_biped = props.restore_biped_names

        # --- Duplicate Armature if Restore Biped Names is enabled ---
        temp_armature = None
        export_armature = armature
        bone_mapping = None

        if restore_biped and armature.type == 'ARMATURE' and "biped_name_mapping" in armature.data:
            bone_mapping = json.loads(armature.data["biped_name_mapping"])
            if bone_mapping:
                # Create a full independent copy of the armature
                temp_arm_data = armature.data.copy()
                temp_armature = armature.copy()
                temp_armature.data = temp_arm_data
                # Clear animation data so bone rename won't corrupt shared Actions
                if temp_armature.animation_data:
                    temp_armature.animation_data_clear()
                # Link to scene so it can be exported
                context.collection.objects.link(temp_armature)
                # Rename bones back to original names on the COPY
                for new_name, old_name in bone_mapping.items():
                    bone = temp_arm_data.bones.get(new_name)
                    if bone:
                        bone.name = old_name
                export_armature = temp_armature

        # --- Export each mesh ---
        count = 0
        errors = []
        for mesh in meshes:
            bpy.ops.object.select_all(action='DESELECT')
            
            temp_mesh = None
            export_mesh = mesh
            original_name = mesh.name
            need_duplicate = force_smooth or restore_biped
            
            if need_duplicate:
                # Duplicate the mesh
                mesh.select_set(True)
                context.view_layer.objects.active = mesh
                bpy.ops.object.duplicate(linked=False)
                export_mesh = context.active_object
                temp_mesh = export_mesh
                
                # --- Force Shade Smooth (on duplicate) ---
                if force_smooth:
                    if temp_mesh.data.has_custom_normals:
                        try:
                            bpy.ops.mesh.customdata_custom_splitnormals_clear()
                        except:
                            pass
                    
                    # Remove modifiers that generate sharp edges dynamically
                    for mod in list(temp_mesh.modifiers):
                        is_smooth_nodes = (mod.type == 'NODES' and mod.node_group and "Smooth by Angle" in mod.node_group.name)
                        is_smooth_name = ("Smooth by Angle" in mod.name)
                        is_edge_split = (mod.type == 'EDGE_SPLIT')
                        
                        if is_smooth_nodes or is_smooth_name or is_edge_split:
                            temp_mesh.modifiers.remove(mod)
                    
                    temp_mesh.data.polygons.foreach_set("use_smooth", [True] * len(temp_mesh.data.polygons))
                    for edge in temp_mesh.data.edges:
                        edge.use_edge_sharp = False
                    temp_mesh.data.update()
                
                # --- Restore Biped Vertex Group Names (on duplicate) ---
                if restore_biped and bone_mapping:
                    # Use biped_vg_mapping if available, else use bone_mapping as fallback
                    vg_mapping = bone_mapping
                    if "biped_vg_mapping" in mesh:
                        try:
                            vg_mapping = json.loads(mesh["biped_vg_mapping"])
                        except:
                            pass
                    for new_name, old_name in vg_mapping.items():
                        vg = temp_mesh.vertex_groups.get(new_name)
                        if vg:
                            vg.name = old_name
                    # Update armature modifier to point to temp armature
                    if temp_armature:
                        for mod in temp_mesh.modifiers:
                            if mod.type == 'ARMATURE' and mod.object == armature:
                                mod.object = temp_armature
                
                # Fix naming so FBX internal nodes are correct
                mesh.name = original_name + "_temp_export"
                export_mesh.name = original_name
                
                bpy.ops.object.select_all(action='DESELECT')
            
            # Select armature and mesh for export
            export_armature.select_set(True)
            export_mesh.select_set(True)
            context.view_layer.objects.active = export_mesh
            
            filename = original_name + ".fbx"
            filepath = os.path.join(export_dir, filename)
            
            export_kwargs = preset_params.copy()
            export_kwargs["filepath"] = filepath
            export_kwargs["use_selection"] = True
            
            try:
                bpy.ops.better_export.fbx(**export_kwargs)
                count += 1
            except Exception as e:
                errors.append(f"{original_name}: {str(e)}")
                
            # Cleanup temp mesh and restore original name
            if temp_mesh:
                temp_data = temp_mesh.data
                bpy.data.objects.remove(temp_mesh, do_unlink=True)
                if temp_data.users == 0:
                    bpy.data.meshes.remove(temp_data)
                mesh.name = original_name

        # --- Cleanup temp armature ---
        if temp_armature:
            temp_arm_data = temp_armature.data
            bpy.data.objects.remove(temp_armature, do_unlink=True)
            if temp_arm_data.users == 0:
                bpy.data.armatures.remove(temp_arm_data)

        # Restore original selection
        bpy.ops.object.select_all(action='DESELECT')
        for obj in original_selected:
            try:
                obj.select_set(True)
            except:
                pass
        context.view_layer.objects.active = original_active

        if errors:
            self.report({'WARNING'}, f"Exported {count} files. Errors in: {', '.join(errors)}")
        else:
            self.report({'INFO'}, f"Successfully exported {count} files to {export_dir}")
            
        return {'FINISHED'}

# =====================================================================
#  GitHub Update Operators
# =====================================================================


class BATCH_FBX_OT_check_update(bpy.types.Operator):
    """ตรวจสอบอัปเดตจาก GitHub"""
    bl_idname = "kenji_export.check_update"
    bl_label = "Check for Updates"

    def execute(self, context):
        global _update_info
        _update_info["error"] = ""
        _update_info["current_version"] = bl_info["version"]
        _update_info["changelog"] = []

        try:
            req = urllib.request.Request(GITHUB_RAW_URL)
            req.add_header('User-Agent', 'Blender-Addon-Updater')

            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8')

            match = re.search(
                r'"version"\s*:\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
                content,
            )
            if not match:
                _update_info["error"] = "ไม่สามารถอ่านเวอร์ชันจาก GitHub ได้"
                _update_info["checked"] = True
                bpy.ops.kenji_export.update_popup('INVOKE_DEFAULT')
                return {'CANCELLED'}

            latest = tuple(int(match.group(index)) for index in range(1, 4))
            _update_info["latest_version"] = latest
            _update_info["has_update"] = latest > bl_info["version"]
            _update_info["checked"] = True

            if _update_info["has_update"]:
                try:
                    req_cl = urllib.request.Request(GITHUB_CHANGELOG_URL)
                    req_cl.add_header('User-Agent', 'Blender-Addon-Updater')
                    with urllib.request.urlopen(req_cl, timeout=5) as response:
                        changelog_content = response.read().decode('utf-8')
                    _update_info["changelog"] = _wrap_changelog(changelog_content)
                except Exception:
                    pass

        except urllib.error.URLError as error:
            _update_info["error"] = f"ไม่สามารถเชื่อมต่อ: {error.reason}"
            _update_info["checked"] = True
        except Exception as error:
            _update_info["error"] = str(error)
            _update_info["checked"] = True

        bpy.ops.kenji_export.update_popup('INVOKE_DEFAULT')
        return {'FINISHED'}


def _wrap_changelog(content, width=45, max_lines=15):
    lines = []
    for source_line in content.splitlines():
        source_line = source_line.strip()
        if not source_line:
            continue

        is_first = True
        while len(source_line) > width:
            split_at = source_line.rfind(' ', 0, width)
            split_at = split_at if split_at > 0 else width
            chunk = source_line[:split_at]
            lines.append(chunk if is_first else f"  {chunk}")
            source_line = source_line[split_at:].strip()
            is_first = False

        if source_line:
            lines.append(source_line if is_first else f"  {source_line}")

    return lines[:max_lines]


class BATCH_FBX_OT_update_popup(bpy.types.Operator):
    """แสดงข้อมูลเวอร์ชันและอัปเดต"""
    bl_idname = "kenji_export.update_popup"
    bl_label = "Kenji Export — Update"

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

        current = ".".join(str(value) for value in info["current_version"])
        latest = ".".join(str(value) for value in info["latest_version"])
        layout.label(text=f"เวอร์ชันปัจจุบัน:  v{current}", icon='PACKAGE')
        layout.label(text=f"เวอร์ชันล่าสุด:      v{latest}", icon='WORLD')
        layout.separator()

        if info["has_update"]:
            box = layout.box()
            box.label(text="มีเวอร์ชันใหม่!", icon='INFO')
            if info["changelog"]:
                box.separator()
                box.label(text="What's New:", icon='TEXT')
                for line in info["changelog"]:
                    box.label(text=line)
                box.separator()
            box.label(text="* เมื่อกด Update Now เสร็จแล้ว", icon='ERROR')
            box.label(text="  โปรด Restart Blender หรือกด F3 พิมพ์ Reload Scripts")
            box.operator("kenji_export.do_update", text="Update Now", icon='IMPORT')
        else:
            layout.label(text="เวอร์ชันล่าสุดแล้ว ✓", icon='CHECKMARK')

    def execute(self, context):
        return {'FINISHED'}


class BATCH_FBX_OT_do_update(bpy.types.Operator):
    """ดาวน์โหลดและติดตั้งอัปเดตจาก GitHub"""
    bl_idname = "kenji_export.do_update"
    bl_label = "Update Add-on"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            req = urllib.request.Request(GITHUB_API_CONTENTS)
            req.add_header('User-Agent', 'Blender-Addon-Updater')
            with urllib.request.urlopen(req, timeout=15) as response:
                files = json.loads(response.read().decode('utf-8'))

            addon_path = os.path.join(
                bpy.utils.user_resource('SCRIPTS'), "addons", GITHUB_ADDON_FOLDER
            )
            os.makedirs(addon_path, exist_ok=True)

            updated_count = 0
            for file_info in files:
                if file_info.get("type") != "file":
                    continue
                download_url = file_info.get("download_url")
                if not download_url:
                    continue

                download_request = urllib.request.Request(download_url)
                download_request.add_header('User-Agent', 'Blender-Addon-Updater')
                with urllib.request.urlopen(download_request, timeout=15) as response:
                    content = response.read()

                with open(os.path.join(addon_path, file_info["name"]), 'wb') as file:
                    file.write(content)
                updated_count += 1

            self.report(
                {'INFO'},
                f"อัปเดตเสร็จ! ({updated_count} ไฟล์) กรุณา Restart Blender หรือกด F3 พิมพ์ Reload Scripts",
            )
        except Exception as error:
            self.report({'ERROR'}, f"อัปเดตล้มเหลว: {error}")
            return {'CANCELLED'}

        return {'FINISHED'}


class BATCH_FBX_PT_panel(bpy.types.Panel):
    bl_label = "Kenji Export"
    bl_idname = "BATCH_FBX_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Kenji Export"

    def draw(self, context):
        layout = self.layout
        props = context.scene.batch_better_fbx_props

        header = layout.row(align=True)
        header.label(text="Kenji Export", icon='EXPORT')
        header.operator("kenji_export.check_update", text="", icon='WORLD')
        layout.separator()

        # Target Armature Picker
        box = layout.box()
        box.label(text="1. Target Armature:", icon='ARMATURE_DATA')
        box.prop(props, "target_armature", text="")
        
        layout.separator()

        # Mesh List
        box = layout.box()
        box.label(text="2. Meshes to Export:", icon='MESH_DATA')
        row = box.row()
        row.template_list("BATCH_FBX_UL_mesh_list", "", props, "mesh_list", props, "mesh_list_index", rows=5)
        
        col = row.column(align=True)
        col.operator("export.batch_better_fbx_add_mesh", icon='ADD', text="")
        col.operator("export.batch_better_fbx_remove_mesh", icon='REMOVE', text="")
        col.separator()
        col.operator("export.batch_better_fbx_clear_meshes", icon='TRASH', text="")
        
        layout.separator()
        
        # Export Settings
        box = layout.box()
        box.label(text="3. Export Settings:", icon='EXPORT')
        box.prop(props, "export_dir")
        box.prop(props, "preset_enum", text="Preset")
        
        # Options sub-box
        opt_box = box.box()
        opt_box.label(text="Options:", icon='OPTIONS')
        opt_box.prop(props, "force_shade_smooth")
        opt_box.prop(props, "restore_biped_names")
        
        layout.separator()
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator("export.batch_better_fbx", icon='EXPORT', text="Kenji Batch Export")

classes = (
    BATCH_FBX_MeshItem,
    BATCH_FBX_Properties,
    BATCH_FBX_UL_mesh_list,
    BATCH_FBX_OT_add_meshes,
    BATCH_FBX_OT_remove_mesh,
    BATCH_FBX_OT_clear_meshes,
    BATCH_FBX_OT_export,
    BATCH_FBX_OT_check_update,
    BATCH_FBX_OT_update_popup,
    BATCH_FBX_OT_do_update,
    BATCH_FBX_PT_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.batch_better_fbx_props = bpy.props.PointerProperty(type=BATCH_FBX_Properties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.batch_better_fbx_props

if __name__ == "__main__":
    register()
