#!/bin/bash
# How to run this script : 
# in n-body-sim directory, run ./run.sh X Y Z
# X is the number of bodies you want to simulate around the earth, moon, and sun
# Y is the number of steps you want the simulation to take
# Z is the length of a timestep (dt) between calculations
# 
# Example : 
# ./run.sh 5 100 100
# should run pretty quickly ~0.25 seconds for the whole sim after compiled
# 
# Notes :
# right now N body position and direction are random
# settings I like : 
# ./run.sh 100 10000 1000

echo "Starting run"

nvcc mainsim.cu -o sim.exe
./sim.exe $1 $2 $3
cd visualization
python3 visualize.py ./steps
cd ..