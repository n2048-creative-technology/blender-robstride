$fn=180;

color("gray") motor();
color("blue"){
    translate([0,0,41.51]) bearing();
}
c1();

module motor(){
translate([-54.08,-40.16,23.53]) import("/home/mauricio/Documents/Mauricio/blender-robstride/models/RS02-body.stl");
translate([-54.08,-40.16,23.53]) import("/home/mauricio/Documents/Mauricio/blender-robstride/models/RS02-out.stl");
}


module bearing(){
    linear_extrude(7)
    difference(){
        circle(d=65);
        circle(d=50);
    }
}


module c1(){
    translate([0,0,48.5/2]){
    //wall
    difference(){
        linear_extrude(48.5,center=true) offset(5) circle(d=78.5);
        linear_extrude(50,center=true) circle(d=78.5);
    }
}
}