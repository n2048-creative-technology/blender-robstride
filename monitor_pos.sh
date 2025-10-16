#!/bin/bash
# monitor_pos.sh — poll RobStride mechpos and print pos in rad/deg
# Usage: ./monitor_pos.sh [can-iface] [period_seconds]
# Defaults: iface=can0, period=0.1

set -euo pipefail

IFACE="${1:-can0}"
PERIOD="${2:-0.1}"

echo "Polling mechpos on ${IFACE} every ${PERIOD}s. Press Ctrl-C to stop."

# Start the request loop in the background
(
  while true; do
    # Read mechpos request (extended ID 0x1100AA7F)
    cansend "${IFACE}" 1100AA7F#1970000000000000
    sleep "${PERIOD}"
  done
) &
SENDER_PID=$!

# Ensure we kill the sender on exit
cleanup() {
  kill "${SENDER_PID}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# Decode replies (extended ID 0x11007FAA) in the foreground
candump -td "${IFACE}",11007FAA:1FFFFFFF | \
python3 -u - <<'PY'
import sys, re, struct, math
for ln in sys.stdin:
    # Extract the 8 data bytes shown by candump
    m = re.findall(r"\b[0-9A-Fa-f]{2}\b", ln)
    if len(m) >= 8:
        # last 4 bytes are a little-endian float (radians)
        b = bytes(int(x,16) for x in m[-4:])
        pos = struct.unpack("<f", b)[0]
        print(f"{ln.strip()}  -> pos_rad={pos:.6f}  pos_deg={pos*180/math.pi:.2f}")
        sys.stdout.flush()
PY
