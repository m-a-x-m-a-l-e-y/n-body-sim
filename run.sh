#!/bin/bash

echo "Starting run"

nvcc mainsim.cu -o sim.exe
./sim.exe $1
cd visualization
python3 visualize.py ./steps
cd ..