# scripts/test_service.jl
using HTTP, JSON3
using Test

@testset "SciML Service Integration" begin
    @testset "Health endpoint" begin
        response = HTTP.get("http://localhost:8083/health")
        @test response.status == 200
        body = JSON3.read(String(response.body))
        @test body["status"] == "ok"
    end
    
    @testset "Adjoint endpoint" begin
        response = HTTP.post("http://localhost:8083/adjoint",
            ["Content-Type" => "application/json"],
            JSON3.write(Dict(
                "action" => "adjoint_sensitivity",
                "initial_state" => [1.0],
                "params" => Dict(),
                "loss_function" => "physics_residual"
            ))
        )
        @test response.status == 200
        body = JSON3.read(String(response.body))
        @test haskey(body, "adjoint_gradients")
    end
end
