"""Battery's Level-3 development variant: training-time numerics, a menu.

BATTERY-CLIMB-1-REVIEW (the Test Lead's F1 review of level-climb-1,
2026-10-07). Level 3 is a declarative menu only (OWNER-GRAPHITE-DEV-LEVELS-01
F2): two choices for the polish stage, run by Carbon's own code
(`carbon.battery.level3_numerics`).

- `numerics.quasi_newton_family`: lbfgs (today's polish), bfgs, ssbfgs or
  ssbroyden.
- `numerics.line_search`: strong_wolfe (today's), backtracking or none.

**Guards** (the Test Lead's attack review, 2026-10-07):
- **Dense memory.** A dense routine's inverse Hessian is p² values. It is
  refused here, at compile and before any rebuild, when p² × the recipe's
  float size exceeds the rebuild worker's memory bound
  (`worker_memory_bytes`, the contract's envelope). The worker's bound is the
  tighter ceiling a CPU rebuild runs under; no parameter threshold is invented.
- **Evaluations.** Each line search has a fixed, recorded cap on its steps,
  and the reconstruction records the worst-case evaluations per polish step
  for the cost calculator.
- **Lane.** The dense routines are CPU_ONLY_DEV (`level3_worker`).
- **Attribution.** A diverged or non-finite polish is the candidate's own
  (its predictions fail the exam's finite-shape gate); a non-CPU device is
  Carbon's environment, never the candidate's.
- **No-op choices.** A non-default choice on a recipe without a polish stage
  changes nothing Carbon rebuilds and is refused.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from carbon.battery import level3_numerics as numerics
from carbon.battery import level3_worker
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

CHALLENGE = BATTERY_CHALLENGE
LEVEL = 3
VERSION = "battery-l3-numerics-v1"
QUASI_NEWTON = level3_worker.QUASI_NEWTON
LINE_SEARCH = level3_worker.LINE_SEARCH
APPLIES_TO = ("deeponet", "mlp")
BACKENDS = ("jax",)
REVIEW = {
    "reviewer": "Test Lead",
    "record": (
        "carbon/challenge_pipeline/proposals/battery-fastcharge-ageing-development-v1/"
        "climbs/level-climb-1-disposition.json (2026-10-07)"
    ),
}
AUTHORITY = (
    "OWNER-GRAPHITE-TEST-WAVE-03 section 1; OWNER-GRAPHITE-DEV-LEVELS-01 F1 and F2; "
    "the Test Lead's review of level-climb-1 (BATTERY-CLIMB-1-REVIEW)"
)
_SUMMARIES = {
    QUASI_NEWTON: (
        "The polish stage's quasi-Newton routine: memory-limited L-BFGS (today's), "
        "full-memory BFGS, self-scaled BFGS or self-scaled Broyden."
    ),
    LINE_SEARCH: (
        "The polish stage's line search: strong Wolfe (today's), Armijo "
        "backtracking, or none (the unit quasi-Newton step)."
    ),
}
_SURFACES = {
    QUASI_NEWTON: ["train", "choice", list(numerics.ROUTINES), None, "lbfgs"],
    LINE_SEARCH: ["train", "choice", list(numerics.SEARCHES), None, "strong_wolfe"],
}


def _bounds(capability_id):
    if capability_id == QUASI_NEWTON:
        return {
            "menu": list(numerics.ROUTINES),
            "default": numerics.DEFAULT["routine"],
            "dense": sorted(numerics.DENSE),
            "broyden_phi_and_self_scaling": {
                k: list(v) for k, v in sorted(numerics.BROYDEN.items())
            },
            "dense_memory": "p^2 x float size <= the worker's memory bound",
            "lane": level3_worker.LANE,
            "requires": "polish_steps > 0",
        }
    return {
        "menu": list(numerics.SEARCHES),
        "default": numerics.DEFAULT["line_search"],
        "line_search_steps_cap": dict(numerics.LINE_SEARCH_STEPS),
        "requires": "polish_steps > 0",
    }


def variant_document(version=VERSION, *, base=None):
    """The Level-3 variant's registered document, built from this module so
    the registered policy and the code cannot drift apart."""
    from carbon.reconstruction import expansion_record
    from carbon.reconstruction.capability_registry import contract

    if base is None:
        records = expansion_record.records(CHALLENGE)
        base = {
            "digest": contract(CHALLENGE).digest,
            "record_sequence": records[-1]["sequence"],
        }
    return {
        "schema": "carbon.construction-development-variant.v1",
        "version": version,
        "challenge": CHALLENGE,
        "level": LEVEL,
        "scope": "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS",
        "status": "REGISTERED_DEVELOPMENT_POLICY",
        "authority": AUTHORITY,
        "review": dict(REVIEW),
        "base_contract": dict(base),
        "participant_code": False,
        "widened": [
            {
                "id": capability_id,
                "summary": _SUMMARIES[capability_id],
                "surface": list(_SURFACES[capability_id]),
                "applies_to": list(APPLIES_TO),
                "bounds": _bounds(capability_id),
            }
            for capability_id in (QUASI_NEWTON, LINE_SEARCH)
        ],
    }


def _refused(issues):
    from carbon.reconstruction import development_variants as dv

    return dv.VariantRefused(dv.PARAMETER_REFUSED, issues=issues)


def _common(recipe, path, value, default):
    issues = []
    if recipe.family not in APPLIES_TO:
        issues.append(("development.not_applicable", path))
    if recipe.settings.get("backend", "jax") not in BACKENDS:
        issues.append(("development.backend_not_served", "/parameters/backend"))
    if value != default and not recipe.settings.get("polish_steps"):
        issues.append(("development.no_polish_stage", path))
    return issues


def memory_bound():
    """The rebuild worker's memory bound, from the contract's envelope."""
    from carbon.reconstruction.capability_registry import contract

    return int(dict(contract(CHALLENGE).document()["envelope"])["worker_memory_bytes"])


@lru_cache(maxsize=1)
def _material():
    from carbon.battery.challenge import PublicMaterial

    return PublicMaterial.load(Path(__file__).resolve().parents[2])


def parameter_count(recipe):
    """The parameters one member trains, without training it."""
    from carbon.battery import level3_training
    from carbon.battery.recipes import Structure

    material = _material()
    settings = dict(recipe.settings)
    members = settings["ensemble_members"]
    if members > 1:
        settings["steps"] //= members
    model = level3_training.NumericsMLP(recipe.family, settings, numerics.DEFAULT)
    return model.parameter_count(
        material.train, Structure(material.ocv_soc, material.ocv_v)
    )


def reconstruct_quasi_newton(value, admitted, granted):
    """Carbon's reconstruction of `numerics.quasi_newton_family`: the routine,
    and for a dense one its inverse Hessian's size against the worker's
    memory bound (refused before any rebuild)."""
    path = "/parameters/quasi_newton_family"
    recipe = admitted.construction
    issues = _common(recipe, path, value, numerics.DEFAULT["routine"])
    if issues:
        raise _refused(issues)
    record = {"routine": value, "dense": value in numerics.DENSE}
    if value in numerics.DENSE:
        itemsize = 8 if recipe.settings.get("precision") == "float64" else 4
        parameters = parameter_count(recipe)
        needed = numerics.hessian_bytes(parameters, itemsize)
        bound = memory_bound()
        if needed > bound:
            raise _refused([("development.inverse_hessian_too_large", path)])
        record.update(
            parameters=parameters,
            inverse_hessian_bytes=needed,
            memory_bound_bytes=bound,
            lane=level3_worker.LANE,
        )
    return record


def reconstruct_line_search(value, admitted, granted):
    """Carbon's reconstruction of `numerics.line_search`: the search, its
    fixed step cap and the worst-case evaluations per polish step."""
    path = "/parameters/line_search"
    issues = _common(
        admitted.construction, path, value, numerics.DEFAULT["line_search"]
    )
    if issues:
        raise _refused(issues)
    return {
        "line_search": value,
        "line_search_steps_cap": numerics.LINE_SEARCH_STEPS[value],
        "evaluations_per_polish_step": numerics.evaluations_per_step(value),
    }


RECONSTRUCTIONS = {
    (CHALLENGE, QUASI_NEWTON): reconstruct_quasi_newton,
    (CHALLENGE, LINE_SEARCH): reconstruct_line_search,
}
