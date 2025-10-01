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

    # Public API used by the add-on
    def configure(self, interface: str, channel: str, bitrate: int) -> None:
        self.interface = interface
        self.channel = channel
        self.bitrate = int(bitrate)
        # Do not auto-connect here; explicit connect() controls connection state

    def scan(self) -> List[Dict[str, Any]]:
        if self.simulate:
            return [
                {"id": 1, "name": "Sim node 1"},
                {"id": 2, "name": "Sim node 2"},
            ]

        if not self.connected:
            return []

        if robstride_lib is not None:
            # If an official library exists, prefer it (placeholder usage)
            # Expectation: robstride_lib.scan(interface, channel, bitrate) -> list of dicts
            try:
                nodes = robstride_lib.scan(interface=self.interface, channel=self.channel, bitrate=self.bitrate)
                return [
                    {"id": int(m.get("id", 0)), "name": str(m.get("name", f"node {m.get('id', 0)}"))}
                    for m in nodes
                ]
            except Exception:
                pass

        if self._co_net is not None and canopen is not None:
            try:
                # Active scan for nodes on the bus
                self._co_net.scanner.search()
                # Wait a short period to collect replies
                import time
                time.sleep(0.5)
                node_ids = list(self._co_net.scanner.nodes)
                return [{"id": nid, "name": f"Node {nid}"} for nid in node_ids]
            except Exception:
                pass

        # No simulation and no real backend available
        return []

        # TODO: Actual discovery logic for RobStride nodes over CAN.
        # For now, return an empty list to avoid making assumptions.
        return []

    def set_pid(self, node_id: int, kp: float, ki: float, kd: float) -> None:
        if self.simulate:
            # No-op in simulation for now
            return

        if not self.connected:
            return

        if robstride_lib is not None:
            try:
                robstride_lib.set_pid(node_id, kp, ki, kd)
                return
            except Exception:
                pass

        if self._co_net is not None and canopen is not None:
            try:
                node = self._get_or_add_node(node_id)
                # Placeholder vendor-specific indices; replace with RobStride spec
                # Example indices: 0x3000: Kp, 0x3001: Ki, 0x3002: Kd (subindex 0)
                import struct
                node.sdo.download(0x3000, 0x00, struct.pack('<f', float(kp)))
                node.sdo.download(0x3001, 0x00, struct.pack('<f', float(ki)))
                node.sdo.download(0x3002, 0x00, struct.pack('<f', float(kd)))
                return
            except Exception:
                pass

        # Without a backend and not simulating, do nothing
        return
        # TODO: send PID configuration message per protocol

    def enable_node(self, node_id: int, enable: bool) -> None:
        if self.simulate:
            # No-op in simulation; enable/disable ignored
            return

        if not self.connected:
            return

        if robstride_lib is not None:
            try:
                robstride_lib.enable(node_id, enable)
                return
            except Exception:
                pass

        if self._co_net is not None and canopen is not None:
            try:
                node = self._get_or_add_node(node_id)
                # CiA 402 controlword to enable/disable operation
                import struct
                if enable:
                    # Switch on, enable operation
                    controlword = 0x000F
                else:
                    # Shutdown
                    controlword = 0x0006
                node.sdo.download(0x6040, 0x00, struct.pack('<H', controlword))
                return
            except Exception:
                pass

        # Without a backend and not simulating, do nothing
        return
        # TODO: send enable/disable command per protocol

    def send_position(self, node_id: int, value: float) -> None:
        if self.simulate:
            # Remember last output so reads can reflect it
            self._stub_last[node_id] = float(value)
            return

        if not self.connected:
            return

        if robstride_lib is not None:
            try:
                robstride_lib.set_position(node_id, float(value))
                return
            except Exception:
                pass

        if self._co_net is not None and canopen is not None:
            try:
                node = self._get_or_add_node(node_id)
                import struct
                # Switch to Profile Position mode (1)
                node.sdo.download(0x6060, 0x00, struct.pack('<b', 1))
                # Target position (32-bit signed)
                node.sdo.download(0x607A, 0x00, struct.pack('<i', int(value)))
                # Trigger new set-point: set CW bit 4 and 5 momentarily
                # Read current controlword (if available, otherwise write a default sequence)
                try:
                    cw_bytes = node.sdo.upload(0x6040, 0x00)
                    cw = int.from_bytes(cw_bytes, 'little')
                except Exception:
                    cw = 0x000F
                cw |= (1 << 4) | (1 << 5)
                node.sdo.download(0x6040, 0x00, struct.pack('<H', cw))
                # Clear bit 4 after
                cw &= ~(1 << 4)
                node.sdo.download(0x6040, 0x00, struct.pack('<H', cw))
                return
            except Exception:
                pass

        # Without a backend and not simulating, do nothing
        return
        # TODO: encode and send target position frame

    def read_position(self, node_id: int) -> float:
        if self.simulate:
            base = self._stub_last.get(node_id, 0.0)
            self._stub_phase += 0.1
            return base + 0.1 * math.sin(self._stub_phase)

        if not self.connected:
            return 0.0

        if robstride_lib is not None:
            try:
                return float(robstride_lib.get_position(node_id))
            except Exception:
                pass

        if self._co_net is not None and canopen is not None:
            try:
                node = self._get_or_add_node(node_id)
                pos_bytes = node.sdo.upload(0x6064, 0x00)
                # 32-bit signed position
                return int.from_bytes(pos_bytes, 'little', signed=True)
            except Exception:
                pass

        # TODO: request and/or parse encoder feedback frame
        return 0.0

    # Internal helpers
    def _open_bus(self) -> None:
        self._bus = None
        self._co_net = None
        self._nodes = {}
        if canopen is not None:
            try:
                self._co_net = canopen.Network()
                self._co_net.connect(bustype=self.interface, channel=self.channel, bitrate=self.bitrate)
                return
            except Exception:
                self._co_net = None
        if can is not None:
            try:
                self._bus = can.Bus(interface=self.interface, channel=self.channel, bitrate=self.bitrate)
                return
            except Exception:
                try:
                    self._bus = can.Bus(interface=self.interface, channel=self.channel)
                except Exception:
                    self._bus = None

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
        if self.simulate:
            # Treat simulation as a virtual connection so UI can toggle
            self.connected = True
            return True
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
        if self.simulate:
            return True
        if not self.connected:
            return False
        if self._co_net is not None and canopen is not None:
            return node_id in self._nodes
        if self._bus is not None:
            # For raw CAN we don't track nodes; assume unknown -> False
            return False
        return False


# Singleton instance used by the add-on
manager = RobStrideManager()
