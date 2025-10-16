#!/usr/bin/env python3
# scan_nodes.py — probe RobStride node IDs by requesting mechpos
# Usage: sudo ./scan_nodes.py [iface] [first_id] [last_id]
# Defaults: iface=can0, first_id=0, last_id=127

import sys, time
import can

iface    = sys.argv[1] if len(sys.argv) > 1 else "can0"
first_id = int(sys.argv[2]) if len(sys.argv) > 2 else 0
last_id  = int(sys.argv[3]) if len(sys.argv) > 3 else 127

REQ_BASE = 0x11000000
def req_id(n):  return REQ_BASE | (0xAA << 8) | (n & 0xFF)        # 0x1100AA<ID>
def resp_id(n): return REQ_BASE | ((n & 0xFF) << 8) | 0xAA        # 0x1100<ID>AA

payload = bytes([0x19, 0x70, 0x00, 0x00, 0, 0, 0, 0])  # read mechpos

found = []

with can.Bus(interface='socketcan', channel=iface) as bus:
    # drain any stale frames
    t_end = time.time() + 0.2
    while time.time() < t_end:
        msg = bus.recv(timeout=0.01)
        if not msg: break

    for nid in range(first_id, last_id + 1):
        rid = resp_id(nid)
        # Send the request
        bus.send(can.Message(arbitration_id=req_id(nid),
                             data=payload,
                             is_extended_id=True))
        # Wait briefly for the reply from this node
        t0 = time.time()
        ok = False
        while time.time() - t0 < 0.03:  # 30 ms per ID (tune as needed)
            msg = bus.recv(timeout=0.01)
            if msg and msg.arbitration_id == rid and len(msg.data) == 8:
                found.append(nid)
                ok = True
                break
        # small gap to avoid flooding
        time.sleep(0.002)

print("Found node IDs:", found)
