
template <typename T>
struct intialize_velocity_functor
{
    T dt;
    __host__ __device__
    void operator()(Body<T>& body){
        body.INIT_VELOCITY(dt);
    }
};
