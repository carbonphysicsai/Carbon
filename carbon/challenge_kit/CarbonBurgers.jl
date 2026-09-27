# The Burgers challenge kit, from Julia.
#
# One implementation, not a port: this calls the same Python kit - the
# challenge's own public generator and the C-04 reference solvers, byte-identical
# to the validator's - and reads its arrays back with NPZ. Available in both the
# `current` and `pde` environments.
#
#     include(CarbonBurgers_PATH)            # path printed by the kit's docs
#     data = CarbonBurgers.dataset(rand(UInt8, 32), 1000)            # Cole-Hopf
#     data = CarbonBurgers.dataset(root, 200; role="stress", method="finite_volume")
#     data["solution"]  # (count, 13, 64) array, data["initial"] (count, 64), ...
#
# Everything you compute with it is self-reported research. Final evaluation
# cases come from private roots that never leave the controller.

module CarbonBurgers

using NPZ

const PYTHON = "/opt/carbon-worker/bin/python"
const ROLES = ("train", "eval", "stress")
const METHODS = ("cole_hopf", "finite_volume", "etdrk4")

"""
    dataset(root, count; role="train", method="cole_hopf") -> Dict{String,Array}

Draw `count` cases from the challenge's public law using your own 32-byte
`root`, label them with a registered reference method, and return the arrays:
`positions`, `initial`, `viscosity`, `times`, `solution`.
"""
function dataset(root::AbstractVector{UInt8}, count::Integer; role::String="train",
                 method::String="cole_hopf")
    length(root) == 32 || throw(ArgumentError("a seed root is exactly 32 bytes"))
    count > 0 || throw(ArgumentError("count must be positive"))
    role in ROLES || throw(ArgumentError("role must be one of $(ROLES)"))
    method in METHODS || throw(ArgumentError("method must be one of $(METHODS)"))
    out = tempname() * ".npz"
    try
        run(`$PYTHON -I -m carbon.challenge_kit.burgers generate
             --root-hex $(bytes2hex(root)) --count $count --role $role
             --method $method --out $out`)
        return npzread(out)
    finally
        isfile(out) && rm(out)
    end
end

end # module
