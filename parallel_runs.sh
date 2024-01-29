#!/bin/bash

# Extract the script name
n_seeds=4
script_name="gene.jax/evaluate_cgp.py"

# Set the XLA_PYTHON_CLIENT_PREALLOCATE environment variable to false to disable preallocation
export XLA_PYTHON_CLIENT_PREALLOCATE=false 

# Function to clean up and terminate the Python processes
cleanup() {
    pkill -f $script_name
    exit 1
}

# Function to print a completion message
print_completion_message() {
    local seed=$1
    echo "Python script with seed $seed is done"
}

# Set the trap to catch the interrupt signal and call the cleanup function
trap cleanup SIGINT

# Run the Python script with different envs in parallel and pipe the output and error to specific files
# envs: "halfcheetah", "walker2d", "hopper", "swimmer"
envs="halfcheetah walker2d hopper swimmer"

for env in $envs;
do
    sleep 1
    echo $script_name --task=$env "$@" 
    export XLA_PYTHON_CLIENT_MEM_FRACTION=$memory_fraction
    # Run and print a message when it ends
    python $script_name --task=$env "$@" &
done

# Wait for all background processes to finish
wait