#!/bin/bash
# scan_nodes.sh — probe RobStride node IDs by requesting mechpos
# Usage: sudo ./scan_nodes.sh [iface] [first_id] [last_id] [wait_s]
# Defaults: iface=can0, ids 0..127, wait 0.05s

set -euo pipefail

IFACE="${1:-can0}"
FIRST="${2:-0}"
LAST="${3:-127}"
WAIT="${4:-0.05}"   # how long to wait for each ID's reply

found=()

for ((id=FIRST; id<=LAST; id++)); do
  printf -v IDHEX "%02X" "$id"
  REQ_ID="1100AA${IDHEX}"   # request to node
  RESP_ID="1100${IDHEX}AA"  # expected reply from node

  # For each ID:
  # 1) start a candump that will exit after the first matching frame
  # 2) give it a few ms to attach
  # 3) send the read-mechpos request
  # 4) wait (with timeout) for candump to catch a reply
  if timeout "${WAIT}" bash -c '
    set -e
    candump -td "'"$IFACE"','"$RESP_ID"':1FFFFFFF" -n 1 >/dev/null &
    DPID=$!
    sleep 0.003
    cansend "'"$IFACE"'" "'"$REQ_ID"'#1970000000000000"
    wait $DPID
  '; then
    echo "Found node ID ${id} (0x${IDHEX})"
    found+=("$id")
  fi
done

echo "Nodes: ${found[*]:-none}"
