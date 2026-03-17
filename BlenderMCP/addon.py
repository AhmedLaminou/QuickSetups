
# Code created by Siddharth Ahuja: www.github.com/ahujasid © 2025

import re
import bpy
import mathutils
import json
import threading
import socket
import time
import requests
import tempfile
import traceback
import os
import shutil
import zipfile
from bpy.props import IntProperty, BoolProperty
import io
from datetime import datetime
import hashlib, hmac, base64
import os.path as osp
from contextlib import redirect_stdout, suppress

bl_info = {
    "name": "Blender MCP",
    "author": "BlenderMCP",
    "version": (1, 2),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > BlenderMCP",
    "description": "Connect Blender to Claude via MCP",
    "category": "Interface",
}

RODIN_FREE_TRIAL_KEY = "k9TcfFoEhNd9cCPP2guHAHHHkctZHIRhZDywZ1euGUXwihbYLpOjQhofby80NJez"

# Add User-Agent as required by Poly Haven API
REQ_HEADERS = requests.utils.default_headers()
REQ_HEADERS.update({"User-Agent": "blender-mcp"})

class BlenderMCPServer:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.server_thread = None

    def start(self):
        if self.running:
            print("Server is already running")
            return

        self.running = True

        try:
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)

            # Start server thread
            self.server_thread = threading.Thread(target=self._server_loop)
            self.server_thread.daemon = True
            self.server_thread.start()

            print(f"BlenderMCP server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to start server: {str(e)}")
            self.stop()

    def stop(self):
        self.running = False

        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        # Wait for thread to finish
        if self.server_thread:
            try:
                if self.server_thread.is_alive():
                    self.server_thread.join(timeout=1.0)
            except:
                pass
            self.server_thread = None

        print("BlenderMCP server stopped")

    def _server_loop(self):
        """Main server loop in a separate thread"""
        print("Server thread started")
        self.socket.settimeout(1.0)  # Timeout to allow for stopping

        while self.running:
            try:
                # Accept new connection
                try:
                    client, address = self.socket.accept()
                    print(f"Connected to client: {address}")

                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    # Just check running condition
                    continue
                except Exception as e:
                    print(f"Error accepting connection: {str(e)}")
                    time.sleep(0.5)
            except Exception as e:
                print(f"Error in server loop: {str(e)}")
                if not self.running:
                    break
                time.sleep(0.5)

        print("Server thread stopped")

    def _handle_client(self, client):
        """Handle connected client"""
        print("Client handler started")
        client.settimeout(None)  # No timeout
        buffer = b''

        try:
            while self.running:
                # Receive data
                try:
                    data = client.recv(8192)
                    if not data:
                        print("Client disconnected")
                        break

                    buffer += data
                    try:
                        # Try to parse command
                        command = json.loads(buffer.decode('utf-8'))
                        buffer = b''

                        # Execute command in Blender's main thread
                        def execute_wrapper():
                            try:
                                response = self.execute_command(command)
                                response_json = json.dumps(response)
                                try:
                                    client.sendall(response_json.encode('utf-8'))
                                except:
                                    print("Failed to send response - client disconnected")
                            except Exception as e:
                                print(f"Error executing command: {str(e)}")
                                traceback.print_exc()
                                try:
                                    error_response = {
                                        "status": "error",
                                        "message": str(e)
                                    }
                                    client.sendall(json.dumps(error_response).encode('utf-8'))
                                except:
                                    pass
                            return None

                        # Schedule execution in main thread
                        bpy.app.timers.register(execute_wrapper, first_interval=0.0)
                    except json.JSONDecodeError:
                        # Incomplete data, wait for more
                        pass
                except Exception as e:
                    print(f"Error receiving data: {str(e)}")
                    break
        except Exception as e:
            print(f"Error in client handler: {str(e)}")
        finally:
            try:
                client.close()
            except:
                pass
            print("Client handler stopped")

    def execute_command(self, command):
        """Execute a command in the main Blender thread"""
        try:
            return self._execute_command_internal(command)

        except Exception as e:
            print(f"Error executing command: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _execute_command_internal(self, command):
        """Internal command execution with proper context"""
        cmd_type = command.get("type")
        params = command.get("params", {})

        # Add a handler for checking PolyHaven status
        if cmd_type == "get_polyhaven_status":
            return {"status": "success", "result": self.get_polyhaven_status()}

        # Base handlers that are always available
        handlers = {
            "get_scene_info": self.get_scene_info,
            "get_object_info": self.get_object_info,
            "get_viewport_screenshot": self.get_viewport_screenshot,
            "execute_code": self.execute_code,
            "get_telemetry_consent": self.get_telemetry_consent,
            "get_polyhaven_status": self.get_polyhaven_status,
            "get_hyper3d_status": self.get_hyper3d_status,
            "get_sketchfab_status": self.get_sketchfab_status,
            "get_hunyuan3d_status": self.get_hunyuan3d_status,
            # Extended Blender control tools
            "list_materials": self.list_materials,
            "get_material_info": self.get_material_info,
            "modify_material": self.modify_material,
            "create_material": self.create_material,
            "assign_material": self.assign_material,
            "batch_modify_materials": self.batch_modify_materials,
            "list_collections": self.list_collections,
            "manage_collection": self.manage_collection,
            "select_objects": self.select_objects,
            "modify_object": self.modify_object,
            "delete_objects": self.delete_objects,
            "duplicate_objects": self.duplicate_objects,
            "find_objects": self.find_objects,
            "set_object_color": self.set_object_color,
            "move_to_collection": self.move_to_collection,
            "set_viewport_shading": self.set_viewport_shading,
            "set_viewport_camera": self.set_viewport_camera,
            "set_render_engine": self.set_render_engine,
            "get_render_settings": self.get_render_settings,
            "set_render_settings": self.set_render_settings,
            "manage_world": self.manage_world,
            "manage_lights": self.manage_lights,
            "list_addons": self.list_addons,
            "enable_addon": self.enable_addon,
            "save_file": self.save_file,
            "export_scene": self.export_scene,
            "get_scene_stats": self.get_scene_stats,
            "recalculate_normals": self.recalculate_normals,
            "fix_materials_missing": self.fix_materials_missing,
            # Phase 2 tools - full human-level control
            "manage_modifiers": self.manage_modifiers,
            "edit_geometry_nodes": self.edit_geometry_nodes,
            "mesh_operations": self.mesh_operations,
            "file_operations": self.file_operations,
            "purge_data": self.purge_data,
            "manage_hierarchy": self.manage_hierarchy,
            "batch_transform": self.batch_transform,
            "render_image": self.render_image,
            "manage_uv": self.manage_uv,
            "manage_constraints": self.manage_constraints,
            "save_collection_as_file": self.save_collection_as_file,
            "call_operator": self.call_operator,
            "manage_cameras": self.manage_cameras,
            "manage_images": self.manage_images,
        }

        # Add Polyhaven handlers only if enabled
        if bpy.context.scene.blendermcp_use_polyhaven:
            polyhaven_handlers = {
                "get_polyhaven_categories": self.get_polyhaven_categories,
                "search_polyhaven_assets": self.search_polyhaven_assets,
                "download_polyhaven_asset": self.download_polyhaven_asset,
                "set_texture": self.set_texture,
            }
            handlers.update(polyhaven_handlers)

        # Add Hyper3d handlers only if enabled
        if bpy.context.scene.blendermcp_use_hyper3d:
            polyhaven_handlers = {
                "create_rodin_job": self.create_rodin_job,
                "poll_rodin_job_status": self.poll_rodin_job_status,
                "import_generated_asset": self.import_generated_asset,
            }
            handlers.update(polyhaven_handlers)

        # Add Sketchfab handlers only if enabled
        if bpy.context.scene.blendermcp_use_sketchfab:
            sketchfab_handlers = {
                "search_sketchfab_models": self.search_sketchfab_models,
                "get_sketchfab_model_preview": self.get_sketchfab_model_preview,
                "download_sketchfab_model": self.download_sketchfab_model,
            }
            handlers.update(sketchfab_handlers)
        
        # Add Hunyuan3d handlers only if enabled
        if bpy.context.scene.blendermcp_use_hunyuan3d:
            hunyuan_handlers = {
                "create_hunyuan_job": self.create_hunyuan_job,
                "poll_hunyuan_job_status": self.poll_hunyuan_job_status,
                "import_generated_asset_hunyuan": self.import_generated_asset_hunyuan
            }
            handlers.update(hunyuan_handlers)

        handler = handlers.get(cmd_type)
        if handler:
            try:
                print(f"Executing handler for {cmd_type}")
                result = handler(**params)
                print(f"Handler execution complete")
                return {"status": "success", "result": result}
            except Exception as e:
                print(f"Error in handler: {str(e)}")
                traceback.print_exc()
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}



    def get_scene_info(self):
        """Get information about the current Blender scene"""
        try:
            print("Getting scene info...")
            # Simplify the scene info to reduce data size
            scene_info = {
                "name": bpy.context.scene.name,
                "object_count": len(bpy.context.scene.objects),
                "objects": [],
                "materials_count": len(bpy.data.materials),
            }

            # Collect minimal object information (limit to first 10 objects)
            for i, obj in enumerate(bpy.context.scene.objects):
                if i >= 10:  # Reduced from 20 to 10
                    break

                obj_info = {
                    "name": obj.name,
                    "type": obj.type,
                    # Only include basic location data
                    "location": [round(float(obj.location.x), 2),
                                round(float(obj.location.y), 2),
                                round(float(obj.location.z), 2)],
                }
                scene_info["objects"].append(obj_info)

            print(f"Scene info collected: {len(scene_info['objects'])} objects")
            return scene_info
        except Exception as e:
            print(f"Error in get_scene_info: {str(e)}")
            traceback.print_exc()
            return {"error": str(e)}

    @staticmethod
    def _get_aabb(obj):
        """ Returns the world-space axis-aligned bounding box (AABB) of an object. """
        if obj.type != 'MESH':
            raise TypeError("Object must be a mesh")

        # Get the bounding box corners in local space
        local_bbox_corners = [mathutils.Vector(corner) for corner in obj.bound_box]

        # Convert to world coordinates
        world_bbox_corners = [obj.matrix_world @ corner for corner in local_bbox_corners]

        # Compute axis-aligned min/max coordinates
        min_corner = mathutils.Vector(map(min, zip(*world_bbox_corners)))
        max_corner = mathutils.Vector(map(max, zip(*world_bbox_corners)))

        return [
            [*min_corner], [*max_corner]
        ]



    def get_object_info(self, name):
        """Get detailed information about a specific object"""
        obj = bpy.data.objects.get(name)
        if not obj:
            raise ValueError(f"Object not found: {name}")

        # Basic object info
        obj_info = {
            "name": obj.name,
            "type": obj.type,
            "location": [obj.location.x, obj.location.y, obj.location.z],
            "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
            "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            "visible": obj.visible_get(),
            "materials": [],
        }

        if obj.type == "MESH":
            bounding_box = self._get_aabb(obj)
            obj_info["world_bounding_box"] = bounding_box

        # Add material slots
        for slot in obj.material_slots:
            if slot.material:
                obj_info["materials"].append(slot.material.name)

        # Add mesh data if applicable
        if obj.type == 'MESH' and obj.data:
            mesh = obj.data
            obj_info["mesh"] = {
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
            }

        return obj_info

    def get_viewport_screenshot(self, max_size=800, filepath=None, format="png"):
        """
        Capture a screenshot of the current 3D viewport and save it to the specified path.

        Parameters:
        - max_size: Maximum size in pixels for the largest dimension of the image
        - filepath: Path where to save the screenshot file
        - format: Image format (png, jpg, etc.)

        Returns success/error status
        """
        try:
            if not filepath:
                return {"error": "No filepath provided"}

            # Find the active 3D viewport
            area = None
            for a in bpy.context.screen.areas:
                if a.type == 'VIEW_3D':
                    area = a
                    break

            if not area:
                return {"error": "No 3D viewport found"}

            # Take screenshot with proper context override
            with bpy.context.temp_override(area=area):
                bpy.ops.screen.screenshot_area(filepath=filepath)

            # Load and resize if needed
            img = bpy.data.images.load(filepath)
            width, height = img.size

            if max(width, height) > max_size:
                scale = max_size / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img.scale(new_width, new_height)

                # Set format and save
                img.file_format = format.upper()
                img.save()
                width, height = new_width, new_height

            # Cleanup Blender image data
            bpy.data.images.remove(img)

            return {
                "success": True,
                "width": width,
                "height": height,
                "filepath": filepath
            }

        except Exception as e:
            return {"error": str(e)}

    def execute_code(self, code):
        """Execute arbitrary Blender Python code"""
        # This is powerful but potentially dangerous - use with caution
        try:
            # Create a local namespace for execution
            namespace = {"bpy": bpy}

            # Capture stdout during execution, and return it as result
            capture_buffer = io.StringIO()
            with redirect_stdout(capture_buffer):
                exec(code, namespace)

            captured_output = capture_buffer.getvalue()
            return {"executed": True, "result": captured_output}
        except Exception as e:
            raise Exception(f"Code execution error: {str(e)}")



    def get_polyhaven_categories(self, asset_type):
        """Get categories for a specific asset type from Polyhaven"""
        try:
            if asset_type not in ["hdris", "textures", "models", "all"]:
                return {"error": f"Invalid asset type: {asset_type}. Must be one of: hdris, textures, models, all"}

            response = requests.get(f"https://api.polyhaven.com/categories/{asset_type}", headers=REQ_HEADERS)
            if response.status_code == 200:
                return {"categories": response.json()}
            else:
                return {"error": f"API request failed with status code {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def search_polyhaven_assets(self, asset_type=None, categories=None):
        """Search for assets from Polyhaven with optional filtering"""
        try:
            url = "https://api.polyhaven.com/assets"
            params = {}

            if asset_type and asset_type != "all":
                if asset_type not in ["hdris", "textures", "models"]:
                    return {"error": f"Invalid asset type: {asset_type}. Must be one of: hdris, textures, models, all"}
                params["type"] = asset_type

            if categories:
                params["categories"] = categories

            response = requests.get(url, params=params, headers=REQ_HEADERS)
            if response.status_code == 200:
                # Limit the response size to avoid overwhelming Blender
                assets = response.json()
                # Return only the first 20 assets to keep response size manageable
                limited_assets = {}
                for i, (key, value) in enumerate(assets.items()):
                    if i >= 20:  # Limit to 20 assets
                        break
                    limited_assets[key] = value

                return {"assets": limited_assets, "total_count": len(assets), "returned_count": len(limited_assets)}
            else:
                return {"error": f"API request failed with status code {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def download_polyhaven_asset(self, asset_id, asset_type, resolution="1k", file_format=None):
        try:
            # First get the files information
            files_response = requests.get(f"https://api.polyhaven.com/files/{asset_id}", headers=REQ_HEADERS)
            if files_response.status_code != 200:
                return {"error": f"Failed to get asset files: {files_response.status_code}"}

            files_data = files_response.json()

            # Handle different asset types
            if asset_type == "hdris":
                # For HDRIs, download the .hdr or .exr file
                if not file_format:
                    file_format = "hdr"  # Default format for HDRIs

                if "hdri" in files_data and resolution in files_data["hdri"] and file_format in files_data["hdri"][resolution]:
                    file_info = files_data["hdri"][resolution][file_format]
                    file_url = file_info["url"]

                    # For HDRIs, we need to save to a temporary file first
                    # since Blender can't properly load HDR data directly from memory
                    with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False) as tmp_file:
                        # Download the file
                        response = requests.get(file_url, headers=REQ_HEADERS)
                        if response.status_code != 200:
                            return {"error": f"Failed to download HDRI: {response.status_code}"}

                        tmp_file.write(response.content)
                        tmp_path = tmp_file.name

                    try:
                        # Create a new world if none exists
                        if not bpy.data.worlds:
                            bpy.data.worlds.new("World")

                        world = bpy.data.worlds[0]
                        world.use_nodes = True
                        node_tree = world.node_tree

                        # Clear existing nodes
                        for node in node_tree.nodes:
                            node_tree.nodes.remove(node)

                        # Create nodes
                        tex_coord = node_tree.nodes.new(type='ShaderNodeTexCoord')
                        tex_coord.location = (-800, 0)

                        mapping = node_tree.nodes.new(type='ShaderNodeMapping')
                        mapping.location = (-600, 0)

                        # Load the image from the temporary file
                        env_tex = node_tree.nodes.new(type='ShaderNodeTexEnvironment')
                        env_tex.location = (-400, 0)
                        env_tex.image = bpy.data.images.load(tmp_path)

                        # Use a color space that exists in all Blender versions
                        if file_format.lower() == 'exr':
                            # Try to use Linear color space for EXR files
                            try:
                                env_tex.image.colorspace_settings.name = 'Linear'
                            except:
                                # Fallback to Non-Color if Linear isn't available
                                env_tex.image.colorspace_settings.name = 'Non-Color'
                        else:  # hdr
                            # For HDR files, try these options in order
                            for color_space in ['Linear', 'Linear Rec.709', 'Non-Color']:
                                try:
                                    env_tex.image.colorspace_settings.name = color_space
                                    break  # Stop if we successfully set a color space
                                except:
                                    continue

                        background = node_tree.nodes.new(type='ShaderNodeBackground')
                        background.location = (-200, 0)

                        output = node_tree.nodes.new(type='ShaderNodeOutputWorld')
                        output.location = (0, 0)

                        # Connect nodes
                        node_tree.links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
                        node_tree.links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])
                        node_tree.links.new(env_tex.outputs['Color'], background.inputs['Color'])
                        node_tree.links.new(background.outputs['Background'], output.inputs['Surface'])

                        # Set as active world
                        bpy.context.scene.world = world

                        # Clean up temporary file
                        try:
                            tempfile._cleanup()  # This will clean up all temporary files
                        except:
                            pass

                        return {
                            "success": True,
                            "message": f"HDRI {asset_id} imported successfully",
                            "image_name": env_tex.image.name
                        }
                    except Exception as e:
                        return {"error": f"Failed to set up HDRI in Blender: {str(e)}"}
                else:
                    return {"error": f"Requested resolution or format not available for this HDRI"}

            elif asset_type == "textures":
                if not file_format:
                    file_format = "jpg"  # Default format for textures

                downloaded_maps = {}

                try:
                    for map_type in files_data:
                        if map_type not in ["blend", "gltf"]:  # Skip non-texture files
                            if resolution in files_data[map_type] and file_format in files_data[map_type][resolution]:
                                file_info = files_data[map_type][resolution][file_format]
                                file_url = file_info["url"]

                                # Use NamedTemporaryFile like we do for HDRIs
                                with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False) as tmp_file:
                                    # Download the file
                                    response = requests.get(file_url, headers=REQ_HEADERS)
                                    if response.status_code == 200:
                                        tmp_file.write(response.content)
                                        tmp_path = tmp_file.name

                                        # Load image from temporary file
                                        image = bpy.data.images.load(tmp_path)
                                        image.name = f"{asset_id}_{map_type}.{file_format}"

                                        # Pack the image into .blend file
                                        image.pack()

                                        # Set color space based on map type
                                        if map_type in ['color', 'diffuse', 'albedo']:
                                            try:
                                                image.colorspace_settings.name = 'sRGB'
                                            except:
                                                pass
                                        else:
                                            try:
                                                image.colorspace_settings.name = 'Non-Color'
                                            except:
                                                pass

                                        downloaded_maps[map_type] = image

                                        # Clean up temporary file
                                        try:
                                            os.unlink(tmp_path)
                                        except:
                                            pass

                    if not downloaded_maps:
                        return {"error": f"No texture maps found for the requested resolution and format"}

                    # Create a new material with the downloaded textures
                    mat = bpy.data.materials.new(name=asset_id)
                    mat.use_nodes = True
                    nodes = mat.node_tree.nodes
                    links = mat.node_tree.links

                    # Clear default nodes
                    for node in nodes:
                        nodes.remove(node)

                    # Create output node
                    output = nodes.new(type='ShaderNodeOutputMaterial')
                    output.location = (300, 0)

                    # Create principled BSDF node
                    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
                    principled.location = (0, 0)
                    links.new(principled.outputs[0], output.inputs[0])

                    # Add texture nodes based on available maps
                    tex_coord = nodes.new(type='ShaderNodeTexCoord')
                    tex_coord.location = (-800, 0)

                    mapping = nodes.new(type='ShaderNodeMapping')
                    mapping.location = (-600, 0)
                    mapping.vector_type = 'TEXTURE'  # Changed from default 'POINT' to 'TEXTURE'
                    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

                    # Position offset for texture nodes
                    x_pos = -400
                    y_pos = 300

                    # Connect different texture maps
                    for map_type, image in downloaded_maps.items():
                        tex_node = nodes.new(type='ShaderNodeTexImage')
                        tex_node.location = (x_pos, y_pos)
                        tex_node.image = image

                        # Set color space based on map type
                        if map_type.lower() in ['color', 'diffuse', 'albedo']:
                            try:
                                tex_node.image.colorspace_settings.name = 'sRGB'
                            except:
                                pass  # Use default if sRGB not available
                        else:
                            try:
                                tex_node.image.colorspace_settings.name = 'Non-Color'
                            except:
                                pass  # Use default if Non-Color not available

                        links.new(mapping.outputs['Vector'], tex_node.inputs['Vector'])

                        # Connect to appropriate input on Principled BSDF
                        if map_type.lower() in ['color', 'diffuse', 'albedo']:
                            links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
                        elif map_type.lower() in ['roughness', 'rough']:
                            links.new(tex_node.outputs['Color'], principled.inputs['Roughness'])
                        elif map_type.lower() in ['metallic', 'metalness', 'metal']:
                            links.new(tex_node.outputs['Color'], principled.inputs['Metallic'])
                        elif map_type.lower() in ['normal', 'nor']:
                            # Add normal map node
                            normal_map = nodes.new(type='ShaderNodeNormalMap')
                            normal_map.location = (x_pos + 200, y_pos)
                            links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
                            links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
                        elif map_type in ['displacement', 'disp', 'height']:
                            # Add displacement node
                            disp_node = nodes.new(type='ShaderNodeDisplacement')
                            disp_node.location = (x_pos + 200, y_pos - 200)
                            links.new(tex_node.outputs['Color'], disp_node.inputs['Height'])
                            links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])

                        y_pos -= 250

                    return {
                        "success": True,
                        "message": f"Texture {asset_id} imported as material",
                        "material": mat.name,
                        "maps": list(downloaded_maps.keys())
                    }

                except Exception as e:
                    return {"error": f"Failed to process textures: {str(e)}"}

            elif asset_type == "models":
                # For models, prefer glTF format if available
                if not file_format:
                    file_format = "gltf"  # Default format for models

                if file_format in files_data and resolution in files_data[file_format]:
                    file_info = files_data[file_format][resolution][file_format]
                    file_url = file_info["url"]

                    # Create a temporary directory to store the model and its dependencies
                    temp_dir = tempfile.mkdtemp()
                    main_file_path = ""

                    try:
                        # Download the main model file
                        main_file_name = file_url.split("/")[-1]
                        main_file_path = os.path.join(temp_dir, main_file_name)

                        response = requests.get(file_url, headers=REQ_HEADERS)
                        if response.status_code != 200:
                            return {"error": f"Failed to download model: {response.status_code}"}

                        with open(main_file_path, "wb") as f:
                            f.write(response.content)

                        # Check for included files and download them
                        if "include" in file_info and file_info["include"]:
                            for include_path, include_info in file_info["include"].items():
                                # Get the URL for the included file - this is the fix
                                include_url = include_info["url"]

                                # Create the directory structure for the included file
                                include_file_path = os.path.join(temp_dir, include_path)
                                os.makedirs(os.path.dirname(include_file_path), exist_ok=True)

                                # Download the included file
                                include_response = requests.get(include_url, headers=REQ_HEADERS)
                                if include_response.status_code == 200:
                                    with open(include_file_path, "wb") as f:
                                        f.write(include_response.content)
                                else:
                                    print(f"Failed to download included file: {include_path}")

                        # Import the model into Blender
                        if file_format == "gltf" or file_format == "glb":
                            bpy.ops.import_scene.gltf(filepath=main_file_path)
                        elif file_format == "fbx":
                            bpy.ops.import_scene.fbx(filepath=main_file_path)
                        elif file_format == "obj":
                            bpy.ops.import_scene.obj(filepath=main_file_path)
                        elif file_format == "blend":
                            # For blend files, we need to append or link
                            with bpy.data.libraries.load(main_file_path, link=False) as (data_from, data_to):
                                data_to.objects = data_from.objects

                            # Link the objects to the scene
                            for obj in data_to.objects:
                                if obj is not None:
                                    bpy.context.collection.objects.link(obj)
                        else:
                            return {"error": f"Unsupported model format: {file_format}"}

                        # Get the names of imported objects
                        imported_objects = [obj.name for obj in bpy.context.selected_objects]

                        return {
                            "success": True,
                            "message": f"Model {asset_id} imported successfully",
                            "imported_objects": imported_objects
                        }
                    except Exception as e:
                        return {"error": f"Failed to import model: {str(e)}"}
                    finally:
                        # Clean up temporary directory
                        with suppress(Exception):
                            shutil.rmtree(temp_dir)
                else:
                    return {"error": f"Requested format or resolution not available for this model"}

            else:
                return {"error": f"Unsupported asset type: {asset_type}"}

        except Exception as e:
            return {"error": f"Failed to download asset: {str(e)}"}

    def set_texture(self, object_name, texture_id):
        """Apply a previously downloaded Polyhaven texture to an object by creating a new material"""
        try:
            # Get the object
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"error": f"Object not found: {object_name}"}

            # Make sure object can accept materials
            if not hasattr(obj, 'data') or not hasattr(obj.data, 'materials'):
                return {"error": f"Object {object_name} cannot accept materials"}

            # Find all images related to this texture and ensure they're properly loaded
            texture_images = {}
            for img in bpy.data.images:
                if img.name.startswith(texture_id + "_"):
                    # Extract the map type from the image name
                    map_type = img.name.split('_')[-1].split('.')[0]

                    # Force a reload of the image
                    img.reload()

                    # Ensure proper color space
                    if map_type.lower() in ['color', 'diffuse', 'albedo']:
                        try:
                            img.colorspace_settings.name = 'sRGB'
                        except:
                            pass
                    else:
                        try:
                            img.colorspace_settings.name = 'Non-Color'
                        except:
                            pass

                    # Ensure the image is packed
                    if not img.packed_file:
                        img.pack()

                    texture_images[map_type] = img
                    print(f"Loaded texture map: {map_type} - {img.name}")

                    # Debug info
                    print(f"Image size: {img.size[0]}x{img.size[1]}")
                    print(f"Color space: {img.colorspace_settings.name}")
                    print(f"File format: {img.file_format}")
                    print(f"Is packed: {bool(img.packed_file)}")

            if not texture_images:
                return {"error": f"No texture images found for: {texture_id}. Please download the texture first."}

            # Create a new material
            new_mat_name = f"{texture_id}_material_{object_name}"

            # Remove any existing material with this name to avoid conflicts
            existing_mat = bpy.data.materials.get(new_mat_name)
            if existing_mat:
                bpy.data.materials.remove(existing_mat)

            new_mat = bpy.data.materials.new(name=new_mat_name)
            new_mat.use_nodes = True

            # Set up the material nodes
            nodes = new_mat.node_tree.nodes
            links = new_mat.node_tree.links

            # Clear default nodes
            nodes.clear()

            # Create output node
            output = nodes.new(type='ShaderNodeOutputMaterial')
            output.location = (600, 0)

            # Create principled BSDF node
            principled = nodes.new(type='ShaderNodeBsdfPrincipled')
            principled.location = (300, 0)
            links.new(principled.outputs[0], output.inputs[0])

            # Add texture nodes based on available maps
            tex_coord = nodes.new(type='ShaderNodeTexCoord')
            tex_coord.location = (-800, 0)

            mapping = nodes.new(type='ShaderNodeMapping')
            mapping.location = (-600, 0)
            mapping.vector_type = 'TEXTURE'  # Changed from default 'POINT' to 'TEXTURE'
            links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

            # Position offset for texture nodes
            x_pos = -400
            y_pos = 300

            # Connect different texture maps
            for map_type, image in texture_images.items():
                tex_node = nodes.new(type='ShaderNodeTexImage')
                tex_node.location = (x_pos, y_pos)
                tex_node.image = image

                # Set color space based on map type
                if map_type.lower() in ['color', 'diffuse', 'albedo']:
                    try:
                        tex_node.image.colorspace_settings.name = 'sRGB'
                    except:
                        pass  # Use default if sRGB not available
                else:
                    try:
                        tex_node.image.colorspace_settings.name = 'Non-Color'
                    except:
                        pass  # Use default if Non-Color not available

                links.new(mapping.outputs['Vector'], tex_node.inputs['Vector'])

                # Connect to appropriate input on Principled BSDF
                if map_type.lower() in ['color', 'diffuse', 'albedo']:
                    links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
                elif map_type.lower() in ['roughness', 'rough']:
                    links.new(tex_node.outputs['Color'], principled.inputs['Roughness'])
                elif map_type.lower() in ['metallic', 'metalness', 'metal']:
                    links.new(tex_node.outputs['Color'], principled.inputs['Metallic'])
                elif map_type.lower() in ['normal', 'nor', 'dx', 'gl']:
                    # Add normal map node
                    normal_map = nodes.new(type='ShaderNodeNormalMap')
                    normal_map.location = (x_pos + 200, y_pos)
                    links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
                    links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
                elif map_type.lower() in ['displacement', 'disp', 'height']:
                    # Add displacement node
                    disp_node = nodes.new(type='ShaderNodeDisplacement')
                    disp_node.location = (x_pos + 200, y_pos - 200)
                    disp_node.inputs['Scale'].default_value = 0.1  # Reduce displacement strength
                    links.new(tex_node.outputs['Color'], disp_node.inputs['Height'])
                    links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])

                y_pos -= 250

            # Second pass: Connect nodes with proper handling for special cases
            texture_nodes = {}

            # First find all texture nodes and store them by map type
            for node in nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    for map_type, image in texture_images.items():
                        if node.image == image:
                            texture_nodes[map_type] = node
                            break

            # Now connect everything using the nodes instead of images
            # Handle base color (diffuse)
            for map_name in ['color', 'diffuse', 'albedo']:
                if map_name in texture_nodes:
                    links.new(texture_nodes[map_name].outputs['Color'], principled.inputs['Base Color'])
                    print(f"Connected {map_name} to Base Color")
                    break

            # Handle roughness
            for map_name in ['roughness', 'rough']:
                if map_name in texture_nodes:
                    links.new(texture_nodes[map_name].outputs['Color'], principled.inputs['Roughness'])
                    print(f"Connected {map_name} to Roughness")
                    break

            # Handle metallic
            for map_name in ['metallic', 'metalness', 'metal']:
                if map_name in texture_nodes:
                    links.new(texture_nodes[map_name].outputs['Color'], principled.inputs['Metallic'])
                    print(f"Connected {map_name} to Metallic")
                    break

            # Handle normal maps
            for map_name in ['gl', 'dx', 'nor']:
                if map_name in texture_nodes:
                    normal_map_node = nodes.new(type='ShaderNodeNormalMap')
                    normal_map_node.location = (100, 100)
                    links.new(texture_nodes[map_name].outputs['Color'], normal_map_node.inputs['Color'])
                    links.new(normal_map_node.outputs['Normal'], principled.inputs['Normal'])
                    print(f"Connected {map_name} to Normal")
                    break

            # Handle displacement
            for map_name in ['displacement', 'disp', 'height']:
                if map_name in texture_nodes:
                    disp_node = nodes.new(type='ShaderNodeDisplacement')
                    disp_node.location = (300, -200)
                    disp_node.inputs['Scale'].default_value = 0.1  # Reduce displacement strength
                    links.new(texture_nodes[map_name].outputs['Color'], disp_node.inputs['Height'])
                    links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])
                    print(f"Connected {map_name} to Displacement")
                    break

            # Handle ARM texture (Ambient Occlusion, Roughness, Metallic)
            if 'arm' in texture_nodes:
                separate_rgb = nodes.new(type='ShaderNodeSeparateRGB')
                separate_rgb.location = (-200, -100)
                links.new(texture_nodes['arm'].outputs['Color'], separate_rgb.inputs['Image'])

                # Connect Roughness (G) if no dedicated roughness map
                if not any(map_name in texture_nodes for map_name in ['roughness', 'rough']):
                    links.new(separate_rgb.outputs['G'], principled.inputs['Roughness'])
                    print("Connected ARM.G to Roughness")

                # Connect Metallic (B) if no dedicated metallic map
                if not any(map_name in texture_nodes for map_name in ['metallic', 'metalness', 'metal']):
                    links.new(separate_rgb.outputs['B'], principled.inputs['Metallic'])
                    print("Connected ARM.B to Metallic")

                # For AO (R channel), multiply with base color if we have one
                base_color_node = None
                for map_name in ['color', 'diffuse', 'albedo']:
                    if map_name in texture_nodes:
                        base_color_node = texture_nodes[map_name]
                        break

                if base_color_node:
                    mix_node = nodes.new(type='ShaderNodeMixRGB')
                    mix_node.location = (100, 200)
                    mix_node.blend_type = 'MULTIPLY'
                    mix_node.inputs['Fac'].default_value = 0.8  # 80% influence

                    # Disconnect direct connection to base color
                    for link in base_color_node.outputs['Color'].links:
                        if link.to_socket == principled.inputs['Base Color']:
                            links.remove(link)

                    # Connect through the mix node
                    links.new(base_color_node.outputs['Color'], mix_node.inputs[1])
                    links.new(separate_rgb.outputs['R'], mix_node.inputs[2])
                    links.new(mix_node.outputs['Color'], principled.inputs['Base Color'])
                    print("Connected ARM.R to AO mix with Base Color")

            # Handle AO (Ambient Occlusion) if separate
            if 'ao' in texture_nodes:
                base_color_node = None
                for map_name in ['color', 'diffuse', 'albedo']:
                    if map_name in texture_nodes:
                        base_color_node = texture_nodes[map_name]
                        break

                if base_color_node:
                    mix_node = nodes.new(type='ShaderNodeMixRGB')
                    mix_node.location = (100, 200)
                    mix_node.blend_type = 'MULTIPLY'
                    mix_node.inputs['Fac'].default_value = 0.8  # 80% influence

                    # Disconnect direct connection to base color
                    for link in base_color_node.outputs['Color'].links:
                        if link.to_socket == principled.inputs['Base Color']:
                            links.remove(link)

                    # Connect through the mix node
                    links.new(base_color_node.outputs['Color'], mix_node.inputs[1])
                    links.new(texture_nodes['ao'].outputs['Color'], mix_node.inputs[2])
                    links.new(mix_node.outputs['Color'], principled.inputs['Base Color'])
                    print("Connected AO to mix with Base Color")

            # CRITICAL: Make sure to clear all existing materials from the object
            while len(obj.data.materials) > 0:
                obj.data.materials.pop(index=0)

            # Assign the new material to the object
            obj.data.materials.append(new_mat)

            # CRITICAL: Make the object active and select it
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)

            # CRITICAL: Force Blender to update the material
            bpy.context.view_layer.update()

            # Get the list of texture maps
            texture_maps = list(texture_images.keys())

            # Get info about texture nodes for debugging
            material_info = {
                "name": new_mat.name,
                "has_nodes": new_mat.use_nodes,
                "node_count": len(new_mat.node_tree.nodes),
                "texture_nodes": []
            }

            for node in new_mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    connections = []
                    for output in node.outputs:
                        for link in output.links:
                            connections.append(f"{output.name} → {link.to_node.name}.{link.to_socket.name}")

                    material_info["texture_nodes"].append({
                        "name": node.name,
                        "image": node.image.name,
                        "colorspace": node.image.colorspace_settings.name,
                        "connections": connections
                    })

            return {
                "success": True,
                "message": f"Created new material and applied texture {texture_id} to {object_name}",
                "material": new_mat.name,
                "maps": texture_maps,
                "material_info": material_info
            }

        except Exception as e:
            print(f"Error in set_texture: {str(e)}")
            traceback.print_exc()
            return {"error": f"Failed to apply texture: {str(e)}"}

    # ================================================================
    # EXTENDED BLENDER CONTROL TOOLS
    # ================================================================

    # ---- MODIFIER MANAGEMENT ----
    def manage_modifiers(self, object_name, action="list", modifier_name=None,
                         modifier_type=None, properties=None, apply_as="DATA"):
        """Full modifier management: list, add, remove, apply, move, configure.
        action: list|add|remove|apply|apply_all|move_up|move_down|configure
        modifier_type: ARRAY, BOOLEAN, SOLIDIFY, SUBSURF, MIRROR, BEVEL, NODES, etc.
        properties: dict of modifier property names→values to set"""
        try:
            import bpy
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"error": f"Object '{object_name}' not found"}
            if action == "list":
                mods = []
                for m in obj.modifiers:
                    info = {"name": m.name, "type": m.type, "show_viewport": m.show_viewport,
                            "show_render": m.show_render}
                    if m.type == 'NODES' and m.node_group:
                        info["node_group"] = m.node_group.name
                        inputs = {}
                        for i, inp in enumerate(m.node_group.interface.items_tree):
                            if inp.item_type == 'SOCKET' and inp.in_out == 'INPUT':
                                key = inp.name
                                try:
                                    val = m[inp.identifier]
                                    if hasattr(val, '__iter__'):
                                        val = list(val)
                                    inputs[key] = val
                                except:
                                    inputs[key] = "N/A"
                        info["inputs"] = inputs
                    mods.append(info)
                return {"object": object_name, "modifiers": mods, "count": len(mods)}
            elif action == "add":
                if not modifier_type:
                    return {"error": "modifier_type required for add"}
                mod = obj.modifiers.new(name=modifier_name or modifier_type, type=modifier_type)
                if properties:
                    for k, v in properties.items():
                        try:
                            setattr(mod, k, v)
                        except:
                            pass
                return {"success": True, "modifier": mod.name, "type": mod.type}
            elif action == "remove":
                if not modifier_name:
                    return {"error": "modifier_name required"}
                mod = obj.modifiers.get(modifier_name)
                if not mod:
                    return {"error": f"Modifier '{modifier_name}' not found"}
                obj.modifiers.remove(mod)
                return {"success": True, "removed": modifier_name}
            elif action == "apply":
                if not modifier_name:
                    return {"error": "modifier_name required"}
                ctx = bpy.context.copy()
                ctx['object'] = obj
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.modifier_apply(modifier=modifier_name, apply_as=apply_as)
                return {"success": True, "applied": modifier_name}
            elif action == "apply_all":
                applied = []
                bpy.context.view_layer.objects.active = obj
                for mod in list(obj.modifiers):
                    try:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                        applied.append(mod.name)
                    except:
                        pass
                return {"success": True, "applied": applied}
            elif action == "configure":
                if not modifier_name or not properties:
                    return {"error": "modifier_name and properties required"}
                mod = obj.modifiers.get(modifier_name)
                if not mod:
                    return {"error": f"Modifier '{modifier_name}' not found"}
                set_props = {}
                for k, v in properties.items():
                    try:
                        setattr(mod, k, v)
                        set_props[k] = v
                    except Exception as e:
                        set_props[k] = f"FAILED: {e}"
                return {"success": True, "configured": set_props}
            elif action in ("move_up", "move_down"):
                bpy.context.view_layer.objects.active = obj
                if action == "move_up":
                    bpy.ops.object.modifier_move_up(modifier=modifier_name)
                else:
                    bpy.ops.object.modifier_move_down(modifier=modifier_name)
                return {"success": True, "moved": modifier_name, "direction": action}
            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    # ---- GEOMETRY NODES ----
    def edit_geometry_nodes(self, object_name, modifier_name=None, action="info", inputs=None):
        """Inspect or modify Geometry Nodes inputs on an object.
        action: info|set_inputs|list_groups
        inputs: dict of input_name→value to set"""
        try:
            import bpy
            if action == "list_groups":
                groups = []
                for ng in bpy.data.node_groups:
                    if ng.type == 'GEOMETRY':
                        ins = []
                        for item in ng.interface.items_tree:
                            if item.item_type == 'SOCKET' and item.in_out == 'INPUT':
                                ins.append({"name": item.name, "type": item.socket_type,
                                            "identifier": item.identifier})
                        groups.append({"name": ng.name, "inputs": ins})
                return {"groups": groups, "count": len(groups)}
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"error": f"Object '{object_name}' not found"}
            # Find the GeoNodes modifier
            mod = None
            if modifier_name:
                mod = obj.modifiers.get(modifier_name)
            else:
                for m in obj.modifiers:
                    if m.type == 'NODES':
                        mod = m
                        break
            if not mod or mod.type != 'NODES':
                return {"error": "No Geometry Nodes modifier found"}
            if not mod.node_group:
                return {"error": "Modifier has no node group"}
            if action == "info":
                info = {"modifier": mod.name, "node_group": mod.node_group.name, "inputs": {}}
                for item in mod.node_group.interface.items_tree:
                    if item.item_type == 'SOCKET' and item.in_out == 'INPUT':
                        try:
                            val = mod[item.identifier]
                            if hasattr(val, '__iter__'):
                                val = list(val)
                            info["inputs"][item.name] = {"value": val, "type": item.socket_type,
                                                         "identifier": item.identifier}
                        except:
                            info["inputs"][item.name] = {"value": "N/A", "type": item.socket_type}
                return info
            elif action == "set_inputs":
                if not inputs:
                    return {"error": "inputs dict required"}
                results = {}
                id_map = {}
                for item in mod.node_group.interface.items_tree:
                    if item.item_type == 'SOCKET' and item.in_out == 'INPUT':
                        id_map[item.name] = item.identifier
                for name, value in inputs.items():
                    ident = id_map.get(name)
                    if not ident:
                        results[name] = "NOT FOUND"
                        continue
                    try:
                        mod[ident] = value
                        results[name] = "OK"
                    except Exception as e:
                        results[name] = f"FAILED: {e}"
                obj.update_tag()
                bpy.context.view_layer.update()
                return {"success": True, "results": results}
            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    # ---- MESH OPERATIONS ----
    def mesh_operations(self, action, object_names=None, collection_name=None, **kwargs):
        """Mesh editing operations: join, separate, merge_by_distance, clean_loose,
        dissolve_degenerate, flip_normals, shade_smooth, shade_flat, triangulate,
        make_manifold, set_origin.
        kwargs: threshold (merge dist), origin_type (ORIGIN_GEOMETRY, ORIGIN_CENTER_OF_MASS, etc.)"""
        try:
            import bpy, bmesh
            # Gather objects
            objs = []
            if object_names:
                for n in object_names:
                    o = bpy.data.objects.get(n)
                    if o and o.type == 'MESH':
                        objs.append(o)
            elif collection_name:
                col = bpy.data.collections.get(collection_name)
                if col:
                    def gather(c):
                        for o in c.objects:
                            if o.type == 'MESH':
                                objs.append(o)
                        for ch in c.children:
                            gather(ch)
                    gather(col)
            if not objs and action != "set_origin":
                return {"error": "No mesh objects found"}

            if action == "join":
                bpy.ops.object.select_all(action='DESELECT')
                for o in objs:
                    o.select_set(True)
                bpy.context.view_layer.objects.active = objs[0]
                bpy.ops.object.join()
                return {"success": True, "result": objs[0].name, "joined_count": len(objs)}

            elif action == "separate":
                sep_type = kwargs.get("separate_type", "LOOSE")
                bpy.ops.object.select_all(action='DESELECT')
                objs[0].select_set(True)
                bpy.context.view_layer.objects.active = objs[0]
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.separate(type=sep_type)
                bpy.ops.object.mode_set(mode='OBJECT')
                return {"success": True, "separated_by": sep_type}

            elif action == "merge_by_distance":
                threshold = kwargs.get("threshold", 0.0001)
                total_removed = 0
                for obj in objs:
                    bm = bmesh.new()
                    bm.from_mesh(obj.data)
                    result = bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=threshold)
                    removed = len(result.get("verts", []))
                    total_removed += removed
                    bm.to_mesh(obj.data)
                    bm.free()
                return {"success": True, "removed_vertices": total_removed, "objects": len(objs)}

            elif action == "clean_loose":
                total = 0
                for obj in objs:
                    bm = bmesh.new()
                    bm.from_mesh(obj.data)
                    loose_verts = [v for v in bm.verts if not v.link_faces]
                    loose_edges = [e for e in bm.edges if not e.link_faces]
                    bmesh.ops.delete(bm, geom=loose_verts + loose_edges, context='VERTS')
                    total += len(loose_verts) + len(loose_edges)
                    bm.to_mesh(obj.data)
                    bm.free()
                return {"success": True, "removed_loose": total}

            elif action == "shade_smooth":
                bpy.ops.object.select_all(action='DESELECT')
                for o in objs:
                    o.select_set(True)
                bpy.context.view_layer.objects.active = objs[0]
                bpy.ops.object.shade_smooth()
                return {"success": True, "smoothed": len(objs)}

            elif action == "shade_flat":
                bpy.ops.object.select_all(action='DESELECT')
                for o in objs:
                    o.select_set(True)
                bpy.context.view_layer.objects.active = objs[0]
                bpy.ops.object.shade_flat()
                return {"success": True, "flattened": len(objs)}

            elif action == "triangulate":
                for obj in objs:
                    bm = bmesh.new()
                    bm.from_mesh(obj.data)
                    bmesh.ops.triangulate(bm, faces=bm.faces)
                    bm.to_mesh(obj.data)
                    bm.free()
                return {"success": True, "triangulated": len(objs)}

            elif action == "set_origin":
                origin_type = kwargs.get("origin_type", "ORIGIN_GEOMETRY")
                center = kwargs.get("center", "MEDIAN")
                if objs:
                    bpy.ops.object.select_all(action='DESELECT')
                    for o in objs:
                        o.select_set(True)
                    bpy.context.view_layer.objects.active = objs[0]
                bpy.ops.object.origin_set(type=origin_type, center=center)
                return {"success": True, "origin_set": origin_type}

            elif action == "flip_normals":
                for obj in objs:
                    bm = bmesh.new()
                    bm.from_mesh(obj.data)
                    for f in bm.faces:
                        f.normal_flip()
                    bm.to_mesh(obj.data)
                    bm.free()
                return {"success": True, "flipped": len(objs)}

            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    # ---- FILE / IMPORT / APPEND OPERATIONS ----
    def file_operations(self, action, filepath=None, **kwargs):
        """File operations: new, open, save_as, append, link, import_fbx, import_obj,
        import_gltf, import_blend_objects, save_selection_as.
        For append/link: data_type (Object, Collection, Material, NodeTree), names (list).
        For save_selection_as: saves selected objects to a new .blend file."""
        try:
            import bpy, os
            if action == "new":
                bpy.ops.wm.read_factory_settings(use_empty=True)
                return {"success": True, "action": "new_file"}
            elif action == "open":
                if not filepath:
                    return {"error": "filepath required"}
                bpy.ops.wm.open_mainfile(filepath=filepath)
                return {"success": True, "opened": filepath}
            elif action == "save_as":
                if not filepath:
                    return {"error": "filepath required"}
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                compress = kwargs.get("compress", True)
                bpy.ops.wm.save_as_mainfile(filepath=filepath, compress=compress)
                return {"success": True, "saved_as": filepath}
            elif action in ("append", "link"):
                if not filepath:
                    return {"error": "filepath required (path to .blend)"}
                data_type = kwargs.get("data_type", "Object")
                names = kwargs.get("names", [])
                inner_path = data_type
                results = []
                for name in names:
                    full_path = os.path.join(filepath, inner_path, name)
                    try:
                        if action == "append":
                            bpy.ops.wm.append(filepath=full_path,
                                              directory=os.path.join(filepath, inner_path),
                                              filename=name)
                        else:
                            bpy.ops.wm.link(filepath=full_path,
                                            directory=os.path.join(filepath, inner_path),
                                            filename=name)
                        results.append({"name": name, "status": "OK"})
                    except Exception as e:
                        results.append({"name": name, "status": f"FAILED: {e}"})
                return {"success": True, "action": action, "results": results}
            elif action == "import_fbx":
                if not filepath:
                    return {"error": "filepath required"}
                bpy.ops.import_scene.fbx(filepath=filepath)
                return {"success": True, "imported": filepath, "format": "FBX"}
            elif action == "import_obj":
                if not filepath:
                    return {"error": "filepath required"}
                bpy.ops.wm.obj_import(filepath=filepath)
                return {"success": True, "imported": filepath, "format": "OBJ"}
            elif action == "import_gltf":
                if not filepath:
                    return {"error": "filepath required"}
                bpy.ops.import_scene.gltf(filepath=filepath)
                return {"success": True, "imported": filepath, "format": "glTF"}
            elif action == "save_selection_as":
                if not filepath:
                    return {"error": "filepath required"}
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                selected = [o for o in bpy.context.selected_objects]
                if not selected:
                    return {"error": "No objects selected"}
                # Use blend file library override to save selection
                bpy.ops.object.select_all(action='DESELECT')
                for o in selected:
                    o.select_set(True)
                bpy.ops.export_scene.gltf(filepath=filepath.replace('.blend', '.glb'),
                                           use_selection=True) if filepath.endswith('.glb') else None
                # For .blend, we use a different approach
                if filepath.endswith('.blend'):
                    # Create a copy of the data we need
                    data_blocks = set()
                    for obj in selected:
                        data_blocks.add(obj)
                    bpy.data.libraries.write(filepath, data_blocks, fake_user=True, compress=True)
                return {"success": True, "saved_selection": filepath, "objects": len(selected)}
            elif action == "list_blend_contents":
                if not filepath:
                    return {"error": "filepath required"}
                contents = {}
                with bpy.data.libraries.load(filepath) as (data_from, data_to):
                    contents["objects"] = list(data_from.objects)
                    contents["collections"] = list(data_from.collections)
                    contents["materials"] = list(data_from.materials)
                    contents["node_groups"] = list(data_from.node_groups)
                    contents["meshes"] = list(data_from.meshes)
                    contents["images"] = list(data_from.images)
                return {"success": True, "filepath": filepath, "contents": contents}
            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    # ---- PURGE / CLEANUP / FILE SIZE ----
    def purge_data(self, action="purge_orphans", **kwargs):
        """Data cleanup: purge_orphans, unpack_textures, pack_textures,
        resize_textures, remove_unused_materials, remove_unused_images,
        stats, compact.
        For resize_textures: max_size (int, e.g. 1024), formats (list)."""
        try:
            import bpy
            if action == "purge_orphans":
                # Recursive purge
                removed = {"meshes": 0, "materials": 0, "images": 0, "node_groups": 0, "others": 0}
                for _ in range(10):  # Multiple passes
                    found = False
                    for block_name in ['meshes', 'materials', 'textures', 'images',
                                       'node_groups', 'actions', 'curves', 'armatures']:
                        block = getattr(bpy.data, block_name, None)
                        if not block:
                            continue
                        for item in list(block):
                            if item.users == 0:
                                block.remove(item)
                                key = block_name if block_name in removed else "others"
                                removed[key] = removed.get(key, 0) + 1
                                found = True
                    if not found:
                        break
                return {"success": True, "removed": removed}

            elif action == "remove_unused_materials":
                removed = []
                for mat in list(bpy.data.materials):
                    if mat.users == 0:
                        removed.append(mat.name)
                        bpy.data.materials.remove(mat)
                return {"success": True, "removed": removed, "count": len(removed)}

            elif action == "remove_unused_images":
                removed = []
                for img in list(bpy.data.images):
                    if img.users == 0:
                        removed.append(img.name)
                        bpy.data.images.remove(img)
                return {"success": True, "removed": removed, "count": len(removed)}

            elif action == "resize_textures":
                max_size = kwargs.get("max_size", 1024)
                resized = []
                for img in bpy.data.images:
                    if img.size[0] > max_size or img.size[1] > max_size:
                        old_size = (img.size[0], img.size[1])
                        ratio = max_size / max(img.size[0], img.size[1])
                        new_w = int(img.size[0] * ratio)
                        new_h = int(img.size[1] * ratio)
                        img.scale(new_w, new_h)
                        resized.append({"name": img.name, "old": old_size, "new": (new_w, new_h)})
                return {"success": True, "resized": resized, "count": len(resized)}

            elif action == "pack_textures":
                count = 0
                for img in bpy.data.images:
                    if not img.packed_file and img.filepath:
                        try:
                            img.pack()
                            count += 1
                        except:
                            pass
                return {"success": True, "packed": count}

            elif action == "unpack_textures":
                method = kwargs.get("method", "USE_ORIGINAL")
                count = 0
                for img in bpy.data.images:
                    if img.packed_file:
                        try:
                            img.unpack(method=method)
                            count += 1
                        except:
                            pass
                return {"success": True, "unpacked": count}

            elif action == "stats":
                import os
                stats = {
                    "file": bpy.data.filepath,
                    "file_size_mb": round(os.path.getsize(bpy.data.filepath) / (1024*1024), 2) if bpy.data.filepath else 0,
                    "objects": len(bpy.data.objects),
                    "meshes": len(bpy.data.meshes),
                    "materials": len(bpy.data.materials),
                    "images": len(bpy.data.images),
                    "node_groups": len(bpy.data.node_groups),
                    "unused_meshes": sum(1 for m in bpy.data.meshes if m.users == 0),
                    "unused_materials": sum(1 for m in bpy.data.materials if m.users == 0),
                    "unused_images": sum(1 for i in bpy.data.images if i.users == 0),
                }
                # Image sizes
                total_pixels = 0
                for img in bpy.data.images:
                    total_pixels += img.size[0] * img.size[1]
                stats["total_image_pixels"] = total_pixels
                stats["estimated_texture_memory_mb"] = round(total_pixels * 4 / (1024*1024), 2)
                return stats

            elif action == "compact":
                # Full cleanup: purge then save compressed
                for _ in range(10):
                    found = False
                    for attr in ['meshes', 'materials', 'textures', 'images',
                                 'node_groups', 'actions', 'curves']:
                        block = getattr(bpy.data, attr, None)
                        if block:
                            for item in list(block):
                                if item.users == 0:
                                    block.remove(item)
                                    found = True
                    if not found:
                        break
                if bpy.data.filepath:
                    bpy.ops.wm.save_mainfile(compress=True)
                    import os
                    size_mb = round(os.path.getsize(bpy.data.filepath) / (1024*1024), 2)
                    return {"success": True, "compacted": True, "new_size_mb": size_mb}
                return {"success": True, "compacted": True, "note": "Save manually for size reduction"}

            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    # ---- PARENT / HIERARCHY ----
    def manage_hierarchy(self, action="info", parent_name=None, child_names=None,
                         object_name=None, keep_transform=True):
        """Object hierarchy: parent, unparent, info, list_children.
        action: parent|unparent|info|list_children"""
        try:
            import bpy
            if action == "parent":
                if not parent_name or not child_names:
                    return {"error": "parent_name and child_names required"}
                parent = bpy.data.objects.get(parent_name)
                if not parent:
                    return {"error": f"Parent '{parent_name}' not found"}
                parented = []
                for cname in child_names:
                    child = bpy.data.objects.get(cname)
                    if child:
                        child.parent = parent
                        if keep_transform:
                            child.matrix_parent_inverse = parent.matrix_world.inverted()
                        parented.append(cname)
                return {"success": True, "parent": parent_name, "children": parented}
            elif action == "unparent":
                if not child_names:
                    return {"error": "child_names required"}
                unparented = []
                for cname in child_names:
                    child = bpy.data.objects.get(cname)
                    if child and child.parent:
                        if keep_transform:
                            world_mat = child.matrix_world.copy()
                            child.parent = None
                            child.matrix_world = world_mat
                        else:
                            child.parent = None
                        unparented.append(cname)
                return {"success": True, "unparented": unparented}
            elif action == "info":
                obj = bpy.data.objects.get(object_name or parent_name)
                if not obj:
                    return {"error": "Object not found"}
                return {
                    "name": obj.name,
                    "parent": obj.parent.name if obj.parent else None,
                    "children": [c.name for c in obj.children],
                    "children_recursive": [c.name for c in obj.children_recursive]
                }
            elif action == "list_children":
                obj = bpy.data.objects.get(object_name or parent_name)
                if not obj:
                    return {"error": "Object not found"}
                return {"name": obj.name,
                        "direct_children": [c.name for c in obj.children],
                        "all_descendants": [c.name for c in obj.children_recursive]}
            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    # ---- BATCH TRANSFORM ----
    def batch_transform(self, action, object_names=None, collection_name=None, **kwargs):
        """Batch transforms: align, distribute, randomize, snap_to_ground, apply_transforms.
        align: axis (X/Y/Z), align_to (MIN/MAX/CENTER/CURSOR)
        distribute: axis (X/Y/Z), spacing (float)
        randomize: location_range, rotation_range, scale_range (each [min,max])
        snap_to_ground: ray cast down to find ground
        apply_transforms: apply location/rotation/scale"""
        try:
            import bpy
            from mathutils import Vector
            import random
            objs = []
            if object_names:
                for n in object_names:
                    o = bpy.data.objects.get(n)
                    if o:
                        objs.append(o)
            elif collection_name:
                col = bpy.data.collections.get(collection_name)
                if col:
                    def gather(c):
                        for o in c.objects:
                            objs.append(o)
                        for ch in c.children:
                            gather(ch)
                    gather(col)
            if not objs:
                return {"error": "No objects found"}

            if action == "align":
                axis = kwargs.get("axis", "X").upper()
                align_to = kwargs.get("align_to", "CENTER")
                axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]
                if align_to == "MIN":
                    target = min(o.location[axis_idx] for o in objs)
                elif align_to == "MAX":
                    target = max(o.location[axis_idx] for o in objs)
                elif align_to == "CENTER":
                    target = sum(o.location[axis_idx] for o in objs) / len(objs)
                elif align_to == "CURSOR":
                    target = bpy.context.scene.cursor.location[axis_idx]
                else:
                    target = float(align_to)
                for o in objs:
                    o.location[axis_idx] = target
                return {"success": True, "aligned": len(objs), "axis": axis, "to": target}

            elif action == "distribute":
                axis = kwargs.get("axis", "X").upper()
                spacing = kwargs.get("spacing", 10.0)
                axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]
                sorted_objs = sorted(objs, key=lambda o: o.location[axis_idx])
                start = sorted_objs[0].location[axis_idx]
                for i, o in enumerate(sorted_objs):
                    o.location[axis_idx] = start + i * spacing
                return {"success": True, "distributed": len(objs), "axis": axis, "spacing": spacing}

            elif action == "randomize":
                loc_range = kwargs.get("location_range", [0, 0])
                rot_range = kwargs.get("rotation_range", [0, 0])
                scale_range = kwargs.get("scale_range", [1, 1])
                for o in objs:
                    if loc_range[1] > 0:
                        o.location.x += random.uniform(loc_range[0], loc_range[1])
                        o.location.y += random.uniform(loc_range[0], loc_range[1])
                    if rot_range[1] > 0:
                        o.rotation_euler.z += random.uniform(rot_range[0], rot_range[1])
                    if scale_range[0] != 1 or scale_range[1] != 1:
                        s = random.uniform(scale_range[0], scale_range[1])
                        o.scale = (s, s, s)
                return {"success": True, "randomized": len(objs)}

            elif action == "apply_transforms":
                bpy.ops.object.select_all(action='DESELECT')
                for o in objs:
                    o.select_set(True)
                bpy.context.view_layer.objects.active = objs[0]
                location = kwargs.get("location", True)
                rotation = kwargs.get("rotation", True)
                scale = kwargs.get("scale", True)
                bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)
                return {"success": True, "applied_transforms": len(objs)}

            elif action == "snap_to_ground":
                from bpy_extras.object_utils import world_to_camera_view
                snapped = []
                depsgraph = bpy.context.evaluated_depsgraph_get()
                scene = bpy.context.scene
                for o in objs:
                    origin = o.location.copy()
                    origin.z += 1000  # Cast from high above
                    direction = Vector((0, 0, -1))
                    hit, loc, normal, idx, hit_obj, matrix = scene.ray_cast(
                        depsgraph, origin, direction)
                    if hit and hit_obj != o:
                        o.location.z = loc.z
                        snapped.append(o.name)
                return {"success": True, "snapped": snapped, "count": len(snapped)}

            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    # ---- RENDER TO FILE ----
    def render_image(self, filepath=None, resolution_x=1920, resolution_y=1080,
                     samples=64, use_viewport_camera=True, format="PNG"):
        """Render the scene to an image file."""
        try:
            import bpy, os
            scene = bpy.context.scene
            scene.render.resolution_x = resolution_x
            scene.render.resolution_y = resolution_y
            scene.render.image_settings.file_format = format
            if hasattr(scene, 'cycles'):
                scene.cycles.samples = samples
            if not filepath:
                filepath = os.path.join(os.path.dirname(bpy.data.filepath), "render_output.png")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            scene.render.filepath = filepath
            bpy.ops.render.render(write_still=True)
            return {"success": True, "rendered": filepath, "resolution": f"{resolution_x}x{resolution_y}"}
        except Exception as e:
            return {"error": str(e)}

    # ---- UV OPERATIONS ----
    def manage_uv(self, object_names=None, action="smart_project", **kwargs):
        """UV operations: smart_project, unwrap, cube_project, reset, list_maps.
        kwargs: angle_limit (smart project), island_margin"""
        try:
            import bpy
            if action == "list_maps":
                obj = bpy.data.objects.get(object_names[0]) if object_names else None
                if not obj or obj.type != 'MESH':
                    return {"error": "Need a mesh object"}
                maps = [uv.name for uv in obj.data.uv_layers]
                return {"object": obj.name, "uv_maps": maps, "active": obj.data.uv_layers.active.name if obj.data.uv_layers.active else None}
            
            objs = []
            if object_names:
                for n in object_names:
                    o = bpy.data.objects.get(n)
                    if o and o.type == 'MESH':
                        objs.append(o)
            if not objs:
                return {"error": "No mesh objects found"}
            
            results = []
            for obj in objs:
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                if action == "smart_project":
                    angle = kwargs.get("angle_limit", 66.0)
                    margin = kwargs.get("island_margin", 0.02)
                    bpy.ops.uv.smart_project(angle_limit=angle, island_margin=margin)
                elif action == "unwrap":
                    margin = kwargs.get("island_margin", 0.02)
                    bpy.ops.uv.unwrap(margin=margin)
                elif action == "cube_project":
                    bpy.ops.uv.cube_project()
                elif action == "reset":
                    bpy.ops.uv.reset()
                bpy.ops.object.mode_set(mode='OBJECT')
                results.append(obj.name)
            return {"success": True, "action": action, "objects": results}
        except Exception as e:
            return {"error": str(e)}

    # ---- CONSTRAINTS ----
    def manage_constraints(self, object_name, action="list", constraint_type=None,
                           constraint_name=None, properties=None):
        """Manage constraints: list, add, remove, configure.
        constraint_type: COPY_LOCATION, COPY_ROTATION, TRACK_TO, LIMIT_LOCATION, etc."""
        try:
            import bpy
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"error": f"Object '{object_name}' not found"}
            if action == "list":
                cons = []
                for c in obj.constraints:
                    cons.append({"name": c.name, "type": c.type, "enabled": c.enabled,
                                 "influence": c.influence})
                return {"object": object_name, "constraints": cons}
            elif action == "add":
                if not constraint_type:
                    return {"error": "constraint_type required"}
                con = obj.constraints.new(type=constraint_type)
                if constraint_name:
                    con.name = constraint_name
                if properties:
                    for k, v in properties.items():
                        try:
                            if k == "target":
                                v = bpy.data.objects.get(v)
                            setattr(con, k, v)
                        except:
                            pass
                return {"success": True, "added": con.name, "type": con.type}
            elif action == "remove":
                if not constraint_name:
                    return {"error": "constraint_name required"}
                con = obj.constraints.get(constraint_name)
                if con:
                    obj.constraints.remove(con)
                    return {"success": True, "removed": constraint_name}
                return {"error": f"Constraint '{constraint_name}' not found"}
            elif action == "configure":
                if not constraint_name or not properties:
                    return {"error": "constraint_name and properties required"}
                con = obj.constraints.get(constraint_name)
                if not con:
                    return {"error": f"Constraint '{constraint_name}' not found"}
                for k, v in properties.items():
                    try:
                        if k == "target":
                            v = bpy.data.objects.get(v)
                        setattr(con, k, v)
                    except:
                        pass
                return {"success": True, "configured": constraint_name}
            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    # ---- SCENE SEPARATION / DISTRICT MANAGEMENT ----
    def save_collection_as_file(self, collection_name, filepath, include_materials=True,
                                 include_textures=True):
        """Save an entire collection (and its children) to a separate .blend file.
        Perfect for splitting a city into district files."""
        try:
            import bpy, os
            col = bpy.data.collections.get(collection_name)
            if not col:
                return {"error": f"Collection '{collection_name}' not found"}
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            # Gather all data blocks
            data_blocks = set()
            def gather_collection(c):
                data_blocks.add(c)
                for obj in c.objects:
                    data_blocks.add(obj)
                    if obj.data:
                        data_blocks.add(obj.data)
                    if include_materials:
                        for slot in getattr(obj, 'material_slots', []):
                            if slot.material:
                                data_blocks.add(slot.material)
                                if include_textures and slot.material.use_nodes:
                                    for node in slot.material.node_tree.nodes:
                                        if node.type == 'TEX_IMAGE' and node.image:
                                            data_blocks.add(node.image)
                for child_col in c.children:
                    gather_collection(child_col)
            gather_collection(col)
            bpy.data.libraries.write(filepath, data_blocks, compress=True)
            return {"success": True, "saved": filepath, "data_blocks": len(data_blocks),
                    "collection": collection_name}
        except Exception as e:
            return {"error": str(e)}

    # ---- ADDON EXECUTION / OPERATOR CALLING ----
    def call_operator(self, operator_path, **kwargs):
        """Call any Blender operator by its full path, e.g. 'bpy.ops.mesh.primitive_cube_add'.
        Pass operator arguments as kwargs."""
        try:
            import bpy
            parts = operator_path.replace("bpy.ops.", "").split(".")
            if len(parts) != 2:
                return {"error": "operator_path should be like 'bpy.ops.category.operator' or 'category.operator'"}
            category, op_name = parts
            op_category = getattr(bpy.ops, category, None)
            if not op_category:
                return {"error": f"Operator category '{category}' not found"}
            op = getattr(op_category, op_name, None)
            if not op:
                return {"error": f"Operator '{op_name}' not found in '{category}'"}
            result = op(**kwargs)
            return {"success": True, "operator": operator_path, "result": str(result)}
        except Exception as e:
            return {"error": str(e)}

    # ---- SCENE CAMERA MANAGEMENT ----
    def manage_cameras(self, action="list", name=None, location=None, rotation=None,
                       lens=None, set_active=False):
        """Manage cameras: list, create, delete, configure, set_active.
        For creating: provide name, location, rotation, lens."""
        try:
            import bpy
            from math import radians
            if action == "list":
                cams = []
                for obj in bpy.data.objects:
                    if obj.type == 'CAMERA':
                        cams.append({
                            "name": obj.name,
                            "location": list(obj.location),
                            "rotation": [round(r, 4) for r in obj.rotation_euler],
                            "lens": obj.data.lens,
                            "is_active": obj == bpy.context.scene.camera
                        })
                return {"cameras": cams}
            elif action == "create":
                cam_data = bpy.data.cameras.new(name or "Camera")
                cam_obj = bpy.data.objects.new(name or "Camera", cam_data)
                bpy.context.collection.objects.link(cam_obj)
                if location:
                    cam_obj.location = location
                if rotation:
                    cam_obj.rotation_euler = [radians(r) if abs(r) > 6.28 else r for r in rotation]
                if lens:
                    cam_data.lens = lens
                if set_active:
                    bpy.context.scene.camera = cam_obj
                return {"success": True, "created": cam_obj.name}
            elif action == "set_active":
                obj = bpy.data.objects.get(name)
                if not obj or obj.type != 'CAMERA':
                    return {"error": f"Camera '{name}' not found"}
                bpy.context.scene.camera = obj
                return {"success": True, "active_camera": name}
            elif action == "configure":
                obj = bpy.data.objects.get(name)
                if not obj or obj.type != 'CAMERA':
                    return {"error": f"Camera '{name}' not found"}
                if location:
                    obj.location = location
                if rotation:
                    obj.rotation_euler = rotation
                if lens:
                    obj.data.lens = lens
                return {"success": True, "configured": name}
            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    # ---- IMAGE / TEXTURE MANAGEMENT ----
    def manage_images(self, action="list", name=None, filepath=None, **kwargs):
        """Image management: list, info, load, remove, resize, pack, unpack.
        list: all images with size/packed status.
        load: load image from disk. resize: resize by max_size."""
        try:
            import bpy
            if action == "list":
                imgs = []
                for img in bpy.data.images:
                    imgs.append({
                        "name": img.name,
                        "size": [img.size[0], img.size[1]],
                        "packed": img.packed_file is not None,
                        "filepath": img.filepath,
                        "users": img.users,
                        "pixels_mb": round(img.size[0] * img.size[1] * 4 / (1024*1024), 2)
                    })
                return {"images": imgs, "count": len(imgs),
                        "total_mb": round(sum(i["pixels_mb"] for i in imgs), 2)}
            elif action == "info":
                img = bpy.data.images.get(name)
                if not img:
                    return {"error": f"Image '{name}' not found"}
                return {"name": img.name, "size": list(img.size), "packed": img.packed_file is not None,
                        "filepath": img.filepath, "users": img.users, "colorspace": img.colorspace_settings.name}
            elif action == "load":
                if not filepath:
                    return {"error": "filepath required"}
                img = bpy.data.images.load(filepath)
                return {"success": True, "loaded": img.name, "size": list(img.size)}
            elif action == "remove":
                img = bpy.data.images.get(name)
                if not img:
                    return {"error": f"Image '{name}' not found"}
                bpy.data.images.remove(img)
                return {"success": True, "removed": name}
            elif action == "resize":
                max_size = kwargs.get("max_size", 1024)
                img = bpy.data.images.get(name)
                if not img:
                    return {"error": f"Image '{name}' not found"}
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_w, new_h = int(img.size[0] * ratio), int(img.size[1] * ratio)
                    old_size = list(img.size)
                    img.scale(new_w, new_h)
                    return {"success": True, "resized": name, "old": old_size, "new": [new_w, new_h]}
                return {"success": True, "no_resize_needed": name, "size": list(img.size)}
            return {"error": f"Unknown action '{action}'"}
        except Exception as e:
            return {"error": str(e)}

    def list_materials(self, pattern=None, limit=50):
        """List all materials in the scene with key properties"""
        try:
            materials = []
            for mat in bpy.data.materials:
                if pattern and pattern.lower() not in mat.name.lower():
                    continue
                mat_info = {
                    "name": mat.name,
                    "users": mat.users,
                    "use_nodes": mat.use_nodes,
                    "is_fake_user": mat.use_fake_user,
                }
                if mat.use_nodes and mat.node_tree:
                    for node in mat.node_tree.nodes:
                        if node.type == 'BSDF_PRINCIPLED':
                            bc = node.inputs.get('Base Color')
                            if bc and not bc.is_linked:
                                mat_info["base_color"] = list(bc.default_value)
                            met = node.inputs.get('Metallic')
                            if met and not met.is_linked:
                                mat_info["metallic"] = met.default_value
                            rough = node.inputs.get('Roughness')
                            if rough and not rough.is_linked:
                                mat_info["roughness"] = rough.default_value
                            em = node.inputs.get('Emission Color')
                            if em and not em.is_linked:
                                mat_info["emission_color"] = list(em.default_value)
                            break
                materials.append(mat_info)
                if len(materials) >= limit:
                    break
            return {"materials": materials, "total_in_file": len(bpy.data.materials), "returned": len(materials)}
        except Exception as e:
            return {"error": str(e)}

    def get_material_info(self, name):
        """Get detailed material node tree information"""
        try:
            mat = bpy.data.materials.get(name)
            if not mat:
                return {"error": f"Material not found: {name}"}
            info = {
                "name": mat.name,
                "users": mat.users,
                "use_nodes": mat.use_nodes,
                "nodes": [],
                "links": [],
            }
            if mat.use_nodes and mat.node_tree:
                for node in mat.node_tree.nodes:
                    node_info = {
                        "name": node.name,
                        "type": node.type,
                        "label": node.label,
                        "location": [node.location.x, node.location.y],
                        "inputs": {},
                        "outputs": [],
                    }
                    for inp in node.inputs:
                        inp_data = {"type": inp.type, "is_linked": inp.is_linked}
                        if not inp.is_linked and hasattr(inp, 'default_value'):
                            try:
                                val = inp.default_value
                                if hasattr(val, '__iter__'):
                                    inp_data["value"] = [round(float(v), 4) for v in val]
                                else:
                                    inp_data["value"] = round(float(val), 4)
                            except (TypeError, ValueError):
                                inp_data["value"] = str(val)
                        node_info["inputs"][inp.name] = inp_data
                    for out in node.outputs:
                        node_info["outputs"].append({"name": out.name, "type": out.type})
                    if node.type == 'TEX_IMAGE' and node.image:
                        node_info["image"] = {
                            "name": node.image.name,
                            "size": list(node.image.size),
                            "colorspace": node.image.colorspace_settings.name,
                        }
                    info["nodes"].append(node_info)
                for link in mat.node_tree.links:
                    info["links"].append({
                        "from_node": link.from_node.name,
                        "from_socket": link.from_socket.name,
                        "to_node": link.to_node.name,
                        "to_socket": link.to_socket.name,
                    })
            return info
        except Exception as e:
            return {"error": str(e)}

    def modify_material(self, name, base_color=None, metallic=None, roughness=None,
                        emission_color=None, emission_strength=None, alpha=None,
                        specular=None, subsurface_weight=None):
        """Modify Principled BSDF properties of an existing material"""
        try:
            mat = bpy.data.materials.get(name)
            if not mat:
                return {"error": f"Material not found: {name}"}
            if not mat.use_nodes or not mat.node_tree:
                return {"error": f"Material {name} does not use nodes"}
            principled = None
            for node in mat.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled = node
                    break
            if not principled:
                return {"error": f"No Principled BSDF node found in {name}"}
            changed = []
            if base_color is not None:
                inp = principled.inputs.get('Base Color')
                if inp:
                    inp.default_value = base_color if len(base_color) == 4 else list(base_color) + [1.0]
                    changed.append("base_color")
            if metallic is not None:
                inp = principled.inputs.get('Metallic')
                if inp:
                    inp.default_value = metallic
                    changed.append("metallic")
            if roughness is not None:
                inp = principled.inputs.get('Roughness')
                if inp:
                    inp.default_value = roughness
                    changed.append("roughness")
            if emission_color is not None:
                inp = principled.inputs.get('Emission Color')
                if inp:
                    inp.default_value = emission_color if len(emission_color) == 4 else list(emission_color) + [1.0]
                    changed.append("emission_color")
            if emission_strength is not None:
                inp = principled.inputs.get('Emission Strength')
                if inp:
                    inp.default_value = emission_strength
                    changed.append("emission_strength")
            if alpha is not None:
                inp = principled.inputs.get('Alpha')
                if inp:
                    inp.default_value = alpha
                    changed.append("alpha")
            if specular is not None:
                inp = principled.inputs.get('Specular IOR Level')
                if inp:
                    inp.default_value = specular
                    changed.append("specular")
            return {"success": True, "material": name, "changed": changed}
        except Exception as e:
            return {"error": str(e)}

    def create_material(self, name, base_color=None, metallic=0.0, roughness=0.5,
                        emission_color=None, emission_strength=0.0):
        """Create a new PBR material with Principled BSDF"""
        try:
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            principled = None
            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled = node
                    break
            if principled:
                if base_color:
                    bc = base_color if len(base_color) == 4 else list(base_color) + [1.0]
                    principled.inputs['Base Color'].default_value = bc
                principled.inputs['Metallic'].default_value = metallic
                principled.inputs['Roughness'].default_value = roughness
                if emission_color:
                    ec = emission_color if len(emission_color) == 4 else list(emission_color) + [1.0]
                    principled.inputs['Emission Color'].default_value = ec
                principled.inputs['Emission Strength'].default_value = emission_strength
            return {"success": True, "material": mat.name}
        except Exception as e:
            return {"error": str(e)}

    def assign_material(self, object_name, material_name, slot_index=None):
        """Assign a material to an object, optionally at a specific slot"""
        try:
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"error": f"Object not found: {object_name}"}
            mat = bpy.data.materials.get(material_name)
            if not mat:
                return {"error": f"Material not found: {material_name}"}
            if slot_index is not None and slot_index < len(obj.material_slots):
                obj.material_slots[slot_index].material = mat
            else:
                if obj.data and hasattr(obj.data, 'materials'):
                    obj.data.materials.append(mat)
            return {"success": True, "object": object_name, "material": material_name}
        except Exception as e:
            return {"error": str(e)}

    def list_collections(self, include_hidden=True):
        """List all collections with hierarchy, object counts, and visibility"""
        try:
            def collect_info(layer_col, depth=0):
                col = layer_col.collection
                info = {
                    "name": col.name,
                    "depth": depth,
                    "objects": len(col.objects),
                    "all_objects": len(col.all_objects),
                    "visible": layer_col.is_visible if hasattr(layer_col, 'is_visible') else True,
                    "exclude": layer_col.exclude,
                    "hide_viewport": layer_col.hide_viewport,
                    "children": [],
                }
                for child_lc in layer_col.children:
                    if include_hidden or not child_lc.exclude:
                        info["children"].append(collect_info(child_lc, depth + 1))
                return info
            root = bpy.context.view_layer.layer_collection
            tree = collect_info(root)
            return tree
        except Exception as e:
            return {"error": str(e)}

    def manage_collection(self, name, action="info", new_name=None, exclude=None,
                          hide_viewport=None, parent_name=None):
        """Manage collections: info, create, rename, delete, toggle visibility"""
        try:
            if action == "create":
                col = bpy.data.collections.new(name)
                parent = bpy.data.collections.get(parent_name) if parent_name else bpy.context.scene.collection
                parent.children.link(col)
                return {"success": True, "action": "created", "name": col.name}
            col = bpy.data.collections.get(name)
            if not col:
                return {"error": f"Collection not found: {name}"}
            if action == "rename" and new_name:
                col.name = new_name
                return {"success": True, "action": "renamed", "old_name": name, "new_name": col.name}
            if action == "delete":
                bpy.data.collections.remove(col)
                return {"success": True, "action": "deleted", "name": name}
            if action == "info":
                result = {
                    "name": col.name,
                    "objects": [obj.name for obj in col.objects],
                    "children": [c.name for c in col.children],
                }
                return result

            # Toggle visibility via layer collection
            def find_layer_col(lc, target_name):
                if lc.collection.name == target_name:
                    return lc
                for child in lc.children:
                    found = find_layer_col(child, target_name)
                    if found:
                        return found
                return None

            lc = find_layer_col(bpy.context.view_layer.layer_collection, name)
            if lc:
                if exclude is not None:
                    lc.exclude = exclude
                if hide_viewport is not None:
                    lc.hide_viewport = hide_viewport
                return {"success": True, "action": "visibility_updated", "name": name,
                        "exclude": lc.exclude, "hide_viewport": lc.hide_viewport}
            return {"error": f"Layer collection not found for: {name}"}
        except Exception as e:
            return {"error": str(e)}

    def select_objects(self, names=None, pattern=None, collection_name=None,
                       object_type=None, deselect_first=True):
        """Select objects by name list, regex pattern, collection, or type"""
        try:
            if deselect_first:
                bpy.ops.object.select_all(action='DESELECT')
            selected = []
            candidates = bpy.context.scene.objects
            if collection_name:
                col = bpy.data.collections.get(collection_name)
                if not col:
                    return {"error": f"Collection not found: {collection_name}"}
                candidates = col.all_objects
            for obj in candidates:
                match = False
                if names and obj.name in names:
                    match = True
                elif pattern and re.search(pattern, obj.name, re.IGNORECASE):
                    match = True
                elif not names and not pattern:
                    match = True
                if object_type and obj.type != object_type:
                    match = False
                if match:
                    obj.select_set(True)
                    selected.append(obj.name)
            if selected:
                bpy.context.view_layer.objects.active = bpy.data.objects.get(selected[0])
            return {"success": True, "selected_count": len(selected), "selected": selected[:50]}
        except Exception as e:
            return {"error": str(e)}

    def modify_object(self, name, location=None, rotation=None, scale=None,
                      new_name=None, hide_viewport=None, hide_render=None):
        """Modify object transform, name, or visibility"""
        try:
            obj = bpy.data.objects.get(name)
            if not obj:
                return {"error": f"Object not found: {name}"}
            changed = []
            if location is not None:
                obj.location = mathutils.Vector(location)
                changed.append("location")
            if rotation is not None:
                obj.rotation_euler = mathutils.Euler(rotation)
                changed.append("rotation")
            if scale is not None:
                obj.scale = mathutils.Vector(scale)
                changed.append("scale")
            if new_name is not None:
                obj.name = new_name
                changed.append("name")
            if hide_viewport is not None:
                obj.hide_viewport = hide_viewport
                changed.append("hide_viewport")
            if hide_render is not None:
                obj.hide_render = hide_render
                changed.append("hide_render")
            return {"success": True, "object": obj.name, "changed": changed}
        except Exception as e:
            return {"error": str(e)}

    def delete_objects(self, names=None, collection_name=None, confirm=False):
        """Delete objects by name list or collection. Requires confirm=True."""
        try:
            if not confirm:
                return {"error": "Set confirm=True to actually delete objects. This is irreversible."}
            to_delete = []
            if names:
                for n in names:
                    obj = bpy.data.objects.get(n)
                    if obj:
                        to_delete.append(obj)
            elif collection_name:
                col = bpy.data.collections.get(collection_name)
                if col:
                    to_delete = list(col.all_objects)
            deleted_names = [o.name for o in to_delete]
            for obj in to_delete:
                bpy.data.objects.remove(obj, do_unlink=True)
            return {"success": True, "deleted": deleted_names, "count": len(deleted_names)}
        except Exception as e:
            return {"error": str(e)}

    def duplicate_objects(self, names, linked=False, offset=None):
        """Duplicate objects by name list"""
        try:
            new_objects = []
            for n in names:
                src = bpy.data.objects.get(n)
                if not src:
                    continue
                if linked:
                    new_obj = src.copy()
                else:
                    new_obj = src.copy()
                    if src.data:
                        new_obj.data = src.data.copy()
                if offset:
                    new_obj.location.x += offset[0]
                    new_obj.location.y += offset[1]
                    new_obj.location.z += offset[2] if len(offset) > 2 else 0
                for col in src.users_collection:
                    col.objects.link(new_obj)
                new_objects.append(new_obj.name)
            return {"success": True, "new_objects": new_objects}
        except Exception as e:
            return {"error": str(e)}

    def set_viewport_shading(self, mode, studio_light=None, color_type=None,
                             use_scene_lights=None, use_scene_world=None):
        """Set viewport shading mode: WIREFRAME, SOLID, MATERIAL, RENDERED"""
        try:
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces[0]
                    space.shading.type = mode.upper()
                    if studio_light and mode.upper() == 'SOLID':
                        space.shading.studio_light = studio_light
                    if color_type and mode.upper() == 'SOLID':
                        space.shading.color_type = color_type
                    if use_scene_lights is not None:
                        space.shading.use_scene_lights = use_scene_lights
                    if use_scene_world is not None:
                        space.shading.use_scene_world = use_scene_world
                    return {"success": True, "mode": space.shading.type}
            return {"error": "No 3D viewport found"}
        except Exception as e:
            return {"error": str(e)}

    def set_render_engine(self, engine):
        """Set render engine: BLENDER_EEVEE_NEXT, CYCLES, BLENDER_WORKBENCH"""
        try:
            bpy.context.scene.render.engine = engine.upper()
            return {"success": True, "engine": bpy.context.scene.render.engine}
        except Exception as e:
            return {"error": str(e)}

    def manage_world(self, action="info", color=None, strength=None, hdri_rotation=None):
        """Manage world environment: get info, set color, set strength"""
        try:
            world = bpy.context.scene.world
            if not world:
                world = bpy.data.worlds.new("World")
                bpy.context.scene.world = world
            if not world.use_nodes:
                world.use_nodes = True
            if action == "info":
                info = {"name": world.name, "use_nodes": world.use_nodes, "nodes": []}
                if world.node_tree:
                    for node in world.node_tree.nodes:
                        info["nodes"].append({"name": node.name, "type": node.type})
                return info
            bg = None
            for node in world.node_tree.nodes:
                if node.type == 'BACKGROUND':
                    bg = node
                    break
            if color is not None and bg:
                bg.inputs['Color'].default_value = color if len(color) == 4 else list(color) + [1.0]
            if strength is not None and bg:
                bg.inputs['Strength'].default_value = strength
            if hdri_rotation is not None:
                for node in world.node_tree.nodes:
                    if node.type == 'MAPPING':
                        node.inputs['Rotation'].default_value = hdri_rotation
                        break
            return {"success": True, "world": world.name}
        except Exception as e:
            return {"error": str(e)}

    def list_addons(self, enabled_only=False):
        """List installed Blender addons"""
        try:
            import addon_utils
            addons = []
            for mod in addon_utils.modules():
                info = mod.bl_info if hasattr(mod, 'bl_info') else {}
                is_enabled = addon_utils.check(mod.__name__)[0]
                if enabled_only and not is_enabled:
                    continue
                addons.append({
                    "name": info.get("name", mod.__name__),
                    "module": mod.__name__,
                    "enabled": is_enabled,
                    "category": info.get("category", ""),
                    "description": info.get("description", ""),
                    "version": str(info.get("version", "")),
                })
            return {"addons": addons, "count": len(addons)}
        except Exception as e:
            return {"error": str(e)}

    def enable_addon(self, module_name, enable=True):
        """Enable or disable a Blender addon by module name"""
        try:
            import addon_utils
            if enable:
                bpy.ops.preferences.addon_enable(module=module_name)
            else:
                bpy.ops.preferences.addon_disable(module=module_name)
            is_enabled = addon_utils.check(module_name)[0]
            return {"success": True, "module": module_name, "enabled": is_enabled}
        except Exception as e:
            return {"error": str(e)}

    def save_file(self, filepath=None, compress=False):
        """Save the current .blend file"""
        try:
            if filepath:
                bpy.ops.wm.save_as_mainfile(filepath=filepath, compress=compress)
            else:
                if bpy.data.filepath:
                    bpy.ops.wm.save_mainfile(filepath=bpy.data.filepath, compress=compress)
                else:
                    return {"error": "No filepath set. Provide a filepath for first save."}
            return {"success": True, "filepath": bpy.data.filepath}
        except Exception as e:
            return {"error": str(e)}

    def export_scene(self, filepath, format="fbx", selection_only=False):
        """Export scene to FBX, glTF, OBJ, or other formats"""
        try:
            fmt = format.lower()
            if fmt == "fbx":
                bpy.ops.export_scene.fbx(
                    filepath=filepath,
                    use_selection=selection_only,
                    apply_scale_options='FBX_SCALE_ALL',
                    path_mode='COPY',
                    embed_textures=True,
                )
            elif fmt in ("gltf", "glb"):
                bpy.ops.export_scene.gltf(
                    filepath=filepath,
                    use_selection=selection_only,
                    export_format='GLB' if fmt == 'glb' else 'GLTF_SEPARATE',
                )
            elif fmt == "obj":
                bpy.ops.wm.obj_export(
                    filepath=filepath,
                    export_selected_objects=selection_only,
                )
            else:
                return {"error": f"Unsupported format: {format}. Use fbx, gltf, glb, or obj."}
            return {"success": True, "filepath": filepath, "format": fmt}
        except Exception as e:
            return {"error": str(e)}

    def batch_modify_materials(self, pattern, base_color=None, metallic=None, roughness=None,
                               emission_color=None, emission_strength=None):
        """Modify Principled BSDF properties on all materials matching a name pattern"""
        try:
            modified = []
            for mat in bpy.data.materials:
                if not re.search(pattern, mat.name, re.IGNORECASE):
                    continue
                if not mat.use_nodes or not mat.node_tree:
                    continue
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        if base_color is not None:
                            bc = base_color if len(base_color) == 4 else list(base_color) + [1.0]
                            node.inputs['Base Color'].default_value = bc
                        if metallic is not None:
                            node.inputs['Metallic'].default_value = metallic
                        if roughness is not None:
                            node.inputs['Roughness'].default_value = roughness
                        if emission_color is not None:
                            ec = emission_color if len(emission_color) == 4 else list(emission_color) + [1.0]
                            node.inputs['Emission Color'].default_value = ec
                        if emission_strength is not None:
                            node.inputs['Emission Strength'].default_value = emission_strength
                        modified.append(mat.name)
                        break
            return {"success": True, "modified": modified, "count": len(modified)}
        except Exception as e:
            return {"error": str(e)}

    def get_scene_stats(self):
        """Get detailed scene statistics"""
        try:
            mesh_count = sum(1 for o in bpy.context.scene.objects if o.type == 'MESH')
            light_count = sum(1 for o in bpy.context.scene.objects if o.type == 'LIGHT')
            camera_count = sum(1 for o in bpy.context.scene.objects if o.type == 'CAMERA')
            empty_count = sum(1 for o in bpy.context.scene.objects if o.type == 'EMPTY')
            curve_count = sum(1 for o in bpy.context.scene.objects if o.type == 'CURVE')
            total_verts = 0
            total_faces = 0
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and obj.data:
                    total_verts += len(obj.data.vertices)
                    total_faces += len(obj.data.polygons)
            return {
                "total_objects": len(bpy.context.scene.objects),
                "meshes": mesh_count,
                "lights": light_count,
                "cameras": camera_count,
                "empties": empty_count,
                "curves": curve_count,
                "total_vertices": total_verts,
                "total_faces": total_faces,
                "total_materials": len(bpy.data.materials),
                "total_images": len(bpy.data.images),
                "total_collections": len(bpy.data.collections),
                "render_engine": bpy.context.scene.render.engine,
                "file_path": bpy.data.filepath,
                "frame_current": bpy.context.scene.frame_current,
            }
        except Exception as e:
            return {"error": str(e)}

    def find_objects(self, name_pattern=None, object_type=None, collection_name=None,
                     has_material=None, limit=100):
        """Find objects with flexible filtering"""
        try:
            results = []
            candidates = bpy.context.scene.objects
            if collection_name:
                col = bpy.data.collections.get(collection_name)
                if not col:
                    return {"error": f"Collection not found: {collection_name}"}
                candidates = col.all_objects
            for obj in candidates:
                if name_pattern and not re.search(name_pattern, obj.name, re.IGNORECASE):
                    continue
                if object_type and obj.type != object_type.upper():
                    continue
                if has_material is not None:
                    obj_mats = [s.material.name for s in obj.material_slots if s.material]
                    if has_material not in obj_mats:
                        continue
                info = {
                    "name": obj.name,
                    "type": obj.type,
                    "location": [round(obj.location.x, 2), round(obj.location.y, 2), round(obj.location.z, 2)],
                    "materials": [s.material.name for s in obj.material_slots if s.material],
                    "collection": [c.name for c in obj.users_collection],
                }
                results.append(info)
                if len(results) >= limit:
                    break
            return {"objects": results, "count": len(results)}
        except Exception as e:
            return {"error": str(e)}

    def set_object_color(self, names=None, pattern=None, collection_name=None, color=None):
        """Set viewport display color on objects (for SOLID mode Object color)"""
        try:
            if not color:
                return {"error": "color is required as [R, G, B, A]"}
            targets = []
            if names:
                for n in names:
                    obj = bpy.data.objects.get(n)
                    if obj:
                        targets.append(obj)
            elif pattern:
                for obj in bpy.context.scene.objects:
                    if re.search(pattern, obj.name, re.IGNORECASE):
                        targets.append(obj)
            elif collection_name:
                col = bpy.data.collections.get(collection_name)
                if col:
                    targets = list(col.all_objects)
            for obj in targets:
                obj.color = color if len(color) == 4 else list(color) + [1.0]
            return {"success": True, "count": len(targets)}
        except Exception as e:
            return {"error": str(e)}

    def manage_lights(self, name=None, action="list", light_type=None, energy=None,
                      color=None, location=None, rotation=None, size=None):
        """Manage scene lights: list, create, modify"""
        try:
            if action == "list":
                lights = []
                for obj in bpy.context.scene.objects:
                    if obj.type == 'LIGHT':
                        l = obj.data
                        lights.append({
                            "name": obj.name,
                            "type": l.type,
                            "energy": l.energy,
                            "color": list(l.color),
                            "location": [round(obj.location.x, 2), round(obj.location.y, 2), round(obj.location.z, 2)],
                        })
                return {"lights": lights, "count": len(lights)}
            if action == "create":
                lt = light_type or 'POINT'
                light_data = bpy.data.lights.new(name=name or "Light", type=lt)
                if energy is not None:
                    light_data.energy = energy
                if color is not None:
                    light_data.color = color[:3]
                if size is not None and hasattr(light_data, 'shadow_soft_size'):
                    light_data.shadow_soft_size = size
                obj = bpy.data.objects.new(name=name or "Light", object_data=light_data)
                bpy.context.scene.collection.objects.link(obj)
                if location:
                    obj.location = mathutils.Vector(location)
                if rotation:
                    obj.rotation_euler = mathutils.Euler(rotation)
                return {"success": True, "name": obj.name, "type": lt}
            if action == "modify" and name:
                obj = bpy.data.objects.get(name)
                if not obj or obj.type != 'LIGHT':
                    return {"error": f"Light not found: {name}"}
                l = obj.data
                if energy is not None:
                    l.energy = energy
                if color is not None:
                    l.color = color[:3]
                if location is not None:
                    obj.location = mathutils.Vector(location)
                if rotation is not None:
                    obj.rotation_euler = mathutils.Euler(rotation)
                if size is not None and hasattr(l, 'shadow_soft_size'):
                    l.shadow_soft_size = size
                return {"success": True, "name": obj.name}
            return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}

    def set_viewport_camera(self, location=None, target=None, lens=None, clip_start=None, clip_end=None):
        """Configure the 3D viewport camera position and settings"""
        try:
            import math
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces[0]
                    rd = space.region_3d
                    if location and target:
                        loc = mathutils.Vector(location)
                        tgt = mathutils.Vector(target)
                        direction = tgt - loc
                        rd.view_location = tgt
                        rd.view_distance = direction.length
                        rot = direction.to_track_quat('-Z', 'Y')
                        rd.view_rotation = rot
                        rd.view_perspective = 'PERSP'
                    if lens:
                        space.lens = lens
                    if clip_start is not None:
                        space.clip_start = clip_start
                    if clip_end is not None:
                        space.clip_end = clip_end
                    return {"success": True}
            return {"error": "No 3D viewport found"}
        except Exception as e:
            return {"error": str(e)}

    def get_render_settings(self):
        """Get current render settings"""
        try:
            scene = bpy.context.scene
            r = scene.render
            result = {
                "engine": r.engine,
                "resolution_x": r.resolution_x,
                "resolution_y": r.resolution_y,
                "resolution_percentage": r.resolution_percentage,
                "film_transparent": r.film_transparent,
                "fps": r.fps,
                "frame_start": scene.frame_start,
                "frame_end": scene.frame_end,
                "output_path": r.filepath,
                "file_format": r.image_settings.file_format,
            }
            if r.engine == 'CYCLES':
                result["cycles_samples"] = scene.cycles.samples
                result["cycles_device"] = scene.cycles.device
            if r.engine == 'BLENDER_EEVEE_NEXT':
                result["eevee_samples"] = scene.eevee.taa_render_samples
            return result
        except Exception as e:
            return {"error": str(e)}

    def set_render_settings(self, resolution_x=None, resolution_y=None,
                            resolution_percentage=None, samples=None,
                            film_transparent=None, output_path=None, file_format=None):
        """Set render settings"""
        try:
            r = bpy.context.scene.render
            changed = []
            if resolution_x is not None:
                r.resolution_x = resolution_x
                changed.append("resolution_x")
            if resolution_y is not None:
                r.resolution_y = resolution_y
                changed.append("resolution_y")
            if resolution_percentage is not None:
                r.resolution_percentage = resolution_percentage
                changed.append("resolution_percentage")
            if film_transparent is not None:
                r.film_transparent = film_transparent
                changed.append("film_transparent")
            if output_path is not None:
                r.filepath = output_path
                changed.append("output_path")
            if file_format is not None:
                r.image_settings.file_format = file_format
                changed.append("file_format")
            if samples is not None:
                if r.engine == 'CYCLES':
                    bpy.context.scene.cycles.samples = samples
                    changed.append("cycles_samples")
                elif r.engine == 'BLENDER_EEVEE_NEXT':
                    bpy.context.scene.eevee.taa_render_samples = samples
                    changed.append("eevee_samples")
            return {"success": True, "changed": changed}
        except Exception as e:
            return {"error": str(e)}

    def move_to_collection(self, object_names, target_collection, create_if_missing=True):
        """Move objects to a target collection"""
        try:
            col = bpy.data.collections.get(target_collection)
            if not col:
                if create_if_missing:
                    col = bpy.data.collections.new(target_collection)
                    bpy.context.scene.collection.children.link(col)
                else:
                    return {"error": f"Collection not found: {target_collection}"}
            moved = []
            for name in object_names:
                obj = bpy.data.objects.get(name)
                if not obj:
                    continue
                # Unlink from current collections
                for old_col in list(obj.users_collection):
                    old_col.objects.unlink(obj)
                col.objects.link(obj)
                moved.append(name)
            return {"success": True, "moved": moved, "target": col.name}
        except Exception as e:
            return {"error": str(e)}

    def recalculate_normals(self, object_names=None, collection_name=None, inside=False):
        """Recalculate normals for mesh objects to fix black face rendering"""
        try:
            targets = []
            if object_names:
                for n in object_names:
                    obj = bpy.data.objects.get(n)
                    if obj and obj.type == 'MESH':
                        targets.append(obj)
            elif collection_name:
                col = bpy.data.collections.get(collection_name)
                if col:
                    targets = [o for o in col.all_objects if o.type == 'MESH']
            else:
                targets = [o for o in bpy.context.scene.objects if o.type == 'MESH']
            if not targets:
                return {"error": "No mesh objects found"}
            fixed = []
            for obj in targets:
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.normals_make_consistent(inside=inside)
                bpy.ops.object.mode_set(mode='OBJECT')
                fixed.append(obj.name)
            return {"success": True, "fixed": fixed, "count": len(fixed)}
        except Exception as e:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except:
                pass
            return {"error": str(e)}

    def fix_materials_missing(self, collection_name=None, default_color=None):
        """Find and fix objects with missing materials (causes black rendering)"""
        try:
            if default_color is None:
                default_color = [0.5, 0.5, 0.5, 1.0]
            fixed = []
            candidates = bpy.context.scene.objects
            if collection_name:
                col = bpy.data.collections.get(collection_name)
                if col:
                    candidates = col.all_objects
            for obj in candidates:
                if obj.type != 'MESH':
                    continue
                needs_fix = False
                if len(obj.material_slots) == 0:
                    needs_fix = True
                else:
                    for slot in obj.material_slots:
                        if slot.material is None:
                            needs_fix = True
                            break
                if needs_fix:
                    mat_name = f"Fix_{obj.name}"
                    mat = bpy.data.materials.new(name=mat_name)
                    mat.use_nodes = True
                    for node in mat.node_tree.nodes:
                        if node.type == 'BSDF_PRINCIPLED':
                            node.inputs['Base Color'].default_value = default_color
                            break
                    if len(obj.material_slots) == 0:
                        obj.data.materials.append(mat)
                    else:
                        for slot in obj.material_slots:
                            if slot.material is None:
                                slot.material = mat
                    fixed.append(obj.name)
            return {"success": True, "fixed": fixed, "count": len(fixed)}
        except Exception as e:
            return {"error": str(e)}

    def get_telemetry_consent(self):
        """Get the current telemetry consent status"""
        try:
            # Get addon preferences - use the module name
            addon_prefs = bpy.context.preferences.addons.get(__name__)
            if addon_prefs:
                consent = addon_prefs.preferences.telemetry_consent
            else:
                # Fallback to default if preferences not available
                consent = True
        except (AttributeError, KeyError):
            # Fallback to default if preferences not available
            consent = True
        return {"consent": consent}

    def get_polyhaven_status(self):
        """Get the current status of PolyHaven integration"""
        enabled = bpy.context.scene.blendermcp_use_polyhaven
        if enabled:
            return {"enabled": True, "message": "PolyHaven integration is enabled and ready to use."}
        else:
            return {
                "enabled": False,
                "message": """PolyHaven integration is currently disabled. To enable it:
                            1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                            2. Check the 'Use assets from Poly Haven' checkbox
                            3. Restart the connection to Claude"""
        }

    #region Hyper3D
    def get_hyper3d_status(self):
        """Get the current status of Hyper3D Rodin integration"""
        enabled = bpy.context.scene.blendermcp_use_hyper3d
        if enabled:
            if not bpy.context.scene.blendermcp_hyper3d_api_key:
                return {
                    "enabled": False,
                    "message": """Hyper3D Rodin integration is currently enabled, but API key is not given. To enable it:
                                1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                                2. Keep the 'Use Hyper3D Rodin 3D model generation' checkbox checked
                                3. Choose the right plaform and fill in the API Key
                                4. Restart the connection to Claude"""
                }
            mode = bpy.context.scene.blendermcp_hyper3d_mode
            message = f"Hyper3D Rodin integration is enabled and ready to use. Mode: {mode}. " + \
                f"Key type: {'private' if bpy.context.scene.blendermcp_hyper3d_api_key != RODIN_FREE_TRIAL_KEY else 'free_trial'}"
            return {
                "enabled": True,
                "message": message
            }
        else:
            return {
                "enabled": False,
                "message": """Hyper3D Rodin integration is currently disabled. To enable it:
                            1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                            2. Check the 'Use Hyper3D Rodin 3D model generation' checkbox
                            3. Restart the connection to Claude"""
            }

    def create_rodin_job(self, *args, **kwargs):
        match bpy.context.scene.blendermcp_hyper3d_mode:
            case "MAIN_SITE":
                return self.create_rodin_job_main_site(*args, **kwargs)
            case "FAL_AI":
                return self.create_rodin_job_fal_ai(*args, **kwargs)
            case _:
                return f"Error: Unknown Hyper3D Rodin mode!"

    def create_rodin_job_main_site(
            self,
            text_prompt: str=None,
            images: list[tuple[str, str]]=None,
            bbox_condition=None
        ):
        try:
            if images is None:
                images = []
            """Call Rodin API, get the job uuid and subscription key"""
            files = [
                *[("images", (f"{i:04d}{img_suffix}", img)) for i, (img_suffix, img) in enumerate(images)],
                ("tier", (None, "Sketch")),
                ("mesh_mode", (None, "Raw")),
            ]
            if text_prompt:
                files.append(("prompt", (None, text_prompt)))
            if bbox_condition:
                files.append(("bbox_condition", (None, json.dumps(bbox_condition))))
            response = requests.post(
                "https://hyperhuman.deemos.com/api/v2/rodin",
                headers={
                    "Authorization": f"Bearer {bpy.context.scene.blendermcp_hyper3d_api_key}",
                },
                files=files
            )
            data = response.json()
            return data
        except Exception as e:
            return {"error": str(e)}

    def create_rodin_job_fal_ai(
            self,
            text_prompt: str=None,
            images: list[tuple[str, str]]=None,
            bbox_condition=None
        ):
        try:
            req_data = {
                "tier": "Sketch",
            }
            if images:
                req_data["input_image_urls"] = images
            if text_prompt:
                req_data["prompt"] = text_prompt
            if bbox_condition:
                req_data["bbox_condition"] = bbox_condition
            response = requests.post(
                "https://queue.fal.run/fal-ai/hyper3d/rodin",
                headers={
                    "Authorization": f"Key {bpy.context.scene.blendermcp_hyper3d_api_key}",
                    "Content-Type": "application/json",
                },
                json=req_data
            )
            data = response.json()
            return data
        except Exception as e:
            return {"error": str(e)}

    def poll_rodin_job_status(self, *args, **kwargs):
        match bpy.context.scene.blendermcp_hyper3d_mode:
            case "MAIN_SITE":
                return self.poll_rodin_job_status_main_site(*args, **kwargs)
            case "FAL_AI":
                return self.poll_rodin_job_status_fal_ai(*args, **kwargs)
            case _:
                return f"Error: Unknown Hyper3D Rodin mode!"

    def poll_rodin_job_status_main_site(self, subscription_key: str):
        """Call the job status API to get the job status"""
        response = requests.post(
            "https://hyperhuman.deemos.com/api/v2/status",
            headers={
                "Authorization": f"Bearer {bpy.context.scene.blendermcp_hyper3d_api_key}",
            },
            json={
                "subscription_key": subscription_key,
            },
        )
        data = response.json()
        return {
            "status_list": [i["status"] for i in data["jobs"]]
        }

    def poll_rodin_job_status_fal_ai(self, request_id: str):
        """Call the job status API to get the job status"""
        response = requests.get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}/status",
            headers={
                "Authorization": f"KEY {bpy.context.scene.blendermcp_hyper3d_api_key}",
            },
        )
        data = response.json()
        return data

    @staticmethod
    def _clean_imported_glb(filepath, mesh_name=None):
        # Get the set of existing objects before import
        existing_objects = set(bpy.data.objects)

        # Import the GLB file
        bpy.ops.import_scene.gltf(filepath=filepath)

        # Ensure the context is updated
        bpy.context.view_layer.update()

        # Get all imported objects
        imported_objects = list(set(bpy.data.objects) - existing_objects)
        # imported_objects = [obj for obj in bpy.context.view_layer.objects if obj.select_get()]

        if not imported_objects:
            print("Error: No objects were imported.")
            return

        # Identify the mesh object
        mesh_obj = None

        if len(imported_objects) == 1 and imported_objects[0].type == 'MESH':
            mesh_obj = imported_objects[0]
            print("Single mesh imported, no cleanup needed.")
        else:
            if len(imported_objects) == 2:
                empty_objs = [i for i in imported_objects if i.type == "EMPTY"]
                if len(empty_objs) != 1:
                    print("Error: Expected an empty node with one mesh child or a single mesh object.")
                    return
                parent_obj = empty_objs.pop()
                if len(parent_obj.children) == 1:
                    potential_mesh = parent_obj.children[0]
                    if potential_mesh.type == 'MESH':
                        print("GLB structure confirmed: Empty node with one mesh child.")

                        # Unparent the mesh from the empty node
                        potential_mesh.parent = None

                        # Remove the empty node
                        bpy.data.objects.remove(parent_obj)
                        print("Removed empty node, keeping only the mesh.")

                        mesh_obj = potential_mesh
                    else:
                        print("Error: Child is not a mesh object.")
                        return
                else:
                    print("Error: Expected an empty node with one mesh child or a single mesh object.")
                    return
            else:
                print("Error: Expected an empty node with one mesh child or a single mesh object.")
                return

        # Rename the mesh if needed
        try:
            if mesh_obj and mesh_obj.name is not None and mesh_name:
                mesh_obj.name = mesh_name
                if mesh_obj.data.name is not None:
                    mesh_obj.data.name = mesh_name
                print(f"Mesh renamed to: {mesh_name}")
        except Exception as e:
            print("Having issue with renaming, give up renaming.")

        return mesh_obj

    def import_generated_asset(self, *args, **kwargs):
        match bpy.context.scene.blendermcp_hyper3d_mode:
            case "MAIN_SITE":
                return self.import_generated_asset_main_site(*args, **kwargs)
            case "FAL_AI":
                return self.import_generated_asset_fal_ai(*args, **kwargs)
            case _:
                return f"Error: Unknown Hyper3D Rodin mode!"

    def import_generated_asset_main_site(self, task_uuid: str, name: str):
        """Fetch the generated asset, import into blender"""
        response = requests.post(
            "https://hyperhuman.deemos.com/api/v2/download",
            headers={
                "Authorization": f"Bearer {bpy.context.scene.blendermcp_hyper3d_api_key}",
            },
            json={
                'task_uuid': task_uuid
            }
        )
        data_ = response.json()
        temp_file = None
        for i in data_["list"]:
            if i["name"].endswith(".glb"):
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    prefix=task_uuid,
                    suffix=".glb",
                )

                try:
                    # Download the content
                    response = requests.get(i["url"], stream=True)
                    response.raise_for_status()  # Raise an exception for HTTP errors

                    # Write the content to the temporary file
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_file.write(chunk)

                    # Close the file
                    temp_file.close()

                except Exception as e:
                    # Clean up the file if there's an error
                    temp_file.close()
                    os.unlink(temp_file.name)
                    return {"succeed": False, "error": str(e)}

                break
        else:
            return {"succeed": False, "error": "Generation failed. Please first make sure that all jobs of the task are done and then try again later."}

        try:
            obj = self._clean_imported_glb(
                filepath=temp_file.name,
                mesh_name=name
            )
            result = {
                "name": obj.name,
                "type": obj.type,
                "location": [obj.location.x, obj.location.y, obj.location.z],
                "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
                "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            }

            if obj.type == "MESH":
                bounding_box = self._get_aabb(obj)
                result["world_bounding_box"] = bounding_box

            return {
                "succeed": True, **result
            }
        except Exception as e:
            return {"succeed": False, "error": str(e)}

    def import_generated_asset_fal_ai(self, request_id: str, name: str):
        """Fetch the generated asset, import into blender"""
        response = requests.get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}",
            headers={
                "Authorization": f"Key {bpy.context.scene.blendermcp_hyper3d_api_key}",
            }
        )
        data_ = response.json()
        temp_file = None

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            prefix=request_id,
            suffix=".glb",
        )

        try:
            # Download the content
            response = requests.get(data_["model_mesh"]["url"], stream=True)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Write the content to the temporary file
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)

            # Close the file
            temp_file.close()

        except Exception as e:
            # Clean up the file if there's an error
            temp_file.close()
            os.unlink(temp_file.name)
            return {"succeed": False, "error": str(e)}

        try:
            obj = self._clean_imported_glb(
                filepath=temp_file.name,
                mesh_name=name
            )
            result = {
                "name": obj.name,
                "type": obj.type,
                "location": [obj.location.x, obj.location.y, obj.location.z],
                "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
                "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            }

            if obj.type == "MESH":
                bounding_box = self._get_aabb(obj)
                result["world_bounding_box"] = bounding_box

            return {
                "succeed": True, **result
            }
        except Exception as e:
            return {"succeed": False, "error": str(e)}
    #endregion
 
    #region Sketchfab API
    def get_sketchfab_status(self):
        """Get the current status of Sketchfab integration"""
        enabled = bpy.context.scene.blendermcp_use_sketchfab
        api_key = bpy.context.scene.blendermcp_sketchfab_api_key

        # Test the API key if present
        if api_key:
            try:
                headers = {
                    "Authorization": f"Token {api_key}"
                }

                response = requests.get(
                    "https://api.sketchfab.com/v3/me",
                    headers=headers,
                    timeout=30  # Add timeout of 30 seconds
                )

                if response.status_code == 200:
                    user_data = response.json()
                    username = user_data.get("username", "Unknown user")
                    return {
                        "enabled": True,
                        "message": f"Sketchfab integration is enabled and ready to use. Logged in as: {username}"
                    }
                else:
                    return {
                        "enabled": False,
                        "message": f"Sketchfab API key seems invalid. Status code: {response.status_code}"
                    }
            except requests.exceptions.Timeout:
                return {
                    "enabled": False,
                    "message": "Timeout connecting to Sketchfab API. Check your internet connection."
                }
            except Exception as e:
                return {
                    "enabled": False,
                    "message": f"Error testing Sketchfab API key: {str(e)}"
                }

        if enabled and api_key:
            return {"enabled": True, "message": "Sketchfab integration is enabled and ready to use."}
        elif enabled and not api_key:
            return {
                "enabled": False,
                "message": """Sketchfab integration is currently enabled, but API key is not given. To enable it:
                            1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                            2. Keep the 'Use Sketchfab' checkbox checked
                            3. Enter your Sketchfab API Key
                            4. Restart the connection to Claude"""
            }
        else:
            return {
                "enabled": False,
                "message": """Sketchfab integration is currently disabled. To enable it:
                            1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                            2. Check the 'Use assets from Sketchfab' checkbox
                            3. Enter your Sketchfab API Key
                            4. Restart the connection to Claude"""
            }

    def search_sketchfab_models(self, query, categories=None, count=20, downloadable=True):
        """Search for models on Sketchfab based on query and optional filters"""
        try:
            api_key = bpy.context.scene.blendermcp_sketchfab_api_key
            if not api_key:
                return {"error": "Sketchfab API key is not configured"}

            # Build search parameters with exact fields from Sketchfab API docs
            params = {
                "type": "models",
                "q": query,
                "count": count,
                "downloadable": downloadable,
                "archives_flavours": False
            }

            if categories:
                params["categories"] = categories

            # Make API request to Sketchfab search endpoint
            # The proper format according to Sketchfab API docs for API key auth
            headers = {
                "Authorization": f"Token {api_key}"
            }


            # Use the search endpoint as specified in the API documentation
            response = requests.get(
                "https://api.sketchfab.com/v3/search",
                headers=headers,
                params=params,
                timeout=30  # Add timeout of 30 seconds
            )

            if response.status_code == 401:
                return {"error": "Authentication failed (401). Check your API key."}

            if response.status_code != 200:
                return {"error": f"API request failed with status code {response.status_code}"}

            response_data = response.json()

            # Safety check on the response structure
            if response_data is None:
                return {"error": "Received empty response from Sketchfab API"}

            # Handle 'results' potentially missing from response
            results = response_data.get("results", [])
            if not isinstance(results, list):
                return {"error": f"Unexpected response format from Sketchfab API: {response_data}"}

            return response_data

        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Check your internet connection."}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response from Sketchfab API: {str(e)}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def get_sketchfab_model_preview(self, uid):
        """Get thumbnail preview image of a Sketchfab model by its UID"""
        try:
            import base64
            
            api_key = bpy.context.scene.blendermcp_sketchfab_api_key
            if not api_key:
                return {"error": "Sketchfab API key is not configured"}

            headers = {"Authorization": f"Token {api_key}"}
            
            # Get model info which includes thumbnails
            response = requests.get(
                f"https://api.sketchfab.com/v3/models/{uid}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 401:
                return {"error": "Authentication failed (401). Check your API key."}
            
            if response.status_code == 404:
                return {"error": f"Model not found: {uid}"}
            
            if response.status_code != 200:
                return {"error": f"Failed to get model info: {response.status_code}"}
            
            data = response.json()
            thumbnails = data.get("thumbnails", {}).get("images", [])
            
            if not thumbnails:
                return {"error": "No thumbnail available for this model"}
            
            # Find a suitable thumbnail (prefer medium size ~640px)
            selected_thumbnail = None
            for thumb in thumbnails:
                width = thumb.get("width", 0)
                if 400 <= width <= 800:
                    selected_thumbnail = thumb
                    break
            
            # Fallback to the first available thumbnail
            if not selected_thumbnail:
                selected_thumbnail = thumbnails[0]
            
            thumbnail_url = selected_thumbnail.get("url")
            if not thumbnail_url:
                return {"error": "Thumbnail URL not found"}
            
            # Download the thumbnail image
            img_response = requests.get(thumbnail_url, timeout=30)
            if img_response.status_code != 200:
                return {"error": f"Failed to download thumbnail: {img_response.status_code}"}
            
            # Encode image as base64
            image_data = base64.b64encode(img_response.content).decode('ascii')
            
            # Determine format from content type or URL
            content_type = img_response.headers.get("Content-Type", "")
            if "png" in content_type or thumbnail_url.endswith(".png"):
                img_format = "png"
            else:
                img_format = "jpeg"
            
            # Get additional model info for context
            model_name = data.get("name", "Unknown")
            author = data.get("user", {}).get("username", "Unknown")
            
            return {
                "success": True,
                "image_data": image_data,
                "format": img_format,
                "model_name": model_name,
                "author": author,
                "uid": uid,
                "thumbnail_width": selected_thumbnail.get("width"),
                "thumbnail_height": selected_thumbnail.get("height")
            }
            
        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Check your internet connection."}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to get model preview: {str(e)}"}

    def download_sketchfab_model(self, uid, normalize_size=False, target_size=1.0):
        """Download a model from Sketchfab by its UID
        
        Parameters:
        - uid: The unique identifier of the Sketchfab model
        - normalize_size: If True, scale the model so its largest dimension equals target_size
        - target_size: The target size in Blender units (meters) for the largest dimension
        """
        try:
            api_key = bpy.context.scene.blendermcp_sketchfab_api_key
            if not api_key:
                return {"error": "Sketchfab API key is not configured"}

            # Use proper authorization header for API key auth
            headers = {
                "Authorization": f"Token {api_key}"
            }

            # Request download URL using the exact endpoint from the documentation
            download_endpoint = f"https://api.sketchfab.com/v3/models/{uid}/download"

            response = requests.get(
                download_endpoint,
                headers=headers,
                timeout=30  # Add timeout of 30 seconds
            )

            if response.status_code == 401:
                return {"error": "Authentication failed (401). Check your API key."}

            if response.status_code != 200:
                return {"error": f"Download request failed with status code {response.status_code}"}

            data = response.json()

            # Safety check for None data
            if data is None:
                return {"error": "Received empty response from Sketchfab API for download request"}

            # Extract download URL with safety checks
            gltf_data = data.get("gltf")
            if not gltf_data:
                return {"error": "No gltf download URL available for this model. Response: " + str(data)}

            download_url = gltf_data.get("url")
            if not download_url:
                return {"error": "No download URL available for this model. Make sure the model is downloadable and you have access."}

            # Download the model (already has timeout)
            model_response = requests.get(download_url, timeout=60)  # 60 second timeout

            if model_response.status_code != 200:
                return {"error": f"Model download failed with status code {model_response.status_code}"}

            # Save to temporary file
            temp_dir = tempfile.mkdtemp()
            zip_file_path = os.path.join(temp_dir, f"{uid}.zip")

            with open(zip_file_path, "wb") as f:
                f.write(model_response.content)

            # Extract the zip file with enhanced security
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                # More secure zip slip prevention
                for file_info in zip_ref.infolist():
                    # Get the path of the file
                    file_path = file_info.filename

                    # Convert directory separators to the current OS style
                    # This handles both / and \ in zip entries
                    target_path = os.path.join(temp_dir, os.path.normpath(file_path))

                    # Get absolute paths for comparison
                    abs_temp_dir = os.path.abspath(temp_dir)
                    abs_target_path = os.path.abspath(target_path)

                    # Ensure the normalized path doesn't escape the target directory
                    if not abs_target_path.startswith(abs_temp_dir):
                        with suppress(Exception):
                            shutil.rmtree(temp_dir)
                        return {"error": "Security issue: Zip contains files with path traversal attempt"}

                    # Additional explicit check for directory traversal
                    if ".." in file_path:
                        with suppress(Exception):
                            shutil.rmtree(temp_dir)
                        return {"error": "Security issue: Zip contains files with directory traversal sequence"}

                # If all files passed security checks, extract them
                zip_ref.extractall(temp_dir)

            # Find the main glTF file
            gltf_files = [f for f in os.listdir(temp_dir) if f.endswith('.gltf') or f.endswith('.glb')]

            if not gltf_files:
                with suppress(Exception):
                    shutil.rmtree(temp_dir)
                return {"error": "No glTF file found in the downloaded model"}

            main_file = os.path.join(temp_dir, gltf_files[0])

            # Import the model
            bpy.ops.import_scene.gltf(filepath=main_file)

            # Get the imported objects
            imported_objects = list(bpy.context.selected_objects)
            imported_object_names = [obj.name for obj in imported_objects]

            # Clean up temporary files
            with suppress(Exception):
                shutil.rmtree(temp_dir)

            # Find root objects (objects without parents in the imported set)
            root_objects = [obj for obj in imported_objects if obj.parent is None]

            # Helper function to recursively get all mesh children
            def get_all_mesh_children(obj):
                """Recursively collect all mesh objects in the hierarchy"""
                meshes = []
                if obj.type == 'MESH':
                    meshes.append(obj)
                for child in obj.children:
                    meshes.extend(get_all_mesh_children(child))
                return meshes

            # Collect ALL meshes from the entire hierarchy (starting from roots)
            all_meshes = []
            for obj in root_objects:
                all_meshes.extend(get_all_mesh_children(obj))
            
            if all_meshes:
                # Calculate combined world bounding box for all meshes
                all_min = mathutils.Vector((float('inf'), float('inf'), float('inf')))
                all_max = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))
                
                for mesh_obj in all_meshes:
                    # Get world-space bounding box corners
                    for corner in mesh_obj.bound_box:
                        world_corner = mesh_obj.matrix_world @ mathutils.Vector(corner)
                        all_min.x = min(all_min.x, world_corner.x)
                        all_min.y = min(all_min.y, world_corner.y)
                        all_min.z = min(all_min.z, world_corner.z)
                        all_max.x = max(all_max.x, world_corner.x)
                        all_max.y = max(all_max.y, world_corner.y)
                        all_max.z = max(all_max.z, world_corner.z)
                
                # Calculate dimensions
                dimensions = [
                    all_max.x - all_min.x,
                    all_max.y - all_min.y,
                    all_max.z - all_min.z
                ]
                max_dimension = max(dimensions)
                
                # Apply normalization if requested
                scale_applied = 1.0
                if normalize_size and max_dimension > 0:
                    scale_factor = target_size / max_dimension
                    scale_applied = scale_factor
                    
                    # ✅ Only apply scale to ROOT objects (not children!)
                    # Child objects inherit parent's scale through matrix_world
                    for root in root_objects:
                        root.scale = (
                            root.scale.x * scale_factor,
                            root.scale.y * scale_factor,
                            root.scale.z * scale_factor
                        )
                    
                    # Update the scene to recalculate matrix_world for all objects
                    bpy.context.view_layer.update()
                    
                    # Recalculate bounding box after scaling
                    all_min = mathutils.Vector((float('inf'), float('inf'), float('inf')))
                    all_max = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))
                    
                    for mesh_obj in all_meshes:
                        for corner in mesh_obj.bound_box:
                            world_corner = mesh_obj.matrix_world @ mathutils.Vector(corner)
                            all_min.x = min(all_min.x, world_corner.x)
                            all_min.y = min(all_min.y, world_corner.y)
                            all_min.z = min(all_min.z, world_corner.z)
                            all_max.x = max(all_max.x, world_corner.x)
                            all_max.y = max(all_max.y, world_corner.y)
                            all_max.z = max(all_max.z, world_corner.z)
                    
                    dimensions = [
                        all_max.x - all_min.x,
                        all_max.y - all_min.y,
                        all_max.z - all_min.z
                    ]
                
                world_bounding_box = [[all_min.x, all_min.y, all_min.z], [all_max.x, all_max.y, all_max.z]]
            else:
                world_bounding_box = None
                dimensions = None
                scale_applied = 1.0

            result = {
                "success": True,
                "message": "Model imported successfully",
                "imported_objects": imported_object_names
            }
            
            if world_bounding_box:
                result["world_bounding_box"] = world_bounding_box
            if dimensions:
                result["dimensions"] = [round(d, 4) for d in dimensions]
            if normalize_size:
                result["scale_applied"] = round(scale_applied, 6)
                result["normalized"] = True
            
            return result

        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Check your internet connection and try again with a simpler model."}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response from Sketchfab API: {str(e)}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to download model: {str(e)}"}
    #endregion

    #region Hunyuan3D
    def get_hunyuan3d_status(self):
        """Get the current status of Hunyuan3D integration"""
        enabled = bpy.context.scene.blendermcp_use_hunyuan3d
        hunyuan3d_mode = bpy.context.scene.blendermcp_hunyuan3d_mode
        if enabled:
            match hunyuan3d_mode:
                case "OFFICIAL_API":
                    if not bpy.context.scene.blendermcp_hunyuan3d_secret_id or not bpy.context.scene.blendermcp_hunyuan3d_secret_key:
                        return {
                            "enabled": False, 
                            "mode": hunyuan3d_mode, 
                            "message": """Hunyuan3D integration is currently enabled, but SecretId or SecretKey is not given. To enable it:
                                1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                                2. Keep the 'Use Tencent Hunyuan 3D model generation' checkbox checked
                                3. Choose the right platform and fill in the SecretId and SecretKey
                                4. Restart the connection to Claude"""
                        }
                case "LOCAL_API":
                    if not bpy.context.scene.blendermcp_hunyuan3d_api_url:
                        return {
                            "enabled": False, 
                            "mode": hunyuan3d_mode, 
                            "message": """Hunyuan3D integration is currently enabled, but API URL  is not given. To enable it:
                                1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                                2. Keep the 'Use Tencent Hunyuan 3D model generation' checkbox checked
                                3. Choose the right platform and fill in the API URL
                                4. Restart the connection to Claude"""
                        }
                case _:
                    return {
                        "enabled": False, 
                        "message": "Hunyuan3D integration is enabled and mode is not supported."
                    }
            return {
                "enabled": True, 
                "mode": hunyuan3d_mode,
                "message": "Hunyuan3D integration is enabled and ready to use."
            }
        return {
            "enabled": False, 
            "message": """Hunyuan3D integration is currently disabled. To enable it:
                        1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)
                        2. Check the 'Use Tencent Hunyuan 3D model generation' checkbox
                        3. Restart the connection to Claude"""
        }
    
    @staticmethod
    def get_tencent_cloud_sign_headers(
        method: str,
        path: str,
        headParams: dict,
        data: dict,
        service: str,
        region: str,
        secret_id: str,
        secret_key: str,
        host: str = None
    ):
        """Generate the signature header required for Tencent Cloud API requests headers"""
        # Generate timestamp
        timestamp = int(time.time())
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
        
        # If host is not provided, it is generated based on service and region.
        if not host:
            host = f"{service}.tencentcloudapi.com"
        
        endpoint = f"https://{host}"
        
        # Constructing the request body
        payload_str = json.dumps(data)
        
        # ************* Step 1: Concatenate the canonical request string *************
        canonical_uri = path
        canonical_querystring = ""
        ct = "application/json; charset=utf-8"
        canonical_headers = f"content-type:{ct}\nhost:{host}\nx-tc-action:{headParams.get('Action', '').lower()}\n"
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        
        canonical_request = (method + "\n" +
                            canonical_uri + "\n" +
                            canonical_querystring + "\n" +
                            canonical_headers + "\n" +
                            signed_headers + "\n" +
                            hashed_request_payload)

        # ************* Step 2: Construct the reception signature string *************
        credential_scope = f"{date}/{service}/tc3_request"
        hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = ("TC3-HMAC-SHA256" + "\n" +
                        str(timestamp) + "\n" +
                        credential_scope + "\n" +
                        hashed_canonical_request)

        # ************* Step 3: Calculate the signature *************
        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = sign(secret_date, service)
        secret_signing = sign(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing, 
            string_to_sign.encode("utf-8"), 
            hashlib.sha256
        ).hexdigest()

        # ************* Step 4: Connect Authorization *************
        authorization = ("TC3-HMAC-SHA256" + " " +
                        "Credential=" + secret_id + "/" + credential_scope + ", " +
                        "SignedHeaders=" + signed_headers + ", " +
                        "Signature=" + signature)

        # Constructing request headers
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-TC-Action": headParams.get("Action", ""),
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": headParams.get("Version", ""),
            "X-TC-Region": region
        }

        return headers, endpoint

    def create_hunyuan_job(self, *args, **kwargs):
        match bpy.context.scene.blendermcp_hunyuan3d_mode:
            case "OFFICIAL_API":
                return self.create_hunyuan_job_main_site(*args, **kwargs)
            case "LOCAL_API":
                return self.create_hunyuan_job_local_site(*args, **kwargs)
            case _:
                return f"Error: Unknown Hunyuan3D mode!"

    def create_hunyuan_job_main_site(
        self,
        text_prompt: str = None,
        image: str = None
    ):
        try:
            secret_id = bpy.context.scene.blendermcp_hunyuan3d_secret_id
            secret_key = bpy.context.scene.blendermcp_hunyuan3d_secret_key

            if not secret_id or not secret_key:
                return {"error": "SecretId or SecretKey is not given"}

            # Parameter verification
            if not text_prompt and not image:
                return {"error": "Prompt or Image is required"}
            if text_prompt and image:
                return {"error": "Prompt and Image cannot be provided simultaneously"}
            # Fixed parameter configuration
            service = "hunyuan"
            action = "SubmitHunyuanTo3DJob"
            version = "2023-09-01"
            region = "ap-guangzhou"

            headParams={
                "Action": action,
                "Version": version,
                "Region": region,
            }

            # Constructing request parameters
            data = {
                "Num": 1  # The current API limit is only 1
            }

            # Handling text prompts
            if text_prompt:
                if len(text_prompt) > 200:
                    return {"error": "Prompt exceeds 200 characters limit"}
                data["Prompt"] = text_prompt

            # Handling image
            if image:
                if re.match(r'^https?://', image, re.IGNORECASE) is not None:
                    data["ImageUrl"] = image
                else:
                    try:
                        # Convert to Base64 format
                        with open(image, "rb") as f:
                            image_base64 = base64.b64encode(f.read()).decode("ascii")
                        data["ImageBase64"] = image_base64
                    except Exception as e:
                        return {"error": f"Image encoding failed: {str(e)}"}
            
            # Get signed headers
            headers, endpoint = self.get_tencent_cloud_sign_headers("POST", "/", headParams, data, service, region, secret_id, secret_key)

            response = requests.post(
                endpoint,
                headers = headers,
                data = json.dumps(data)
            )

            if response.status_code == 200:
                return response.json()
            return {
                "error": f"API request failed with status {response.status_code}: {response}"
            }
        except Exception as e:
            return {"error": str(e)}

    def create_hunyuan_job_local_site(
        self,
        text_prompt: str = None,
        image: str = None):
        try:
            base_url = bpy.context.scene.blendermcp_hunyuan3d_api_url.rstrip('/')
            octree_resolution = bpy.context.scene.blendermcp_hunyuan3d_octree_resolution
            num_inference_steps = bpy.context.scene.blendermcp_hunyuan3d_num_inference_steps
            guidance_scale = bpy.context.scene.blendermcp_hunyuan3d_guidance_scale
            texture = bpy.context.scene.blendermcp_hunyuan3d_texture

            if not base_url:
                return {"error": "API URL is not given"}
            # Parameter verification
            if not text_prompt and not image:
                return {"error": "Prompt or Image is required"}

            # Constructing request parameters
            data = {
                "octree_resolution": octree_resolution,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                "texture": texture,
            }

            # Handling text prompts
            if text_prompt:
                data["text"] = text_prompt

            # Handling image
            if image:
                if re.match(r'^https?://', image, re.IGNORECASE) is not None:
                    try:
                        resImg = requests.get(image)
                        resImg.raise_for_status()
                        image_base64 = base64.b64encode(resImg.content).decode("ascii")
                        data["image"] = image_base64
                    except Exception as e:
                        return {"error": f"Failed to download or encode image: {str(e)}"} 
                else:
                    try:
                        # Convert to Base64 format
                        with open(image, "rb") as f:
                            image_base64 = base64.b64encode(f.read()).decode("ascii")
                        data["image"] = image_base64
                    except Exception as e:
                        return {"error": f"Image encoding failed: {str(e)}"}

            response = requests.post(
                f"{base_url}/generate",
                json = data,
            )

            if response.status_code != 200:
                return {
                    "error": f"Generation failed: {response.text}"
                }
        
            # Decode base64 and save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as temp_file:
                temp_file.write(response.content)
                temp_file_name = temp_file.name

            # Import the GLB file in the main thread
            def import_handler():
                bpy.ops.import_scene.gltf(filepath=temp_file_name)
                os.unlink(temp_file.name)
                return None
            
            bpy.app.timers.register(import_handler)

            return {
                "status": "DONE",
                "message": "Generation and Import glb succeeded"
            }
        except Exception as e:
            print(f"An error occurred: {e}")
            return {"error": str(e)}
        
    
    def poll_hunyuan_job_status(self, *args, **kwargs):
        return self.poll_hunyuan_job_status_ai(*args, **kwargs)
    
    def poll_hunyuan_job_status_ai(self, job_id: str):
        """Call the job status API to get the job status"""
        print(job_id)
        try:
            secret_id = bpy.context.scene.blendermcp_hunyuan3d_secret_id
            secret_key = bpy.context.scene.blendermcp_hunyuan3d_secret_key

            if not secret_id or not secret_key:
                return {"error": "SecretId or SecretKey is not given"}
            if not job_id:
                return {"error": "JobId is required"}
            
            service = "hunyuan"
            action = "QueryHunyuanTo3DJob"
            version = "2023-09-01"
            region = "ap-guangzhou"

            headParams={
                "Action": action,
                "Version": version,
                "Region": region,
            }

            clean_job_id = job_id.removeprefix("job_")
            data = {
                "JobId": clean_job_id
            }

            headers, endpoint = self.get_tencent_cloud_sign_headers("POST", "/", headParams, data, service, region, secret_id, secret_key)

            response = requests.post(
                endpoint,
                headers=headers,
                data=json.dumps(data)
            )

            if response.status_code == 200:
                return response.json()
            return {
                "error": f"API request failed with status {response.status_code}: {response}"
            }
        except Exception as e:
            return {"error": str(e)}

    def import_generated_asset_hunyuan(self, *args, **kwargs):
        return self.import_generated_asset_hunyuan_ai(*args, **kwargs)
            
    def import_generated_asset_hunyuan_ai(self, name: str , zip_file_url: str):
        if not zip_file_url:
            return {"error": "Zip file not found"}
        
        # Validate URL
        if not re.match(r'^https?://', zip_file_url, re.IGNORECASE):
            return {"error": "Invalid URL format. Must start with http:// or https://"}
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp(prefix="tencent_obj_")
        zip_file_path = osp.join(temp_dir, "model.zip")
        obj_file_path = osp.join(temp_dir, "model.obj")
        mtl_file_path = osp.join(temp_dir, "model.mtl")

        try:
            # Download ZIP file
            zip_response = requests.get(zip_file_url, stream=True)
            zip_response.raise_for_status()
            with open(zip_file_path, "wb") as f:
                for chunk in zip_response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Unzip the ZIP
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find the .obj file (there may be multiple, assuming the main file is model.obj)
            for file in os.listdir(temp_dir):
                if file.endswith(".obj"):
                    obj_file_path = osp.join(temp_dir, file)

            if not osp.exists(obj_file_path):
                return {"succeed": False, "error": "OBJ file not found after extraction"}

            # Import obj file
            if bpy.app.version>=(4, 0, 0):
                bpy.ops.wm.obj_import(filepath=obj_file_path)
            else:
                bpy.ops.import_scene.obj(filepath=obj_file_path)

            imported_objs = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
            if not imported_objs:
                return {"succeed": False, "error": "No mesh objects imported"}

            obj = imported_objs[0]
            if name:
                obj.name = name

            result = {
                "name": obj.name,
                "type": obj.type,
                "location": [obj.location.x, obj.location.y, obj.location.z],
                "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
                "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            }

            if obj.type == "MESH":
                bounding_box = self._get_aabb(obj)
                result["world_bounding_box"] = bounding_box

            return {"succeed": True, **result}
        except Exception as e:
            return {"succeed": False, "error": str(e)}
        finally:
            #  Clean up temporary zip and obj, save texture and mtl
            try:
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path) 
                if os.path.exists(obj_file_path):
                    os.remove(obj_file_path)
            except Exception as e:
                print(f"Failed to clean up temporary directory {temp_dir}: {e}")
    #endregion

# Blender Addon Preferences
class BLENDERMCP_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    
    telemetry_consent: BoolProperty(
        name="Allow Telemetry",
        description="Allow collection of prompts, code snippets, and screenshots to help improve Blender MCP",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        
        # Telemetry section
        layout.label(text="Telemetry & Privacy:", icon='PREFERENCES')
        
        box = layout.box()
        row = box.row()
        row.prop(self, "telemetry_consent", text="Allow Telemetry")
        
        # Info text
        box.separator()
        if self.telemetry_consent:
            box.label(text="With consent: We collect anonymized prompts, code, and screenshots.", icon='INFO')
        else:
            box.label(text="Without consent: We only collect minimal anonymous usage data", icon='INFO')
            box.label(text="(tool names, success/failure, duration - no prompts or code).", icon='BLANK1')
        box.separator()
        box.label(text="All data is fully anonymized. You can change this anytime.", icon='CHECKMARK')
        
        # Terms and Conditions link
        box.separator()
        row = box.row()
        row.operator("blendermcp.open_terms", text="View Terms and Conditions", icon='TEXT')

# Blender UI Panel
class BLENDERMCP_PT_Panel(bpy.types.Panel):
    bl_label = "Blender MCP"
    bl_idname = "BLENDERMCP_PT_Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BlenderMCP'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "blendermcp_port")
        layout.prop(scene, "blendermcp_use_polyhaven", text="Use assets from Poly Haven")

        layout.prop(scene, "blendermcp_use_hyper3d", text="Use Hyper3D Rodin 3D model generation")
        if scene.blendermcp_use_hyper3d:
            layout.prop(scene, "blendermcp_hyper3d_mode", text="Rodin Mode")
            layout.prop(scene, "blendermcp_hyper3d_api_key", text="API Key")
            layout.operator("blendermcp.set_hyper3d_free_trial_api_key", text="Set Free Trial API Key")

        layout.prop(scene, "blendermcp_use_sketchfab", text="Use assets from Sketchfab")
        if scene.blendermcp_use_sketchfab:
            layout.prop(scene, "blendermcp_sketchfab_api_key", text="API Key")

        layout.prop(scene, "blendermcp_use_hunyuan3d", text="Use Tencent Hunyuan 3D model generation")
        if scene.blendermcp_use_hunyuan3d:
            layout.prop(scene, "blendermcp_hunyuan3d_mode", text="Hunyuan3D Mode")
            if scene.blendermcp_hunyuan3d_mode == 'OFFICIAL_API':
                layout.prop(scene, "blendermcp_hunyuan3d_secret_id", text="SecretId")
                layout.prop(scene, "blendermcp_hunyuan3d_secret_key", text="SecretKey")
            if scene.blendermcp_hunyuan3d_mode == 'LOCAL_API':
                layout.prop(scene, "blendermcp_hunyuan3d_api_url", text="API URL")
                layout.prop(scene, "blendermcp_hunyuan3d_octree_resolution", text="Octree Resolution")
                layout.prop(scene, "blendermcp_hunyuan3d_num_inference_steps", text="Number of Inference Steps")
                layout.prop(scene, "blendermcp_hunyuan3d_guidance_scale", text="Guidance Scale")
                layout.prop(scene, "blendermcp_hunyuan3d_texture", text="Generate Texture")
        
        if not scene.blendermcp_server_running:
            layout.operator("blendermcp.start_server", text="Connect to MCP server")
        else:
            layout.operator("blendermcp.stop_server", text="Disconnect from MCP server")
            layout.label(text=f"Running on port {scene.blendermcp_port}")

# Operator to set Hyper3D API Key
class BLENDERMCP_OT_SetFreeTrialHyper3DAPIKey(bpy.types.Operator):
    bl_idname = "blendermcp.set_hyper3d_free_trial_api_key"
    bl_label = "Set Free Trial API Key"

    def execute(self, context):
        context.scene.blendermcp_hyper3d_api_key = RODIN_FREE_TRIAL_KEY
        context.scene.blendermcp_hyper3d_mode = 'MAIN_SITE'
        self.report({'INFO'}, "API Key set successfully!")
        return {'FINISHED'}

# Operator to start the server
class BLENDERMCP_OT_StartServer(bpy.types.Operator):
    bl_idname = "blendermcp.start_server"
    bl_label = "Connect to Claude"
    bl_description = "Start the BlenderMCP server to connect with Claude"

    def execute(self, context):
        scene = context.scene

        # Create a new server instance
        if not hasattr(bpy.types, "blendermcp_server") or not bpy.types.blendermcp_server:
            bpy.types.blendermcp_server = BlenderMCPServer(port=scene.blendermcp_port)

        # Start the server
        bpy.types.blendermcp_server.start()
        scene.blendermcp_server_running = True

        return {'FINISHED'}

# Operator to stop the server
class BLENDERMCP_OT_StopServer(bpy.types.Operator):
    bl_idname = "blendermcp.stop_server"
    bl_label = "Stop the connection to Claude"
    bl_description = "Stop the connection to Claude"

    def execute(self, context):
        scene = context.scene

        # Stop the server if it exists
        if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
            bpy.types.blendermcp_server.stop()
            del bpy.types.blendermcp_server

        scene.blendermcp_server_running = False

        return {'FINISHED'}

# Operator to open Terms and Conditions
class BLENDERMCP_OT_OpenTerms(bpy.types.Operator):
    bl_idname = "blendermcp.open_terms"
    bl_label = "View Terms and Conditions"
    bl_description = "Open the Terms and Conditions document"

    def execute(self, context):
        # Open the Terms and Conditions on GitHub
        terms_url = "https://github.com/ahujasid/blender-mcp/blob/main/TERMS_AND_CONDITIONS.md"
        try:
            import webbrowser
            webbrowser.open(terms_url)
            self.report({'INFO'}, "Terms and Conditions opened in browser")
        except Exception as e:
            self.report({'ERROR'}, f"Could not open Terms and Conditions: {str(e)}")
        
        return {'FINISHED'}

# Registration functions
def register():
    bpy.types.Scene.blendermcp_port = IntProperty(
        name="Port",
        description="Port for the BlenderMCP server",
        default=9876,
        min=1024,
        max=65535
    )

    bpy.types.Scene.blendermcp_server_running = bpy.props.BoolProperty(
        name="Server Running",
        default=False
    )

    bpy.types.Scene.blendermcp_use_polyhaven = bpy.props.BoolProperty(
        name="Use Poly Haven",
        description="Enable Poly Haven asset integration",
        default=False
    )

    bpy.types.Scene.blendermcp_use_hyper3d = bpy.props.BoolProperty(
        name="Use Hyper3D Rodin",
        description="Enable Hyper3D Rodin generatino integration",
        default=False
    )

    bpy.types.Scene.blendermcp_hyper3d_mode = bpy.props.EnumProperty(
        name="Rodin Mode",
        description="Choose the platform used to call Rodin APIs",
        items=[
            ("MAIN_SITE", "hyper3d.ai", "hyper3d.ai"),
            ("FAL_AI", "fal.ai", "fal.ai"),
        ],
        default="MAIN_SITE"
    )

    bpy.types.Scene.blendermcp_hyper3d_api_key = bpy.props.StringProperty(
        name="Hyper3D API Key",
        subtype="PASSWORD",
        description="API Key provided by Hyper3D",
        default=""
    )

    bpy.types.Scene.blendermcp_use_hunyuan3d = bpy.props.BoolProperty(
        name="Use Hunyuan 3D",
        description="Enable Hunyuan asset integration",
        default=False
    )

    bpy.types.Scene.blendermcp_hunyuan3d_mode = bpy.props.EnumProperty(
        name="Hunyuan3D Mode",
        description="Choose a local or official APIs",
        items=[
            ("LOCAL_API", "local api", "local api"),
            ("OFFICIAL_API", "official api", "official api"),
        ],
        default="LOCAL_API"
    )

    bpy.types.Scene.blendermcp_hunyuan3d_secret_id = bpy.props.StringProperty(
        name="Hunyuan 3D SecretId",
        description="SecretId provided by Hunyuan 3D",
        default=""
    )

    bpy.types.Scene.blendermcp_hunyuan3d_secret_key = bpy.props.StringProperty(
        name="Hunyuan 3D SecretKey",
        subtype="PASSWORD",
        description="SecretKey provided by Hunyuan 3D",
        default=""
    )

    bpy.types.Scene.blendermcp_hunyuan3d_api_url = bpy.props.StringProperty(
        name="API URL",
        description="URL of the Hunyuan 3D API service",
        default="http://localhost:8081"
    )

    bpy.types.Scene.blendermcp_hunyuan3d_octree_resolution = bpy.props.IntProperty(
        name="Octree Resolution",
        description="Octree resolution for the 3D generation",
        default=256,
        min=128,
        max=512,
    )

    bpy.types.Scene.blendermcp_hunyuan3d_num_inference_steps = bpy.props.IntProperty(
        name="Number of Inference Steps",
        description="Number of inference steps for the 3D generation",
        default=20,
        min=20,
        max=50,
    )

    bpy.types.Scene.blendermcp_hunyuan3d_guidance_scale = bpy.props.FloatProperty(
        name="Guidance Scale",
        description="Guidance scale for the 3D generation",
        default=5.5,
        min=1.0,
        max=10.0,
    )

    bpy.types.Scene.blendermcp_hunyuan3d_texture = bpy.props.BoolProperty(
        name="Generate Texture",
        description="Whether to generate texture for the 3D model",
        default=False,
    )
    
    bpy.types.Scene.blendermcp_use_sketchfab = bpy.props.BoolProperty(
        name="Use Sketchfab",
        description="Enable Sketchfab asset integration",
        default=False
    )

    bpy.types.Scene.blendermcp_sketchfab_api_key = bpy.props.StringProperty(
        name="Sketchfab API Key",
        subtype="PASSWORD",
        description="API Key provided by Sketchfab",
        default=""
    )

    # Register preferences class
    bpy.utils.register_class(BLENDERMCP_AddonPreferences)

    bpy.utils.register_class(BLENDERMCP_PT_Panel)
    bpy.utils.register_class(BLENDERMCP_OT_SetFreeTrialHyper3DAPIKey)
    bpy.utils.register_class(BLENDERMCP_OT_StartServer)
    bpy.utils.register_class(BLENDERMCP_OT_StopServer)
    bpy.utils.register_class(BLENDERMCP_OT_OpenTerms)

    print("BlenderMCP addon registered")

def unregister():
    # Stop the server if it's running
    if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
        bpy.types.blendermcp_server.stop()
        del bpy.types.blendermcp_server

    bpy.utils.unregister_class(BLENDERMCP_PT_Panel)
    bpy.utils.unregister_class(BLENDERMCP_OT_SetFreeTrialHyper3DAPIKey)
    bpy.utils.unregister_class(BLENDERMCP_OT_StartServer)
    bpy.utils.unregister_class(BLENDERMCP_OT_StopServer)
    bpy.utils.unregister_class(BLENDERMCP_OT_OpenTerms)
    bpy.utils.unregister_class(BLENDERMCP_AddonPreferences)

    del bpy.types.Scene.blendermcp_port
    del bpy.types.Scene.blendermcp_server_running
    del bpy.types.Scene.blendermcp_use_polyhaven
    del bpy.types.Scene.blendermcp_use_hyper3d
    del bpy.types.Scene.blendermcp_hyper3d_mode
    del bpy.types.Scene.blendermcp_hyper3d_api_key
    del bpy.types.Scene.blendermcp_use_sketchfab
    del bpy.types.Scene.blendermcp_sketchfab_api_key
    del bpy.types.Scene.blendermcp_use_hunyuan3d
    del bpy.types.Scene.blendermcp_hunyuan3d_mode
    del bpy.types.Scene.blendermcp_hunyuan3d_secret_id
    del bpy.types.Scene.blendermcp_hunyuan3d_secret_key
    del bpy.types.Scene.blendermcp_hunyuan3d_api_url
    del bpy.types.Scene.blendermcp_hunyuan3d_octree_resolution
    del bpy.types.Scene.blendermcp_hunyuan3d_num_inference_steps
    del bpy.types.Scene.blendermcp_hunyuan3d_guidance_scale
    del bpy.types.Scene.blendermcp_hunyuan3d_texture

    print("BlenderMCP addon unregistered")

if __name__ == "__main__":
    register()
