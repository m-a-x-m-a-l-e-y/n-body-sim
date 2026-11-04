#include "bodies.cu"

template <typename T>
struct force_functor
{
    Body<T> * gpu_bodies_arr;
    size_t arr_size;


    __host__ __device__
    void operator()(Body<T>* input){
        for(size_t j = 0; j < arr_size; j++){
            input->add_force(gpu_bodies_arr[j]);
        }
    }
};
