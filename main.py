import UnityPy
import os
import json
import traceback
import re
from tqdm import tqdm

def sanitize_filename(name: str) -> str:
    sane_name = re.sub(r'[<>:"/\\|?*]', '_', name)
    sane_name = sane_name.replace(' ', '_')
    sane_name = sane_name.strip('_').strip()
    if not sane_name:
        return "Untitled"
    return sane_name

def get_object_name(data, obj_type: str, path_id: int) -> str:
    name_candidates = ["name", "m_Name"]

    for attr_name in name_candidates:
        if hasattr(data, attr_name):
            candidate = getattr(data, attr_name)
            if candidate:
                if isinstance(candidate, bytes):
                    decoded_candidate = candidate.decode('utf-8', errors='ignore').strip()
                    if decoded_candidate:
                        return sanitize_filename(decoded_candidate)
                elif isinstance(candidate, str) and candidate.strip():
                    return sanitize_filename(candidate.strip())
    
    if obj_type == "MonoScript" and hasattr(data, "m_ClassName") and data.m_ClassName:
        return sanitize_filename(data.m_ClassName)

    if hasattr(data, "m_PathID") and data.m_PathID != 0:
        return f"Object_{data.m_PathID}"

    return f"Unnamed_{path_id}"

def extract_bundle(bundle_path: str = None, output_dir: str = None):
    if not bundle_path:
        bundle_path = input("Please enter the .bundle file path: ").strip()
    
    if not bundle_path:
        print("Error: Bundle file path cannot be empty. Please provide a valid path.")
        return

    if not output_dir:
        output_dir = input("Please enter the output folder path: ").strip()
    
    if not output_dir:
        print("Error: Output folder path cannot be empty. Please provide a valid path.")
        return

    if not os.path.exists(bundle_path):
        print(f"Error: File '{bundle_path}' not found. Please check the path and try again.")
        return

    os.makedirs(output_dir, exist_ok=True)
    log_file = os.path.join(output_dir, "extraction_log.txt") 

    log = {
        "total_objects_processed": 0,
        "successful_extractions": 0,
        "failed_extractions": 0,
        "errors": []
    }
    extracted_counts = {}

    try:
        with open(bundle_path, "rb") as f:
            env = UnityPy.load(f)
    except Exception as e:
        print(f"Critical Error: Could not load bundle '{bundle_path}'. Is it a valid Unity bundle? Details: {e}")
        with open(log_file, "w", encoding="utf-8", errors="replace") as log_out:
            log_out.write("== UnityFS Bundle Extraction Log ==\n")
            log_out.write(f"Critical Error: Could not load bundle.\nDetails: {e}\n")
            log_out.write(f"Traceback:\n{traceback.format_exc()}\n")
        return

    objects = list(env.objects)
    print(f"\nTotal objects found in bundle: {len(objects)}\n")

    with tqdm(total=len(objects), desc="Extracting Objects") as pbar:
        for obj in objects:
            log["total_objects_processed"] += 1
            extracted_successfully_current_obj = False

            try:
                data = obj.read()
                obj_type = obj.type.name
                
                obj_name = get_object_name(data, obj_type, obj.path_id)
                if not obj_name:
                    obj_name = f"Unnamed_Sanitized_{obj.path_id}"

                final_output_path = os.path.join(output_dir, obj_type, obj_name)
                os.makedirs(os.path.dirname(final_output_path), exist_ok=True)

                if obj_type == "Texture2D" or obj_type == "Sprite":
                    data.image.save(final_output_path + ".png")
                    extracted_successfully_current_obj = True
                elif obj_type == "TextAsset":
                    content = ""
                    if hasattr(data, "m_Script") and data.m_Script is not None:
                        if isinstance(data.m_Script, bytes):
                            content = data.m_Script.decode(errors="ignore")
                        elif isinstance(data.m_Script, str):
                            content = data.m_Script
                    
                    ext = ".json" if content.strip().startswith("{") and content.strip().endswith("}") else ".txt"
                    with open(final_output_path + ext, "w", encoding="utf-8", errors="replace") as out_file:
                        out_file.write(content)
                    extracted_successfully_current_obj = True
                elif obj_type == "AudioClip":
                    try:
                        if hasattr(data, "samples") and data.samples:
                            with open(final_output_path + ".wav", "wb") as out_file:
                                out_file.write(data.samples)
                            extracted_successfully_current_obj = True
                        elif hasattr(data, "m_AudioData") and data.m_AudioData:
                            with open(final_output_path + ".ogg", "wb") as out_file:
                                out_file.write(data.m_AudioData)
                            extracted_successfully_current_obj = True
                        else:
                            raise ValueError("No valid audio data (samples or m_AudioData) found.")
                    except Exception as audio_e:
                        metadata = {
                            "name": obj_name,
                            "length": getattr(data, "m_Length", "Unknown"),
                            "frequency": getattr(data, "m_Frequency", "Unknown"),
                            "error": str(audio_e),
                            "note": "Failed to extract audio stream, saved metadata only."
                        }
                        with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                            json.dump(metadata, out_file, indent=4)
                        extracted_successfully_current_obj = False
                elif obj_type == "Font":
                    if hasattr(data, "m_FontData") and data.m_FontData:
                        with open(final_output_path + ".ttf", "wb") as out_file:
                            out_file.write(data.m_FontData)
                        extracted_successfully_current_obj = True
                    else:
                        with open(final_output_path + ".txt", "w", encoding="utf-8", errors="replace") as out_file:
                            out_file.write(f"No font data found for {obj_name}.\n\n{str(data)}")
                        extracted_successfully_current_obj = False
                elif obj_type == "MonoScript":
                    try:
                        info = data.read_typetree()
                        with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                            json.dump(info, out_file, indent=4)
                        extracted_successfully_current_obj = True
                    except:
                        if hasattr(data, "m_Script") and data.m_Script is not None:
                            script_content = ""
                            if isinstance(data.m_Script, bytes):
                                script_content = data.m_Script.decode(errors="ignore")
                            elif isinstance(data.m_Script, str):
                                script_content = data.m_Script
                            
                            if script_content.strip().startswith("using ") or script_content.strip().startswith("namespace "):
                                with open(final_output_path + ".cs", "w", encoding="utf-8", errors="replace") as out_file:
                                    out_file.write(script_content)
                                extracted_successfully_current_obj = True
                            else:
                                with open(final_output_path + ".txt", "w", encoding="utf-8", errors="replace") as out_file:
                                    out_file.write(script_content)
                                extracted_successfully_current_obj = True
                        else:
                            with open(final_output_path + ".monoscript", "w", encoding="utf-8") as out_file:
                                out_file.write(str(data))
                            extracted_successfully_current_obj = True
                elif obj_type == "AssetBundle":
                    if hasattr(data, "m_Container") and isinstance(data.m_Container, dict):
                        container_info = {k: v.path for k, v in data.m_Container.items()}
                        with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                            json.dump(container_info, out_file, indent=4)
                        extracted_successfully_current_obj = True
                    elif hasattr(data, "raw_data") and data.raw_data:
                        with open(final_output_path + ".bundle", "wb") as out_file:
                            out_file.write(data.raw_data)
                        extracted_successfully_current_obj = True
                    else: 
                        with open(final_output_path + ".txt", "w", encoding="utf-8", errors="replace") as out_file:
                            out_file.write(str(data))
                        extracted_successfully_current_obj = True
                elif obj_type == "MonoBehaviour":
                    extracted_basic_fields = {}
                    if hasattr(data, "m_Name"): extracted_basic_fields["m_Name"] = data.m_Name
                    if hasattr(data, "m_Enabled"): extracted_basic_fields["m_Enabled"] = data.m_Enabled
                    if hasattr(data, "m_GameObject") and hasattr(data.m_GameObject, 'path_id'): 
                        extracted_basic_fields["m_GameObject_PathID"] = data.m_GameObject.path_id
                    if hasattr(data, "m_Script") and hasattr(data.m_Script, 'path_id'): 
                        extracted_basic_fields["m_Script_PathID"] = data.m_Script.path_id
                    
                    if extracted_basic_fields:
                        # Attempt to read typetree, but if it fails, basic fields are still saved.
                        # This specific handling for MonoBehaviour is to avoid AttributeError: 'MonoBehaviour' object has no attribute 'read_typetree'
                        try:
                            # If read_typetree is available and works for this specific MonoBehaviour instance
                            info = data.read_typetree() 
                            with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                                json.dump(info, out_file, indent=4)
                            extracted_successfully_current_obj = True
                        except Exception as e_typetree_mono:
                            # If typetree read fails, save the extracted basic fields.
                            with open(final_output_path + "_basic.json", "w", encoding="utf-8") as out_file:
                                json.dump(extracted_basic_fields, out_file, indent=4)
                            extracted_successfully_current_obj = True
                            log["errors"].append({
                                "object_id": obj.path_id,
                                "type": obj.type.name,
                                "error": f"Typetree read failed for MonoBehaviour ({e_typetree_mono}). Saved basic fields instead.",
                                "traceback": traceback.format_exc()
                            })
                    else:
                        with open(final_output_path + ".txt", "w", encoding="utf-8", errors="replace") as out_file:
                            out_file.write(f"Could not extract structured data for {obj_type}.\n\n{str(data)}")
                        extracted_successfully_current_obj = False
                elif obj_type in [
                    "Mesh", "Material", "AnimationClip", "Shader", "Prefab", "Scene", 
                    "Animator", "Avatar", "MeshFilter", "MeshRenderer", 
                    "ParticleSystem", "ParticleSystemRenderer", "PlayableDirector", "SkinnedMeshRenderer",
                    "GameObject", "Transform", "Camera", "Light", "BoxCollider", "SphereCollider", 
                    "CapsuleCollider", "MeshCollider", "Rigidbody", "Animation", "Canvas", 
                    "RectTransform", "CanvasRenderer", "AudioSource", "AudioListener", 
                    "SpriteRenderer", "Behaviour", "LightmapSettings", "OcclusionCullingSettings", 
                    "RenderSettings", "NavMeshSettings", "ResourceManager", "QualitySettings",
                    "InputManager", "TagManager", "PhysicsManager", "TimeManager", "LayerManager",
                    "AudioManager", "BuildSettings", "EditorSettings", "PlayerSettings", "GraphicsSettings",
                    "NetworkManager", "ClusterInputManager", "CrashReportManager", "PerformanceReportingManager",
                    "UnityConnectSettings", "VFXManager", "TerrainLayer", "TerrainData", "Tree", "Foliage",
                    "OcclusionPortal", "OcclusionArea", "LODGroup", "ReflectionProbe", "LightProbeGroup",
                    "AnimatorController", "AnimatorOverrideController"
                ]:
                    try:
                        info = data.read_typetree()
                        with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                            json.dump(info, out_file, indent=4)
                        extracted_successfully_current_obj = True
                    except Exception as e_typetree:
                        with open(final_output_path + ".txt", "w", encoding="utf-8", errors="replace") as out_file:
                            out_file.write(f"Error reading typetree for {obj_type}: {e_typetree}\n\n{str(data)}")
                        extracted_successfully_current_obj = False
                else:
                    try:
                        info = data.read_typetree()
                        with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                            json.dump(info, out_file, indent=4)
                        extracted_successfully_current_obj = True
                    except Exception as e_typetree:
                        file_ext = ".bin" if hasattr(data, 'raw_data') and data.raw_data else f".{obj_type.lower()}.txt"
                        mode = "wb" if hasattr(data, 'raw_data') and data.raw_data else "w"
                        encoding = None if hasattr(data, 'raw_data') and data.raw_data else "utf-8"

                        with open(final_output_path + file_ext, mode, encoding=encoding, errors="replace") as out_file:
                            if hasattr(data, 'raw_data') and data.raw_data:
                                out_file.write(data.raw_data)
                            else:
                                out_file.write(str(data))
                        
                        extracted_successfully_current_obj = False
                        log["errors"].append({
                            "object_id": obj.path_id,
                            "type": obj.type.name,
                            "error": f"Typetree read failed for generic type ({e_typetree}). Saved as {file_ext}.",
                            "traceback": traceback.format_exc()
                        })

                if extracted_successfully_current_obj:
                    log["successful_extractions"] += 1
                    extracted_counts[obj_type] = extracted_counts.get(obj_type, 0) + 1
                else:
                    log["failed_extractions"] += 1
                    if not any(err['object_id'] == obj.path_id and err['type'] == obj.type.name and ("Saved basic fields instead." in err.get('error', '') or "Failed to extract basic MonoBehaviour fields" in err.get('error', '')) for err in log["errors"]):
                         log["errors"].append({
                            "object_id": obj.path_id,
                            "type": obj.type.name,
                            "error": "Extraction failed or saved as generic fallback due to an issue.",
                            "traceback": traceback.format_exc()
                        })

            except Exception as e:
                log["failed_extractions"] += 1
                log["errors"].append({
                    "object_id": obj.path_id,
                    "type": obj.type.name,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })

            pbar.update(1)

    with open(log_file, "w", encoding="utf-8", errors="replace") as log_out:
        log_out.write("== UnityFS Bundle Extraction Log ==\n")
        log_out.write(f"Total objects processed: {log['total_objects_processed']}\n")
        log_out.write(f"Successfully extracted: {log['successful_extractions']}\n")
        log_out.write(f"Failed extractions: {log['failed_extractions']}\n\n")
        
        log_out.write("== Extracted Object Type Counts ==\n")
        if not extracted_counts:
            log_out.write("No objects were successfully extracted.\n")
        else:
            for obj_type, count in sorted(extracted_counts.items()):
                log_out.write(f"- {obj_type}: {count}\n")
        
        log_out.write("\n== Error Details ==\n")
        if not log["errors"]:
            log_out.write("No errors recorded.\n")
        else:
            for error in log["errors"]:
                log_out.write(f"Object ID: {error['object_id']}\n")
                log_out.write(f"Type: {error['type']}\n")
                log_out.write(f"Error: {error['error']}\n")
                if error.get('traceback'):
                    log_out.write(f"Traceback:\n{error['traceback']}\n")
                log_out.write("=" * 50 + "\n")

    print(f"\nExtraction completed. Files saved to '{output_dir}'. Log saved to '{log_file}'.")
    print(f"Summary: {log['successful_extractions']} objects successfully extracted, {log['failed_extractions']} failed or extracted to generic format.")
    print("Thanks for using this script! Credit: @alwizba. Licensed under MIT License.")
    
if __name__ == "__main__":
    extract_bundle()