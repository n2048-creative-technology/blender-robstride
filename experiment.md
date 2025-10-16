
# change ID:
```
cansend can0 07{NEW_ID=01}{HOST_ID=AA}{CURRENT_ID=127}#0000000000000000
```

example change the id of motor 127 to 01
```
cansend can0 0701AA7F#0000000000000000
```


# From terminal A, send commands to request position
```
while true; do   
  cansend can0 1100AA7F#1970000000000000
  sleep 0.1; 
done
```


# From terminal B, parse response:
```
candump -td can0,11007FAA:1FFFFFFF | python3 -u -c 'import sys,re,struct,math
for ln in sys.stdin:
    m=re.findall(r"\b[0-9A-Fa-f]{2}\b", ln)
    if len(m) >= 8:
        # last 4 bytes = little-endian float
        b = bytes(int(x,16) for x in m[-4:])
        pos = struct.unpack("<f", b)[0]
        print(f"{ln.strip()}  -> pos_rad={pos:.6f}  pos_deg={pos*180/math.pi:.2f}")'
```



# run_mode = 1 (Position)
```
cansend can0 1200AA7F#0570000001000000
```
# enable
```
cansend can0 0300AA7F#0000000000000000
```

# Send a position
```
deg=123
hexbytes=$(python3 - <<'PY'
import struct,math,os
deg = float(os.environ['deg'])
rad = deg*math.pi/180.0
print(''.join(f'{b:02X}' for b in struct.pack('<f',rad)))
PY
)
echo "Target ${deg}° → LE float bytes ${hexbytes}"
cansend can0 1200AA7F#16700000${hexbytes}
```
