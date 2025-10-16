import time
import can
import robstride
import math
import random

MID=0
C=0

def moveTo(rs, deg):
    target = deg*2*math.pi/360
    err = 1
    while abs(err) > 0.1:
        rs.write_param(MID, 'loc_ref', target);  time.sleep(0.5);
        actual = float(rs.read_param(MID, "mechpos"));
        actual_deg = actual*360.0/2.0/math.pi
        err = target - actual
        err_deg = err*360.0/2.0/math.pi
        print(f"target={deg:.2f}°, actual={actual:.2f}°, error={err_deg:.2f}°")

with can.Bus(interface='socketcan', channel='can0') as bus:
    rs = robstride.Client(bus)

    # Position mode + enable
    rs.write_param(MID, 'run_mode', robstride.RunMode.Position)

    print("enable");
    rs.enable(MID)
    
    # Move
    while True:
        C=((math.floor(random.random()*360*2)-360)/10)*10
        print("go to {C:.2f}");
        moveTo(rs,C);

    print("disable");
    rs.disable(MID)
