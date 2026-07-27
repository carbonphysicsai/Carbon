# test/runtests.jl
using Test
using CarbonSciML

@testset "CarbonSciML" begin
    @testset "Health check" begin
        result = health_check()
        @test result["status"] == "ok"
        @test result["service"] == "carbon-sciml-ground-truth"
    end
    
    @testset "Adjoint sensitivity" begin
        # Test with mock request
        request = Dict(
            "action" => "adjoint_sensitivity",
            "initial_state" => [1.0],
            "params" => Dict(),
            "loss_function" => "physics_residual"
        )
        result = compute_adjoint_sensitivity(request)
        @test haskey(result, "adjoint_gradients")
        @test haskey(result, "rel_error")
    end
end
