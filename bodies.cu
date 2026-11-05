template <typename T>
struct Body{
    static constexpr T G = 6.673e-11;

    // x,y,z coords 
    T rx;
    T ry;
    T rz;
    // x,y,z velocities
    T vx;
    T vy;
    T vz;
    // x,y,z accelerations
    T ax;
    T ay;
    T az;
    // x,y,z force [ undecided if these need to be here or can exist outsside]
    T Fx;
    T Fy;
    T Fz;
    // mass
    T m;


    // Functions list: 
    // =============================================================================
        //  Notes ** 
        //  All functions are __host__ __device__ so they can be tested with both 
        //  methods **

        // __host__ __device__ void step(T other);
        // step() : 
        // updates values of v(x,y,z) and r(x,y,z) from the values of F(x,y,z)

        // __host__ __device__ T distance_to (Body<T>* other);
        // distance_to() :
        // calcs 3D distance between two points
        
        // __host__ __device__ void add_force(Body<T>* other);
        // add_force() : 
        // adds force due to another body onto this body (uses distance_to())

        // __host__ __device__ T circular_orbit_velocity(Body<T>* other);
        // circular_orbit_velocity():
        // calculates starting velocity to enable circular orbits
    // =============================================================================
    
    __host__ __device__ void step(){
        // first order euler partial implicit
        // update to leapfrog 
        this->vx += this->fx/this->m;
        this->vy += this->fy/this->m;
        this->vz += this->fz/this->m;
        this->rx += this->vx * this->dt;
        this->ry += this->vy * this->dt;
        this-> rz += this->vz * this->dt;
    }
    __host__ __device__ T distance_to (Body* other){
        // Differences in current position
        T dx = other->rx - this->rx;
        T dy = other->ry - this->ry;
        T dz = other->rz - this->rz;
        // Pythagoreon theorem dist:
        T squared_dist = (dx^2) * (dy^2) * (dz^2);
        return (std::sqrt(squared_dist));
    }
    
    __host__ __device__ void add_force(Body* other){
        // F = G *(m1 * m2) / (d)^2
        T r = distance_to(other);
        T F = this->G * this->m * other->m / (r); 

        // F_ = F * cos(theta) [theta = angle between x axis and F vector]
        // Deriving this, I can demonstrate how Fx (force in X direction) = F * dx/r (dx = difference in x coordinate; r = distance vector)
        // First consider a triangle where the base side is dx. now make the hypotenuse of this triangle the distance vector. This is guaranteed to be possible because dx starts from the same place at r, and therefore same place as F.
        // Now we have a 2 dimensional triangle, where dx is the base width, hypotenuse is r. This triangle will be 2d on an auxillary axis '1'.
        // In this situation we know Fx = F cos(phi), where phi = angle between r and x axis measuring on axis '1' and x axis. 
        // cos(phi) = dx/r 
        // Fx = F * dx/r 
        T dx = other->rx - this->rx;
        T dy = other->ry - this->ry;
        T dz = other->rz - this->rz;
        this->Fx += F * dx/r;
        this->Fy += F * dy/r;
        this->Fz += F * dz/r;

    }

    __host__ __device__ T circular_orbit_velocity(Body* central){
        T r =  this->rx - central->rx;
        T M = central->m;
        T v = sqrt(this->G * M / r);
        return v;
    }


};

template <typename T>
struct Gravitational : Body<T>{
    int grav;
};

