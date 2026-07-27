# julia/src/handlers/validate.jl

function validate_against_reference(request::Dict)
    """Validate model prediction against SciML reference solution."""
    try
        model_prediction = request["model_prediction"]
        pde_spec = request["pde_spec"]
        params = request["params"]
        
        reference = solve_pde_reference(pde_spec, params)
        
        # Compute error metrics
        error_metrics = compute_error_metrics(request["model_prediction"], reference["solution"])
        
        return Dict(
            "passes" => all(v < 1e-3 for v in error_metrics.values()),
            "error_metrics" => error_metrics,
            "reference_solution" => reference
        )
    catch e
        @error "validate_solution failed" exception=e
        return Dict("error" => string(e), "success" => false)
    end
end

function compute_error_metrics(prediction, reference)
    """Compute error metrics between prediction and reference."""
    # Convert to arrays
    pred = Float64.(prediction)
    ref = Float64.(reference)
    
    # Relative L2 error
    l2_rel = norm(prediction - reference) / (norm(reference) + 1e-12)
    
    # L-infinity error
    linf = maximum(abs.(prediction .- reference))
    
    # Conservation error
    conservation = sum(abs, prediction .- reference)
    
    return Dict(
        "l2_relative" => l2_rel,
        "linf" => linf,
        "conservation_error" => conservation
    )
end
