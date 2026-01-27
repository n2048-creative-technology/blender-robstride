#!/usr/bin/env bash
set -euo pipefail

# Read RobStride-style motor param "mechpos" (0x7019) via can-utils.
# Usage:
#   ./read_mechpos.sh can0 <motor_id> [host_can_id]
#
# Example:
#   ./read_mechpos.sh can0 1
#   ./read_mechpos.sh can0 1 0xAA

IFACE="${1:-}"
MOTOR_ID="${2:-}"
HOST_ID="${3:-0xAA}"

if [[ -z "${IFACE}" || -z "${MOTOR_ID}" ]]; then
  echo "Usage: $0 <can_iface> <motor_id> [host_can_id]"
  exit 1
fi

# Normalize motor id to integer
if [[ "${MOTOR_ID}" =~ ^0x ]]; then
  MOTOR_ID_DEC=$((MOTOR_ID))
else
  MOTOR_ID_DEC=$((10#${MOTOR_ID}))
fi

# Normalize host id to integer
if [[ "${HOST_ID}" =~ ^0x ]]; then
  HOST_ID_DEC=$((HOST_ID))
else
  HOST_ID_DEC=$((10#${HOST_ID}))
fi

# MotorMsg.ReadParam = 17 decimal = 0x11
MSG_TYPE_DEC=17

# Param mechpos = 0x7019, sent little-endian in first 2 bytes
PARAM_LO="19"
PARAM_HI="70"

# Request arbitration id format from your code:
# arb_id = id_data_2 + (id_data_1 << 8) + (msg_type << 24)
# id_data_2 = motor_id
# id_data_1 = host_can_id
REQ_AID_DEC=$(( MOTOR_ID_DEC + (HOST_ID_DEC << 8) + (MSG_TYPE_DEC << 24) ))

# Response arbitration id validation in your code expects:
# msg_type = 0x11, msg_motor_id = motor_id (in bits 8..15), host_id = host (bits 0..7)
RESP_AID_DEC=$(( (MSG_TYPE_DEC << 24) | (MOTOR_ID_DEC << 8) | HOST_ID_DEC ))

# Filter for candump: match full 29-bit arbitration id
FILTER_ID_HEX
FILTER_ID_HEX=$(printf "%08X" "${RESP_AID_DEC}")

REQ_ID_HEX
REQ_ID_HEX=$(printf "%08X" "${REQ_AID_DEC}")

# Payload: [param_lo param_hi 00 00 00 00 00 00]
DATA_HEX="${PARAM_LO}${PARAM_HI}000000000000"

# Send request (extended frame by virtue of 29-bit id)
cansend "${IFACE}" "${REQ_ID_HEX}#${DATA_HEX}"

# Read one matching response, with a timeout
LINE="$(timeout 2s candump -n 1 "${IFACE},${FILTER_ID_HEX}:1FFFFFFF" 2>/dev/null || true)"

if [[ -z "${LINE}" ]]; then
  echo "No response (timeout)."
  exit 2
fi

# Extract the 8 data bytes from candump output
# Typical format: can0  11123AAA   [8]  19 70 00 00 12 34 56 78
BYTES_HEX="$(echo "${LINE}" | awk '
  {
    # find the "[8]" token then print the next 8 fields
    for (i=1; i<=NF; i++) {
      if ($i ~ /^\[[0-9]+\]$/) {
        # data starts at i+1
        for (j=i+1; j<=i+8; j++) printf "%s", $j;
        printf "\n";
        exit
      }
    }
  }' | tr -d '[:space:]')"

if [[ ${#BYTES_HEX} -lt 16 ]]; then
  echo "Could not parse response bytes from: ${LINE}"
  exit 3
fi

# Validate param id echoed back in bytes 0..1 (little-endian)
RESP_PARAM="${BYTES_HEX:0:4}" # "1970"
if [[ "${RESP_PARAM,,}" != "1970" ]]; then
  echo "Unexpected param id in response: 0x${RESP_PARAM}"
  exit 4
fi

# Value is float32 little-endian in bytes 4..7 (offset 8 hex chars)
VAL_HEX="${BYTES_HEX:8:8}"

# Decode float32 little-endian using python (only for decoding)
MECHPOS="$(python3 - <<PY
import struct
h = bytes.fromhex("${VAL_HEX}")
print(struct.unpack("<f", h)[0])
PY
)"

echo "${MECHPOS}"
