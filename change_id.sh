#!/usr/bin/env bash
# -----------------------------------------------------------
# RobStride RS motor ID changer via CAN
#
# Usage:
#   sudo ./change_motor_id.sh <old_id> <new_id> [host_id]
#
# Example:
#   sudo ./change_motor_id.sh 127 1
#   sudo ./change_motor_id.sh 0x7F 0x01 0xAA
#
# Default host_id = 0xAA (as in manual examples)
# -----------------------------------------------------------

CAN_IFACE="can0"
HOST_ID="AA"  # default

# --- check args ---
if [ $# -lt 2 ]; then
  echo "Usage: $0 <old_id> <new_id> [host_id]"
  exit 1
fi

OLD_ID_HEX=$(printf "%02X" $(( $(printf "%d" $1) )))
NEW_ID_HEX=$(printf "%02X" $(( $(printf "%d" $2) )))

#echo $OLD_ID_HEX $NEW_ID_HEX
#exit 0

if [ $# -ge 3 ]; then
  HOST_ID=$(printf "%02X" $(( $(printf "%d" $3) )))
fi

# --- build CAN frame ---
# Format: 07{NEW_ID}{HOST_ID}{OLD_ID}#0000000000000000
FRAME_ID="07${NEW_ID_HEX}${HOST_ID}${OLD_ID_HEX}"
DATA="0000000000000000"

# --- send ---
echo "[INFO] Changing motor ID from 0x${OLD_ID_HEX} to 0x${NEW_ID_HEX} (host 0x${HOST_ID})"
echo "[INFO] Command: cansend ${CAN_IFACE} ${FRAME_ID}#${DATA}"
cansend ${CAN_IFACE} ${FRAME_ID}#${DATA}

# --- feedback ---
if [ $? -eq 0 ]; then
  echo "[OK] Command sent successfully."
  echo "Now power-cycle the motor for the new ID to take effect."
else
  echo "[ERROR] cansend failed."
fi
