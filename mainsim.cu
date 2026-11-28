// 
// Instructions to run this file are in run.sh
//
// Things that need to be fixed:
// 


#include <cmath>
#include <iostream>
#include <fstream>
#include <chrono>
#include <random>

#include "bodies.cuh"
#include "force_functor.cuh"
#include "step_functor.cuh"
#include "initialize_velocity_functor.cuh"

#include <thrust/device_vector.h>
#include <thrust/host_vector.h>
#include <thrust/transform.h>
#include <thrust/for_each.h>
#include <thrust/execution_policy.h>

// Function definitions 
template<typename T> void print_to_timestep_files(std::vector<std::vector<T>>*,std::vector<std::vector<T>>*,std::vector<std::vector<T>>*,std::vector<std::vector<std::vector<T> > >* NBody_VTK);
//

// Constant for newtonian calculations : 
// static const double G = 6.673e-11; // used in method functions not needed here
static const double Mass_Sun = 1.9884e30; // kg 
static const double Mass_Earth = 5.9722e24; 
static const double Mass_Moon = 7.35e22;
static const double Sun_Position [] = {0,0,0}; // x , y, z
static const double Earth_Position [] = {Sun_Position[0] + 1.49e11, Sun_Position[1] + 0, Sun_Position[2] + 1e9};
static const double Moon_Position [] = {Earth_Position[0] + 3.844e8,Earth_Position[1] + 0,Earth_Position[2] + 0};
// 
template<typename T>
void run(int N, int steps,T dt){
    // Create bodies:
    Body <T> Sun = { .rx = 0, .ry = 0, .rz = 0,
                          .vx = 0, .vy = 0, .vz = 0,
                          .Fx = 0, .Fy = 0, .Fz = 0,
                          .m = Mass_Sun, .radius = 695.7e6};
    
    Body <T> Earth = {.rx = Earth_Position[0], .ry = Earth_Position[1], .rz = Earth_Position[2],
                          .vx = 0, .vy = 0, .vz = 0,
                          .Fx = 0, .Fy = 0, .Fz = 0,
                          .m = Mass_Earth, .radius = 6371e3};
    
    Body <T> Moon = { .rx = Moon_Position[0], .ry = Moon_Position[1], .rz = Moon_Position[2],
                          .vx = 0, .vy = 0, .vz = 0,
                          .Fx = 0, .Fy = 0, .Fz = 0,
                          .m = Mass_Moon, .radius = 1737e3};


    // All 3 bodies are along the X-Axis, so circular starting velocities are in the y-direction
    Earth.vy = Earth.circular_orbit_velocity(&Sun);
    Moon.vy = Earth.circular_orbit_velocity(&Sun) + Moon.circular_orbit_velocity(&Earth);
    Sun.vz = Earth.vy / 3;

    // Add Leapfrog off by 1/2 'i' offset to velocity. 
    
    //Add all bodies to thrust vectors ========================================
        
        // Setup gravitational bodies----------------------------
            std::vector <Body<T>> grav_bodies;
            thrust::device_vector <Body<T>> grav_bodies_D;
            // thrust::device_vector <Gravitational<T>> grav_bodies_D;
            grav_bodies.push_back(Earth);
            grav_bodies.push_back(Sun);
            grav_bodies.push_back(Moon);
            // Copy over to device_vector
            grav_bodies_D = grav_bodies;
        // -------------------------------------------------------
        
        // Setup passive bodies-----------------------------------
            std::vector <Body<T>> passive_bodies;
            thrust::device_vector <Body<T>> passive_bodies_D;
            // Push back N-bodies
            

            // randomization for pos and direction
            std::random_device rd;
            std::mt19937 gen(rd());
            std::uniform_real_distribution <double> r_distr(-1e11, 1e11);
            std::uniform_real_distribution <double> v_distr(-Earth.vy, Earth.vy);

            for(size_t i = 0; i < N; i++){

                Body<T> point = { .rx = r_distr(gen), .ry = r_distr(gen), .rz = r_distr(gen),
                                .vx = v_distr(gen), .vy = v_distr(gen), .vz = v_distr(gen),
                                .Fx = 0, .Fy = 0, .Fz = 0,
                                .m = 1};
                passive_bodies.push_back(point);
            }
            // Copy over to device_vector
            passive_bodies_D = passive_bodies;
        // -------------------------------------------------------
    //========================================================================

    

    
    // Visualization Elements
    // Array for keeping VTK data ( [ [0,1,2]... ])
    std::vector<std::vector<T>> Sun_VTK;
    std::vector<std::vector<T>> Earth_VTK;
    std::vector<std::vector<T>> Moon_VTK;
    std::vector<std::vector<std::vector<T>>> NBody_VTK(N); // array of N body data lists which have 3 wide vectors of values
    

    // Execution loop / end of setup >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    // int maximum = 1e6;
    int iterations = 0;

    // Timing +++++++++++++++++++++++++++++++++++++++++++++++++
    auto start = std::chrono::high_resolution_clock::now();
    // Timing +++++++++++++++++++++++++++++++++++++++++++++++++

    while(iterations < steps - 1){  // Temp fix for out of bounding with leapfrog
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
        // Initialize velocities at the v(1/2) value, after force has been computed
        // This only runs on first loop
            if(iterations == 0){
                thrust::for_each(thrust::device, grav_bodies_D.begin(), grav_bodies_D.end(), intialize_velocity_functor<T>{dt});
            }

        // ==============================================================================================================================================
        // **Loops 3 & 4 step everything from passive bodies and grav bodies
        // 
            thrust::for_each(thrust::device, passive_bodies_D.begin(), passive_bodies_D.end(), step_functor<T>{dt});
            thrust::for_each(thrust::device, grav_bodies_D.begin(), grav_bodies_D.end(), step_functor<T>{dt});
        //
        // ==============================================================================================================================================
        // **Optional save to array which takes a lot of extra time
        // relies on order added to vector
            if(iterations % 10 == 0){
                Body<T> Earth_ = grav_bodies_D[0];
                Body<T> Sun_ = grav_bodies_D[1];
                Body<T> Moon_ = grav_bodies_D[2];
                Sun_VTK.push_back({Sun_.rx,Sun_.ry,Sun_.rz});
                Earth_VTK.push_back({Earth_.rx,Earth_.ry,Earth_.rz});
                Moon_VTK.push_back({Moon_.rx,Moon_.ry,Moon_.rz});
                for(size_t i = 0; i < N; ++i){
                    Body<T> b = passive_bodies_D[i];
                    NBody_VTK[i].push_back({b.rx, b.ry, b.rz});
                }
            }

            
        // ==============================================================================================================================================


       
        iterations++;
    } 
    // >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    
    // Timing +++++++++++++++++++++++++++++++++++++++++++++++++
    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
    // Timing +++++++++++++++++++++++++++++++++++++++++++++++++
    
    
    std::cout << "Computed " << steps << " steps with timestep " << dt <<"s in " << duration.count() << "ms" << std::endl;
    std::cout << "Total computations : " << steps * (3 + N) << std::endl;
    // New printout writes out dat ato each file
    print_to_timestep_files(&Sun_VTK, &Earth_VTK, &Moon_VTK, &NBody_VTK);


    
}
template<typename T>
void print_to_timestep_files(std::vector<std::vector<T>>* Sun_VTK,  
                             std::vector<std::vector<T>>* Earth_VTK,
                             std::vector<std::vector<T>> * Moon_VTK, 
                             std::vector<std::vector<std::vector<T> > >* NBody_VTK ){
    for(size_t i = 0; i < Sun_VTK->size(); i++){
        std::string pathname = "visualization/steps/timestep_" + std::to_string(i)      + ".txt";
        std::ofstream  vtkstring(pathname);
        for (size_t j = 0; j < 3; ++j){
            vtkstring << (*Sun_VTK)  [i][j] << " ";
        }
        vtkstring << "\n";
        for (size_t j = 0; j < 3; ++j){
            vtkstring << (*Earth_VTK)[i][j] << " ";        
        }
        vtkstring << "\n";
        for (size_t j = 0; j < 3; ++j){
            vtkstring << (*Moon_VTK) [i][j] << " ";
        }
        vtkstring << "\n";
        for(size_t x = 0; x < NBody_VTK->size(); ++x){
            
            for (size_t j = 0; j < 3; ++j){
                // [x][i][j] gives the Nth vector and then i gives timestep, j gives 3 values
                vtkstring << (*NBody_VTK)[x][i][j] << " ";
            }
            vtkstring << "\n";
        }
        
    }
    
}

int main(int argc, char* argv[]){
    
    auto start = std::chrono::high_resolution_clock::now(); // Timing


    int N     = std::stoi(argv[1]);
    int steps = std::stoi(argv[2]); 
    double dt = std::stoi(argv[3]); 

    // Actual Simulation Run ==============================
    run<double>(N, steps, dt);
    // run<T>(p1,p2,p3) ...
    // Parameter 1 is how many passive bodies there are
    // Parameter 2 is how many steps are taken
    // Parameter 3 is how many seconds/step (dt)
    // ====================================================
    
    // Timing
    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start );
    std::cout << "Total simulation time : " << double(duration.count()) << "ms" << std::endl;
    // ######

    // Historical data collection an storage
    std::ofstream run_data("run_data/data.txt", std::ios::app); // Append default so we don't lose data
    run_data << "| steps : " << steps << " | dt : " << dt << " | N : "  << std::stoi(argv[argc - 1]) << " | total simulation time : " << duration.count() << "ms \n"; 
    std::cout << "| steps : " << steps << " | dt : " << dt << " | N : "  << std::stoi(argv[argc - 1]) << " | total simulation time : " << duration.count() << "ms ";
    // =====================================
}











