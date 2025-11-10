$fn=180;

//plateA();
//plateB();
//translate([0,0,-8])plateC();
plateD();

//!aluMount90p1();
//%motor();
//%translate([40,0,86]) rotate([0,-90]) motor();

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

module aluMount90p3(){    
        a=78.5/2;
        hull(){
           translate([a+1,a-7]) cube([5,5,50]);
           translate([a-14,a-7]) cube([20,5,4]);
        }
}

module aluMount90p2(){
    difference(){
        mount90deg();
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
        
        hull(){
           translate([a+1,a-7]) cube([5,5,50]);
           translate([a-14,a-7]) cube([20,5,4]);
        }
        hull(){
           translate([a+1,7-a]) cube([5,5,50]);
           translate([a-14,7-a]) cube([20,5,4]);
        }        
    }
}

module aluMount90p1(){
    difference(){
        mount90deg();
        a=78.5/2;
        
        translate([a+5,0,86]) 
        rotate([0,90]) linear_extrude(5,center=true)
        difference(){
            hull(){
                circle(r=a);
                translate([86,0]) square([5,2*a],center=true);             
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
}

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
    
    translate([a+5,0,100]) 
    rotate([0,90]) linear_extrude(5,center=true)
    difference(){
        hull(){
            circle(r=a);
            translate([100,0]) square([5,2*a],center=true);             
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



module plateB(l=80,e=10){
    a=30/2;
    r=8;
    b=(r^2-a^2+(l/2)^2)/(2*(a-r));
    h=a*(b+r)/b;
    t=sqrt(h^2-a^2);
    echo(a,h,t);

    
    linear_extrude(10+e)
        for(i=[0:120:360]) rotate(i) translate([0,24/2]) circle(d=4);

    translate([l,0])
    linear_extrude(10+e)
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
    
    
    linear_extrude(5+e)
    difference(){
        union(){
            circle(r=a);
            translate([l,0]) circle(r=a);        
        }
        
        circle(d=10);
        for(i=[0:60:360]) rotate(i) translate([24/2,0]) circle(d=4.2);
        translate([l,0]){
            circle(d=10);
            for(i=[0:60:360]) rotate(i) translate([24/2,0]) circle(d=4.2);
        }
    }
    
}



module plateC(){
    a=30/2;
    r=8;
    
    difference(){
        union(){
    translate([0,0,1.5]){
    linear_extrude(10)
        for(i=[0:120:360]) rotate(i) translate([0,24/2]) circle(d=4);

    linear_extrude(5)
    difference(){
        circle(r=a);    
        circle(d=10);
        for(i=[0:60:360]) rotate(i) translate([24/2,0]) circle(d=4.1);
    }
}
    
difference(){
    translate([0,0,-2]) linear_extrude(7) 
        difference() {
            circle(d=80);
            circle(d=29);
        }
        
    translate([0,25,-10]) cube([200,20,20],center=true);  
    translate([0,-25,-10]) cube([200,20,20],center=true);  
    translate([0,0,-10]) cube([200,20,20],center=true);    
        translate([0,0,-1])linear_extrude(5,center=true) for(i=[0:60:360]) rotate(i) translate([24/2,0]) circle(d=9);
    }
    
    difference(){
        translate([0,0,-28]) linear_extrude(35) {
            circle(d=80);
            translate([80/2,0])square(80,center=true);
        }
        cylinder(d=43,h=100,center=true);
    translate([0,25,-10]) cube([200,20,20],center=true);  
    translate([0,-25,-10]) cube([200,20,20],center=true);    
    translate([0,0,-10]) cube([200,20,20],center=true);    
    }
}

translate([0,0,-10]) rotate([90,0]) cylinder(d=5,h=200,center=true);
translate([30,0,-10]) rotate([90,0]) cylinder(d=5,h=200,center=true);
translate([60,0,-10]) rotate([90,0]) cylinder(d=5,h=200,center=true);
}
}



module plateD(){    
    a=78.5/2;
    
    difference(){
    linear_extrude(30,center=true)
    difference(){
        hull(){
        offset(30) circle(r=a);
            translate([-(a+30),0]) square([1,a+100],center=true);
        }
        offset(0.5) circle(r=a);
        
        translate([-10,a+15]) circle(d=5);
        translate([20,a+15]) circle(d=5);
        translate([-40,a+15]) circle(d=5);

        translate([-10,-(a+15)]) circle(d=5);
        translate([20,-(a+15)]) circle(d=5);
        translate([-40,-(a+15)]) circle(d=5);
    }
    
    translate([0,a+15]) cube([200,20,20],center=true);  
    translate([0,-(a+15)]) cube([200,20,20],center=true);  
    translate([0,0,20]) cube([200,30,30],center=true);  
        
}
    
difference(){
    translate([0,0,10])
    linear_extrude(5)    
    difference(){
        hull(){
            offset(10) circle(r=a);
        }
        for(i=[0:40:360]) rotate(i) translate([73/2,0]) circle(d=3.2);
             circle(d=65.6);
    }
        translate([0,0,20]) cube([200,30,30],center=true);  

}
   
}