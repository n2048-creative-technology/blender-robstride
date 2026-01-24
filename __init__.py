bl_info = {
    "name": "RobStride CAN Controller",
    "author": "N2048",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > RobStride",
    "description": "Scan RobStride nodes over CAN, link to objects, and sync rotations in Run/Learn modes.",
    "category": "System",
}

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
    BoolProperty,
)
import json
import os
import math
import time

# Local module providing CAN communication (stubbed if python-can not available)
from . import robstride_can
from . import deps


# --- Helpers to enforce one controller per object in LEARN mode ---
def _has_learn_conflict(this_node, scene) -> bool:
    """Return True if another node (different node_id) is learning the same object."""
    try:
        obj = getattr(this_node, 'object_ref', None)
        if not obj:
            return False
        this_id = int(getattr(this_node, 'node_id', -1))
        obj_name = getattr(obj, 'name', None)
        for n in getattr(scene, 'robstride_nodes', []):
            try:
                if int(getattr(n, 'node_id', -2)) == this_id:
                    continue  # skip self by ID
            except Exception:
                pass
            n_obj = getattr(n, 'object_ref', None)
            if not n_obj:
                continue
            if getattr(n, 'mode', 'RUN') != 'LEARN':
                continue
            if getattr(n_obj, 'name', None) == obj_name:
                return True
    except Exception:
        pass
    return False


def _on_node_mode_update(self, context):
    # Prevent multiple nodes learning the same object at once
    if getattr(self, 'mode', 'RUN') == 'LEARN':
        scene = getattr(context, 'scene', None) or bpy.context.scene
        if _has_learn_conflict(self, scene):
            # Revert to RUN if conflict detected
            try:
                self.mode = 'RUN'
            except Exception:
                pass


def _on_node_object_update(self, context):
    # If node is already in LEARN and object changes to one under control, revert mode
    if getattr(self, 'mode', 'RUN') == 'LEARN':
        scene = getattr(context, 'scene', None) or bpy.context.scene
        if _has_learn_conflict(self, scene):
            try:
                self.mode = 'RUN'
            except Exception:
                pass


def _remove_simulated_nodes(scene):
    nodes = getattr(scene, 'robstride_nodes', None)
    if nodes is None:
        return
    remove_indices = [i for i, n in enumerate(nodes) if getattr(n, 'is_simulated', False)]
    for i in reversed(remove_indices):
        nodes.remove(i)


def _sync_simulated_nodes(scene, enable: bool):
    if not enable:
        _remove_simulated_nodes(scene)
        return
    nodes = getattr(scene, 'robstride_nodes', None)
    if nodes is None:
        return
    existing = {int(n.node_id): n for n in nodes}
    sim_defs = [
        {"id": 126, "name": "sim node 126"},
        {"id": 127, "name": "sim node 127"},
    ]
    for sim in sim_defs:
        sim_id = int(sim["id"])
        if sim_id in existing:
            if getattr(existing[sim_id], 'is_simulated', False):
                continue
            # Do not overwrite real nodes with same ID
            continue
        n = nodes.add()
        n.node_id = sim_id
        n.name = str(sim["name"])
        n.is_simulated = True
        try:
            _enabled_state[int(sim_id)] = False
        except Exception:
            pass


def _has_simulated_nodes(scene) -> bool:
    try:
        return any(getattr(n, 'is_simulated', False) for n in scene.robstride_nodes)
    except Exception:
        return False


def _is_simulated_node(node) -> bool:
    try:
        return bool(getattr(node, 'is_simulated', False))
    except Exception:
        return False


def _schedule_simulated_sync(scene, enable: bool):
    global _sim_sync_pending
    if _sim_sync_pending:
        return
    _sim_sync_pending = True
    def _run():
        global _sim_sync_pending
        _sim_sync_pending = False
        try:
            _sync_simulated_nodes(scene, enable)
        except Exception:
            pass
        return None
    try:
        bpy.app.timers.register(_run, first_interval=0.0)
    except Exception:
        _run()


def _simulated_value_for_node(node) -> float:
    kind, _axis = _transform_spec(node.transform)
    phase = time.time()
    if kind == "ROT":
        return math.sin(phase) * math.pi
    return math.sin(phase)


def _update_simulated_position(node):
    try:
        node_units = _simulated_value_for_node(node)
        _simulated_pos[int(node.node_id)] = float(node_units)
    except Exception:
        pass


def _on_scene_simulated_update(self, context):
    scene = getattr(context, 'scene', None) or bpy.context.scene
    if robstride_can.manager.is_connected():
        try:
            scene.robstride_show_simulated = False
        except Exception:
            pass
        _schedule_simulated_sync(scene, False)
        return
    _schedule_simulated_sync(scene, bool(getattr(scene, 'robstride_show_simulated', False)))


class RobStrideAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    interface: StringProperty(
        name="CAN Interface",
        description="python-can interface (e.g., robstride, socketcan, kvaser)",
        default="socketcan",
    )
    channel: StringProperty(
        name="Channel",
        description="Interface channel (e.g., can0, CH0)",
        default="can0",
    )
    bitrate: IntProperty(
        name="Baudrate",
        description="Bus bitrate in bit/s",
        default=1000000,
        min=10000,
        soft_max=2000000,
    )
    host_id_low: IntProperty(
        name="Host ID (low byte)",
        description="Low 8 bits of host/master ID for raw protocol (use 0xAA per your working frames)",
        default=0xAA,
        min=0,
        max=255,
    )
    scan_min_id: IntProperty(
        name="Scan Min ID",
        description="Lowest node ID to probe when scanning (raw protocol)",
        default=0,
        min=0,
        max=127,
    )
    scan_max_id: IntProperty(
        name="Scan Max ID",
        description="Highest node ID to probe when scanning (raw protocol)",
        default=127,
        min=1,
        max=127,
    )
    scan_quick: BoolProperty(
        name="Quick Scan",
        description="Probe common IDs only (faster). Disable for full range scan.",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "interface")
        col.prop(self, "channel")
        col.prop(self, "bitrate")
        col.prop(self, "host_id_low")
        # Scan options
        col.prop(self, "scan_quick")
        grid = layout.grid_flow(columns=2, even_columns=True, even_rows=True)
        grid.prop(self, "scan_min_id")
        grid.prop(self, "scan_max_id")


class RobStridenodeNode(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Node")
    node_id: IntProperty(name="ID", default=0, min=0)
    object_ref: PointerProperty(name="Object", type=bpy.types.Object, update=_on_node_object_update)
    is_simulated: BoolProperty(name="Simulated", default=False)
    mode: EnumProperty(
        name="Mode",
        items=[
            ("RUN", "Run", "Send object transform to node"),
            ("LEARN", "Learn", "Read encoder and keyframe object transform"),
        ],
        default="RUN",
        update=_on_node_mode_update,
    )
    transform: EnumProperty(
        name="Transform",
        items=[
            ("ROT_X", "Rotation X", "Use X rotation"),
            ("ROT_Y", "Rotation Y", "Use Y rotation"),
            ("ROT_Z", "Rotation Z", "Use Z rotation"),
            ("LOC_X", "Translation X", "Use X translation"),
            ("LOC_Y", "Translation Y", "Use Y translation"),
            ("LOC_Z", "Translation Z", "Use Z translation"),
        ],
        default="ROT_Z",
    )
    scale: FloatProperty(
        name="Scale",
        description="Radians in/out (device speaks radians). Keep 1.0 unless you need gearing/scaling.",
        default=1.0,
    )
    offset: FloatProperty(
        name="Offset",
        description="Radians offset (additive) if needed. Typically 0.0.",
        default=0.0,
    )


class ROBSTRIDE_OT_scan(bpy.types.Operator):
    bl_idname = "robstride.scan"
    bl_label = "Scan RobStride Nodes"
    bl_description = "Find nodes on the configured CAN bus and populate nodes"
    bl_options = {"REGISTER"}

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences

        # Initialize CAN manager with preferences
        deps.ensure_dependencies()
        robstride_can.manager.configure(
            interface=prefs.interface,
            channel=prefs.channel,
            bitrate=prefs.bitrate,
        )
        # Force raw protocol to match provided scripts
        try:
            robstride_can.manager.set_prefer_vendor(False)
        except Exception:
            pass
        # Match raw protocol host/master low byte with working scripts (default 0xAA)
        try:
            robstride_can.manager._host_addr = int(prefs.host_id_low) & 0xFF  # type: ignore[attr-defined]
        except Exception:
            pass
        # Scan options for raw protocol
        try:
            robstride_can.manager.set_scan_options(
                min_id=int(prefs.scan_min_id), max_id=int(prefs.scan_max_id), quick=bool(prefs.scan_quick)
            )
        except Exception:
            pass
        # Respect simulation toggle; scan should merge sim + real when possible
        connected = robstride_can.manager.is_connected()

        # If not connected, attempt a temporary connection for scanning
        temp_connected = False
        if not connected:
            if robstride_can.manager.connect():
                temp_connected = True
            # If connection fails, continue; scan() may still return known nodes

        found = robstride_can.manager.scan()

        scene = context.scene
        nodes = scene.robstride_nodes

        # Remove nodes that are no longer present
        found_ids = {int(m.get("id", 0)) for m in found}
        remove_indices = [i for i, n in enumerate(nodes) if n.node_id not in found_ids]
        for i in reversed(remove_indices):
            nodes.remove(i)

        # Build a map of existing nodes by ID (after removals)
        existing = {n.node_id: n for n in nodes}

        # Update or add nodes
        for m in found:
            m_id = int(m.get("id", 0))
            m_name = str(m.get("name", f"node {m_id}"))
            if m_id in existing:
                # Keep user-customized name; do not overwrite
                n = existing[m_id]
                if getattr(n, 'is_simulated', False):
                    n.is_simulated = False
            else:
                n = nodes.add()
                n.name = m_name
                n.node_id = m_id
                # Default newly discovered nodes to disabled
                try:
                    _enabled_state[int(m_id)] = False
                except Exception:
                    pass

        if not connected:
            _sync_simulated_nodes(scene, bool(getattr(scene, 'robstride_show_simulated', False)))
        else:
            _remove_simulated_nodes(scene)

        # Disconnect if we connected temporarily just for the scan
        if temp_connected:
            try:
                robstride_can.manager.disconnect()
            except Exception:
                pass

        self.report({'INFO'}, f"Found {len(found)} nodes")
        return {'FINISHED'}


class ROBSTRIDE_OT_connect_toggle(bpy.types.Operator):
    bl_idname = "robstride.connect_toggle"
    bl_label = "Connect/Disconnect"
    bl_description = "Connect or disconnect from the CAN network"
    bl_options = {"REGISTER"}

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        scene = context.scene

        deps.ensure_dependencies()
        robstride_can.manager.configure(
            interface=prefs.interface,
            channel=prefs.channel,
            bitrate=prefs.bitrate,
        )
        try:
            robstride_can.manager.set_prefer_vendor(False)
        except Exception:
            pass
        # Ensure raw protocol host/master low byte matches expected (0xAA)
        try:
            robstride_can.manager._host_addr = int(prefs.host_id_low) & 0xFF  # type: ignore[attr-defined]
        except Exception:
            pass
        # Scan options for raw protocol
        try:
            robstride_can.manager.set_scan_options(
                min_id=int(prefs.scan_min_id), max_id=int(prefs.scan_max_id), quick=bool(prefs.scan_quick)
            )
        except Exception:
            pass

        if robstride_can.manager.is_connected():
            robstride_can.manager.disconnect()
            self.report({'INFO'}, "Disconnected")
            return {'FINISHED'}

        # Connect
        if not robstride_can.manager.connect():
            self.report({'ERROR'}, "Failed to connect")
            return {'CANCELLED'}
        try:
            scene.robstride_show_simulated = False
        except Exception:
            pass

        # After connecting, scan and ensure nodes are added/prepared
        found = robstride_can.manager.scan()
        nodes = scene.robstride_nodes

        # Do not remove on connect; only add/update
        existing = {n.node_id: n for n in nodes}
        for m in found:
            m_id = int(m.get("id", 0))
            m_name = str(m.get("name", f"node {m_id}"))
            if m_id in existing:
                # Keep user-defined name
                n = existing[m_id]
                if getattr(n, 'is_simulated', False):
                    n.is_simulated = False
            else:
                n = nodes.add()
                n.name = m_name
                n.node_id = m_id
                # Default newly discovered nodes to disabled
                try:
                    _enabled_state[int(m_id)] = False
                except Exception:
                    pass
        _remove_simulated_nodes(scene)

        # Prepare canopen nodes where applicable
        for n in nodes:
            robstride_can.manager.prepare_node(n.node_id)

        self.report({'INFO'}, "Connected and prepared nodes")
        return {'FINISHED'}


class ROBSTRIDE_OT_node_enable(bpy.types.Operator):
    bl_idname = "robstride.node_enable"
    bl_label = "Enable"
    bl_description = "Enable the selected node using raw protocol semantics"
    bl_options = {"REGISTER"}

    node_id: IntProperty()

    def execute(self, context):
        # Prevent enabling if node is in LEARN mode; enforce disabled state
        try:
            scene = context.scene
            node = next((n for n in scene.robstride_nodes if int(n.node_id) == int(self.node_id)), None)
        except Exception:
            node = None
        if node and _is_simulated_node(node):
            if node.mode == 'LEARN':
                _enabled_state[int(self.node_id)] = False
                self.report({'INFO'}, "Simulated node in Learn mode: disabled")
                return {'FINISHED'}
            _enabled_state[int(self.node_id)] = True
            self.report({'INFO'}, f"Enabled simulated node {int(self.node_id)}")
            return {'FINISHED'}
        if node and node.mode == 'LEARN':
            prefs = context.preferences.addons[__name__].preferences
            try:
                robstride_can.manager._host_addr = int(prefs.host_id_low) & 0xFF  # type: ignore[attr-defined]
            except Exception:
                pass
            temp = False
            if not robstride_can.manager.is_connected():
                if robstride_can.manager.connect():
                    temp = True
            try:
                robstride_can.manager.enable_node(int(self.node_id), False)
                _enabled_state[int(self.node_id)] = False
                self.report({'INFO'}, "Node in Learn mode: motor disabled")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Disable in Learn failed: {e}")
                return {'CANCELLED'}
            finally:
                if temp:
                    try:
                        robstride_can.manager.disconnect()
                    except Exception:
                        pass

        prefs = context.preferences.addons[__name__].preferences
        # Ensure host low byte matches scripts and connect if needed
        try:
            robstride_can.manager._host_addr = int(prefs.host_id_low) & 0xFF  # type: ignore[attr-defined]
        except Exception:
            pass
        temp = False
        if not robstride_can.manager.is_connected():
            if robstride_can.manager.connect():
                temp = True
        try:
            robstride_can.manager.enable_node(int(self.node_id), True)
            _enabled_state[int(self.node_id)] = True
            self.report({'INFO'}, f"Enabled node {int(self.node_id)}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Enable failed: {e}")
            return {'CANCELLED'}
        finally:
            if temp:
                try:
                    robstride_can.manager.disconnect()
                except Exception:
                    pass


class ROBSTRIDE_OT_node_disable(bpy.types.Operator):
    bl_idname = "robstride.node_disable"
    bl_label = "Disable"
    bl_description = "Disable/STOP the selected node using raw protocol semantics"
    bl_options = {"REGISTER"}

    node_id: IntProperty()

    def execute(self, context):
        try:
            scene = context.scene
            node = next((n for n in scene.robstride_nodes if int(n.node_id) == int(self.node_id)), None)
        except Exception:
            node = None
        if node and _is_simulated_node(node):
            _enabled_state[int(self.node_id)] = False
            self.report({'INFO'}, f"Disabled simulated node {int(self.node_id)}")
            return {'FINISHED'}
        prefs = context.preferences.addons[__name__].preferences
        try:
            robstride_can.manager._host_addr = int(prefs.host_id_low) & 0xFF  # type: ignore[attr-defined]
        except Exception:
            pass
        temp = False
        if not robstride_can.manager.is_connected():
            if robstride_can.manager.connect():
                temp = True
        try:
            robstride_can.manager.enable_node(int(self.node_id), False)
            _enabled_state[int(self.node_id)] = False
            self.report({'INFO'}, f"Disabled node {int(self.node_id)}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Disable failed: {e}")
            return {'CANCELLED'}
        finally:
            if temp:
                try:
                    robstride_can.manager.disconnect()
                except Exception:
                    pass


class ROBSTRIDE_OT_enable_all(bpy.types.Operator):
    bl_idname = "robstride.enable_all"
    bl_label = "Enable All"
    bl_description = "Enable all nodes currently in Run mode (ignores Learn mode)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        sim_only = True
        for n in scene.robstride_nodes:
            if not _is_simulated_node(n):
                sim_only = False
                break
        if sim_only:
            count = 0
            for n in scene.robstride_nodes:
                if n.mode != 'RUN':
                    continue
                _enabled_state[int(n.node_id)] = True
                count += 1
            self.report({'INFO'}, f"Enabled {count} simulated RUN nodes")
            return {'FINISHED'}
        prefs = context.preferences.addons[__name__].preferences
        # Ensure host low byte matches scripts and connect if needed
        try:
            robstride_can.manager._host_addr = int(prefs.host_id_low) & 0xFF  # type: ignore[attr-defined]
        except Exception:
            pass
        temp = False
        if not robstride_can.manager.is_connected():
            if robstride_can.manager.connect():
                temp = True
        count = 0
        try:
            for n in scene.robstride_nodes:
                try:
                    if n.mode != 'RUN':
                        continue
                    robstride_can.manager.enable_node(int(n.node_id), True)
                    _enabled_state[int(n.node_id)] = True
                    count += 1
                except Exception:
                    # Continue enabling others even if one fails
                    pass
            self.report({'INFO'}, f"Enabled {count} RUN nodes")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Enable All failed: {e}")
            return {'CANCELLED'}
        finally:
            if temp:
                try:
                    robstride_can.manager.disconnect()
                except Exception:
                    pass


class ROBSTRIDE_OT_disable_all(bpy.types.Operator):
    bl_idname = "robstride.disable_all"
    bl_label = "Disable All"
    bl_description = "Disable all nodes currently in Run mode (ignores Learn mode)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        sim_only = True
        for n in scene.robstride_nodes:
            if not _is_simulated_node(n):
                sim_only = False
                break
        if sim_only:
            count = 0
            for n in scene.robstride_nodes:
                if n.mode != 'RUN':
                    continue
                _enabled_state[int(n.node_id)] = False
                count += 1
            self.report({'INFO'}, f"Disabled {count} simulated RUN nodes")
            return {'FINISHED'}
        prefs = context.preferences.addons[__name__].preferences
        try:
            robstride_can.manager._host_addr = int(prefs.host_id_low) & 0xFF  # type: ignore[attr-defined]
        except Exception:
            pass
        temp = False
        if not robstride_can.manager.is_connected():
            if robstride_can.manager.connect():
                temp = True
        count = 0
        try:
            for n in scene.robstride_nodes:
                try:
                    if n.mode != 'RUN':
                        continue
                    robstride_can.manager.enable_node(int(n.node_id), False)
                    _enabled_state[int(n.node_id)] = False
                    count += 1
                except Exception:
                    pass
            self.report({'INFO'}, f"Disabled {count} RUN nodes")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Disable All failed: {e}")
            return {'CANCELLED'}
        finally:
            if temp:
                try:
                    robstride_can.manager.disconnect()
                except Exception:
                    pass

class ROBSTRIDE_OT_save_config(bpy.types.Operator):
    bl_idname = "robstride.save_config"
    bl_label = "Save Config"
    bl_description = "Save CAN and node node configuration to a JSON file"
    bl_options = {"REGISTER"}

    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = os.path.join(
                os.path.expanduser("~"),
                "robstride_config.json",
            )
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        scene = context.scene
        prefs = context.preferences.addons[__name__].preferences

        data = {
            "can": {
                "interface": prefs.interface,
                "channel": prefs.channel,
                "bitrate": int(prefs.bitrate),
            },
            "nodes": [],
        }

        for node in scene.robstride_nodes:
            if getattr(node, 'is_simulated', False):
                continue
            data["nodes"].append({
                "id": int(node.node_id),
                "name": node.name,
                "object": node.object_ref.name if node.object_ref else "",
                "mode": node.mode,
                "transform": node.transform,
                "scale": float(node.scale),
                "offset": float(node.offset),
            })

        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Saved config: {self.filepath}")
        return {'FINISHED'}


class ROBSTRIDE_OT_load_config(bpy.types.Operator):
    bl_idname = "robstride.load_config"
    bl_label = "Load Config"
    bl_description = "Load CAN and node node configuration from a JSON file"
    bl_options = {"REGISTER"}

    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        scene = context.scene
        prefs = context.preferences.addons[__name__].preferences

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load: {e}")
            return {'CANCELLED'}

        # Apply CAN settings
        can_data = data.get("can", {})
        prefs.interface = str(can_data.get("interface", prefs.interface))
        prefs.channel = str(can_data.get("channel", prefs.channel))
        prefs.bitrate = int(can_data.get("bitrate", prefs.bitrate))

        # Replace nodes with loaded data
        nodes = scene.robstride_nodes
        nodes.clear()

        for m in data.get("nodes", []):
            n = nodes.add()
            n.node_id = int(m.get("id", 0))
            n.name = str(m.get("name", f"node {n.node_id}"))
            n.is_simulated = False
            obj_name = str(m.get("object", ""))
            n.object_ref = bpy.data.objects.get(obj_name) if obj_name else None
            mode = str(m.get("mode", "RUN"))
            n.mode = mode if mode in {"RUN", "LEARN"} else "RUN"
            transform = str(m.get("transform", "ROT_Z"))
            if transform in {"ROT_X", "ROT_Y", "ROT_Z", "LOC_X", "LOC_Y", "LOC_Z"}:
                n.transform = transform
            else:
                n.transform = "ROT_Z"
            n.scale = float(m.get("scale", 1.0))
            n.offset = float(m.get("offset", 0.0))
            # Default loaded nodes to disabled until user enables explicitly
            try:
                _enabled_state[int(n.node_id)] = False
            except Exception:
                pass

        self.report({'INFO'}, f"Loaded config: {self.filepath}")
        return {'FINISHED'}


class ROBSTRIDE_OT_install_deps(bpy.types.Operator):
    bl_idname = "robstride.install_deps"
    bl_label = "Install Deps"
    bl_description = "Install python-can, canopen, and robstride from bundled wheels"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, msg = deps.ensure_dependencies()
        if ok:
            self.report({'INFO'}, f"Dependencies ready ({msg})")
            return {'FINISHED'}
        self.report({'ERROR'}, f"Dependencies not ready: {msg}")
        return {'CANCELLED'}


class ROBSTRIDE_PT_panel(bpy.types.Panel):
    bl_label = "RobStride"
    bl_idname = "ROBSTRIDE_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RobStride'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # CAN settings box
        prefs = context.preferences.addons[__name__].preferences
        can_box = layout.box()
        can_box.label(text="CAN Settings", icon='MOD_SIMPLIFY')
        col = can_box.column(align=True)
        # Hide interface in UI per request
        col.prop(prefs, "interface")
        col.prop(prefs, "channel")
        col.prop(prefs, "bitrate")
        # Simulation removed: real hardware only
        # Connection status only
        net_row = can_box.row(align=True)
        connected = robstride_can.manager.is_connected()
        net_icon = 'LINKED' if connected else 'UNLINKED'
        net_row.label(text=f"Network: {'Connected' if connected else 'Disconnected'}", icon=net_icon)
        if not connected:
            can_box.prop(scene, "robstride_show_simulated")
            if bool(getattr(scene, "robstride_show_simulated", False)) and not _has_simulated_nodes(scene):
                _schedule_simulated_sync(scene, True)

        row = can_box.row(align=True)
        row.operator(ROBSTRIDE_OT_scan.bl_idname, icon='VIEWZOOM', text="Scan")
        conn_icon = 'UNLINKED' if robstride_can.manager.is_connected() else 'LINKED'
        row.operator("robstride.connect_toggle", icon=conn_icon, text=("Disconnect" if robstride_can.manager.is_connected() else "Connect"))
        row.operator("robstride.save_config", icon='FILE_TICK', text="Save")
        row.operator("robstride.load_config", icon='FILE_FOLDER', text="Load")
        # Batch enable/disable for RUN-mode nodes
        row2 = can_box.row(align=True)
        row2.operator("robstride.enable_all", icon='PLAY', text="Enable All")
        row2.operator("robstride.disable_all", icon='PAUSE', text="Disable All")
        # Only show Install Deps if not installed yet (check without side-effects)
        try:
            has_can, has_canopen, _has_rs = deps.have_modules()
            deps_ready = bool(has_can and has_canopen)
        except Exception:
            deps_ready = False
        if not deps_ready:
            row.operator("robstride.install_deps", icon='IMPORT', text="Install Deps")

        if len(scene.robstride_nodes) == 0:
            layout.label(text="No nodes. Click Scan.")
            return

        # Precompute which objects are controlled in LEARN mode
        learn_by_object = {}
        try:
            for n in scene.robstride_nodes:
                if n.object_ref and n.mode == 'LEARN':
                    learn_by_object.setdefault(n.object_ref.name, []).append(n)
        except Exception:
            learn_by_object = {}

        for idx, node in enumerate(scene.robstride_nodes):
            box = layout.box()
            header = box.row(align=True)
            header.prop(node, "name", text="Name")
            online = robstride_can.manager.node_status(node.node_id)
            online_icon = 'CHECKMARK' if online else 'ERROR'
            header.label(text=f"ID {node.node_id}", icon='DRIVER')
            if getattr(node, 'is_simulated', False):
                header.label(text="Simulated", icon='GHOST_ENABLED')
            else:
                header.label(text=("Online" if online else "Offline"), icon=online_icon)
            # Show enabled/disabled state indicator (derived from tracked state and mode)
            try:
                en_state = _enabled_state.get(int(node.node_id))
            except Exception:
                en_state = None
            if en_state is None:
                # Default to disabled when unknown
                en_state = False
            en_icon = 'PLAY' if (en_state and node.mode != 'LEARN') else 'PAUSE'
            en_text = 'Enabled' if (en_state and node.mode != 'LEARN') else 'Disabled'
            header.label(text=en_text, icon=en_icon)

            col = box.column(align=True)
            col.prop(node, "object_ref")
            col.prop(node, "transform")
            # Draw RUN/LEARN as separate toggles so we can disable LEARN per-object
            row_mode = col.row(align=True)
            row_mode.prop_enum(node, "mode", "RUN")
            sub_learn = row_mode.row(align=True)
            # Disable LEARN if another node already controls the same object
            learn_conflict = False
            try:
                if node.object_ref and node.object_ref.name in learn_by_object:
                    controllers = learn_by_object[node.object_ref.name]
                    # treat as conflict if any controller has a different node_id
                    learn_conflict = any(int(getattr(c, 'node_id', -1)) != int(node.node_id) for c in controllers)
            except Exception:
                learn_conflict = False
            sub_learn.enabled = (not learn_conflict) or (node.mode == 'LEARN')
            sub_learn.prop_enum(node, "mode", "LEARN")

            # Simple raw control buttons based on enable.py/disable.py/move.py
            row_ctl = box.row(align=True)
            sub_en = row_ctl.row(align=True)
            sub_en.enabled = (node.mode != 'LEARN')
            # Highlight Enable/Disable depending on tracked enabled state
            try:
                en_state = _enabled_state.get(int(node.node_id))
            except Exception:
                en_state = None
            if en_state is None:
                # Default to disabled until explicitly enabled
                en_state = False
            is_enabled_ui = bool(en_state and node.mode != 'LEARN')
            is_disabled_ui = not is_enabled_ui
            op_en = sub_en.operator(ROBSTRIDE_OT_node_enable.bl_idname, text="Enable", icon='PLAY', depress=is_enabled_ui)
            op_en.node_id = node.node_id
            op_dis = row_ctl.operator(ROBSTRIDE_OT_node_disable.bl_idname, text="Disable", icon='PAUSE', depress=is_disabled_ui)
            op_dis.node_id = node.node_id

            grid = box.grid_flow(columns=2, even_columns=True, even_rows=True)
            grid.prop(node, "scale")
            grid.prop(node, "offset")

            # Show constraint limits and whether clamping is currently active
            try:
                if node.object_ref:
                    kind, axis = _transform_spec(node.transform)
                    if kind != "ROT":
                        continue
                    axis_label = ("X", "Y", "Z")[axis]
                    try:
                        limits = _get_rot_limits(node.object_ref, axis)
                    except Exception:
                        limits = None
                    if limits:
                        zmin, zmax = limits
                        lim_row = box.row(align=True)
                        lim_row.label(text=f"Limits {axis_label}: {_fmt_deg(zmin)} .. {_fmt_deg(zmax)}", icon='CON_ROTLIMIT')

                        # RUN direction: check current intended object Z vs limits
                        if node.mode == 'RUN':
                            try:
                                z_eval = _get_evaluated_transform(node.object_ref, kind, axis)
                                if z_eval is None:
                                    z_eval = float(node.object_ref.rotation_euler[axis])
                                if not (zmin <= float(z_eval) <= zmax):
                                    clamp_row = box.row(align=True)
                                    side = 'below min' if float(z_eval) < zmin else 'above max'
                                    clamp_row.label(text=f"RUN clamping active ({side})", icon='ERROR')
                            except Exception:
                                pass

                        # LEARN direction: check last cached motor-derived Z vs limits
                        if node.mode == 'LEARN':
                            try:
                                pos = robstride_can.manager.get_cached_position(node.node_id)
                                if pos is not None:
                                    z_raw = (float(pos) - float(node.offset)) / float(node.scale) if float(node.scale) != 0.0 else 0.0
                                    if not (zmin <= z_raw <= zmax):
                                        clamp_row = box.row(align=True)
                                        side = 'below min' if z_raw < zmin else 'above max'
                                        clamp_row.label(text=f"LEARN clamping active ({side})", icon='ERROR')
                            except Exception:
                                pass
            except Exception:
                # Ensure one bad node doesn't break the panel drawing
                pass


# Cache last-sent outputs to reduce bus traffic
_last_out = {}
_last_mode = {}
_enabled_state = {}
_simulated_pos = {}
_sim_sync_pending = False

# Continuous Z unwrapping per node_id
_unwrap_prev = {}
_unwrap_accum = {}


def _unwrap_update(node_id: int, angle_rad: float) -> float:
    """Return a continuous (unwrapped) Z angle for the given node.
    Stores state per node_id to avoid truncation to [-pi, pi].
    """
    try:
        key = int(node_id)
    except Exception:
        key = node_id
    prev = _unwrap_prev.get(key)
    if prev is None:
        _unwrap_prev[key] = float(angle_rad)
        _unwrap_accum[key] = float(angle_rad)
        return float(angle_rad)
    # Minimal signed delta across wrap boundary
    diff = float(angle_rad) - float(prev)
    twopi = 2.0 * math.pi
    diff = (diff + math.pi) % twopi - math.pi
    accum = float(_unwrap_accum.get(key, 0.0)) + diff
    _unwrap_prev[key] = float(angle_rad)
    _unwrap_accum[key] = float(accum)
    return float(accum)


def _unwrap_reset(node_id: int, angle_rad: float | None = None) -> None:
    """Reset unwrapping state for a node, optionally to a specific angle."""
    try:
        key = int(node_id)
    except Exception:
        key = node_id
    if angle_rad is None:
        _unwrap_prev.pop(key, None)
        _unwrap_accum.pop(key, None)
        return
    _unwrap_prev[key] = float(angle_rad)
    _unwrap_accum[key] = float(angle_rad)


def _fmt_deg(val: float) -> str:
    """Format radians as degrees, handling infinities gracefully for UI."""
    try:
        d = math.degrees(float(val))
        if math.isfinite(d):
            return f"{d:.1f}°"
        return "+∞" if d > 0 else "-∞" if d < 0 else "nan"
    except Exception:
        return "?"


def _replace_transform_keyframe(obj, data_path, index, frame):
    try:
        ad = obj.animation_data_create()
        if ad.action is None:
            ad.action = bpy.data.actions.new(name=f"{obj.name}Action")
    except Exception:
        ad = getattr(obj, 'animation_data', None)
    if ad and ad.action:
        for fc in _iter_action_fcurves(ad.action):
            if fc.data_path == data_path and fc.array_index == index:
                # Remove any keyframe at the current frame so the new one takes priority
                remove = [kp for kp in fc.keyframe_points if abs(kp.co.x - frame) < 1e-5]
                for kp in remove:
                    fc.keyframe_points.remove(kp)
                fc.update()
                break
    # Insert the new keyframe for the selected transform at this frame
    try:
        obj.keyframe_insert(data_path=data_path, index=index, frame=frame)
    except Exception:
        obj.keyframe_insert(data_path=data_path, index=index)


def _get_anim_value(obj, data_path, index, frame):
    ad = getattr(obj, 'animation_data', None)
    if not (ad and ad.action):
        return None
    for fc in _iter_action_fcurves(ad.action):
        if fc.data_path == data_path and fc.array_index == index:
            try:
                return float(fc.evaluate(frame))
            except Exception:
                return None
    return None


def _iter_action_fcurves(action):
    """Yield fcurves from an Action across Blender versions."""
    try:
        fcurves = getattr(action, "fcurves", None)
        if fcurves is not None:
            for fc in fcurves:
                yield fc
            return
    except Exception:
        pass
    try:
        curves = getattr(action, "curves", None)
        if curves is not None:
            for fc in curves:
                yield fc
            return
    except Exception:
        pass
    try:
        layers = getattr(action, "layers", None)
        if layers:
            for layer in layers:
                strips = getattr(layer, "strips", None)
                if not strips:
                    continue
                for strip in strips:
                    bag = getattr(strip, "channelbag", None)
                    if bag is None:
                        continue
                    fcurves = getattr(bag, "fcurves", None)
                    if not fcurves:
                        continue
                    for fc in fcurves:
                        yield fc
    except Exception:
        pass


def _is_animation_playing() -> bool:
    try:
        wm = bpy.context.window_manager
        for win in wm.windows:
            scr = getattr(win, 'screen', None)
            if scr and getattr(scr, 'is_animation_playing', False):
                return True
    except Exception:
        pass
    return False


def _auto_keying_enabled(scene=None) -> bool:
    try:
        if scene is None:
            scene = bpy.context.scene
        ts = getattr(scene, 'tool_settings', None)
        return bool(getattr(ts, 'use_keyframe_insert_auto', False))
    except Exception:
        return False


def _transform_spec(transform: str):
    if transform == "ROT_X":
        return "ROT", 0
    if transform == "ROT_Y":
        return "ROT", 1
    if transform == "ROT_Z":
        return "ROT", 2
    if transform == "LOC_X":
        return "LOC", 0
    if transform == "LOC_Y":
        return "LOC", 1
    if transform == "LOC_Z":
        return "LOC", 2
    return "ROT", 2


def _transform_data_path(kind: str) -> str:
    return "rotation_euler" if kind == "ROT" else "location"


def _get_evaluated_transform(obj, kind, axis, depsgraph=None):
    """Return object's evaluated transform value for the given kind/axis."""
    try:
        if depsgraph is None:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        if kind == "ROT":
            rot_mode = getattr(obj, 'rotation_mode', 'XYZ')
            try:
                return float(obj_eval.matrix_local.to_euler(rot_mode)[axis])
            except Exception:
                return float(obj_eval.rotation_euler[axis])
        # LOC
        try:
            return float(obj_eval.matrix_local.to_translation()[axis])
        except Exception:
            return float(obj_eval.location[axis])
    except Exception:
        return None


# Lightweight timer to update LEARN mode while not playing
_timer_enabled = False
_learn_enforced = set()


def _get_rot_limits(obj, axis):
    """Return (min, max) in radians from active Limit Rotation constraints for axis."""
    try:
        cons = getattr(obj, 'constraints', [])
    except Exception:
        cons = []
    min_v = None
    max_v = None
    for c in cons:
        try:
            if getattr(c, 'type', '') != 'LIMIT_ROTATION':
                continue
            use_key = ("use_limit_x", "use_limit_y", "use_limit_z")[axis]
            if not bool(getattr(c, use_key, False)):
                continue
            if bool(getattr(c, 'mute', False)):
                continue
            if float(getattr(c, 'influence', 1.0)) <= 0.0:
                continue
            min_key = ("min_x", "min_y", "min_z")[axis]
            max_key = ("max_x", "max_y", "max_z")[axis]
            cmin = float(getattr(c, min_key, float('-inf')))
            cmax = float(getattr(c, max_key, float('inf')))
            min_v = cmin if min_v is None else max(min_v, cmin)
            max_v = cmax if max_v is None else min(max_v, cmax)
        except Exception:
            # Ignore malformed constraints; continue intersecting others
            pass
    if min_v is None and max_v is None:
        return None
    # If limits are inverted due to user input, normalize by swapping
    if (min_v is not None) and (max_v is not None) and (min_v > max_v):
        min_v, max_v = max_v, min_v
    return (
        (min_v if min_v is not None else float('-inf')),
        (max_v if max_v is not None else float('inf')),
    )


def _clamp_rot_to_limits(obj, axis, rad_val):
    """Clamp rad_val (radians) to any Limit Rotation constraints on axis."""
    limits = _get_rot_limits(obj, axis)
    if not limits:
        return rad_val
    vmin, vmax = limits
    if rad_val < vmin:
        return vmin
    if rad_val > vmax:
        return vmax
    return rad_val


def _robstride_learn_timer():
    global _timer_enabled
    global _learn_enforced
    if not _timer_enabled:
        return None
    playing = _is_animation_playing()

    try:
        scene = bpy.context.scene
    except Exception:
        return 0.25
    if not robstride_can.manager.is_connected():
        if bool(getattr(scene, 'robstride_show_simulated', False)):
            if not _has_simulated_nodes(scene):
                _sync_simulated_nodes(scene, True)
        else:
            _remove_simulated_nodes(scene)

    # Skip if not connected
    if not robstride_can.manager.is_connected():
        if not _has_simulated_nodes(scene):
            return 0.25

    # During playback, drive RUN updates and still allow LEARN keyframing
    if playing:
        try:
            for node in scene.robstride_nodes:
                if node.mode != 'RUN' or not node.object_ref:
                    continue
                enabled = _enabled_state.get(int(node.node_id))
                if enabled is not True:
                    continue
                obj = node.object_ref
                kind, axis = _transform_spec(node.transform)
                val_eval = _get_evaluated_transform(obj, kind, axis)
                if val_eval is None:
                    try:
                        if kind == "ROT":
                            val_eval = float(obj.rotation_euler[axis])
                        else:
                            val_eval = float(obj.location[axis])
                    except Exception:
                        continue
                if kind == "ROT":
                    val_eval = _unwrap_update(int(node.node_id), float(val_eval))
                    val_eval = _clamp_rot_to_limits(obj, axis, float(val_eval))
                node_units = node.scale * float(val_eval) + node.offset
                prev = _last_out.get(int(node.node_id))
                if prev is None or abs(prev - node_units) > 1e-6:
                    if _is_simulated_node(node):
                        _simulated_pos[int(node.node_id)] = node_units
                        _last_out[int(node.node_id)] = node_units
                    else:
                        try:
                            robstride_can.manager.send_position(int(node.node_id), node_units)
                            _last_out[int(node.node_id)] = node_units
                        except Exception:
                            pass
        except Exception:
            pass

        # LEARN updates + keyframing during playback
        try:
            seen_by_obj = {}
            for n in scene.robstride_nodes:
                if not (n.object_ref and n.mode == 'LEARN'):
                    continue
                key = n.object_ref.name
                if key not in seen_by_obj:
                    seen_by_obj[key] = int(getattr(n, 'node_id', -1))
                else:
                    if int(getattr(n, 'node_id', -1)) != seen_by_obj[key]:
                        try:
                            n.mode = 'RUN'
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            for node in scene.robstride_nodes:
                if node.mode == 'LEARN':
                    if node.node_id not in _learn_enforced:
                        if not _is_simulated_node(node):
                            try:
                                robstride_can.manager.enable_node(int(node.node_id), False)
                            except Exception:
                                pass
                        _learn_enforced.add(node.node_id)
                else:
                    if node.node_id in _learn_enforced:
                        _learn_enforced.discard(node.node_id)
                if node.mode != 'LEARN' or not node.object_ref:
                    continue
                if not _is_simulated_node(node):
                    robstride_can.manager.request_read(node.node_id)
        except Exception:
            pass

        try:
            for node in scene.robstride_nodes:
                if node.mode != 'LEARN' or not node.object_ref:
                    continue
                obj = node.object_ref
                if _is_simulated_node(node):
                    _update_simulated_position(node)
                    pos = _simulated_pos.get(int(node.node_id))
                else:
                    pos = robstride_can.manager.get_cached_position(node.node_id)
                if pos is None:
                    continue
                kind, axis = _transform_spec(node.transform)
                val_raw = (pos - node.offset) / node.scale if node.scale != 0.0 else 0.0
                if kind == "ROT":
                    val_raw = _clamp_rot_to_limits(obj, axis, float(val_raw))
                try:
                    if kind == "ROT":
                        obj.rotation_euler[axis] = float(val_raw)
                    else:
                        obj.location[axis] = float(val_raw)
                    if _auto_keying_enabled(scene):
                        data_path = _transform_data_path(kind)
                        _replace_transform_keyframe(obj, data_path, axis, scene.frame_current)
                except Exception:
                    pass
        except Exception:
            pass

        return 0.02

    # Resolve conflicts: only one LEARN controller per object
    try:
        seen_by_obj = {}
        for n in scene.robstride_nodes:
            if not (n.object_ref and n.mode == 'LEARN'):
                continue
            key = n.object_ref.name
            # Keep the first controller per object; revert others
            if key not in seen_by_obj:
                seen_by_obj[key] = int(getattr(n, 'node_id', -1))
            else:
                if int(getattr(n, 'node_id', -1)) != seen_by_obj[key]:
                    try:
                        n.mode = 'RUN'
                    except Exception:
                        pass
    except Exception:
        pass

    # Ensure motors are disabled in LEARN and request reads for LEARN nodes
    try:
        for node in scene.robstride_nodes:
            if node.mode == 'LEARN':
                if node.node_id not in _learn_enforced:
                    if not _is_simulated_node(node):
                        try:
                            robstride_can.manager.enable_node(int(node.node_id), False)
                        except Exception:
                            pass
                    _learn_enforced.add(node.node_id)
            else:
                if node.node_id in _learn_enforced:
                    _learn_enforced.discard(node.node_id)
            if node.mode != 'LEARN' or not node.object_ref:
                continue
            if not _is_simulated_node(node):
                robstride_can.manager.request_read(node.node_id)
    except Exception:
        pass

    try:
        for node in scene.robstride_nodes:
            if node.mode != 'LEARN' or not node.object_ref:
                continue
            obj = node.object_ref
            if _is_simulated_node(node):
                _update_simulated_position(node)
                pos = _simulated_pos.get(int(node.node_id))
            else:
                pos = robstride_can.manager.get_cached_position(node.node_id)
            if pos is None:
                continue
            kind, axis = _transform_spec(node.transform)
            val_raw = (pos - node.offset) / node.scale if node.scale != 0.0 else 0.0
            if kind == "ROT":
                val_raw = _clamp_rot_to_limits(obj, axis, float(val_raw))
            try:
                if kind == "ROT":
                    obj.rotation_euler[axis] = float(val_raw)
                else:
                    obj.location[axis] = float(val_raw)
                if _auto_keying_enabled(scene):
                    data_path = _transform_data_path(kind)
                    _replace_transform_keyframe(obj, data_path, axis, scene.frame_current)
            except Exception:
                pass
    except Exception:
        pass

    # RUN mode realtime: push current Z to enabled motors when idle
    try:
        for node in scene.robstride_nodes:
            if node.mode != 'RUN' or not node.object_ref:
                continue
            enabled = _enabled_state.get(int(node.node_id))
            if enabled is not True:
                continue
            obj = node.object_ref
            kind, axis = _transform_spec(node.transform)
            # Prefer evaluated value (post-constraints); fallback to raw property
            val_eval = _get_evaluated_transform(obj, kind, axis)
            if val_eval is None:
                try:
                    if kind == "ROT":
                        val_eval = float(obj.rotation_euler[axis])
                    else:
                        val_eval = float(obj.location[axis])
                except Exception:
                    continue

            if kind == "ROT":
                # Unwrap first for continuity across Euler wrap, then clamp to limits
                val_eval = _unwrap_update(int(node.node_id), float(val_eval))
                val_eval = _clamp_rot_to_limits(obj, axis, float(val_eval))
            node_units = node.scale * float(val_eval) + node.offset
            prev = _last_out.get(int(node.node_id))
            if prev is None or abs(prev - node_units) > 1e-6:
                if _is_simulated_node(node):
                    _simulated_pos[int(node.node_id)] = node_units
                    _last_out[int(node.node_id)] = node_units
                else:
                    try:
                        robstride_can.manager.send_position(int(node.node_id), node_units)
                        _last_out[int(node.node_id)] = node_units
                    except Exception:
                        pass
    except Exception:
        pass

    # Poll frequently for snappy updates while idle
    return 0.05


# Simulation removed: no-op


@persistent
def robstride_sync_handler(scene,depsgraph=None):
    # Run on every frame change; avoids relying on context.screen in handlers

    # Keep host ID (low byte) synced from preferences so raw frames match scripts
    try:
        prefs = bpy.context.preferences.addons[__name__].preferences
        try:
            robstride_can.manager.set_prefer_vendor(False)
        except Exception:
            pass
        robstride_can.manager._host_addr = int(getattr(prefs, 'host_id_low', 0xAA)) & 0xFF  # type: ignore[attr-defined]
    except Exception:
        pass

    # If not connected, try to connect so RUN mode can drive motors
    try:
        if not robstride_can.manager.is_connected():
            try:
                if bool(getattr(scene, 'robstride_show_simulated', False)):
                    pass
                else:
                    robstride_can.manager.connect()
            except Exception:
                robstride_can.manager.connect()
        else:
            try:
                if bool(getattr(scene, 'robstride_show_simulated', False)):
                    scene.robstride_show_simulated = False
            except Exception:
                pass
            _remove_simulated_nodes(scene)
    except Exception:
        pass

    for node in scene.robstride_nodes:
        if not node.object_ref:
            continue

        obj = node.object_ref
        node_id = node.node_id
        kind, axis = _transform_spec(node.transform)
        data_path = _transform_data_path(kind)

        # Skip if not connected and not simulated
        if not robstride_can.manager.is_connected() and not _is_simulated_node(node):
            continue

        # PID parameters removed; no PID updates sent

        # Handle mode transitions for safe enable/disable
        prev_mode = _last_mode.get(node_id)
        if prev_mode != node.mode:
            try:
                if node.mode == 'LEARN':
                    if not _is_simulated_node(node):
                        robstride_can.manager.enable_node(node_id, False)
                    _enabled_state[node_id] = False
                    if kind == "ROT":
                        # Ensure object uses Euler so rotation is keyframable and visible
                        try:
                            obj.rotation_mode = 'XYZ'
                        except Exception:
                            pass
                        # Reset unwrapping when entering LEARN
                        try:
                            _unwrap_reset(node_id)
                        except Exception:
                            pass
                elif node.mode == 'RUN':
                    # Do not auto-enable on entering RUN; default remains disabled
                    if kind == "ROT":
                        # Initialize unwrapping at current evaluated angle to avoid jumps
                        try:
                            val_eval = _get_evaluated_transform(obj, kind, axis, depsgraph)
                            if val_eval is None:
                                val_eval = float(obj.rotation_euler[axis])
                            _unwrap_reset(node_id, float(val_eval))
                        except Exception:
                            pass
            except Exception:
                pass
            _last_mode[node_id] = node.mode

        if node.mode == 'RUN':
            # Use recorded animation (keyframes) if present, else current property
            val_from_anim = _get_anim_value(obj, data_path, axis, scene.frame_current)
            if _is_animation_playing() and val_from_anim is not None:
                val_eval = float(val_from_anim)
            else:
                # Prefer evaluated value (post-constraints). If unavailable, use animated/raw.
                val_eval = _get_evaluated_transform(obj, kind, axis, depsgraph)
                if val_eval is None:
                    try:
                        if val_from_anim is not None:
                            val_eval = float(val_from_anim)
                        else:
                            val_eval = float(obj.rotation_euler[axis] if kind == "ROT" else obj.location[axis])
                    except Exception:
                        val_eval = float(obj.rotation_euler[axis] if kind == "ROT" else obj.location[axis])
            if kind == "ROT":
                # Unwrap first for continuity across Euler wrap, then clamp to limits
                val_eval = _unwrap_update(int(node_id), float(val_eval))
                val_eval = _clamp_rot_to_limits(obj, axis, float(val_eval))
            node_units = node.scale * float(val_eval) + node.offset

            # Send synchronously per frame to mirror move.py timing
            enabled = _enabled_state.get(int(node_id))
            if enabled is True:
                if _is_simulated_node(node):
                    _simulated_pos[int(node_id)] = node_units
                else:
                    try:
                        robstride_can.manager.send_position(node_id, node_units)
                    except Exception:
                        pass

        elif node.mode == 'LEARN':
            # Non-blocking: request a read and use last cached value if available
            if _is_simulated_node(node):
                _update_simulated_position(node)
                pos = _simulated_pos.get(int(node_id))
            else:
                robstride_can.manager.request_read(node_id)
                pos = robstride_can.manager.get_cached_position(node_id)
            if pos is None:
                # Skip this frame if not ready to avoid blocking and FPS drops
                continue

            # node units -> value
            val_raw = (pos - node.offset) / node.scale if node.scale != 0.0 else 0.0
            if kind == "ROT":
                val_raw = _clamp_rot_to_limits(obj, axis, float(val_raw))
                obj.rotation_euler[axis] = float(val_raw)
            else:
                obj.location[axis] = float(val_raw)

            # Keyframe if auto keying is enabled
            if _auto_keying_enabled(scene):
                _replace_transform_keyframe(obj, data_path, axis, scene.frame_current)


classes = (
    RobStrideAddonPreferences,
    RobStridenodeNode,
    ROBSTRIDE_OT_scan,
    ROBSTRIDE_OT_connect_toggle,
    ROBSTRIDE_OT_node_enable,
    ROBSTRIDE_OT_node_disable,
    ROBSTRIDE_OT_enable_all,
    ROBSTRIDE_OT_disable_all,
    ROBSTRIDE_OT_save_config,
    ROBSTRIDE_OT_load_config,
    ROBSTRIDE_OT_install_deps,
    ROBSTRIDE_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.robstride_nodes = CollectionProperty(type=RobStridenodeNode)
    bpy.types.Scene.robstride_show_simulated = BoolProperty(
        name="Show Simulated Nodes",
        description="Show 2 simulated nodes when CAN is disconnected",
        default=False,
        update=_on_scene_simulated_update,
    )

    # Install handler
    if robstride_sync_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(robstride_sync_handler)

    # Try to ready dependencies up-front
    deps.ensure_dependencies()

    # Start background timer to keep LEARN mode updating while idle
    global _timer_enabled
    _timer_enabled = True
    try:
        bpy.app.timers.register(_robstride_learn_timer, first_interval=0.1, persistent=True)
    except TypeError:
        # Blender < 3.2 lacks persistent kw
        bpy.app.timers.register(_robstride_learn_timer, first_interval=0.1)


def unregister():
    # Remove handler
    if robstride_sync_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(robstride_sync_handler)

    # Stop background timer
    global _timer_enabled
    _timer_enabled = False

    del bpy.types.Scene.robstride_show_simulated
    del bpy.types.Scene.robstride_nodes

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
