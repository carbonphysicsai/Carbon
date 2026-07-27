# julia/src/handlers/health.jl

function health_check()
    return Dict(
        "status" => "ok",
        "service" => "carbon-sciml-ground-truth",
        "version" => "1.0.0",
        "uptime_seconds" => (Dates.now() - SERVICE_START_TIME).value / 1000,
        "julia_version" => string(VERSION),
        "cuda_available" => CUDA.functional(),
        "julia_version" => string(VERSION),
        "threads" => Threads.nthreads(),
        "memory_gb" => round(Sys.total_memory() / 1e9, digits=2)
    )
end
