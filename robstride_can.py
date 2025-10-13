"""
RobStride CAN manager abstraction.

This module provides a small interface used by the add-on to talk to
RobStride nodes. It tries to use python-can if available, but also
exposes a stub implementation for development/testing without hardware.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List

try:
    import can  # type: ignore
except Exception:  # pragma: no cover - optional
    can = None  # type: ignore
try:
    import canopen  # type: ignore
except Exception:  # pragma: no cover - optional
    canopen = None  # type: ignore
try:
    import robstride as robstride_lib  # type: ignore
except Exception:  # pragma: no cover - optional
    robstride_lib = None  # type: ignore

class RobStrideManager:
    def __init__(self):
        self.interface = "socketcan"
        self.channel = "can0"
        self.bitrate = 1_000_000
        self._bus = None
        self._co_net = None
        self._nodes = {}
        self._stub_last: Dict[int, float] = {}
        self._stub_phase = 0.0
        self.simulate = False
        self.connected = False
        self._rs_client = None
        self._enabled_nodes = set()
        self._pos_mode_nodes = set()

    # Public API used by the add-on
    def configure(self, interface: str, channel: str, bitrate: int) -> None:
        self.interface = interface
        self.channel = channel
        self.bitrate = int(bitrate)
        # Do not auto-connect here; explicit connect() controls connection state

    def scan(self) -> List[Dict[str, Any]]:
        # If connected, collect real nodes; if simulate is enabled, always include simulated nodes too
        results: List[Dict[str, Any]] = []
        real_ids = set()
        if self.connected:
            # Try official library first
            if robstride_lib is not None:
                try:
                    nodes = robstride_lib.scan(interface=self.interface, channel=self.channel, bitrate=self.bitrate)
                    for m in nodes:
                        nid = int(m.get("id", 0))
                        real_ids.add(nid)
                        results.append({"id": nid, "name": str(m.get("name", f"node {nid}"))})
                except Exception:
                    pass

            # Fallback to CANopen scanner
            if self._co_net is not None and canopen is not None and not results:
                try:
                    self._co_net.scanner.search()
                    time.sleep(0.5)
                    for nid in list(self._co_net.scanner.nodes):
                        nid = int(nid)
                        real_ids.add(nid)
                        results.append({"id": nid, "name": f"Node {nid}"})
                except Exception:
                    pass

        # If simulation toggle is on, add simulated nodes (deduplicated)
        if self.simulate:
            sim_nodes = [
                {"id": 1, "name": "Sim node 1"},
                {"id": 2, "name": "Sim node 2"},
            ]
            for m in sim_nodes:
                if int(m["id"]) not in real_ids:
                    results.append(m)

        return results

    def set_pid(self, node_id: int, kp: float, ki: float, kd: float) -> None:
        # Prefer RobStride client when connected; attempt a reasonable mapping
        if self.connected and robstride_lib is not None and self._rs_client is not None:
            try:
                # Map Blender Kp/Ki/Kd to RobStride params (heuristic)
                self._rs_client.write_param(node_id, 'loc_kp', float(kp))
                self._rs_client.write_param(node_id, 'spd_kp', float(kd))
                self._rs_client.write_param(node_id, 'spd_ki', float(ki))
                return
            except Exception:
                pass

        if self.connected and self._co_net is not None and canopen is not None:
            try:
                node = self._get_or_add_node(node_id)
                import struct
                node.sdo.download(0x3000, 0x00, struct.pack('<f', float(kp)))
                node.sdo.download(0x3001, 0x00, struct.pack('<f', float(ki)))
                node.sdo.download(0x3002, 0x00, struct.pack('<f', float(kd)))
                return
            except Exception:
                pass
        # TODO: send PID configuration message per protocol

    def enable_node(self, node_id: int, enable: bool) -> None:
        # Prefer RobStride client; avoid re-enabling every frame
        if self.connected and robstride_lib is not None and self._rs_client is not None:
            try:
                if enable and node_id not in self._enabled_nodes:
                    self._rs_client.enable(node_id)
                    self._enabled_nodes.add(node_id)
                elif (not enable) and node_id in self._enabled_nodes:
                    self._rs_client.disable(node_id)
                    self._enabled_nodes.discard(node_id)
                return
            except Exception:
                pass

        if self.connected and self._co_net is not None and canopen is not None:
            try:
                node = self._get_or_add_node(node_id)
                import struct
                controlword = 0x000F if enable else 0x0006
                node.sdo.download(0x6040, 0x00, struct.pack('<H', controlword))
                return
            except Exception:
                pass

        if self.simulate:
            return
        # TODO: send enable/disable command per protocol

    def send_position(self, node_id: int, value: float) -> None:
        # Prefer RobStride client; set Position mode once, then update loc_ref
        if self.connected and robstride_lib is not None and self._rs_client is not None:
            try:
                if node_id not in self._pos_mode_nodes:
                    self._rs_client.write_param(node_id, 'run_mode', robstride_lib.RunMode.Position)
                    self._pos_mode_nodes.add(node_id)
                self._rs_client.write_param(node_id, 'loc_ref', float(value))
                return
            except Exception:
                pass

        if self.connected and self._co_net is not None and canopen is not None:
            try:
                node = self._get_or_add_node(node_id)
                import struct
                node.sdo.download(0x6060, 0x00, struct.pack('<b', 1))
                node.sdo.download(0x607A, 0x00, struct.pack('<i', int(value)))
                try:
                    cw_bytes = node.sdo.upload(0x6040, 0x00)
                    cw = int.from_bytes(cw_bytes, 'little')
                except Exception:
                    cw = 0x000F
                cw |= (1 << 4) | (1 << 5)
                node.sdo.download(0x6040, 0x00, struct.pack('<H', cw))
                cw &= ~(1 << 4)
                node.sdo.download(0x6040, 0x00, struct.pack('<H', cw))
                return
            except Exception:
                pass

        if self.simulate:
            self._stub_last[node_id] = float(value)
            return
        # TODO: encode and send target position frame

    def read_position(self, node_id: int) -> float:
        # Prefer RobStride client when connected: read mechanical position (radians)
        if self.connected and robstride_lib is not None and self._rs_client is not None:
            try:
                angle = self._rs_client.read_param(node_id, 'mechpos')
                return float(angle)
            except Exception:
                pass

        if self.connected and self._co_net is not None and canopen is not None:
            try:
                node = self._get_or_add_node(node_id)
                pos_bytes = node.sdo.upload(0x6064, 0x00)
                return int.from_bytes(pos_bytes, 'little', signed=True)
            except Exception:
                pass

        if self.simulate:
            base = self._stub_last.get(node_id, 0.0)
            self._stub_phase += 0.1
            return base + 0.1 * math.sin(self._stub_phase)

        return 0.0

    # Internal helpers
    def _open_bus(self) -> None:
        self._bus = None
        self._co_net = None
        self._nodes = {}
        self._rs_client = None
        self._enabled_nodes.clear()
        self._pos_mode_nodes.clear()
        if canopen is not None:
            try:
                self._co_net = canopen.Network()
                self._co_net.connect(bustype=self.interface, channel=self.channel, bitrate=self.bitrate)
            except Exception:
                self._co_net = None
        if can is not None:
            try:
                self._bus = can.Bus(interface=self.interface, channel=self.channel, bitrate=self.bitrate)
            except Exception:
                try:
                    self._bus = can.Bus(interface=self.interface, channel=self.channel)
                except Exception:
                    self._bus = None
        # Initialize RobStride client if a CAN bus is available
        if self._bus is not None and robstride_lib is not None:
            try:
                self._rs_client = robstride_lib.Client(self._bus, retry_count=0, recv_timeout=0.1)
            except Exception:
                self._rs_client = None

    def _get_or_add_node(self, node_id: int):
        if self._co_net is None or canopen is None:
            raise RuntimeError("CANopen not initialized")
        node = self._nodes.get(node_id)
        if node is None:
            # Add a remote node without EDS; access SDO by raw indices
            node = canopen.RemoteNode(node_id, None)  # type: ignore[arg-type]
            node.network = self._co_net
            self._nodes[node_id] = node
        return node

    def set_simulate(self, value: bool) -> None:
        self.simulate = bool(value)

    # Connection management
    def connect(self) -> bool:
        # Always attempt to open the real bus regardless of simulation flag
        try:
            self._open_bus()
            self.connected = (self._co_net is not None) or (self._bus is not None)
        except Exception:
            self.connected = False
        return self.connected

    def disconnect(self) -> None:
        self.connected = False
        try:
            if self._co_net is not None:
                self._co_net.disconnect()
        except Exception:
            pass
        self._co_net = None
        self._bus = None
        self._nodes = {}
        self._rs_client = None
        self._enabled_nodes.clear()
        self._pos_mode_nodes.clear()

    def is_connected(self) -> bool:
        # Real connection state (simulation handled separately by UI)
        return bool(self.connected)

    def prepare_node(self, node_id: int) -> None:
        if self.simulate:
            return
        if self._co_net is not None and canopen is not None:
            try:
                self._get_or_add_node(node_id)
            except Exception:
                pass

    def node_status(self, node_id: int) -> bool:
        # With RobStride, assume online when connected (no heartbeat implemented here)
        if self.connected:
            return True
        if self.simulate:
            return True
        return False


# Singleton instance used by the add-on
manager = RobStrideManager()
