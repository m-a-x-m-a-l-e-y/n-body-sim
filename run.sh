#!/bin/bash

echo "Starting run"

nvcc mainsim.cu -o sim.exe
./sim.exe
python3 visualization/visualize.py visualization/sun_vtk_data.txt visualization/earth_vtk_data.txt visualization/moon_vtk_data.txt visualization/nbodies_vtk_data.txt -n 5