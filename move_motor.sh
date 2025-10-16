#!/bin/bash
# move_motor.sh — Send a RobStride target position (degrees) over CAN
# Usage: ./move_motor.sh <degrees>

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <target_degrees>"
  exit 1
fi

deg="$1"

# Compute little-endian IEEE-754 float bytes for radians using env var
hexbytes=$(
  DEG="$deg" python3 - <<'PY'
import os, struct, math
deg = float(os.environ['DEG'])
rad = deg * math.pi / 180.0
print(''.join(f'{b:02X}' for b in struct.pack('<f', rad)))
PY
)

# (Optional) also show radians for sanity
rad=$(python3 - <<PY
import math
print(${deg}*math.pi/180.0)
PY
)

echo "Target ${deg}° → radians = ${rad} → LE bytes ${hexbytes}"


./enable.sh

# Send the loc_ref (target position) frame
# ID 0x1200AA7F, payload: 16 70 00 00 <float32 rad (LE)>
#cansend can0 1200AA7F#16700000${hexbytes}
cansend can0 1200AA00#16700000${hexbytes}

