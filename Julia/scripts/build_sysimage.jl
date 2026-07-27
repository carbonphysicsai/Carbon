# scripts/build_sysimage.jl
using PackageCompiler

PackageCompiler.create_sysimage(
    [:CarbonSciML, :DifferentialEquations, :NeuralPDE, :ModelingToolkit, 
     :SciMLSensitivity, :CUDA, :ReverseDiff, :CUDA],
    sysimage_path="sysimage.so",
    precompile_execution_file="precompile.jl",
    incremental=false
)
