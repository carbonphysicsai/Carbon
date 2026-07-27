# scripts/precompile.jl
using CarbonSciML
using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity

println("Precompiling...")
# Trigger compilation of critical paths
CarbonSciML.set_global_determinism(42)

# Warm up JIT
using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity
using LinearAlgebra, Statistics, CUDA

println("Precompilation complete")
