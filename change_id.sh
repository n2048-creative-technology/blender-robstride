#!/bin/bash
# change_id.sh — Change RobStride CAN node ID using robstride + verify on the bus
# Usage: sudo ./change_id.sh <old_id> <new_id> [iface]
# Example: sudo ./change_id.sh 127 1 can0

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <old_id 0-127> <new_id 0-127> [iface]"
  exit 1
fi

OLD="$1"
NEW="$2"
IFACE="${3:-can0}"

# Basic validation
if ! [[ "$OLD" =~ ^[0-9]+$ && "$NEW" =~ ^[0-9]+$ ]]; then
  echo "IDs must be decimal integers (0..127)"; exit 1
fi
if [ "$OLD" -lt 0 ] || [ "$OLD" -gt 127 ] || [ "$NEW" -lt 0 ] || [ "$NEW" -gt 127 ]; then
  echo "IDs must be within 0..127"; exit 1
fi

printf -v OLDHEX "%02X" "$OLD"
printf -v NEWHEX "%02X" "$NEW"

echo "Changing node ID ${OLD} (0x${OLDHEX}) → ${NEW} (0x${NEWHEX}) on ${IFACE}"

TMP=$(mktemp)
cleanup() { rm -f "$TMP"; kill 0 2>/dev/null || true; }
trap cleanup INT TERM EXIT

# Start a sniffer to capture write frames *to the OLD ID* while we change it
# (1200AA<ID> is the write-ID family you've seen for parameters)
candump -td "${IFACE}",1200AA${OLDHEX}:1FFFFFFF > "$TMP" &
SNIFFER_PID=$!
sleep 0.02

# Do the change using robstride (this knows the correct parameter index)
python3 - "$OLD" "$NEW" "$IFACE" <<'PY'
import sys, can, robstride
old = int(sys.argv[1]); new = int(sys.argv[2]); iface = sys.argv[3]
with can.Bus(interface='socketcan', channel=iface) as bus:
    rs = robstride.Client(bus)
    tried = []
    for pname in ("can_id","CAN_ID","node_id","nodeid","id"):
        try:
            rs.write_param(old, pname, new)
            print(f"Wrote {pname}={new}")
            break
        except Exception as e:
            tried.append(f"{pname}:{e}")
    else:
        print("ERROR: none of the param names worked:", "; ".join(tried))
        sys.exit(1)
    # Try to persist (firmware-dependent)
    try:
        rs.save_config(old)
        print("Saved config.")
    except Exception as e:
        print("save_config skipped:", e)
PY

# Give the sniffer a moment to flush, then stop it
sleep 0.05
kill "$SNIFFER_PID" 2>/dev/null || true
sleep 0.02

echo "Observed write frame(s) to OLD ID during change (first few lines):"
grep -Eo '[0-9A-F]{8}\s+\[8\]\s+([0-9A-F]{2}\s+){8}' "$TMP" | sed -n '1,5p' || true
echo

# Helper: probe one ID by requesting mechpos once and waiting briefly for its reply
probe_id() {
  local IDDEC="$1"
  local IDHEX
  printf -v IDHEX "%02X" "$IDDEC"
  local REQ_ID="1100AA${IDHEX}"
  local RESP_ID="1100${IDHEX}AA"
  if timeout 0.08 bash -c '
    candump -td "'"$IFACE"','"$RESP_ID"':1FFFFFFF" -n 1 >/dev/null &
    D=$!; sleep 0.003
    cansend "'"$IFACE"'" "'"$REQ_ID"'#1970000000000000"
    wait $D
  '; then
    echo "  ↳ Node ${IDDEC} replied"
    return 0
  else
    echo "  ↳ Node ${IDDEC} did NOT reply"
    return 1
  fi
}

echo "Verifying new ID:"
probe_id "$NEW" || true
echo "Checking old ID no longer responds:"
probe_id "$OLD" || true

echo "Done."
