"""Custody driver: the receiver's OWN source-free inference pair on a given inputs array, from a retained artifact. No retraining.

It writes an ``inference-pair.json`` (``carbon.source-free-inference-pair.v1``: ``primary`` and ``repeat`` originals, ``inputs_digest``
computed by the same function that wrote 853db913's) that ``pool_binding`` reads as the baseline of the FRESH set. It exists so the fresh
set's baseline comes from the SAME trained state as the sealed one's (a rebuild would add training noise to the leak-attack gap).

**Same execution path as the receiver, nothing reimplemented.** The call is ``paired_inference.infer_frozen_pair`` with the arguments
``lean_recipe_retention._inference_pair_raw`` passes it, and the real container run (``runner=None``: the C-03 worker on the judge
image, the receiver's sandbox and limits); the host must have what the receiver has (Docker, the judge image, the pinned CPU kernels
``cpu_pin.require`` checks). The ledger is a calibration store of its own under ``--work``, never the official one. CPU grading image:
``accelerator`` is None (GPU_REBUILD_RULINGS: rebuild on the GPU, grade on the CPU).

**What it refuses.** Unless the recipe digest and the state digest equal the ones given (``--expect-recipe``, ``--expect-state``: both
REQUIRED), nothing runs. After the run it refuses to write unless the pair records the same two digests, the primary and the repeat
are bit-identical, and (when ``--expect-predictions-sha256`` is given) the primary's ``predictions.json`` hashes to it.

**The acceptance proof** before it touches fresh inputs: run it with ``--pack`` = the SEALED pack and no ``--inputs-npz`` (the sealed
bank's own inputs) and ``--expect-predictions-sha256`` = the retained 853db913's ``predictions.json`` sha256; it must reproduce those
bytes exactly.

    python3 infer_pair.py run --recipe recipe.json --state state.npz --image image.json \\
        --challenge electric-motor-magnetics --version 1.5 --pack PACK_ROOT --copy-hotkey HOTKEY \\
        --expect-recipe sha256:... --expect-state sha256:... --work WORKDIR --out inference-pair.json \\
        [--inputs-npz FRESH_INPUTS.npz] [--expect-predictions-sha256 sha256:...] [--identity-suffix NAME]

``--pack`` supplies the accuracy definition (its ``paired_repeat_procedure``, which the receiver reads the same way) and, unless
``--inputs-npz`` is given, the bank inputs. ``--inputs-npz`` is an ``.npz`` with one member ``inputs`` (the fresh bank's inputs in the
practice-inputs dtype). Output to stdout is digests only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PAIR_SCHEMA = "carbon.source-free-inference-pair.v1"
OWNER = "calibration"


class PairRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise PairRefused(code)


def _digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def check_digest_pin(name, value):
    _need(
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and set(value[7:]) <= set("0123456789abcdef"),
        f"{name}_must_be_a_sha256_digest",
    )


def load_inputs_npz(path, practice_inputs):
    """The fresh bank's inputs from an ``.npz`` with ONE member ``inputs``, in the practice-inputs dtype and shape."""
    import numpy as np

    with np.load(Path(path), allow_pickle=False) as loaded:
        _need(list(loaded.files) == ["inputs"], "inputs_npz_members")
        inputs = loaded["inputs"]
    _need(
        inputs.dtype == practice_inputs.dtype
        and inputs.ndim == practice_inputs.ndim
        and inputs.shape[1:] == practice_inputs.shape[1:]
        and len(inputs) > 0,
        "inputs_npz_contract",
    )
    return inputs


def verify_evidence(evidence, *, recipe_digest, state_digest, predictions_sha256=None):
    """The pair evidence must record the expected recipe and state, hold bit-identical primary and repeat predictions, and (when
    asked) reproduce the expected predictions bytes. Returns the digests-only summary.
    """
    import base64

    _need(evidence.get("schema") == PAIR_SCHEMA, "pair_schema")
    _need(evidence.get("recipe_digest") == recipe_digest, "pair_recipe_digest_differs")
    _need(evidence.get("state_digest") == state_digest, "pair_state_digest_differs")
    raw = {}
    for phase in ("primary", "repeat"):
        original = evidence[phase]["originals"]["predictions.json"]
        body = base64.b64decode(original["raw_base64"], validate=True)
        _need(original["sha256"] == _digest(body), f"pair_{phase}_changed")
        raw[phase] = body
    _need(raw["primary"] == raw["repeat"], "pair_primary_differs_from_repeat")
    got = _digest(raw["primary"])
    if predictions_sha256 is not None:
        _need(got == predictions_sha256, "predictions_do_not_reproduce")
    return {
        "recipe_digest": evidence["recipe_digest"],
        "state_digest": evidence["state_digest"],
        "inputs_digest": evidence["inputs_digest"],
        "predictions_sha256": got,
        "rows": evidence["logical_prediction_rows_per_operation"],
    }


def run_pair(
    *,
    recipe_path,
    state_path,
    image_path,
    challenge,
    version,
    pack_root,
    copy_hotkey,
    expect_recipe,
    expect_state,
    work_root,
    inputs_npz=None,
    expect_predictions_sha256=None,
    identity_suffix="leak-attack-baseline",
    pair_function=None,
):
    """Run the receiver's frozen pair and return ``(evidence, summary)``. ``pair_function`` replaces `infer_frozen_pair` in tests only."""
    import numpy as np

    from carbon.challenge_kit import physical_material
    from carbon.challenge_kit.interface_dtype import output_dtype
    from carbon.challenge_validator import calibration_grade_run as cgr
    from carbon.development_session import paired_inference
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.development_session.research_ledger import CampaignLedger

    check_digest_pin("expect_recipe", expect_recipe)
    check_digest_pin("expect_state", expect_state)
    if expect_predictions_sha256 is not None:
        check_digest_pin("expect_predictions_sha256", expect_predictions_sha256)
    recipe_bytes, state_bytes = (
        Path(recipe_path).read_bytes(),
        Path(state_path).read_bytes(),
    )
    recipe = ConstructionRecipe.from_dict(json.loads(recipe_bytes))
    # nothing runs unless this is the recipe and the trained state the baseline is pinned to
    _need(recipe.digest == expect_recipe, "recipe_digest_differs")
    _need(_digest(state_bytes) == expect_state, "state_digest_differs")

    material = physical_material.bundle_material(challenge, version)
    kit = material["construction_kit"]
    limits = material["construction_limits_document"]
    policy = limits["reconstruction_resource_policy"]
    snapshot = cgr.prepare(pack_root, challenge, version)
    roles = cgr._roles(snapshot, Path(pack_root))
    practice = material["practice_inputs"]
    if inputs_npz is None:
        bank, _adapter, _names = cgr.resolve_bank(
            snapshot, Path(pack_root), challenge, version, copy_hotkey
        )
        inputs = np.asarray(bank["inputs"], dtype=practice.dtype)
    else:
        inputs = load_inputs_npz(inputs_npz, practice)
    _need(inputs.shape[1:] == practice.shape[1:] and len(inputs) > 0, "inputs_contract")

    work_root = Path(work_root)
    work_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    ledger = CampaignLedger(work_root / "ledger")
    cgr.freeze_campaign(ledger)
    image = load_image(image_path)
    call = pair_function or paired_inference.infer_frozen_pair
    pair = call(
        ledger,
        owner=OWNER,
        identity="pair-" + snapshot.manifest_digest + "-" + identity_suffix,
        inference_image=image,
        recipe=recipe,
        challenge_binding={
            "challenge_id": kit["id"],
            "challenge_version": kit["version"],
            "train_digest": kit["train_digest"],
            "interface_digest": kit["interface_digest"],
            "construction_limits_digest": kit["construction_limits_digest"],
        },
        limits_document=limits,
        state_bytes=state_bytes,
        expected_state_digest=expect_state,
        inputs=inputs,
        expected_output_shape=(
            len(inputs),
            *tuple(material["expected_output_shape"])[1:],
        ),
        expected_output_dtype=output_dtype(material["interface_document"]),
        allowlist_bytes=material["allowlist_bytes"],
        seconds=policy["inference_wall_seconds_max"],
        total_seconds=policy["total_reconstruction_wall_seconds_max"],
        accelerator=None,
        procedure=roles["definition"].get(
            "paired_repeat_procedure", "batched_measured"
        ),
    )
    evidence = pair.evidence
    summary = verify_evidence(
        evidence,
        recipe_digest=expect_recipe,
        state_digest=expect_state,
        predictions_sha256=expect_predictions_sha256,
    )
    expected_inputs = paired_inference._digest(paired_inference._tensors(inputs=inputs))
    _need(evidence["inputs_digest"] == expected_inputs, "pair_inputs_digest_differs")
    return evidence, summary


def load_image(path):
    """The judge image identity from the manifest AS PUBLISHED: its ``schema`` key is not an identity field and is dropped; any
    other unknown key is still refused by `WorkerImageIdentity`."""
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    try:
        document = json.loads(Path(path).read_bytes())
        _need(type(document) is dict, "judge_image_unreadable")
        document.pop("schema", None)
        return WorkerImageIdentity(**document)
    except (OSError, ValueError, TypeError) as exc:
        raise PairRefused("judge_image_unreadable") from exc


def write_once(path, evidence):
    path = Path(path)
    raw = _canonical(evidence)
    with path.open("xb") as handle:  # exclusive: an existing pair is never overwritten
        handle.write(raw)
    return _digest(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    for name in ("recipe", "state", "image", "pack", "work", "out"):
        run.add_argument(f"--{name}", type=Path, required=True)
    run.add_argument("--challenge", required=True)
    run.add_argument("--version", required=True)
    run.add_argument("--copy-hotkey", required=True)
    run.add_argument("--expect-recipe", required=True)
    run.add_argument("--expect-state", required=True)
    run.add_argument("--inputs-npz", type=Path)
    run.add_argument("--expect-predictions-sha256")
    run.add_argument("--identity-suffix", default="leak-attack-baseline")
    args = parser.parse_args(argv)
    from carbon.challenge_validator import cpu_pin

    try:
        cpu_pin.require()  # the pair runs on the same pinned kernels as the receiver's
    except cpu_pin.CpuPinRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    try:
        evidence, summary = run_pair(
            recipe_path=args.recipe,
            state_path=args.state,
            image_path=args.image,
            challenge=args.challenge,
            version=args.version,
            pack_root=args.pack,
            copy_hotkey=args.copy_hotkey,
            expect_recipe=args.expect_recipe,
            expect_state=args.expect_state,
            work_root=args.work,
            inputs_npz=args.inputs_npz,
            expect_predictions_sha256=args.expect_predictions_sha256,
            identity_suffix=args.identity_suffix,
        )
        summary["file_sha256"] = write_once(args.out, evidence)
    except PairRefused as refused:
        print(f"inference pair refused: {refused.code}", file=sys.stderr)
        return 3
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
