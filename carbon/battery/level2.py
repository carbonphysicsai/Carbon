"""Battery's Level-2 development variant: `optimizer.muon_spectral` (v1) and
`training_data.pool_selection` (v2).

BATTERY-CLIMB-1-REVIEW (the Test Lead's F1 review of level-climb-1) and the
Test Lead's SpecMuon rulings (2026-10-07). One bounded switch on the Muon
family: Carbon's interpretation `specmuon-carbon-v1`
(`carbon.battery.level2_specmuon`), never claimed to be the paper's exact
algorithm.

**v2 (`battery-l2-v2`, BATTERY-L2-POOL-SELECTION-01)** keeps SpecMuon exactly
and adds the owner's required Level 2 permission, `pool_selection`: a
declarative choice of which published cases Carbon trains on, drawn by
Carbon from the recipe alone (`carbon.battery.pools`). v1 stays registered and
unchanged; v2 is the current Level 2 variant.
- **The pool.** v1 is TRAIN v1 only; PRACTICE is never in a pool and is
  refused by name (the Test Lead, 2026-10-07).
- **The recipe names** a registered pool version, stratum weights in [0, 2]
  (normalised), an optional input box and `cases` N. It never names a case.
- **Every family and both backends:** the selection changes the training
  data only, so it applies wherever Level 0 trains (backend parity).
- **Cost.** N is the recipe's effective TRAIN size (`train_cases`,
  TRAINING-BUDGET-02).

**Guards** (the attack review):
- **Cost.** Each step's SVD (full matrix size) and its extra forward pass are
  inside the compiled training step, so the cost calculator's F4 counts them.
- **Lane.** CPU_ONLY_DEV (`level2_worker`).
- **Attribution.** Divergence is the candidate's own (its predictions fail
  the exam's finite-shape gate).
- **Applicability.** The switch is refused unless the recipe's optimizer
  family is Muon, or when the learning-rate curve is the plateau schedule,
  which the wrapper does not drive.
"""

from __future__ import annotations

from carbon.battery import level2_specmuon as specmuon
from carbon.battery import level2_worker
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

CHALLENGE = BATTERY_CHALLENGE
LEVEL = 2
VERSION_V1 = "battery-l2-spectral-v1"
VERSION = "battery-l2-v2"
VERSIONS = (VERSION_V1, VERSION)
SPECTRAL = level2_worker.SPECTRAL
POOL = level2_worker.POOL
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
    "OWNER-GRAPHITE-TEST-WAVE-03 section 1; OWNER-GRAPHITE-DEV-LEVELS-01 F1; "
    "the Test Lead's review of level-climb-1 (BATTERY-CLIMB-1-REVIEW) and SpecMuon "
    "rulings (BATTERY-L2-SPECMUON-BUILD-01)"
)
CONSTANTS = {
    "kappa": specmuon.KAPPA,
    "top_modes": specmuon.TOP_MODES,
    "eta_sav": specmuon.ETA_SAV,
    "psi": specmuon.PSI,
}


POOL_AUTHORITY = (
    "; the owner's Level 2 data.pool_selection requirement (2026-10-07) and the "
    "Test Lead's pool_selection design acceptance (2026-10-07: PRACTICE dropped, "
    "pool v1 is TRAIN v1 only), BATTERY-L2-POOL-SELECTION-01"
)


def _pool_widened():
    from carbon.battery import pools

    (digest,) = pools.registered()
    return {
        "id": POOL,
        "summary": (
            "Which published cases Carbon trains on: a registered pool version, "
            "stratum weights, an optional input box and a case count; Carbon draws "
            "the subset from the recipe alone and never takes a case id."
        ),
        "surface": None,
        "applies_to": None,
        "bounds": {
            "pool_versions": [digest],
            "parts": ["train"],
            "refused_parts": list(pools.REFUSED_PARTS),
            "weight": [0, pools.MAX_WEIGHT],
            "box_inputs": list(pools.INPUTS),
            "cases": "1 to the pool version's size",
            "draw": pools.DRAW_SCHEMA,
            "cost": "cases counts as train_cases (TRAINING-BUDGET-02)",
        },
    }


def variant_document(version=VERSION, *, base=None):
    """The Level-2 variant's registered document, built from this module. v1
    is SpecMuon alone, byte for byte as registered; v2 adds pool selection."""
    from carbon.reconstruction import expansion_record
    from carbon.reconstruction.capability_registry import contract

    if base is None:
        records = expansion_record.records(CHALLENGE)
        base = {
            "digest": contract(CHALLENGE).digest,
            "record_sequence": records[-1]["sequence"],
        }
    if version not in VERSIONS:
        raise ValueError("unknown Level 2 variant version " + str(version))
    document = {
        "schema": "carbon.construction-development-variant.v1",
        "version": version,
        "challenge": CHALLENGE,
        "level": LEVEL,
        "scope": "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS",
        "status": "REGISTERED_DEVELOPMENT_POLICY",
        "authority": AUTHORITY + (POOL_AUTHORITY if version != VERSION_V1 else ""),
        "review": dict(REVIEW),
        "base_contract": dict(base),
        "participant_code": False,
        "widened": [
            {
                "id": SPECTRAL,
                "summary": (
                    "On the Muon optimizer family, Carbon's SpecMuon "
                    "interpretation (specmuon-carbon-v1): Muon's step with a "
                    "mode-wise RSAV correction along the gradient's dominant "
                    "singular directions."
                ),
                "surface": ["train", "bool", None, None, False],
                "applies_to": list(APPLIES_TO),
                "bounds": {
                    "interpretation": specmuon.INTERPRETATION,
                    "constants": dict(CONSTANTS),
                    "requires": "optimizer_family muon; not the plateau curve",
                    "lane": level2_worker.LANE,
                },
            }
        ],
    }
    if version != VERSION_V1:
        document["widened"].append(_pool_widened())
    return document


def _refused(issues):
    from carbon.reconstruction import development_variants as dv

    return dv.VariantRefused(dv.PARAMETER_REFUSED, issues=issues)


def reconstruct_spectral(value, admitted, granted):
    """Carbon's reconstruction of `optimizer.muon_spectral`."""
    path = "/parameters/muon_spectral"
    if value is False:
        return {"muon_spectral": False}
    recipe = admitted.construction
    settings = recipe.settings
    issues = []
    if recipe.family not in APPLIES_TO:
        issues.append(("development.not_applicable", path))
    if settings.get("backend", "jax") not in BACKENDS:
        issues.append(("development.backend_not_served", "/parameters/backend"))
    if settings.get("optimizer_family") != "muon":
        issues.append(("development.needs_muon", path))
    if settings.get("learning_rate_curve") == "train_loss_plateau":
        issues.append(("development.not_with_plateau_curve", path))
    if issues:
        raise _refused(issues)
    return {
        "muon_spectral": True,
        "interpretation": specmuon.INTERPRETATION,
        "constants": dict(CONSTANTS),
        "extra_forward_pass_per_step": True,
        "lane": level2_worker.LANE,
    }


def reconstruct_pool(value, admitted, granted):
    """Carbon's reconstruction of `training_data.pool_selection`: the drawn
    subset, from the recipe alone."""
    from carbon.battery import challenge, pools

    path = "/parameters/pool_selection"
    try:
        manifest = pools.check(value, path)
        parts = {"train": challenge.PublicMaterial.load().train}
        case_ids = pools.draw(value, parts, path)
    except pools.PoolRefused as refused:
        raise _refused(list(refused.issues)) from None
    total = sum(w for w in value["strata"].values())
    return {
        "pool_selection": True,
        "pool_version": value["pool_version"],
        "pool": manifest["version"],
        "strata": {k: w / total for k, w in sorted(value["strata"].items())},
        "box": {k: list(v) for k, v in sorted(value.get("box", {}).items())},
        "cases": value["cases"],
        "case_ids": case_ids,
        "case_ids_digest": pools.sha256(pools.canonical(case_ids)),
        "draw": pools.DRAW_SCHEMA,
    }


RECONSTRUCTIONS = {
    (CHALLENGE, SPECTRAL): reconstruct_spectral,
    (CHALLENGE, POOL): reconstruct_pool,
}
