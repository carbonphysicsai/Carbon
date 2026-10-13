"""Read pinned parameters only; never solve or adopt a gate."""

import hashlib
import json
from pathlib import Path

import pybamm

from carbon.battery import reference, truth_env

root = Path(__file__).resolve().parents[3]
lock, lock_sha = truth_env.load_lock(root)
overlay = Path("/overlay")
manifest = json.loads((overlay / truth_env.MANIFEST).read_bytes())
verified = json.loads((overlay / truth_env.VERIFIED).read_bytes())
assert manifest["lock_sha256"] == verified["lock_sha256"] == lock_sha
assert verified["base_image"] == lock["base_image"]
assert truth_env.require_truth_runtime(root) == verified["versions"]["pybamm"]
p = pybamm.ParameterValues(reference.SPEC["parameter_set"])
names = [
    "Negative electrode OCP entropic change [V.K-1]",
    "Positive electrode OCP entropic change [V.K-1]",
    "Nominal cell capacity [A.h]",
    "Total heat transfer coefficient [W.m-2.K-1]",
    "Cell cooling surface area [m2]",
    "Cell volume [m3]",
]
values = {name: float(p[name]) for name in names}
model = pybamm.lithium_ion.DFN(dict(reference.SPEC["options"]))
heat_capacity = {
    str(t): float(p.evaluate(model.param.rho_c_p_eff(pybamm.Scalar(t))))
    * values["Cell volume [m3]"]
    for t in [273.15 + x for x in reference.SPEC["input_bounds"]["t_amb_c"]]
}
negative, positive = (values[n] for n in names[:2])
assert negative == positive == 0.0
print(
    json.dumps(
        {
            "schema": "carbon.battery.physics-parameters.v1",
            "scope": "PUBLIC_DEVELOPMENT_DIAGNOSTIC",
            "solver_provenance": truth_env.provenance(root),
            "parameter_set": reference.SPEC["parameter_set"],
            "parameters": values,
            "heat_capacity_j_per_k_at_ambient_bounds": heat_capacity,
            "entropic_cooling_bound_c": 0.0,
            "maximum_protocol_current_a": reference.SPEC["input_bounds"]["c1"][1]
            * values["Nominal cell capacity [A.h]"],
            "derivation": "Both pinned electrode OCP entropic coefficients are identically zero: the reversible heat term and its cooling bound are zero throughout the declared input box.",
            "accuracy_term": "HUMAN_INPUT",
            "other_signed_heat_nonnegative_proof": "HUMAN_INPUT",
            "b9_role": "DIAGNOSTIC_ONLY",
            "gate_adoption": "HUMAN_INPUT",
            "reader_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "reference_source_sha256": hashlib.sha256(
                (root / "carbon/battery/reference.py").read_bytes()
            ).hexdigest(),
            "grid_step_s": reference.SPEC["grid_step_s"],
            "initial_rest_s": reference.SPEC["initial_rest_s"],
        },
        sort_keys=True,
        indent=2,
    )
)
