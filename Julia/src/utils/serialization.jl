# julia/src/utils/serialization.jl

function serialize_array(arr::Array) -> Dict
    """Serialize array for JSON transport"""
    return Dict(
        "data" => Array(arr),
        "shape" => collect(size(arr)),
        "eltype" => string(eltype(arr))
    )
end

function deserialize_array(data::Dict) -> Array
    """Deserialize array from JSON transport"""
    arr = reshape(data["data"], Tuple(data["shape"]))
    return convert(Array{Float64}, arr)
end

# julia/src/utils/validation.jl

function verify_reproducibility(run_fn, seed::Int, n_runs::Int = 3) -> Dict
    """Run function n times, verify identical outputs."""
    set_global_determinism(seed)
    outputs = []
    for i in 1:n_runs
        set_global_determinism(seed)
        output = run_fn()
        push!(outputs, hashlib.sha256(string(output).encode()).hexdigest())
    end
    
    all_same = length(unique(outputs)) == 1
    return Dict(
        "master_seed" => seed,
        "outputs" => outputs,
        "passed" => all_same
    )
end
