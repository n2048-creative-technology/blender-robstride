
bearing_inner_diameter=50;
bearing_outer_diameter=65;
ring_offset=1;
bearing_height=7;
inter_ring_depth=0.2;

motor_total_height = 38;

wall_thickness = 8;
top_thickness = 3.5;
print_offset = 0.2;

electronics_height=26;

box_outer=100;

a=78.5;
b=43;
c=38;


//%translate([0,0,motor_total_height+wall_thickness-2]) bearing();
%translate([0,0,30]) base_box();
translate([0,0,-20]) weight_box();
!# translate([0,0,10]) control_box();

module control_box(){
    
    difference(){
    translate([0,0,-electronics_height]){

    
        linear_extrude(electronics_height+5){
difference(){            

 offset(print_offset) offset(wall_thickness) square(box_outer-2*wall_thickness,center=true);
               offset(print_offset) offset(wall_thickness-3) square(box_outer-2*wall_thickness,center=true);
for(i=[0:90:360]) rotate(i) translate([box_outer/2-wall_thickness,box_outer/2-wall_thickness])  
                   offset(wall_thickness) circle(d=5+print_offset*2);
            }
        }
        
        linear_extrude(electronics_height){
            difference(){
               offset(wall_thickness) square(box_outer-wall_thickness,center=true);
               offset(print_offset) offset(wall_thickness-3) square(box_outer-2*wall_thickness,center=true);
            }
        }
        
        
        
        linear_extrude(electronics_height){
               for(i=[0:90:360]) rotate(i) translate([box_outer/2-wall_thickness,box_outer/2-wall_thickness])         difference(){
                   offset(wall_thickness) circle(d=5+print_offset);  
     circle(d=5+print_offset);  
                   
            }
        }    
    }
    
    translate([0,box_outer/2,-electronics_height+6]){
    linear_extrude(electronics_height-10) square([box_outer-5*wall_thickness,box_outer],center=true);
}
}
}

module weight_box(){
    translate([0,0,-motor_total_height]){

        linear_extrude(motor_total_height+4){
            difference(){
                offset(wall_thickness-3) square(box_outer-2*wall_thickness,center=true);
               offset(print_offset) offset(wall_thickness-6) square(box_outer-2*wall_thickness,center=true);
               for(i=[0:90:360]) rotate(i) translate([box_outer/2-wall_thickness,box_outer/2-wall_thickness])  
                   offset(wall_thickness) circle(d=5+print_offset*2);                 
            }
        }

        
        linear_extrude(motor_total_height){
            difference(){
               offset(wall_thickness) square(box_outer-wall_thickness,center=true);
               offset(print_offset) offset(wall_thickness-3) square(box_outer-2*wall_thickness,center=true);
            }
        }
        
        translate([0,0,-top_thickness])
        linear_extrude(top_thickness){
            difference(){
                offset(wall_thickness) square(box_outer-wall_thickness,center=true);
                for(i=[0:90:360]) rotate(i) translate([box_outer/2-wall_thickness,box_outer/2-wall_thickness]) circle(d=5+print_offset);                
            }
        }
        
        
        linear_extrude(motor_total_height){
               for(i=[0:90:360]) rotate(i) translate([box_outer/2-wall_thickness,box_outer/2-wall_thickness])         difference(){
                   offset(wall_thickness) circle(d=5+print_offset);  
     circle(d=5+print_offset);  
                   
            }
        }    
    }
}

module base_box($fn=180){    
    translate([0,0,15]) linear_extrude(motor_total_height-15){
        difference(){
           offset(wall_thickness) circle(d=a);
           offset(print_offset) circle(d=a);
        }
    }  

    linear_extrude(15){
        difference(){
           offset(wall_thickness) circle(d=a);
           offset(print_offset) circle(d=a);
           translate([-(wall_thickness+a)/2,0]) square(18,center=true);
        }
    }    
    
    linear_extrude(motor_total_height){
        difference(){
           offset(wall_thickness) square(box_outer-wall_thickness,center=true);
           offset(print_offset) offset(wall_thickness) square(box_outer-2*wall_thickness,center=true);
        }
    }
    
    translate([0,0,motor_total_height])
    linear_extrude(top_thickness+bearing_height/2+1){
        difference(){
            offset(wall_thickness) square(box_outer-wall_thickness,center=true);
            offset(print_offset) circle(d=b);
            for(i=[0:40:360]) rotate(i) translate([73/2,0]) circle(d=3+print_offset);
            for(i=[0:90:360]) rotate(i) translate([box_outer/2-wall_thickness,box_outer/2-wall_thickness]) circle(d=5+print_offset);                
        }
    }
    
    
    linear_extrude(motor_total_height){
           for(i=[0:90:360]) rotate(i) translate([box_outer/2-wall_thickness,box_outer/2-wall_thickness])         difference(){
               offset(wall_thickness) circle(d=5+print_offset);  
 circle(d=5+print_offset);  
               
        }
    }    
}

module bearing($fn=180){
    translate([0,0,bearing_height/2]){
        linear_extrude(bearing_height,center=true) {
            // outer ring
            difference(){
                circle(d=bearing_outer_diameter);
                offset(-ring_offset) circle(d=bearing_outer_diameter);
            }
            // inner ring
            difference(){
                offset(ring_offset) circle(d=bearing_inner_diameter);
                circle(d=bearing_inner_diameter);
            }
        }
        //inter ring
        linear_extrude(bearing_height-2*inter_ring_depth,center=true) {
            difference(){
                circle(d=bearing_outer_diameter-ring_offset);
                circle(d=bearing_inner_diameter+ring_offset);
            }
        }
    }

}