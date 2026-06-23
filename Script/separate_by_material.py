import bpy
import os

def clear_scene():
    """Completely clear the scene and purge all orphan data blocks aggressively."""
    # Switch to OBJECT mode if we are in EDIT mode
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')

    # Select and delete all objects in the scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Aggressively delete meshes, materials, textures, and images from data blocks
    # This prevents any naming conflicts (.001, .002) with old assets
    for block in list(bpy.data.meshes):
        try:
            bpy.data.meshes.remove(block)
        except Exception:
            pass
            
    for block in list(bpy.data.materials):
        try:
            bpy.data.materials.remove(block)
        except Exception:
            pass
            
    for block in list(bpy.data.textures):
        try:
            bpy.data.textures.remove(block)
        except Exception:
            pass
            
    for block in list(bpy.data.images):
        try:
            bpy.data.images.remove(block)
        except Exception:
            pass

    # Completely purge all remaining unused/orphan data blocks recursively
    if hasattr(bpy.data, "orphans_purge"):
        try:
            bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        except Exception as e:
            print(f"Purging warning: {e}")
            
    print("Scene database cleared and fully purged.")

def clean_name_string(name):
    """Helper function to clean names by removing .001/.002 and _mat/_MAT suffixes."""
    def strip_suffix(s):
        if "." in s:
            parts = s.split(".")
            # If the last part is a number (like 001, 002), remove it
            if parts[-1].isdigit():
                s = ".".join(parts[:-1])
        return s.strip("_").strip()

    # 1. Strip trailing Blender suffix (e.g. "Gold_mat.001" -> "Gold_mat")
    name = strip_suffix(name)
    # 2. Remove "_mat" and "_MAT"
    name = name.replace("_mat", "").replace("_MAT", "")
    # 3. Strip trailing Blender suffix again (e.g. "Gold.001" -> "Gold")
    name = strip_suffix(name)
    
    return name

def batch_process_fbx():
    import_dir = r"C:\Users\Smart Office\Desktop\Edit_MaterialFur\Import"
    export_dir = r"C:\Users\Smart Office\Desktop\Edit_MaterialFur\Export"

    # Ensure directories exist
    os.makedirs(import_dir, exist_ok=True)
    os.makedirs(export_dir, exist_ok=True)

    # Find all FBX files in the import directory
    fbx_files = [f for f in os.listdir(import_dir) if f.lower().endswith('.fbx')]

    if not fbx_files:
        print(f"No FBX files found in: {import_dir}")
        print("Please place your FBX files in the 'Import' directory and run again.")
        return

    print(f"Found {len(fbx_files)} FBX file(s) to process.")

    for filename in fbx_files:
        import_path = os.path.join(import_dir, filename)
        export_path = os.path.join(export_dir, filename)

        print("-" * 50)
        print(f"Batch Processing File: {filename}")
        print("-" * 50)

        # 1. Clear scene database completely before importing to prevent .001 conflicts
        clear_scene()

        # 2. Import the FBX file
        try:
            bpy.ops.import_scene.fbx(filepath=import_path)
            print(f"Successfully imported: {filename}")
        except Exception as e:
            print(f"Error importing {filename}: {e}")
            continue

        # 3. Separate meshes with 2 or more materials
        initial_meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        for obj in initial_meshes:
            # Count slots that actually contain a material
            valid_materials = [slot.material for slot in obj.material_slots if slot.material]
            
            if len(valid_materials) >= 2:
                print(f"Separating '{obj.name}' by material...")

                # Select only this object and make it active
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Switch to EDIT mode to separate
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                
                # Separate by material
                bpy.ops.mesh.separate(type='MATERIAL')
                
                # Return to OBJECT mode
                bpy.ops.object.mode_set(mode='OBJECT')

        # 4. Process all resulting meshes in the scene
        final_meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        for split_obj in final_meshes:
            if not split_obj.data.polygons:
                continue

            # Find active/used material
            used_slot_index = split_obj.data.polygons[0].material_index
            if used_slot_index < len(split_obj.material_slots):
                mat = split_obj.material_slots[used_slot_index].material
                if mat:
                    # Clean the name string (removes _mat and .001/.002 suffixes)
                    cleaned_name = clean_name_string(mat.name)
                    
                    # Rename the Material itself to be clean
                    mat.name = cleaned_name
                    
                    # Rename both the Object and the Mesh Data to match
                    split_obj.name = cleaned_name
                    split_obj.data.name = cleaned_name
                    
                    # Clean up: remove unused material slots for this split mesh
                    split_obj.data.materials.clear()
                    split_obj.data.materials.append(mat)
                    
                    print(f" -> Processed mesh (Object & Data & Material) renamed to: {cleaned_name}")
                else:
                    split_obj.name = f"{split_obj.name}_NoMaterial"
                    split_obj.data.name = f"{split_obj.name}_NoMaterial"
            else:
                split_obj.name = f"{split_obj.name}_NoMaterial"
                split_obj.data.name = f"{split_obj.name}_NoMaterial"

            # Shade Smooth
            for poly in split_obj.data.polygons:
                poly.use_smooth = True
            
            # Clear Custom Split Normals
            bpy.context.view_layer.objects.active = split_obj
            try:
                bpy.ops.mesh.customdata_custom_splitnormals_clear()
            except Exception as e:
                pass

            # Clear edge marks (Mark Sharp, Seam, Crease, Bevel Weight)
            for edge in split_obj.data.edges:
                if hasattr(edge, "use_edge_sharp"):
                    edge.use_edge_sharp = False
                elif hasattr(edge, "use_sharp"):
                    try:
                        edge.use_sharp = False
                    except:
                        pass
                
                if hasattr(edge, "use_seam"):
                    edge.use_seam = False
                
                if hasattr(edge, "crease"):
                    try:
                        edge.crease = 0.0
                    except:
                        pass
                if hasattr(edge, "bevel_weight"):
                    try:
                        edge.bevel_weight = 0.0
                    except:
                        pass

            # Clear modern attributes (Creases / Bevel weights)
            if hasattr(split_obj.data, "attributes"):
                for attr_name in ["crease_edge", "bevel_weight_edge", "crease_vert", "bevel_weight_vert"]:
                    if attr_name in split_obj.data.attributes:
                        try:
                            split_obj.data.attributes.remove(split_obj.data.attributes[attr_name])
                        except:
                            pass

            split_obj.data.update()

        # 5. Export the processed scene as a new FBX
        try:
            # Select all remaining objects in the scene to ensure correct export selection
            bpy.ops.object.select_all(action='SELECT')
            
            # Export to the export directory
            bpy.ops.export_scene.fbx(filepath=export_path, use_selection=True)
            print(f"Successfully exported: {filename} -> Export folder")
        except Exception as e:
            print(f"Error exporting {filename}: {e}")

    # Final cleanup of the scene
    clear_scene()
    print("=" * 50)
    print("Batch processing completed successfully for all files.")
    print("=" * 50)

# Run the batch process
if __name__ == "__main__":
    batch_process_fbx()
