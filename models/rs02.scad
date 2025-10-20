$fn=180;

//plateA();
//plateB();
!#mount90deg();
motor();
translate([40,0,83]) rotate([0,-90]) motor();

/*
hull(){
scale(1.1)motor();
}
*/

module motor(){
translate([-54.08,-40.16,23.53]) import("/home/mauricio/Documents/Mauricio/blender-robstride/models/RS02-body.stl");
}

/*
mirror([0,0,1])rotate(-90) #translate([-53.0,-39.5,27]) import("/home/mauricio/Documents/Mauricio/blender-robstride/models/RS02-body.stl");

rotate([0,-90]) rotate(-90) translate([-53.0,5,-18]) import("/home/mauricio/Documents/Mauricio/blender-robstride/models/RS02-body.stl");
*/

module mount90deg(){
    a=78.5/2;
    linear_extrude(5,center=true)
    difference(){
        hull(){
            circle(r=a);
            translate([a+5-5,0]) square([5,2*a],center=true);             
        }
        circle(d=44);
        for(i=[0:40:360]) rotate(i) translate([73/2,0]) circle(d=3.2);
    }
    
    translate([a+5,0,83]) 
    rotate([0,90]) linear_extrude(5,center=true)
    difference(){
        hull(){
            circle(r=a);
            translate([83,0]) square([5,2*a],center=true);             
        }
        circle(d=44.);
        for(i=[0:40:360]) rotate(i) translate([73/2,0]) circle(d=3.2);
    }
    
    hull(){
       translate([a+1,a-7]) cube([5,5,50]);
       translate([a-14,a-7]) cube([20,5,4]);
    }
    hull(){
       translate([a+1,7-a]) cube([5,5,50]);
       translate([a-14,7-a]) cube([20,5,4]);
    }
    
}

module plateA(l=150){
    a=78.5/2;
    r=20;
    b=(r^2-a^2+(l/2)^2)/(2*(a-r));
    h=a*(b+r)/b;
    t=sqrt(h^2-a^2);
    echo(a,h,t);
    linear_extrude(5)
    difference(){
        union(){
            circle(r=a);
            translate([l,0]) circle(r=a);        
            translate([l/2,0]) square([l-2*t,2*h],center=true);
        }
        
        translate([l/2,b+r]) circle(r=b);
        translate([l/2,-(b+r)]) circle(r=b);
        circle(d=43.5);
        for(i=[0:40:360]) rotate(i) translate([73/2,0]) circle(d=3.2);
        translate([l,0]){
            circle(d=43.5);
            for(i=[0:40:360]) rotate(i) translate([73/2,0]) circle(d=3.2);
        }
    }
}



module plateB(l=150){
    a=30/2;
    r=8;
    b=(r^2-a^2+(l/2)^2)/(2*(a-r));
    h=a*(b+r)/b;
    t=sqrt(h^2-a^2);
    echo(a,h,t);

    linear_extrude(10)
        for(i=[0:120:360]) rotate(i) translate([0,24/2]) circle(d=4);
    translate([l,0])
    linear_extrude(10)
        for(i=[0:120:360]) rotate(i) translate([0,24/2]) circle(d=4);

    linear_extrude(5)
    difference(){
        union(){
            circle(r=a);
            translate([l,0]) circle(r=a);        
            translate([l/2,0]) square([l-2*t,2*h],center=true);
        }
        
        translate([l/2,b+r]) circle(r=b);
        translate([l/2,-(b+r)]) circle(r=b);
        circle(d=10);
        for(i=[0:60:360]) rotate(i) translate([24/2,0]) circle(d=4.2);
        translate([l,0]){
            circle(d=10);
            for(i=[0:60:360]) rotate(i) translate([24/2,0]) circle(d=4.2);
        }
    }
}