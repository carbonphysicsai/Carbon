# julia/start_server.jl
using HTTP, JSON3, Sockets
using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity
using MethodOfLines, NeuralPDE, SciMLSensitivity, ModelingToolkit

const PORT = 8083

function start_server()
    HTTP.serve(Sockets.localhost, PORT) do http::HTTP.Messages.Request
        try
            request = JSON3.read(String(http.body))
            response = handle_request(request)
            return HTTP.Response(200, JSON3.write(response))
        catch e
            @error "Request failed" exception=e
            return HTTP.Response(500, JSON3.write(Dict("error" => string(e))))
        end
    end
end

# Handle graceful shutdown
atexit(() -> println("SciML Service shutting down..."))

println("Starting SciML Ground Truth Service on port $PORT...")
start_server()
