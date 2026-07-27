# test/test_solvers.jl
using Test
using CarbonSciML

@testset "Reference Solvers" begin
    @testset "Poisson" begin
        pde_spec = Dict("type" => "poisson", "nx" => 64, "ny" => 64)
        params = Dict()
        result = solve_pde_reference(Dict("type" => "poisson"), Dict())
        @test haskey(result, "solution")
        @test haskey(result, "coords")
    end
end
