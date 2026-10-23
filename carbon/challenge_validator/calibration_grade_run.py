"""Driver for the calibration-grade tool: the real call, and a fake-runner mode.

    python -m carbon.challenge_validator.calibration_grade_run \
        --artifact DIR --pack DIR --challenge ID --version V --work DIR \
        --judge-image FILE [--control FILE --run-config FILE --run-config-digest sha256:...]
    python -m carbon.challenge_validator.calibration_grade_run ... --fake

Everything runs in custody and prints aggregates only (``calibration_grade.aggregates``).

- The **artifact** is a verified ``carbon.calibration-artifact.v1`` directory.
- The **pack** is the calibration pack (a sealed v2 batch pack or a development pack),
  sealed and read exactly as the receiver reads it (``evaluation_pack.prepare_pack``;
  ``sealed_batch_source.resolve``); the bank is the pack's, probes included.
- The **material** (kit, limits, interface, allowlist, expected output shape) is the
  Challenge version's own served material (``physical_material.bundle_material``), the
  same the receiver's configuration serves; the binding is derived from that kit, none is
  invented here.
- The **judge image** is the inference worker identity of the host (a JSON
  ``WorkerImageIdentity``), so the inference runs in the same C-03 sandbox and limits an
  official grade uses.
- The **ledger** is a calibration store under ``--work`` (its own ``CampaignLedger``): the
  official receiver ledger, custody receipts and retention are never opened or written;
  this module imports none of them (asserted by its test).
- ``--fake`` replaces only the container run: a stub worker writes the two output files
  (predictions and the inference receipt) exactly as the real program would, and the whole
  path (binding, resource policy, output checks, bank, measure, score, aggregates) runs.
  The stub's predictions come from ``--fake-predictions`` (a JSON list of rows over the
  whole bank, probes included) or, by default, are stand-in numbers (references at the cells,
  their mean at the probes): fake output is for plumbing, never for judging a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from carbon.challenge_validator import calibration_grade as cg


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def prepare(pack_root, challenge_id, version):
    """The sealed calibration pack as the receiver reads it, or a typed refusal."""
    from carbon.challenge_validator.evaluation_pack import parse_pack, prepare_pack
    from carbon.scoring import physical_dual_pack as physical

    pack_root = Path(pack_root)
    try:
        prepared = prepare_pack(
            pack_root,
            physical.MANIFEST_NAME,
            public_root=pack_root,
            private_root=pack_root,
            challenge_id=challenge_id,
            challenge_version=version,
        )
        return parse_pack(
            prepared.sealed_bytes,
            expected_digest=prepared.snapshot.manifest_digest,
            challenge_id=challenge_id,
            challenge_version=version,
        )
    except (ValueError, OSError) as exc:
        raise cg.CalibrationRefused("calibration_pack_unreadable") from exc


def resolve_bank(snapshot, pack_root, challenge_id, version, copy_hotkey=None):
    """``(bank, adapter, names)``: the sealed batch the pack carries, or the
    development bank of a development pack. With ``copy_hotkey`` (a validator's own) the
    pack is graded in the canonical form of that validator's signed copy
    (``copy_package.receive``: the copy sits beside the pack in ``.copies/<name>/``)."""
    from carbon.challenge_kit import physical_pack
    from carbon.scoring import physical_adapters, sealed_batch_source
    from carbon.scoring import physical_dual_pack as physical

    development = physical_adapters.adapter(challenge_id, version)
    if development is None:
        raise cg.CalibrationRefused("calibration_challenge_unregistered")
    try:
        sealed = sealed_batch_source.resolve(
            challenge=development.CHALLENGE,
            version=version,
            selected_pack=snapshot,
            private_root=pack_root,
            development_adapter=development,
            copy_hotkey=copy_hotkey,
        )
    except sealed_batch_source.SealedBankRefused as exc:
        raise cg.CalibrationRefused(exc.code) from exc
    if sealed is None:
        bank = physical_pack.development_bank(development.CHALLENGE, version)
        adapter = development
    else:
        bank, adapter = sealed
    return bank, adapter, physical.input_names(adapter)


def _roles(snapshot, pack_root):
    def json_role(scope, name):
        try:
            return snapshot.read_json_role(
                pack_root, scope, name, max_bytes=1024 * 1024
            )
        except ValueError as exc:
            raise cg.CalibrationRefused("calibration_role_unavailable:" + name) from exc

    try:
        train = snapshot.read_role(pack_root, "public", "train", max_bytes=16 * 1024**2)
    except ValueError as exc:
        raise cg.CalibrationRefused("calibration_role_unavailable:train") from exc
    return {
        "definition": json_role("public", "accuracy_definition"),
        "limits": json_role("public", "important_limit_definition"),
        "objective": json_role("public", "design_objective"),
        "score_pack": json_role("private", "score_pack"),
        "train": train,
    }


# ----------------------------------------------------------------- fake worker


def stub_runner(predictions_of):
    """A stand-in for the container run. ``predictions_of(inputs_bytes, control)`` returns
    the rows the program would predict; the runner writes them and the inference receipt
    under ``ledger.root/<operation>/snapshot`` and returns the worker's record, exactly the
    shape ``_infer_state`` reads back and re-checks."""

    def runner(ledger, *, identity, files, **_kwargs):
        control = json.loads(files["control.json"])
        rows = predictions_of(files["inputs.npz"], control)
        predictions = _canonical(rows)
        receipt = _canonical(
            {
                "schema": "carbon.development.bundle-inference.v1",
                "recipe_digest": control["recipe_digest"],
                "state_digest": control["state_digest"],
                "inputs_digest": control["inputs_digest"],
                "predictions_digest": _digest(predictions),
            }
        )
        operation = "operation-" + hashlib.sha256(identity.encode()).hexdigest()
        snapshot = Path(ledger.root) / operation / "snapshot"
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / "predictions.json").write_bytes(predictions)
        (snapshot / "receipt.json").write_bytes(receipt)
        return {
            "operation": operation,
            "files": {
                "predictions.json": _digest(predictions),
                "receipt.json": _digest(receipt),
            },
        }

    return runner


def _stand_in_rows(bank):
    import numpy as np

    references = np.asarray(bank["references"], dtype=float)
    present = list(bank.get("reference_present") or [True] * len(references))
    mean = np.nanmean(references[[i for i, p in enumerate(present) if p]], axis=0)
    return [
        [float(v) for v in (references[i] if present[i] else mean)]
        for i in range(len(references))
    ]


# ------------------------------------------------------------------------ run


def run(
    *,
    artifact_dir,
    pack_root,
    challenge_id,
    version,
    work_root,
    judge_image=None,
    fake=False,
    fake_predictions=None,
    control=None,
    run_config=None,
    run_config_digest=None,
    pins=None,
    copy_hotkey=None,
):
    """The aggregates for one artifact on one calibration pack. ``judge_image`` is the
    host's inference ``WorkerImageIdentity`` (required unless ``fake``)."""
    from carbon.challenge_kit import physical_material
    from carbon.challenge_kit.interface_dtype import output_dtype
    from carbon.development_session.bundle_construction_worker import (
        _checked_binding,
        verify_direct_resource_policy,
    )
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        RecipeRefused,
    )
    from carbon.development_session.research_ledger import CampaignLedger

    artifact = cg.load_artifact(artifact_dir, challenge_id=challenge_id, **(pins or {}))
    snapshot = prepare(pack_root, challenge_id, version)
    bank, adapter, names = resolve_bank(
        snapshot, Path(pack_root), challenge_id, version
    )
    roles = _roles(snapshot, Path(pack_root))

    material = physical_material.bundle_material(challenge_id, version)
    kit = material["construction_kit"]
    limits_document = material["construction_limits_document"]
    policy = limits_document["reconstruction_resource_policy"]
    try:
        recipe = ConstructionRecipe.from_dict(json.loads(artifact.recipe_bytes))
        binding = _checked_binding(
            recipe,
            {
                "challenge_id": kit["id"],
                "challenge_version": kit["version"],
                "train_digest": kit["train_digest"],
                "interface_digest": kit["interface_digest"],
                "construction_limits_digest": kit["construction_limits_digest"],
            },
        )
        verify_direct_resource_policy(binding, limits_document)
    except (RecipeRefused, ValueError) as exc:
        raise cg.CalibrationRefused(
            "calibration_recipe_" + str(getattr(exc, "code", "binding"))
        ) from exc
    if artifact.recipe_digest != recipe.digest:
        raise cg.CalibrationRefused("calibration_recipe_digest")
    if artifact.manifest["train_sha256"][-64:] != kit["train_digest"][-64:]:
        raise cg.CalibrationRefused("calibration_pin_train")

    work_root = Path(work_root)
    work_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    ledger = CampaignLedger(work_root / "ledger")
    if fake:
        rows = (
            json.loads(Path(fake_predictions).read_bytes())
            if fake_predictions is not None
            else _stand_in_rows(bank)
        )
        runner = stub_runner(lambda _inputs, _control: rows)
        image = judge_image
    else:
        if judge_image is None:
            raise cg.CalibrationRefused("calibration_judge_image_required")
        runner, image = None, judge_image
    output_shape = (len(bank["inputs"]), *tuple(material["expected_output_shape"])[1:])
    infer = cg.worker_infer(
        ledger=ledger,
        owner="calibration",
        identity="calibration-" + artifact.calibration_entry_id[7:23],
        inference_image=image,
        recipe=recipe,
        binding=binding,
        state=artifact.state_bytes,
        state_digest=artifact.state_digest,
        expected_output_shape=output_shape,
        expected_output_dtype=output_dtype(material["interface_document"]),
        allowlist_bytes=material["allowlist_bytes"],
        seconds=policy["inference_wall_seconds_max"],
        runner=runner,
    )
    return cg.grade(
        adapter=adapter,
        bank=bank,
        pack=roles["score_pack"],
        definition=roles["definition"],
        limits=roles["limits"],
        objective=roles["objective"],
        train_raw=roles["train"],
        interface_names=names,
        infer=infer,
        artifact=artifact,
        control=control,
        challenge=adapter.CHALLENGE,
        run_config=run_config,
        run_config_digest=run_config_digest,
    )


def _load_judge_image(path):
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    try:
        return WorkerImageIdentity(**json.loads(Path(path).read_bytes()))
    except (OSError, ValueError, TypeError) as exc:
        raise cg.CalibrationRefused("calibration_judge_image_unreadable") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--judge-image", type=Path)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--fake-predictions", type=Path)
    parser.add_argument("--control", type=Path)
    parser.add_argument("--run-config", type=Path)
    parser.add_argument("--run-config-digest")
    args = parser.parse_args(argv)
    try:
        result = run(
            artifact_dir=args.artifact,
            pack_root=args.pack,
            challenge_id=args.challenge,
            version=args.version,
            work_root=args.work,
            judge_image=(
                _load_judge_image(args.judge_image) if args.judge_image else None
            ),
            fake=args.fake,
            fake_predictions=args.fake_predictions,
            control=json.loads(args.control.read_bytes()) if args.control else None,
            run_config=(
                json.loads(args.run_config.read_bytes()) if args.run_config else None
            ),
            run_config_digest=args.run_config_digest,
        )
    except cg.CalibrationRefused as refused:
        print(f"calibration grade refused: {refused.code}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
