"""Battery's Level 4 admission of a staged submission (development only).

The validator's development-ladder slot (VALIDATOR-25) receives a Level 4
submission as a staging envelope (`carbon.level4.staging`, the staging
contract's transport form) beside the signed strategy. `admit_envelope` runs
every check the staging contract assigns to the receiver, in order, and
returns the bytes it stores and later stages as the rebuild's workspace
(`staging.workspace(raw_manifest, files)`):

1. **Structure.** `staging.from_envelope` checks the schema, the names, the
   base64 and every digest.
2. **Binding.** The envelope's submission digest must equal the strategy's
   Level 4 field (`parameters.composition_graphs`), which the miner signed.
3. **G0 and G3.** `intake.intake`, under the owner's bounds
   (`intake.BOUNDS`), with the isolated parse. It also runs the loss gate
   under the variant's `loss_override`.
4. **G4.** `validate.validate_submission` against battery's development
   interface, at the batch the rebuild trains at, under the owner's caps.

Failures:
* a refusal is `GraphRefused`, the candidate's;
* an unset owner bound is `IntakeBlocked` and an unset cap is
  `CAPS_UNSET` (as `IntakeBlocked`), both Carbon's, never charged to the
  miner;
* a parse worker that cannot start is `IntakeInfraFailure` (`FAILED_INFRA`).

The validator imports this module, so it never reaches the variant mechanism
(`tests/invariants/test_development_variants_unreachable.py` walks it). The
battery helpers it needs are Carbon's own: the public TRAIN material, the
recipe compiler and `level4_model.dims`.
"""

from __future__ import annotations

#: The strategy field that names the submission (`carbon.battery.level4.FIELD`,
#: held equal by a test; named here so this module never imports that one).
FIELD = "composition_graphs"
#: Battery's Challenge id, as `level4_model.CHALLENGE`.
CHALLENGE = "battery-fastcharge-ageing-development-v1"


def _base(strategy):
    """The strategy without its Level 4 field: the recipe the graph replaces
    the network of."""
    parameters = {k: v for k, v in strategy["parameters"].items() if k != FIELD}
    return {**strategy, "parameters": parameters}


def interface_and_batch(strategy, *, root=None):
    """Battery's development interface for the strategy's recipe and the
    batch its rebuild trains at (`level4_model.GraphModel`): the batch size,
    capped at the TRAIN cases the recipe's `train_fraction` uses."""
    from pathlib import Path

    from carbon.level4.validate import Interface

    from . import recipes
    from .challenge import PublicMaterial
    from .compile import build_model, compile_recipe
    from .level4_model import FAMILIES, dims

    _, recipe = compile_recipe(_base(strategy))
    if recipe.family not in FAMILIES:
        from carbon.level4 import graph

        raise graph.GraphRefused("level4_family_not_served", recipe.family)
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    train = PublicMaterial.load(root).train
    model = build_model(recipe)
    model.layout = recipes.Layout(
        train.v.shape[1],
        train.q.shape[1],
        bounded_v=model.bounded_v,
        predict_v0=model.predict_v0,
        fade=model.fade,
    )
    n_in, n_out = dims(model)
    dtype = "float64" if recipe.settings["precision"] == "float64" else "float32"
    cases = len(train.case_ids)
    fraction = recipe.settings["train_fraction"]
    used = cases if fraction >= 1.0 else int(cases * fraction)
    batch = min(recipe.settings["batch_size"], used)
    interface = Interface(
        inputs=(("inputs/features", dtype, (n_in,)),), outputs=((dtype, (n_out,)),)
    )
    return interface, batch


def admit_envelope(strategy, envelope_bytes, *, loss_override, root=None):
    """`(raw_manifest, files)` of an admitted Level 4 submission, or the
    typed failure (module docstring). `envelope_bytes` is the staging
    envelope's JSON, already under the transport bound."""
    import json

    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import graph, intake, staging, validate

    from .level4_model import CAPS_UNSET

    try:
        envelope = json.loads(envelope_bytes)
    except (TypeError, ValueError, UnicodeDecodeError):
        raise graph.GraphRefused("staging_malformed") from None
    declared, raw_manifest, files = staging.from_envelope(envelope)
    parameters = strategy.get("parameters") if isinstance(strategy, dict) else None
    if not isinstance(parameters, dict) or parameters.get(FIELD) != declared:
        raise graph.GraphRefused("staging_submission_mismatch", "strategy")
    interface, batch = interface_and_batch(strategy, root=root)
    allowlist = allowlist_module.load()
    _, parsed = intake.intake(
        raw_manifest,
        files,
        allowlist=allowlist,
        challenge=CHALLENGE,
        interface=interface.digest(),
        loss_override=loss_override,
    )
    verdict = validate.validate_submission(
        parsed,
        allowlist,
        interface=interface,
        batch=batch,
        loss_override=loss_override,
    )
    if verdict["status"] != "admitted":
        raise intake.IntakeBlocked(CAPS_UNSET)
    return raw_manifest, files
