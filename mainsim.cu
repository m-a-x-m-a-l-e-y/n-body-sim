#include "bodies.cu"
#include <cmath>

// Constant for newtonian calculations : 
static const double G = 6.673e-11;
static const double Mass_Sun = 1.9884e30; // kg 
static const double Mass_Earth = 5.9722e24; 
static const double Mass_Moon = 7.35e22;
static const double[] Sun_Position = {0,0,0}; // x , y, z
static const double[] Earth_Position = {150*10e6, 0, 0};
static const double[] Moon_Position = {Earth_Position[0] + 384*10e3,0,0};

// Functions list 
template <typename T> void step(T);
template <typename T> T distance_to (Body*);
void add_force(Body* );
template <typename T> T circular_orbit_velocity(Body*);


template<typename T>
__global__ run(){
    // Create bodies:
    Gravitational<double> Sun = { .rx = 0, .ry = 0, .rz = 0,
                          .vx = 0, .vy = 0, .vz = 0,
                          .Fx = 0, .Fy = 0, .Fz = 0,
                          , .m = Mass_Sun, grav = 1};
    Gravitational<double> Earth = { .rx = Earth_Position[0], .ry = Earth_Position[1], .rz = Earth_Position[2],
                          .vx = 0, .vy = 0, .vz = 0,
                          .Fx = 0, .Fy = 0, .Fz = 0,
                          , .m = Mass_Earth, .grav = 0};
    // Gravitational<double> Moon = { .rx = 0, .ry = 0, .rz = 0,
    //                       .vx = 0, .vy = 0, .vz = 0,
    //                       .Fx = 0, .Fy = 0, .Fz = 0,
    //                       , .m = Mass_Moon , .grav = 1       }

    Earth.vx = circular_orbit_velocity<T>(&Earth, &Sun);
    
    int maximum = 1e5;
    while(iterations < maximum){

    }

    
}












//
// Function Definitions
//

// Calculates the needed velocity to go in a circular orbit based on distance from the sun  
// A circular orbit velocity can be seen as sqrt(G * M / r), where G = gravitational constant, M = mass of central body, and r = radius of orbit
// only calculated at the start
template <typename T> 
T circular_orbit_velocity(Body* orbiting, Body* central){
    T r =  orbiting->rx - central->rx;
    T M = central->m;
    T v = sqrt(G * M / r);

}


//Takes a step of dt and updates r,v,a values accordingly
// __global_
template <typename T>
void step(T dt){
    vx += Fx/m;
    vy += Fy/m;
    vz += Fz/m;
    rx += vx * dt;
    ry += vy * dt;
    rz += vz * dt;
}

// allows this body to calc distance to another body
// __global__
template <typename T> 
T distance_to (Body* other){
    // Differences in current position
    T dx = other->rx - this.rx;
    T dy = other->ry - this.ry;
    T dz = other->rz - this.rz;
    // Pythagoreon theorem dist:
    T squared_dist = (dx^2) * (dy^2) * (dz^2);
    return (std::sqrt(squared_dist));
}

// This adds the force from other body into respective f(x,y,z) of this body 
// unsure if this function needs to be a kernel or if a higher level one will be, will learn which is correct whem making main sim functions
// __global__ 
void add_force(Body* other){
    // F = G *(m1 * m2) / (d)^2
    T F = G * this.m * other->m / (distance_to<T>(other)); 

    // F_ = F * cos(theta) [theta = angle between x axis and F vector]
    // Deriving this, I can demonstrate how Fx (force in X direction) = F * dx/r (dx = difference in x coordinate; r = distance vector)
    // First consider a triangle where the base side is dx. now make the hypotenuse of this triangle the distance vector. This is guaranteed to be possible because dx starts from the same place at r, and therefore same place as F.
    // Now we have a 2 dimensional triangle, where dx is the base width, hypotenuse is r. This triangle will be 2d on an auxillary axis '1'.
    // In this situation we know Fx = F cos(phi), where phi = angle between r and x axis measuring on axis '1' and x axis. 
    // cos(phi) = dx/r 
    // Fx = F * dx/r 
    
    T dx = other->rx - this.rx;
    T dy = other->ry - this.ry;
    T dz = other->rz - this.rz;
    other->Fx += F * dx/r
    other->Fy += F * dy/r
    other->Fz += F * dz/r
}
