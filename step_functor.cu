#include "bodies.cu"

template <typename T>
struct step_functor
{
    Body<T>* ptr;

    __host__ __device__
    void operator()(){
        input->step();
    }
};
