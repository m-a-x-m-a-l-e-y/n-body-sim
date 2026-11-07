
template <typename T>
struct step_functor
{
    T dt;
    __host__ __device__
    void operator()(Body<T>& body){
        body.step(dt);
    }
};
