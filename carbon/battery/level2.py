"""Battery's Level-2 development variant: `optimizer.muon_spectral`.

BATTERY-CLIMB-1-REVIEW (the Test Lead's F1 review of level-climb-1) and the
Test Lead's SpecMuon rulings (2026-10-07). One bounded switch on the Muon
family: Carbon's interpretation `specmuon-carbon-v1`
(`carbon.battery.level2_specmuon`), never claimed to be the paper's exact
algorithm. Pool selection is added in a later version of this variant.

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
VERSION = "battery-l2-spectral-v1"
SPECTRAL = level2_worker.SPECTRAL
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


def variant_document(version=VERSION, *, base=None):
    """The Level-2 variant's registered document, built from this module."""
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


RECONSTRUCTIONS = {(CHALLENGE, SPECTRAL): reconstruct_spectral}
