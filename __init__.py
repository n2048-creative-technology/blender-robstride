bl_info = {
    "name": "RobStride CAN Controller",
    "author": "N2048",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > RobStride",
    "description": "Scan RobStride motors over CAN, link to objects, and sync rotations in Run/Learn modes.",
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

# Local module providing CAN communication (stubbed if python-can not available)
from . import robstride_can
from . import deps


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

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "interface")
        col.prop(self, "channel")
        col.prop(self, "bitrate")


class RobStrideMotorNode(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Motor")
    motor_id: IntProperty(name="ID", default=0, min=0)
    object_ref: PointerProperty(name="Object", type=bpy.types.Object)
    mode: EnumProperty(
        name="Mode",
        items=[
            ("RUN", "Run", "Send object Z rotation to motor"),
            ("LEARN", "Learn", "Read encoder and keyframe object Z"),
        ],
        default="RUN",
    )
    kp: FloatProperty(name="Kp", default=1.0)
    ki: FloatProperty(name="Ki", default=0.0)
    kd: FloatProperty(name="Kd", default=0.0)
    scale: FloatProperty(
        name="Scale",
        description="Multiplier to convert radians <-> motor units",
        default=1.0,
    )
    offset: FloatProperty(
        name="Offset",
        description="Offset for conversion",
        default=0.0,
    )


class ROBSTRIDE_OT_scan(bpy.types.Operator):
    bl_idname = "robstride.scan"
    bl_label = "Scan RobStride Motors"
    bl_description = "Find motors on the configured CAN bus and populate nodes"
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
        # Simulation flag from scene
        sim = context.scene.robstride_simulate
        robstride_can.manager.set_simulate(bool(sim))

        found = robstride_can.manager.scan()

        scene = context.scene
        nodes = scene.robstride_nodes

        # Remove nodes that are no longer present
        found_ids = {int(m.get("id", 0)) for m in found}
        remove_indices = [i for i, n in enumerate(nodes) if n.motor_id not in found_ids]
        for i in reversed(remove_indices):
            nodes.remove(i)

        # Build a map of existing nodes by ID (after removals)
        existing = {n.motor_id: n for n in nodes}

        # Update or add nodes
        for m in found:
            m_id = int(m.get("id", 0))
            m_name = str(m.get("name", f"Motor {m_id}"))
            if m_id in existing:
                # Keep user-customized name; do not overwrite
                n = existing[m_id]
            else:
                n = nodes.add()
                n.name = m_name
                n.motor_id = m_id

        self.report({'INFO'}, f"Found {len(found)} motors")
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
        robstride_can.manager.set_simulate(bool(scene.robstride_simulate))

        if robstride_can.manager.is_connected():
            robstride_can.manager.disconnect()
            self.report({'INFO'}, "Disconnected")
            return {'FINISHED'}

        # Connect
        if not robstride_can.manager.connect():
            self.report({'ERROR'}, "Failed to connect")
            return {'CANCELLED'}

        # After connecting, scan and ensure nodes are added/prepared
        found = robstride_can.manager.scan()
        nodes = scene.robstride_nodes

        # Do not remove on connect; only add/update
        existing = {n.motor_id: n for n in nodes}
        for m in found:
            m_id = int(m.get("id", 0))
            m_name = str(m.get("name", f"Motor {m_id}"))
            if m_id in existing:
                # Keep user-defined name
                pass
            else:
                n = nodes.add()
                n.name = m_name
                n.motor_id = m_id

        # Prepare canopen nodes where applicable
        for n in nodes:
            robstride_can.manager.prepare_node(n.motor_id)

        self.report({'INFO'}, "Connected and prepared nodes")
        return {'FINISHED'}


class ROBSTRIDE_OT_save_config(bpy.types.Operator):
    bl_idname = "robstride.save_config"
    bl_label = "Save Config"
    bl_description = "Save CAN and motor node configuration to a JSON file"
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
            "motors": [],
        }

        for node in scene.robstride_nodes:
            data["motors"].append({
                "id": int(node.motor_id),
                "name": node.name,
                "object": node.object_ref.name if node.object_ref else "",
                "mode": node.mode,
                "kp": float(node.kp),
                "ki": float(node.ki),
                "kd": float(node.kd),
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
    bl_description = "Load CAN and motor node configuration from a JSON file"
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

        for m in data.get("motors", []):
            n = nodes.add()
            n.motor_id = int(m.get("id", 0))
            n.name = str(m.get("name", f"Motor {n.motor_id}"))
            obj_name = str(m.get("object", ""))
            n.object_ref = bpy.data.objects.get(obj_name) if obj_name else None
            mode = str(m.get("mode", "RUN"))
            n.mode = mode if mode in {"RUN", "LEARN"} else "RUN"
            n.kp = float(m.get("kp", 0.0))
            n.ki = float(m.get("ki", 0.0))
            n.kd = float(m.get("kd", 0.0))
            n.scale = float(m.get("scale", 1.0))
            n.offset = float(m.get("offset", 0.0))

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
        col.prop(scene, "robstride_simulate", text="Show Simulated Nodes")
        # Connection status only
        net_row = can_box.row(align=True)
        connected = robstride_can.manager.is_connected()
        net_icon = 'LINKED' if connected else 'UNLINKED'
        net_row.label(text=f"Network: {'Connected' if connected else 'Disconnected'}", icon=net_icon)

        row = can_box.row(align=True)
        row.operator(ROBSTRIDE_OT_scan.bl_idname, icon='VIEWZOOM', text="Scan")
        conn_icon = 'UNLINKED' if robstride_can.manager.is_connected() else 'LINKED'
        row.operator("robstride.connect_toggle", icon=conn_icon, text=("Disconnect" if robstride_can.manager.is_connected() else "Connect"))
        row.operator("robstride.save_config", icon='FILE_TICK', text="Save")
        row.operator("robstride.load_config", icon='FILE_FOLDER', text="Load")
        # Only show Install Deps if not installed yet (check without side-effects)
        try:
            has_can, has_canopen, _has_rs = deps.have_modules()
            deps_ready = bool(has_can and has_canopen)
        except Exception:
            deps_ready = False
        if not deps_ready:
            row.operator("robstride.install_deps", icon='IMPORT', text="Install Deps")

        if len(scene.robstride_nodes) == 0:
            layout.label(text="No motors. Click Scan.")
            return

        for idx, node in enumerate(scene.robstride_nodes):
            box = layout.box()
            header = box.row(align=True)
            header.prop(node, "name", text="Name")
            online = robstride_can.manager.node_status(node.motor_id)
            online_icon = 'CHECKMARK' if online else 'ERROR'
            header.label(text=f"ID {node.motor_id}", icon='DRIVER')
            header.label(text=("Online" if online else "Offline"), icon=online_icon)

            col = box.column(align=True)
            col.prop(node, "object_ref")
            col.prop(node, "mode", expand=True)

            grid = box.grid_flow(columns=2, even_columns=True, even_rows=True)
            grid.prop(node, "kp")
            grid.prop(node, "ki")
            grid.prop(node, "kd")
            grid.prop(node, "scale")
            grid.prop(node, "offset")


# Cache last-sent parameters to reduce bus traffic
_last_pid = {}
_last_out = {}


def _send_pid_if_changed(node):
    key = node.motor_id
    last = _last_pid.get(key)
    current = (node.kp, node.ki, node.kd)
    if last != current:
        try:
            robstride_can.manager.set_pid(key, *current)
            _last_pid[key] = current
        except Exception:
            pass


def _replace_z_keyframe(obj, frame):
    ad = getattr(obj, 'animation_data', None)
    if ad and ad.action:
        fcurves = ad.action.fcurves
        for fc in fcurves:
            if fc.data_path == 'rotation_euler' and fc.array_index == 2:
                # Remove any keyframe at the current frame so the new one takes priority
                remove = [kp for kp in fc.keyframe_points if abs(kp.co.x - frame) < 1e-5]
                for kp in remove:
                    fc.keyframe_points.remove(kp)
                fc.update()
                break
    # Insert the new keyframe for Z rotation at this frame
    obj.keyframe_insert(data_path="rotation_euler", index=2)


def _get_anim_z_value(obj, frame):
    ad = getattr(obj, 'animation_data', None)
    if not (ad and ad.action):
        return None
    for fc in ad.action.fcurves:
        if fc.data_path == 'rotation_euler' and fc.array_index == 2:
            try:
                return float(fc.evaluate(frame))
            except Exception:
                return None
    return None


@persistent
def robstride_sync_handler(scene):
    # Only operate while animation is playing to avoid unexpected bus traffic
    screen = bpy.context.screen
    if not screen or not screen.is_animation_playing:
        return

    for node in scene.robstride_nodes:
        if not node.object_ref:
            continue

        obj = node.object_ref
        motor_id = node.motor_id

        # Skip if not connected and not simulating
        if not (robstride_can.manager.is_connected() or scene.robstride_simulate):
            continue

        # Update PID if needed
        _send_pid_if_changed(node)

        if node.mode == 'RUN':
            # Use recorded animation (keyframes) if present, else current property
            z_from_anim = _get_anim_z_value(obj, scene.frame_current)
            z_rad = z_from_anim if z_from_anim is not None else float(obj.rotation_euler[2])
            motor_units = node.scale * z_rad + node.offset

            last = _last_out.get(motor_id)
            if last is None or abs(last - motor_units) > 1e-6:
                try:
                    robstride_can.manager.enable_motor(motor_id, True)
                    robstride_can.manager.send_position(motor_id, motor_units)
                    _last_out[motor_id] = motor_units
                except Exception:
                    pass

        elif node.mode == 'LEARN':
            try:
                robstride_can.manager.enable_motor(motor_id, False)
                pos = robstride_can.manager.read_position(motor_id)
            except Exception:
                continue

            # Motor units -> radians
            z_rad = (pos - node.offset) / node.scale if node.scale != 0.0 else 0.0
            obj.rotation_euler[2] = z_rad

            # Ensure incoming encoder value overrides any existing key at this frame
            _replace_z_keyframe(obj, scene.frame_current)


classes = (
    RobStrideAddonPreferences,
    RobStrideMotorNode,
    ROBSTRIDE_OT_scan,
    ROBSTRIDE_OT_save_config,
    ROBSTRIDE_OT_load_config,
    ROBSTRIDE_OT_install_deps,
    ROBSTRIDE_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.robstride_nodes = CollectionProperty(type=RobStrideMotorNode)
    bpy.types.Scene.robstride_simulate = BoolProperty(
        name="Simulate",
        description="When enabled, show and use simulated motors instead of requiring real hardware",
        default=False,
    )

    # Install handler
    if robstride_sync_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(robstride_sync_handler)

    # Try to ready dependencies up-front
    deps.ensure_dependencies()


def unregister():
    # Remove handler
    if robstride_sync_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(robstride_sync_handler)

    del bpy.types.Scene.robstride_nodes
    del bpy.types.Scene.robstride_simulate

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
