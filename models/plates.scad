$fn=360;
difference(){
    circle(d=78.5);
    circle(d=65);
    for(i=[0:40:360]) rotate(i) translate([73/2,0]) circle(d=3.2);
    offset(1) square([70,16],center=true);
}

