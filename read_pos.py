import time
import can
import robstride


MID=127
PI=3.14159265359

def readPos(rs):
    mechpos = rs.read_param(MID, "mechpos");
    angle = float(mechpos)*360.0/2.0/PI;
    print(f"mechpos={mechpos:.2f}, angle={angle:.2f}°")

with can.Bus(interface='socketcan', channel='can0') as bus:
    rs = robstride.Client(bus)

    # Position mode + enable
    rs.write_param(MID, 'run_mode', robstride.RunMode.Position)

    print("disable");
    rs.disable(MID)

    while True:
        readPos(rs);

    print("disable");
    rs.disable(MID)
