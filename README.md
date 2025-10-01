RobStride Blender Add-on

RobStride is a Blender add-on that discovers RobStride nodes over CAN, links them to scene objects, and synchronizes motion in Run and Learn modes. It supports simulated nodes for offline work and can vendor Python dependencies for offline use inside Blender.

Features
- Scan for nodes on the CAN bus and list them as nodes
- Link each node to a Blender object
- Per-node editable Name and persistent node ID
- Run mode: stream animated Z rotation to the node during playback
- Learn mode: read encoder and keyframe the object’s Z rotation on every frame
- PID gains (Kp, Ki, Kd), scale, and offset per node
- Save/Load full configuration as JSON
- Simulation toggle to create two virtual nodes when hardware is unavailable
- Connect/Disconnect to manage the CAN connection explicitly
- Connection status indicators for the network and per node
- One-click “Install Deps” (only shown if missing) that installs python-can and canopen from bundled wheels

Requirements
- Blender 3.0+ (tested with Blender 4.x)
- Python dependencies:
  - python-can
  - canopen
  - Optional: robstride (if you have an official Python package)

You can vendor these into the add-on’s vendor/ folder using the setup script below, or install them into Blender’s Python via the panel’s Install Deps button when wheels are bundled.

Installation
1) Clone or copy this folder into your Blender add-ons path:
   - Linux: ~/.config/blender/<version>/scripts/addons/robstride-blender-addon
   - Windows: %APPDATA%/Blender Foundation/Blender/<version>/scripts/addons/robstride-blender-addon
   - macOS: ~/Library/Application Support/Blender/<version>/scripts/addons/robstride-blender-addon

2) Start Blender, go to Preferences > Add-ons, search for “RobStride” and enable it.

3) Optional: Pre-vendor dependencies so the add-on runs offline (see Dependency Setup).

Dependency Setup (vendoring wheels)
From a terminal in the add-on root:

- Create a venv, download wheels, and vendor into vendor/:
  - bash scripts/setup_deps.sh
- Outputs:
  - .venv/ – local virtualenv
  - wheels/ – downloaded wheels for the add-on
  - vendor/ – installed packages used by Blender at runtime

In Blender, the panel shows “Install Deps” only if python-can and canopen aren’t importable. Clicking it installs from wheels/ to vendor/ via the embedded installer.

Panel Overview
Open View3D > Sidebar (N) > RobStride.

- CAN Settings
  - Channel: e.g., can0, CH0
  - Baudrate: e.g., 1000000
  - Show Simulated Nodes: if enabled, Scan/Connect will create two simulated nodes
  - Network: Connected/Disconnected indicator
  - Buttons:
    - Scan: discover nodes (sim or real depending on the toggle)
    - Connect/Disconnect: open/close the CAN connection; on connect, scan and prepare nodes
    - Save/Load: export/import JSON configuration
    - Install Deps: visible only when dependencies are missing

- node Nodes
  - Name: editable, preserved across scans and config saves/loads
  - ID: node/node ID (read-only)
  - Online/Offline: current node status
  - Object: link a Blender object to this node
  - Mode: Run or Learn
  - Parameters: Kp, Ki, Kd (defaults 1, 0, 0), Scale, Offset, Min Z, Max Z (radians)

Run vs Learn Behavior
- Run Mode
  - The add-on evaluates the object’s keyframed Z rotation (if any) at the current frame and sends it to the node.
  - If no animation is present, it falls back to the object’s live Z rotation.
  - No keyframes are written in Run mode.

- Learn Mode
  - nodes are disabled; encoder position is read each frame, converted using scale/offset, and written into the object’s Z rotation.
  - The Z rotation is keyframed every frame during playback.
  - If a keyframe exists at the current frame, it is replaced so encoder data always takes priority for that frame.

Scan, Connect, and Status
- Connect opens the CAN interface (unless simulating) and scans for nodes, adding any found to the panel. Existing nodes are prepared on the CANopen network when applicable.
- Scan can be run independently; it removes nodes that are not present in the latest scan results.
- “Online/Offline” reflects whether a node is known to the manager (for CANopen nodes this means a prepared RemoteNode exists). A heartbeat or SDO ping can be added if you provide details.

Save/Load Configuration
- Save writes a JSON file containing:
  - CAN settings: interface (stored but hidden in the panel), channel, bitrate
  - nodes: for each node — id, name, linked object name, mode, kp, ki, kd, scale, offset
- Load reads the JSON, applies CAN preferences, replaces the node list, and relinks objects by name if they exist in the scene.

Example schema:
{
  "can": {"interface": "robstride", "channel": "can0", "bitrate": 1000000},
  "nodes": [
    {"id": 1, "name": "Shoulder", "object": "Armature.L", "mode": "RUN",
     "kp": 1.0, "ki": 0.0, "kd": 0.0, "scale": 1.0, "offset": 0.0}
  ]
}

Code Structure
- __init__.py
  - Add-on entry (bl_info), registration, UI Panel (ROBSTRIDE_PT_panel)
  - Operators: Scan, Save Config, Load Config, Install Deps, Connect/Disconnect
  - Properties: Scene.robstride_nodes (collection), Scene.robstride_simulate (bool)
  - PropertyGroup: RobStridenodeNode (name, node_id, object_ref, mode, kp/ki/kd, scale, offset)
  - Handler: robstride_sync_handler runs on frame change during playback to implement Run/Learn logic
  - Helpers: _send_pid_if_changed, _replace_z_keyframe, _get_anim_z_value

- robstride_can.py
  - RobStrideManager: abstraction for CAN/CANopen/robstride-lib
    - configure(): set interface/channel/bitrate (no auto-connect)
    - connect()/disconnect()/is_connected(): manage connection
    - scan(): discover nodes (simulation honors the panel toggle)
    - prepare_node(), node_status(): set up and report CANopen node status
    - set_pid(), enable_node(), send_position(), read_position():
      - Prefer robstride library if available (placeholders)
      - Fallback to CANopen SDOs (uses common CiA-402 indices; adjust to your spec)
      - Simulation: stores/synthesizes positions

- deps.py
  - Vendoring helper to add vendor/ to sys.path
  - ensure_dependencies(), have_modules(), and installer from wheels/ to vendor/

- scripts/setup_deps.sh
  - Creates .venv, downloads wheels into wheels/, installs them into vendor/, and verifies imports

- requirements.txt
  - Pinned versions for python-can, canopen, and related dependencies

Safety and Notes
- Run mode sends motion commands; ensure your hardware is safe to move.
- Learn mode disables the node and records incoming encoder values as keyframes.
- PID indices and some CANopen details are placeholders; provide your RobStride device spec/EDS to finalize.
- The add-on hides the “CAN Interface” in the UI but stores it in the JSON and Add-on Preferences; adjust there if you need a different backend.

Troubleshooting
- Button icons fail: Blender’s icon enums vary; we use supported ones (LINKED/UNLINKED, VIEWZOOM, etc.).
- No simulated nodes: Ensure “Show Simulated Nodes” is enabled, then Connect or Scan.
- No hardware nodes: Confirm Channel/Baudrate, click Connect, then Scan.
- Deps missing: Use the Install Deps button or run `bash scripts/setup_deps.sh` to populate vendor/.
