import UnityPy
import os
import json
import traceback
import re
import sys
import struct
import zlib
import lz4.frame
from collections import defaultdict
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

DEBUG_MODE = "--debug" in sys.argv

COMPONENT_TYPES = {
    "Transform", "Animator", "SkinnedMeshRenderer", "MeshRenderer", "MeshFilter",
    "Camera", "Light", "AudioSource", "AudioListener", "CapsuleCollider",
    "PlayableDirector", "LookAtConstraint", "NavMeshAgent"
}

def debug_print(message):
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

def sanitize_filename(name: str) -> str:
    sane_name = re.sub(r'[<>:"/\\|?*]', '_', name)
    sane_name = sane_name.replace(' ', '_')
    sane_name = sane_name.strip('_').strip()
    if not sane_name:
        return "Untitled"
    return sane_name

def detect_compression_type(data: bytes) -> str:
    if data[:4] == b'LZ4\x00':
        return "lz4"
    elif data[:2] == b'\x78\x9c' or data[:2] == b'\x78\x01' or data[:2] == b'\x78\xda':
        return "zlib"
    elif data[:2] == b'\x1f\x8b':
        return "gzip"
    elif data[:8] == b'UnityFS\x00':
        return "unityfs"
    elif data[:7] == b'UnityRaw':
        return "raw"
    return "unknown"

def decompress_data(data: bytes, compression_type: str = None) -> bytes:
    if not compression_type:
        compression_type = detect_compression_type(data)
    
    try:
        if compression_type == "lz4":
            return lz4.frame.decompress(data)
        elif compression_type == "zlib":
            return zlib.decompress(data)
        elif compression_type == "gzip":
            import gzip
            return gzip.decompress(data)
        else:
            return data
    except Exception as e:
        debug_print(f"Decompression failed: {e}")
        return data

def get_file_signature(filepath: str) -> dict:
    try:
        with open(filepath, 'rb') as f:
            header = f.read(32)
            return {
                'signature': header[:8],
                'version': header[8:12] if len(header) > 8 else b'',
                'compression': detect_compression_type(header),
                'size': os.path.getsize(filepath)
            }
    except:
        return {'signature': b'', 'version': b'', 'compression': 'unknown', 'size': 0}

def extract_type_tree_info(obj) -> dict:
    type_info = {
        'class_id': obj.type.value if hasattr(obj.type, 'value') else 0,
        'class_name': obj.type.name,
        'path_id': obj.path_id,
        'data_offset': getattr(obj, 'data_offset', 0),
        'data_size': getattr(obj, 'data_size', 0)
    }
    
    if hasattr(obj, 'serialized_type') and obj.serialized_type:
        st = obj.serialized_type
        type_info.update({
            'script_type_index': getattr(st, 'script_type_index', -1),
            'hash': getattr(st, 'hash', b'').hex() if hasattr(st, 'hash') else '',
            'type_dependencies': getattr(st, 'type_dependencies', [])
        })
    
    return type_info

def get_object_dependencies(obj) -> list:
    dependencies = []
    try:
        data = obj.read()
        if hasattr(data, '__dict__'):
            for attr_name, attr_value in data.__dict__.items():
                if hasattr(attr_value, 'path_id') and attr_value.path_id != 0:
                    dependencies.append({
                        'attribute': attr_name,
                        'path_id': attr_value.path_id,
                        'file_id': getattr(attr_value, 'file_id', 0)
                    })
                elif isinstance(attr_value, list):
                    for i, item in enumerate(attr_value):
                        if hasattr(item, 'path_id') and item.path_id != 0:
                            dependencies.append({
                                'attribute': f"{attr_name}[{i}]",
                                'path_id': item.path_id,
                                'file_id': getattr(item, 'file_id', 0)
                            })
    except:
        pass
    
    return dependencies

def get_object_name(data, obj_type: str, path_id: int) -> str:
    name_candidates = ["name", "m_Name", "m_ClassName", "m_ObjectHideFlags"]

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

    return f"{obj_type}_{path_id}"

def extract_streaming_info(obj) -> dict:
    streaming_info = {}
    try:
        data = obj.read()
        if hasattr(data, 'm_StreamData'):
            stream_data = data.m_StreamData
            streaming_info = {
                'offset': getattr(stream_data, 'offset', 0),
                'size': getattr(stream_data, 'size', 0),
                'path': getattr(stream_data, 'path', ''),
            }
    except:
        pass
    
    return streaming_info

def process_mesh_advanced(data, output_path: str) -> bool:
    try:
        mesh_data = {
            'name': getattr(data, 'm_Name', 'Unknown'),
            'vertex_count': len(data.m_Vertices) if hasattr(data, 'm_Vertices') else 0,
            'triangle_count': len(data.m_Triangles) // 3 if hasattr(data, 'm_Triangles') else 0,
            'submesh_count': len(data.m_SubMeshes) if hasattr(data, 'm_SubMeshes') else 0,
            'blend_shapes': len(data.m_Shapes.shapes) if hasattr(data, 'm_Shapes') and hasattr(data.m_Shapes, 'shapes') else 0,
            'bone_count': len(data.m_BoneNameHashes) if hasattr(data, 'm_BoneNameHashes') else 0
        }
        
        vertices = []
        if hasattr(data, 'm_Vertices'):
            for i, vertex in enumerate(data.m_Vertices):
                if hasattr(vertex, 'x'):
                    vertices.append([vertex.x, vertex.y, vertex.z])
                else:
                    vertices.append(vertex)
        
        if vertices:
            with open(output_path + ".obj", "w") as obj_file:
                obj_file.write(f"# Mesh: {mesh_data['name']}\n")
                obj_file.write(f"# Vertices: {len(vertices)}\n")
                for vertex in vertices:
                    obj_file.write(f"v {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")
                
                if hasattr(data, 'm_Triangles'):
                    triangles = data.m_Triangles
                    for i in range(0, len(triangles), 3):
                        obj_file.write(f"f {triangles[i]+1} {triangles[i+1]+1} {triangles[i+2]+1}\n")
        
        with open(output_path + "_info.json", "w", encoding="utf-8") as info_file:
            json.dump(mesh_data, info_file, indent=4)
        
        return True
    except Exception as e:
        debug_print(f"Mesh processing failed: {e}")
        return False

def process_material_advanced(data, output_path: str) -> bool:
    try:
        material_data = {
            'name': getattr(data, 'm_Name', 'Unknown'),
            'shader': {
                'name': data.m_Shader.name if hasattr(data, 'm_Shader') and hasattr(data.m_Shader, 'name') else 'Unknown',
                'path_id': data.m_Shader.path_id if hasattr(data, 'm_Shader') and hasattr(data.m_Shader, 'path_id') else -1,
            },
            'keywords': getattr(data, 'm_ShaderKeywords', []),
            'properties': {},
            'textures': {}
        }
        
        if hasattr(data, 'm_SavedProperties'):
            props = data.m_SavedProperties
            
            if hasattr(props, 'm_TexEnvs'):
                for tex_env in props.m_TexEnvs:
                    tex_name = tex_env.first if hasattr(tex_env, 'first') else 'Unknown'
                    tex_data = tex_env.second if hasattr(tex_env, 'second') else None
                    if tex_data:
                        material_data['textures'][tex_name] = {
                            'texture_path_id': tex_data.m_Texture.path_id if hasattr(tex_data, 'm_Texture') and hasattr(tex_data.m_Texture, 'path_id') else -1,
                            'scale': [tex_data.m_Scale.x, tex_data.m_Scale.y] if hasattr(tex_data, 'm_Scale') else [1, 1],
                            'offset': [tex_data.m_Offset.x, tex_data.m_Offset.y] if hasattr(tex_data, 'm_Offset') else [0, 0]
                        }
            
            if hasattr(props, 'm_Floats'):
                for float_prop in props.m_Floats:
                    prop_name = float_prop.first if hasattr(float_prop, 'first') else 'Unknown'
                    prop_value = float_prop.second if hasattr(float_prop, 'second') else 0.0
                    material_data['properties'][prop_name] = {'type': 'float', 'value': prop_value}
            
            if hasattr(props, 'm_Colors'):
                for color_prop in props.m_Colors:
                    prop_name = color_prop.first if hasattr(color_prop, 'first') else 'Unknown'
                    color_value = color_prop.second if hasattr(color_prop, 'second') else None
                    if color_value:
                        material_data['properties'][prop_name] = {
                            'type': 'color',
                            'value': [color_value.r, color_value.g, color_value.b, color_value.a] if all(hasattr(color_value, attr) for attr in ['r', 'g', 'b', 'a']) else [0, 0, 0, 1]
                        }
        
        with open(output_path + ".json", "w", encoding="utf-8") as mat_file:
            json.dump(material_data, mat_file, indent=4)
        
        return True
    except Exception as e:
        debug_print(f"Material processing failed: {e}")
        return False

def process_animation_advanced(data, output_path: str) -> bool:
    try:
        anim_data = {
            'name': getattr(data, 'm_Name', 'Unknown'),
            'length': getattr(data, 'm_Length', 0.0),
            'frame_rate': getattr(data, 'm_SampleRate', 30.0),
            'wrap_mode': getattr(data, 'm_WrapMode', 0),
            'curves': []
        }
        
        if hasattr(data, 'm_FloatCurves'):
            for curve in data.m_FloatCurves:
                curve_info = {
                    'attribute': curve.attribute if hasattr(curve, 'attribute') else 'Unknown',
                    'path': curve.path if hasattr(curve, 'path') else '',
                    'type': 'float',
                    'keyframes': []
                }
                
                if hasattr(curve, 'curve') and hasattr(curve.curve, 'm_Curve'):
                    for keyframe in curve.curve.m_Curve:
                        curve_info['keyframes'].append({
                            'time': keyframe.time if hasattr(keyframe, 'time') else 0.0,
                            'value': keyframe.value if hasattr(keyframe, 'value') else 0.0,
                            'in_tangent': keyframe.inTangent if hasattr(keyframe, 'inTangent') else 0.0,
                            'out_tangent': keyframe.outTangent if hasattr(keyframe, 'outTangent') else 0.0
                        })
                
                anim_data['curves'].append(curve_info)
        
        with open(output_path + ".json", "w", encoding="utf-8") as anim_file:
            json.dump(anim_data, anim_file, indent=4)
        
        return True
    except Exception as e:
        debug_print(f"Animation processing failed: {e}")
        return False

def serialize_object_data(data) -> dict:
    if isinstance(data, (dict, list, str, int, float, bool)) or data is None:
        return data

    output = {}
    if hasattr(data, '__dict__'):
        for key, value in data.__dict__.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                output[key] = value
            elif isinstance(value, (list, tuple)):
                output[key] = [serialize_object_data(item) for item in value]
            elif hasattr(value, 'path_id'):
                output[key] = {
                    'type': 'PPtr',
                    'file_id': getattr(value, 'file_id', 0),
                    'path_id': value.path_id
                }
            elif hasattr(value, '__dict__'):
                output[key] = serialize_object_data(value)
            else:
                try:
                    output[key] = str(value)
                except:
                    output[key] = 'Unserializable Object'
    else:
        return str(data)

    return output

def extract_bundle_advanced(bundle_path: str = None, output_dir: str = None):
    if not bundle_path:
        bundle_path = input("Please enter the .bundle file path: ").strip()
    
    if not bundle_path:
        print("Error: Bundle file path cannot be empty.")
        return

    if not output_dir:
        output_dir = input("Please enter the output folder path: ").strip()
    
    if not output_dir:
        print("Error: Output folder path cannot be empty.")
        return

    if not os.path.exists(bundle_path):
        print(f"Error: File '{bundle_path}' not found.")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    bundle_info = get_file_signature(bundle_path)
    debug_print(f"Bundle info: {bundle_info}")
    
    log_file = os.path.join(output_dir, "extraction_log.txt")
    metadata_file = os.path.join(output_dir, "bundle_metadata.json")
    type_tree_file = os.path.join(output_dir, "type_tree.json")
    dependencies_file = os.path.join(output_dir, "dependencies.json")

    log = {
        "timestamp": datetime.now().isoformat(),
        "bundle_path": bundle_path,
        "bundle_info": {
            'signature': bundle_info['signature'].hex(),
            'compression': bundle_info['compression'],
            'size': bundle_info['size']
        },
        "total_objects_processed": 0,
        "successful_extractions": 0,
        "failed_extractions": 0,
        "errors": []
    }
    
    extracted_counts = defaultdict(int)
    type_tree_data = {}
    all_dependencies = {}

    try:
        with open(bundle_path, "rb") as f:
            env = UnityPy.load(f)
    except Exception as e:
        print(f"Critical Error: Could not load bundle. Details: {e}")
        with open(log_file, "w", encoding="utf-8", errors="replace") as log_out:
            log_out.write(f"Critical Error: {e}\n")
            log_out.write(f"Traceback:\n{traceback.format_exc()}\n")
        return

    objects = list(env.objects)
    print(f"\nBundle loaded successfully. Objects found: {len(objects)}")
    
    if DEBUG_MODE:
        print(f"Unity Version: {getattr(env, 'version', 'Unknown')}")
        print(f"Platform: {getattr(env, 'platform', 'Unknown')}")

    container_data = {}
    if hasattr(env, 'container') and env.container:
        for path, obj_data in env.container.items():
            container_data[path] = {
                'path_id': obj_data.path_id if hasattr(obj_data, 'path_id') else -1,
                'type': obj_data.type.name if hasattr(obj_data, 'type') else 'Unknown'
            }
    
    bundle_metadata = {
        'version': getattr(env, 'version', 'Unknown'),
        'platform': str(getattr(env, 'platform', 'Unknown')),
        'object_count': len(objects),
        'container_paths': container_data,
        'extraction_timestamp': datetime.now().isoformat()
    }

    with tqdm(total=len(objects), desc="Processing Assets") as pbar:
        for obj in objects:
            log["total_objects_processed"] += 1
            extracted_successfully = False
            obj_type = obj.type.name

            try:
                data = obj.read()
                type_info = extract_type_tree_info(obj)
                type_tree_data[f"{obj_type}_{obj.path_id}"] = type_info
                
                dependencies = get_object_dependencies(obj)
                if dependencies:
                    all_dependencies[f"{obj_type}_{obj.path_id}"] = dependencies
                
                obj_name = get_object_name(data, obj_type, obj.path_id)

                if obj_type in COMPONENT_TYPES and hasattr(data, 'm_GameObject'):
                    try:
                        game_object_ptr = data.m_GameObject
                        if game_object_ptr and game_object_ptr.path_id != 0:
                            game_object_data = game_object_ptr.read()
                            go_name = getattr(game_object_data, 'm_Name', '')
                            if go_name:
                                obj_name = f"{sanitize_filename(go_name)}_{obj_name}"
                    except Exception as e:
                        debug_print(f"Could not read parent GameObject for {obj_type} {obj.path_id}: {e}")
                
                final_output_path = os.path.join(output_dir, obj_type, obj_name)
                os.makedirs(os.path.dirname(final_output_path), exist_ok=True)

                streaming_info = extract_streaming_info(obj)
                if streaming_info and streaming_info.get('size', 0) > 0:
                    with open(final_output_path + "_streaming.json", "w", encoding="utf-8") as stream_file:
                        json.dump(streaming_info, stream_file, indent=4)

                if obj_type == "Texture2D":
                    try:
                        image = data.image
                        image.save(final_output_path + ".png")
                        
                        tex_info = {
                            'width': data.m_Width if hasattr(data, 'm_Width') else 0,
                            'height': data.m_Height if hasattr(data, 'm_Height') else 0,
                            'format': str(data.m_TextureFormat) if hasattr(data, 'm_TextureFormat') else 'Unknown',
                            'mip_count': data.m_MipCount if hasattr(data, 'm_MipCount') else 1,
                            'is_readable': getattr(data, 'm_IsReadable', False),
                            'streaming_info': streaming_info
                        }
                        
                        with open(final_output_path + "_info.json", "w", encoding="utf-8") as info_file:
                            json.dump(tex_info, info_file, indent=4)
                        
                        extracted_successfully = True
                    except Exception as tex_e:
                        debug_print(f"Texture2D extraction failed: {tex_e}")
                        
                elif obj_type == "Sprite":
                    try:
                        image = data.image
                        image.save(final_output_path + ".png")
                        
                        sprite_info = {
                            'rect_x': data.m_Rect.x if hasattr(data, 'm_Rect') else 0,
                            'rect_y': data.m_Rect.y if hasattr(data, 'm_Rect') else 0,
                            'rect_width': data.m_Rect.width if hasattr(data, 'm_Rect') else 0,
                            'rect_height': data.m_Rect.height if hasattr(data, 'm_Rect') else 0,
                            'pivot_x': data.m_Pivot.x if hasattr(data, 'm_Pivot') else 0.5,
                            'pivot_y': data.m_Pivot.y if hasattr(data, 'm_Pivot') else 0.5,
                            'pixels_per_unit': getattr(data, 'm_PixelsPerUnit', 100),
                            'texture_path_id': data.m_RD.texture.path_id if hasattr(data, 'm_RD') and hasattr(data.m_RD, 'texture') else -1
                        }
                        
                        with open(final_output_path + "_info.json", "w", encoding="utf-8") as info_file:
                            json.dump(sprite_info, info_file, indent=4)
                        
                        extracted_successfully = True
                    except Exception as sprite_e:
                        debug_print(f"Sprite extraction failed: {sprite_e}")

                elif obj_type == "TextAsset":
                    content = ""
                    if hasattr(data, "m_Script") and data.m_Script is not None:
                        if isinstance(data.m_Script, bytes):
                            content = data.m_Script.decode(errors="ignore")
                        elif isinstance(data.m_Script, str):
                            content = data.m_Script
                    
                    is_json = content.strip().startswith(("{", "[")) and content.strip().endswith(("}", "]"))
                    ext = ".json" if is_json else ".txt"
                    
                    with open(final_output_path + ext, "w", encoding="utf-8", errors="replace") as out_file:
                        out_file.write(content)
                    
                    text_info = {
                        'size': len(content),
                        'type': 'json' if is_json else 'text',
                        'encoding': 'utf-8'
                    }
                    
                    with open(final_output_path + "_info.json", "w", encoding="utf-8") as info_file:
                        json.dump(text_info, info_file, indent=4)
                    
                    extracted_successfully = True

                elif obj_type == "AudioClip":
                    try:
                        audio_info = {
                            'name': getattr(data, 'm_Name', 'Unknown'),
                            'length': getattr(data, 'm_Length', 0.0),
                            'frequency': getattr(data, 'm_Frequency', 0),
                            'channels': getattr(data, 'm_Channels', 0),
                            'bits_per_sample': getattr(data, 'm_BitsPerSample', 0),
                            'compression_format': getattr(data, 'm_CompressionFormat', 0),
                            'load_type': getattr(data, 'm_LoadType', 0),
                            'streaming_info': streaming_info
                        }
                        
                        if hasattr(data, "samples") and data.samples:
                            with open(final_output_path + ".wav", "wb") as out_file:
                                out_file.write(data.samples)
                            extracted_successfully = True
                        elif hasattr(data, "m_AudioData") and data.m_AudioData:
                            ext = ".ogg" if audio_info['compression_format'] == 1 else ".wav"
                            with open(final_output_path + ext, "wb") as out_file:
                                out_file.write(data.m_AudioData)
                            extracted_successfully = True
                        
                        with open(final_output_path + "_info.json", "w", encoding="utf-8") as info_file:
                            json.dump(audio_info, info_file, indent=4)
                        
                        if not extracted_successfully:
                            extracted_successfully = True
                    except Exception as audio_e:
                        debug_print(f"AudioClip extraction failed: {audio_e}")

                elif obj_type == "Mesh":
                    extracted_successfully = process_mesh_advanced(data, final_output_path)
                    if not extracted_successfully:
                        try:
                            info = data.read_typetree()
                            with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                                json.dump(info, out_file, indent=4)
                            extracted_successfully = True
                        except:
                            pass

                elif obj_type == "Material":
                    extracted_successfully = process_material_advanced(data, final_output_path)
                    if not extracted_successfully:
                        try:
                            info = data.read_typetree()
                            with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                                json.dump(info, out_file, indent=4)
                            extracted_successfully = True
                        except:
                            pass

                elif obj_type == "AnimationClip":
                    extracted_successfully = process_animation_advanced(data, final_output_path)
                    if not extracted_successfully:
                        try:
                            info = data.read_typetree()
                            with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                                json.dump(info, out_file, indent=4)
                            extracted_successfully = True
                        except:
                            pass

                elif obj_type == "Font":
                    if hasattr(data, "m_FontData") and data.m_FontData:
                        with open(final_output_path + ".ttf", "wb") as out_file:
                            out_file.write(data.m_FontData)
                        extracted_successfully = True
                    else:
                        font_info = {
                            'name': getattr(data, 'm_Name', 'Unknown'),
                            'size': getattr(data, 'm_FontSize', 0),
                            'style': getattr(data, 'm_FontStyle', 0)
                        }
                        with open(final_output_path + "_info.json", "w", encoding="utf-8") as out_file:
                            json.dump(font_info, out_file, indent=4)
                        extracted_successfully = True

                elif obj_type == "MonoScript":
                    try:
                        script_info = {
                            'class_name': getattr(data, 'm_ClassName', 'Unknown'),
                            'namespace': getattr(data, 'm_Namespace', ''),
                            'assembly_name': getattr(data, 'm_AssemblyName', 'Unknown'),
                            'execution_order': getattr(data, 'm_ExecutionOrder', 0)
                        }
                        
                        if hasattr(data, "m_Script") and data.m_Script:
                            script_content = data.m_Script
                            if isinstance(script_content, bytes):
                                script_content = script_content.decode(errors="ignore")
                            
                            is_csharp = script_content.strip().startswith(("using ", "namespace ", "public class", "class "))
                            ext = ".cs" if is_csharp else ".txt"
                            
                            with open(final_output_path + ext, "w", encoding="utf-8", errors="replace") as out_file:
                                out_file.write(script_content)
                        
                        with open(final_output_path + "_info.json", "w", encoding="utf-8") as info_file:
                            json.dump(script_info, info_file, indent=4)
                        
                        extracted_successfully = True
                    except Exception as script_e:
                        debug_print(f"MonoScript extraction failed: {script_e}")

                elif obj_type == "MonoBehaviour":
                    try:
                        info = data.read_typetree()
                        with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                            json.dump(info, out_file, indent=4)
                        extracted_successfully = True
                    except:
                        basic_fields = {
                            'm_Name': getattr(data, 'm_Name', 'Unknown'),
                            'm_Enabled': getattr(data, 'm_Enabled', True),
                            'm_GameObject_PathID': data.m_GameObject.path_id if hasattr(data, 'm_GameObject') and hasattr(data.m_GameObject, 'path_id') else -1,
                            'm_Script_PathID': data.m_Script.path_id if hasattr(data, 'm_Script') and hasattr(data.m_Script, 'path_id') else -1
                        }
                        
                        with open(final_output_path + "_basic.json", "w", encoding="utf-8") as out_file:
                            json.dump(basic_fields, out_file, indent=4)
                        extracted_successfully = True

                else:
                    try:
                        info = data.read_typetree()
                    except AttributeError:
                        debug_print(f"read_typetree() failed for {obj_type}, using safe serialization.")
                        info = serialize_object_data(data)
                    except Exception as e:
                        debug_print(f"An unexpected error occurred with read_typetree for {obj_type}: {e}")
                        info = serialize_object_data(data)
                        log["errors"].append({
                            "object_id": obj.path_id,
                            "type": obj.type.name,
                            "error": f"read_typetree failed, using fallback serializer: {e}",
                            "traceback": traceback.format_exc() if DEBUG_MODE else ""
                        })

                    try:
                        with open(final_output_path + ".json", "w", encoding="utf-8") as out_file:
                            json.dump(info, out_file, indent=4)
                        extracted_successfully = True
                    except Exception as json_e:
                        debug_print(f"JSON serialization failed for {obj_type}: {json_e}")
                        with open(final_output_path + ".txt", "w", encoding="utf-8", errors="replace") as out_file:
                            out_file.write(str(info))
                        extracted_successfully = True
                        log["errors"].append({
                            "object_id": obj.path_id,
                            "type": obj.type.name,
                            "error": f"JSON dump failed, saved as .txt: {json_e}",
                            "traceback": ""
                        })

                if extracted_successfully:
                    log["successful_extractions"] += 1
                    extracted_counts[obj_type] += 1
                else:
                    log["failed_extractions"] += 1

            except Exception as e:
                log["failed_extractions"] += 1
                log["errors"].append({
                    "object_id": obj.path_id,
                    "type": obj.type.name,
                    "error": str(e),
                    "traceback": traceback.format_exc() if DEBUG_MODE else ""
                })
                debug_print(f"Critical extraction error for {obj_type}_{obj.path_id}: {e}")

            pbar.update(1)

    with open(metadata_file, "w", encoding="utf-8") as meta_file:
        json.dump(bundle_metadata, meta_file, indent=4)

    with open(type_tree_file, "w", encoding="utf-8") as tt_file:
        json.dump(type_tree_data, tt_file, indent=4)

    if all_dependencies:
        with open(dependencies_file, "w", encoding="utf-8") as dep_file:
            json.dump(all_dependencies, dep_file, indent=4)

    with open(log_file, "w", encoding="utf-8", errors="replace") as log_out:
        log_out.write("== Enhanced Unity Bundle Extraction Log ==\n")
        log_out.write(f"Timestamp: {log['timestamp']}\n")
        log_out.write(f"Bundle: {log['bundle_path']}\n")
        log_out.write(f"Signature: {log['bundle_info']['signature']}\n")
        log_out.write(f"Compression: {log['bundle_info']['compression']}\n")
        log_out.write(f"Size: {log['bundle_info']['size']} bytes\n\n")
        
        log_out.write(f"Total objects processed: {log['total_objects_processed']}\n")
        log_out.write(f"Successfully extracted: {log['successful_extractions']}\n")
        log_out.write(f"Failed extractions: {log['failed_extractions']}\n\n")
        
        log_out.write("== Asset Type Statistics ==\n")
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

    print(f"\nExtraction completed successfully!")
    print(f"Output directory: {output_dir}")
    print(f"Summary: {log['successful_extractions']} extracted, {log['failed_extractions']} failed")
    print(f"Generated files:")
    print(f"  - extraction_log.txt (detailed log)")
    print(f"  - bundle_metadata.json (bundle information)")
    print(f"  - type_tree.json (object type information)")
    if all_dependencies:
        print(f"  - dependencies.json (object dependencies)")
    print("Thanks for using this script! Credit: @lenzarchive (alwizba). Licensed under MIT License.")

def process_batch_extraction():
    print("Batch Extraction Mode")
    input_path = input("Enter folder path containing bundle files: ").strip()
    
    if not os.path.exists(input_path):
        print(f"Error: Path '{input_path}' not found.")
        return
    
    output_base = input("Enter base output directory: ").strip()
    if not output_base:
        print("Error: Output directory cannot be empty.")
        return
    
    bundle_files = []
    for root, dirs, files in os.walk(input_path):
        for file in files:
            if file.lower().endswith(('.bundle', '.unity3d', '.assets')):
                bundle_files.append(os.path.join(root, file))
    
    if not bundle_files:
        print("No bundle files found in the specified directory.")
        return
    
    print(f"Found {len(bundle_files)} bundle files")
    
    for i, bundle_file in enumerate(bundle_files, 1):
        print(f"\nProcessing [{i}/{len(bundle_files)}]: {os.path.basename(bundle_file)}")
        
        bundle_name = Path(bundle_file).stem
        output_dir = os.path.join(output_base, bundle_name)
        
        try:
            extract_bundle_advanced(bundle_file, output_dir)
        except Exception as e:
            print(f"Failed to process {bundle_file}: {e}")
            continue
    
    print(f"\nBatch extraction completed. Check '{output_base}' for results.")

def show_bundle_info():
    bundle_path = input("Enter bundle path for analysis: ").strip()
    
    if not os.path.exists(bundle_path):
        print(f"Error: File '{bundle_path}' not found.")
        return
    
    print(f"\nAnalyzing: {bundle_path}")
    print("=" * 60)
    
    file_info = get_file_signature(bundle_path)
    print(f"File size: {file_info['size']:,} bytes")
    print(f"Signature: {file_info['signature'].hex().upper()}")
    print(f"Compression: {file_info['compression']}")
    
    try:
        with open(bundle_path, "rb") as f:
            env = UnityPy.load(f)
        
        objects = list(env.objects)
        print(f"Unity version: {getattr(env, 'version', 'Unknown')}")
        print(f"Platform: {getattr(env, 'platform', 'Unknown')}")
        print(f"Total objects: {len(objects)}")
        
        type_counts = defaultdict(int)
        for obj in objects:
            type_counts[obj.type.name] += 1
        
        print(f"\nObject type distribution:")
        for obj_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {obj_type}: {count}")
        
        if hasattr(env, 'container') and env.container:
            print(f"\nContainer paths: {len(env.container)}")
            for path, obj_data in list(env.container.items())[:10]:
                print(f"  {path} -> {obj_data.type.name if hasattr(obj_data, 'type') else 'Unknown'}")
            if len(env.container) > 10:
                print(f"  ... and {len(env.container) - 10} more")
    
    except Exception as e:
        print(f"Error analyzing bundle: {e}")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--batch":
            process_batch_extraction()
            return
        elif sys.argv[1] == "--info":
            show_bundle_info()
            return
        elif sys.argv[1] == "--help":
            print("Enhanced Unity Bundle Extractor")
            print("Usage:")
            print("  python main.py                 - Interactive single extraction")
            print("  python main.py --batch         - Batch extraction mode")
            print("  python main.py --info          - Analyze bundle information")
            print("  python main.py --debug         - Enable debug output")
            print("  python main.py --help          - Show this help")
            return
    
    extract_bundle_advanced()

if __name__ == "__main__":
    main()
