Class body (){
    // x,y,z coords 
    double rx;
    double ry;
    double rz;
    // x,y,z velocities
    double vx;
    double vy;
    double vz;
    // x,y,z accelerations
    double ax;
    double ay;
    double az;
    // x,y,z force
    double fx;
    double fy;
    double fz;
    // mass
    double m;
    // Constants for newtonian calculations : 
    static const double G = 6.673e-11;

    body(double rx, double ry, double rz, double vx, double vy ,double vz, double ax, double ay, double az, double mass){
        // Initialize all body characteristics
        this.rx = rx;
        this.ry = ry;
        this.rz = rz;
        this.vx = vx;
        this.vy = vy;
        this.vz = vz;
        this.ax = ax;
        this.ay = ay;
        this.az = az;
        this.m = mass;
    }

    //Takes a step of dt and updates r,v,a values accordingly
    __global__
    void step(double dt){
        vx += fx/m;
        vy += fy/m;
        vz += fz/m;
        rx += vx * dt;
        ry += vy * dt;
        rz += vz * dt;
    }

    // allows this body to calc distance to another body
    __global__
    double distance_to (Body* other){
        // Differences in current position
        double dx = other->rx - this.rx;
        double dy = other->ry - this.ry;
        double dz = other->rz - this.rz;
        // Pythagoreon theorem dist:
        double squared_dist = (dx^2) * (dy^2) * (dz^2);
        return (std::sqrt(squared_dist));
    }

    // This adds the force from other body into respective f(x,y,z) of this body 
    // unsure if this function needs to be a kernel or if a higher level one will be, will learn which is correct whem making main sim functions
    __global__ 
    void add_force(Body* other){
        // F = G *(m1 * m2) / (d)^2
        double F = G * this.m * other->m / (distance_to(other)); 

        // F_ = F * cos(theta) [theta = angle between x axis and F vector]
        // Deriving this, I can demonstrate how Fx (force in X direction) = F * dx/r (dx = difference in x coordinate; r = distance vector)
        // First consider a triangle where the base side is dx. now make the hypotenuse of this triangle the distance vector. This is guaranteed to be possible because dx starts from the same place at r, and therefore same place as F.
        // Now we have a 2 dimensional triangle, where dx is the base width, hypotenuse is r. This triangle will be 2d on an auxillary axis '1'.
        // In this situation we know Fx = F cos(phi), where phi = angle between r and x axis measuring on axis '1' and x axis. 
        // cos(phi) = dx/r 
        // Fx = F * dx/r 
        double dx = other->rx - this.rx;
        double dy = other->ry - this.ry;
        double dz = other->rz - this.rz;
        fx += F * dx/r
        fy += F * dy/r
        fz += F * dz/r

    }







}