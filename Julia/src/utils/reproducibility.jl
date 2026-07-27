# julia/src/utils/reproducibility.jl

function set_global_determinism(seed::Int = 42)
    """Set all random seeds and deterministic flags."""
    ENV["PYTHONHASHSEED"] = string(seed)
    ENV["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    
    Random.seed!(seed)
    Random.seed!(seed)
    np.random.seed(seed)
    
    # JAX
    JAX.config.update("jax_default_prng_impl", "threefry")
    JAX.config.update("jax_enable_x64", true)
    
    # PyTorch (if used)
    try
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = true
        torch.backends.cudnn.benchmark = false
        torch.use_deterministic_algorithms(true)
    catch
    end
end

function verify_reproducibility(run_fn, seed::Int, n_runs::Int = 3)
    """Run function n times, verify identical outputs."""
    set_global_determinism(seed)
    outputs = []
    for i in 1:n_runs
        set_global_determinism(seed)
        output = run_fn()
        push!(outputs, hashlib.sha256(string(output)).hexdigest())
    end
    
    all_same = length(Set(outputs)) == 1
    return ReproducibilityReport(
        master_seed=seed,
        docker_image_hash=get_docker_image_hash(),
        git_commit=get_git_commit(),
        python_hashseed=seed,
        cublas_config=ENV["CUBLAS_WORKSPACE_CONFIG"],
        torch_deterministic=ENV["TORCH_DETERMINISTIC"] == "1",
        output_hash=outputs[1],
        passed=all_same
    )
end
