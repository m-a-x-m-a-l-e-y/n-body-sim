
template <typename T>
struct force_functor
{
    Body<T> * gpu_grav_bodies_arr;
    size_t arr_size;

    __host__ __device__
    void operator()(Body<T>& input){
        // reset force between each addition:
        input.Fx = 0;
        input.Fy = 0;
        input.Fz = 0;
        for(size_t j = 0; j < arr_size; j++){
            if(&gpu_grav_bodies_arr[j] == &input){ // Having the same gravitational body be attracted by itself blows up
                // same bodies
                continue;
            }
            else if(input.distance_to(&gpu_grav_bodies_arr[j]) == 0){
                // same point in space
                continue;
            }
            input.add_force(&gpu_grav_bodies_arr[j]);
        }
    }
};
