template <typename T>
struct Passive{
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
};
template <typename T>
struct Gravitational : public Passive<T> {
    grav;
};

