#!/bin/bash
# move_motor.sh — Send a RobStride target position (degrees) over CAN
# Usage:
#   ./move_motor.sh <motor_id> <degrees> [host_id]
# Examples:
#   ./move_motor.sh 127 90
#   ./move_motor.sh 0x7F 45 0x00    # custom master/host ID 0x0000 instead of default 0x00AA
#
# Notes:
# - motor_id is the node ID (0–127). It’s encoded in the low 8 bits of the 29-bit CAN ID.
# - host_id (master ID) is 16 bits; default is 0x00AA to match your examples.
# - This sends a Type=0x12 (single-parameter write) with index bytes: 16 70 00 00 (loc_ref),
#   followed by the target position in radians as a little-endian float32.

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <motor_id> <target_degrees> [host_id]"
  exit 1
fi

motor_arg="$1"
deg="$2"
host_arg="${3:-0x00AA}"   # default master/host ID = 0x00AA

# Normalize numeric inputs (accepts dec or 0x.. hex)
to_dec() { printf "%d" "$1"; }  # bash/printf handles 0x.. and decimal

MOTOR_DEC="$(to_dec "$motor_arg")"
HOST_DEC="$(to_dec "$host_arg")"

# Range/sanity checks
if [ "$MOTOR_DEC" -lt 0 ] || [ "$MOTOR_DEC" -gt 255 ]; then
  echo "Error: motor_id must be 0..255"
  exit 1
fi
if [ "$HOST_DEC" -lt 0 ] || [ "$HOST_DEC" -gt 65535 ]; then
  echo "Error: host_id must be 0..65535 (16-bit)"
  exit 1
fi

# Hex encodings used in the extended CAN ID string (no 0x prefix, upper-case, zero-padded)
MOTOR_HEX=$(printf "%02X" "$MOTOR_DEC")
HOST_HEX=$(printf "%04X" "$HOST_DEC")

# Build extended arbitration ID for Type=0x12 (single parameter write)
# Format (as seen in your examples): 0x12{HOST16}{MOTOR8} → e.g., 1200AA7F
EXT_ID="12${HOST_HEX}${MOTOR_HEX}"

# Compute little-endian IEEE-754 float bytes for radians from degrees
hexbytes=$(
  DEG="$deg" python3 - <<'PY'
import os, struct, math
deg = float(os.environ['DEG'])
rad = deg * math.pi / 180.0
print(''.join(f'{b:02X}' for b in struct.pack('<f', rad)))
PY
)

# Also show radians for sanity
rad=$(python3 - <<PY
import math
print(${deg}*math.pi/180.0)
PY
)

echo "Motor ID: 0x${MOTOR_HEX}  Host/Master ID: 0x${HOST_HEX}"
echo "Target ${deg}° → ${rad} rad → LE bytes ${hexbytes}"

# If you have an enable script, pass the motor id if it accepts it; otherwise call it plain.
if [ -x ./enable.sh ]; then
  # Try with motor id; fall back without if it errors.
  if ! ./enable.sh "$MOTOR_DEC"; then
    ./enable.sh || true
  fi
fi

# Send the loc_ref (target position) frame
# Payload: 16 70 00 00 <float32 rad (LE)>
#          ^^^^^^^^^^  = index 0x7016 in little-endian byte order (loc_ref)
DATA_PREFIX="16700000"
echo "cansend can0 ${EXT_ID}#${DATA_PREFIX}${hexbytes}"
cansend can0 "${EXT_ID}#${DATA_PREFIX}${hexbytes}"
