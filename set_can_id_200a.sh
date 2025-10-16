#!/bin/bash
# set_can_id_200a.sh — Set RobStride CAN_ID (index 0x200A) using cansend only
# Usage: sudo ./set_can_id_200a.sh [iface] [current_id] [new_id]
# Defaults: iface=can0, current_id=0, new_id=127

set -euo pipefail
IFACE="${1:-can0}"
CUR="${2:-0}"
NEW="${3:-127}"

printf -v CURHEX "%02X" "$CUR"
printf -v NEWHEX "%02X" "$NEW"

echo "Interface=${IFACE}  currentID=${CUR} (0x${CURHEX})  newID=${NEW} (0x${NEWHEX})"

read_once() {  # read index 0x200A from node $CUR, print last 4 data bytes
  # request: READ index 0x200A → data bytes: 0A 20 00 00 00 00 00 00
  cansend "$IFACE" 1100AA${CURHEX}#0A20000000000000
  # expect reply on 0x1100<CUR>AA
  if candump -td "$IFACE",1100${CURHEX}AA:1FFFFFFF -n 1 -T 200 >/tmp/_idread 2>/dev/null; then
    line=$(tail -n1 /tmp/_idread)
    echo "Reply: $line"
    # extract last 4 bytes
    val=$(echo "$line" | grep -Eo '([0-9A-F]{2}\s+){8}' | awk '{print $(NF-3)$(NF-2)$(NF-1)$NF}')
    echo "Value bytes (LE u32) = ${val}"
  else
    echo "No reply from node ${CUR} on read."
  fi
}

write_via_1200() {
  echo "Writing NEW ID via 0x1200AA${CURHEX}…"
  # write: index 0x200A (0A 20), value NEW (LE u32) = <NEW 00 00 00>
  cansend "$IFACE" 1200AA${CURHEX}#0A200000${NEWHEX}000000
}

write_via_0500() {
  echo "Writing NEW ID via 0x0500AA${CURHEX} (alt path)…"
  cansend "$IFACE" 0500AA${CURHEX}#0A200000${NEWHEX}000000
}

save_to_cur() {
  echo "Saving to flash on CURRENT node ${CUR}…"
  cansend "$IFACE" 0600AA${CURHEX}#0000000000000000
}

echo "Step 1) READ current CAN_ID (index 0x200A) on node ${CUR}:"
read_once
echo

echo "Step 2) WRITE new ID=${NEW} (LE) via 0x1200… and re-read:"
write_via_1200
sleep 0.05
read_once
echo

echo "If value did not change above, try alternate writer (0x0500…) and re-read:"
write_via_0500
sleep 0.05
read_once
echo

echo "Step 3) SAVE to CURRENT node (${CUR}):"
save_to_cur
echo "Now POWER-CYCLE the actuator (turn it off/on). Then verify below."
echo

echo "Verification after power cycle (run these manually when back up):"
cat <<EOT
# quick probe on new ID ${NEW}:
cansend ${IFACE} 1100AA${NEWHEX}#0A20000000000000
candump -td ${IFACE},1100${NEWHEX}AA:1FFFFFFF -n 1

# or scan:
./scan_nodes.sh ${IFACE} 0 127 0.1
EOT
