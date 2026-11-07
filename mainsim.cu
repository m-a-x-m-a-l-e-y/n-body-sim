#include <cmath>
#include <iostream>
#include <fstream>

#include "bodies.cuh"
#include "force_functor.cuh"
#include "step_functor.cuh"

#include <thrust/device_vector.h>
#include <thrust/host_vector.h>
#include <thrust/transform.h>
#include <thrust/for_each.h>
#include <thrust/execution_policy.h>

// Constant for newtonian calculations : 
// static const double G = 6.673e-11; // used in method functions not needed here
static const double Mass_Sun = 1.9884e30; // kg 
static const double Mass_Earth = 5.9722e24; 
static const double Mass_Moon = 7.35e22;
// static const double Sun_Position [] = {0,0,0}; // x , y, z
static const double Earth_Position [] = {1.49e11, 0, 0};
static const double Moon_Position [] = {Earth_Position[0] + 3.844e8,0,0};

template<typename T>
void run(int N, T dt){
    // Create bodies:
    Body <T> Sun = { .rx = 0, .ry = 0, .rz = 0,
                          .vx = 0, .vy = 0, .vz = 0,
                          .Fx = 0, .Fy = 0, .Fz = 0,
                          .m = Mass_Sun};
    // Gravitational<T> Sun = {{ .rx = 0, .ry = 0, .rz = 0,
    //                       .vx = 0, .vy = 0, .vz = 0,
    //                       .Fx = 0, .Fy = 0, .Fz = 1,
    //                       .m = Mass_Sun}, .grav = 1};
    Body <T> Earth = {.rx = Earth_Position[0], .ry = Earth_Position[1], .rz = Earth_Position[2],
                          .vx = 0, .vy = 0, .vz = 0,
                          .Fx = 0, .Fy = 0, .Fz = 0,
                          .m = Mass_Earth};
    // Gravitational <T> Earth = {{ .rx = Earth_Position[0], .ry = Earth_Position[1], .rz = Earth_Position[2],
    //                       .vx = 0, .vy = 0, .vz = 0,
    //                       .Fx = 0, .Fy = 0, .Fz = 0,
    //                       .m = Mass_Earth}, .grav = 1};
    // Moon is a temporary Passive body
    Body <T> Moon = { .rx = Moon_Position[0], .ry = Moon_Position[1], .rz = Moon_Position[2],
                          .vx = 0, .vy = 0, .vz = 0,
                          .Fx = 0, .Fy = 0, .Fz = 0,
                          .m = Mass_Moon};


    // All 3 bodies are along the X-Axis, so circular starting velocities are in the y-direction
    Earth.vy = Earth.circular_orbit_velocity(&Sun);
    Moon.vy = Moon.circular_orbit_velocity(&Earth);
    std::cout << Earth.vy <<std::endl;
    std::cout << Moon.vy << std::endl;
    
    //Add all bodies to thrust vectors ========================================
        std::vector <Body<T>> passive_bodies;
        thrust::device_vector <Body<T>> passive_bodies_D;
        // Setup gravitational bodies----------------------------
            std::vector <Body<T>> grav_bodies;
            thrust::device_vector <Body<T>> grav_bodies_D;
            // thrust::device_vector <Gravitational<T>> grav_bodies_D;
            grav_bodies.push_back(Earth);
            grav_bodies.push_back(Sun);
            // Copy over to device_vector
            grav_bodies_D = grav_bodies;
        // -------------------------------------------------------
        
        // Setup passive bodies-----------------------------------
            // Push back N-bodies
            for(size_t i = 0; i < N; i++){
                Body<T> point = { .rx = Moon_Position[0] + i * 100000, .ry = Moon_Position[1], .rz = Moon_Position[2],
                                .vx = 0, .vy = 0, .vz = 0,
                                .Fx = 0, .Fy = 0, .Fz = 0,
                                .m = Mass_Moon};
                passive_bodies.push_back(point);
            }
            // TEMP **
            // push back moon as a passive temporarily
            passive_bodies.push_back(Moon);
            // **
            // Copy over to device_vector
            passive_bodies_D = passive_bodies;
        // -------------------------------------------------------
    //========================================================================

    

    
    // Visualization Elements
    // Array for keeping VTK data ( [ [0,1,2]... ])
    std::vector<std::vector<T>> Sun_VTK;
    std::vector<std::vector<T>> Earth_VTK;
    std::vector<std::vector<T>> Moon_VTK;

    // Execution loop / end of setup >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    int maximum = 100;
    int iterations = 0;

    while(iterations < maximum){
        //==============================================================================================================================================
        // **First loop adds all the forces from the gravitational bodies onto the passive bodies
        // -- for_each uses : (device type, begin pointer, end pointer, functor to apple) -- 
        // -- runs for each passive body 'p' in the passive_bodies_D array
        // -- functor is contstructed with ptr to array of grav bodies on the gpu
            thrust::for_each(thrust::device, passive_bodies_D.begin(), passive_bodies_D.end(), force_functor<T>{thrust::raw_pointer_cast(grav_bodies_D.data()) , grav_bodies_D.size()});
        //==============================================================================================================================================
        // **Second loop adds all the forces from the gravitational bodies onto the gravitational bodies
        // -- 
            thrust::for_each(thrust::device, grav_bodies_D.begin(), grav_bodies_D.end(), force_functor<T>{thrust::raw_pointer_cast(grav_bodies_D.data()) , grav_bodies_D.size()});
        // ==============================================================================================================================================
        // **Loops 3 & 4 step everything from passive bodies and grav bodies
        // 
            thrust::for_each(thrust::device, passive_bodies_D.begin(), passive_bodies_D.end(), step_functor<T>{});
            thrust::for_each(thrust::device, grav_bodies_D.begin(), grav_bodies_D.end(), step_functor<T>{});
        //
        // ==============================================================================================================================================
        // **Optional save to array which takes a lot of extra time
        // relies on order added to vector
            Body<T> Sun_ = grav_bodies_D[1];
            Body<T> Earth_ = grav_bodies_D[0];
            Sun_VTK.push_back({Sun_.rx,Sun_.ry,Sun_.rz});
            Earth_VTK.push_back({Earth_.rx,Earth_.ry,Earth_.rz});
        // ==============================================================================================================================================


       
        iterations++;
    } 
    // >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    std::cout << "done_with_loop" << std::endl;
    std::cout << Sun_VTK.size() << std::endl;
    std::ofstream Sun_vtkstrg("sun_vtk_data.txt");
    std::ofstream Earth_vtkstrg("earth_vtk_data.txt");
    
    if(Sun_vtkstrg.is_open() && Earth_vtkstrg.is_open()){
        for(int i = 0; i < iterations; i++){
            // std::cout << i << std::endl;
            for(int j = 0; j < 3; j++){
                Sun_vtkstrg << Sun_VTK[i][j] << " ";
                Earth_vtkstrg << Earth_VTK[i][j] << " ";
            }
            Sun_vtkstrg << "\n";
            Earth_vtkstrg << "\n";
    
        }
    }


    
}

int main(){
    // Parameter 1 is how many passive bodies there are
    // Parameter 2 is how many seconds/step (dt)
    run<double>(0, 1000);
}











