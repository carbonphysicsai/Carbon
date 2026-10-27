"""Name which field makes a pool/sealed pack fail `evaluation_pack_registered_material_mismatch`.

The retention step (`lean_recipe_retention._register_retained_pack_source`)
compares five things between a prepared evaluation pack and the pack's OWN source
registration plus the task's ordered query:

  train             sha256(train role)            == trusted_job.train_digest
  interface         sha256(interface role)        == trusted_job.interface_digest
  physics_contract  physics_contract role (JSON)  == trusted_job.physics_contract
  case_bank         case_bank role bytes          == the ordered query (one query)
  solver            solver_evidence role (JSON)   == registration.reference

and refuses with one code for any difference. This reads the pack the same way
and prints, per field, OK or DIFF with the digests or sizes of both sides (never
a value). Read-only: it writes nothing and opens no network connection. Run it as
the receiver's user, with the receiver's own checkout, on the same pack
directories its config names:

    python -B scripts/dev/sealed_exam/pack_material_diff.py \
        --root <evaluation_pack.root> --manifest <evaluation_pack.manifest> \
        --public-root <public_root> --private-root <private_root> \
        --challenge-id electric-motor-magnetics --challenge-version 1.5 \
        [--ordered-query <the task's retained inference inputs.npz>]

Without --ordered-query the case_bank comparison is skipped and its size and
shape are printed. The task's inputs.npz is the retained `inputs.npz` of the
task (the query the receiver ran the model on).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canon(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _shape(raw):
    """Array names and shapes of an npz, never values."""
    try:
        import numpy as np

        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            return {name: list(archive[name].shape) for name in archive.files}
    except Exception as failed:  # noqa: BLE001 - a diagnostic
        return f"not an npz ({type(failed).__name__})"


def _keys_differing(left, right):
    if not (isinstance(left, dict) and isinstance(right, dict)):
        return None
    return sorted(
        key
        for key in set(left) | set(right)
        if left.get(key, "<absent>") != right.get(key, "<absent>")
    )


def compare(snapshot, public_root, private_root, ordered_query=None):
    """The five comparisons as a list of (field, ok|None, detail)."""
    source = snapshot.read_source_registration(private_root)
    job, registration = source["trusted_job"], source["benchmark_registration"]
    train = snapshot.read_role(
        public_root, "public", "train", max_bytes=16 * 1024 * 1024
    )
    interface = snapshot.read_role(public_root, "public", "interface", max_bytes=65536)
    physics = snapshot.read_json_role(
        public_root, "public", "physics_contract", max_bytes=65536
    )
    case_bank = snapshot.read_role(
        private_root, "private", "case_bank", max_bytes=16 * 1024 * 1024
    )
    solver = snapshot.read_json_role(
        private_root, "private", "solver_evidence", max_bytes=65536
    )
    rows = []
    rows.append(
        (
            "train",
            _sha(train) == job.get("train_digest"),
            f"role {_sha(train)} registered {job.get('train_digest')}",
        )
    )
    rows.append(
        (
            "interface",
            _sha(interface) == job.get("interface_digest"),
            f"role {_sha(interface)} registered {job.get('interface_digest')}",
        )
    )
    registered_physics = job.get("physics_contract")
    rows.append(
        (
            "physics_contract",
            physics == registered_physics,
            (
                f"role {_sha(_canon(physics))} registered {_sha(_canon(registered_physics))}"
                f" differing keys {_keys_differing(physics, registered_physics)}"
            ),
        )
    )
    if ordered_query is None:
        rows.append(
            (
                "case_bank",
                None,
                f"skipped (no --ordered-query); role {_sha(case_bank)} {len(case_bank)} bytes {_shape(case_bank)}",
            )
        )
    else:
        rows.append(
            (
                "case_bank",
                case_bank == ordered_query,
                (
                    f"role {_sha(case_bank)} {len(case_bank)} bytes {_shape(case_bank)}; "
                    f"ordered query {_sha(ordered_query)} {len(ordered_query)} bytes "
                    f"{_shape(ordered_query)}"
                ),
            )
        )
    reference = registration.get("reference")
    rows.append(
        (
            "solver",
            solver == reference,
            (
                f"role {_sha(_canon(solver))} registered {_sha(_canon(reference))}"
                f" differing keys {_keys_differing(solver, reference)}"
            ),
        )
    )
    return rows, {
        "pack_digest": snapshot.manifest_digest,
        "evaluation_version": source.get("evaluation_version"),
        "case_bank_kind": snapshot.private["case_bank"].get("kind"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--challenge-id", required=True)
    parser.add_argument("--challenge-version", required=True)
    parser.add_argument("--ordered-query", type=Path)
    args = parser.parse_args(argv)

    from carbon.challenge_validator.evaluation_pack import prepare_pack

    snapshot = prepare_pack(
        args.root,
        args.manifest,
        public_root=args.public_root,
        private_root=args.private_root,
        challenge_id=args.challenge_id,
        challenge_version=args.challenge_version,
    ).snapshot
    query = None if args.ordered_query is None else args.ordered_query.read_bytes()
    rows, facts = compare(snapshot, args.public_root, args.private_root, query)
    print(json.dumps(facts, sort_keys=True))
    bad = 0
    for field, ok, detail in rows:
        label = "SKIP" if ok is None else ("OK  " if ok else "DIFF")
        bad += ok is False
        print(f"{label} {field}: {detail}")
    print(f"{bad} field(s) differ")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
