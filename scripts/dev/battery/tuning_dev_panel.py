"""ev4-dev-tuning-v1: the score-tuning loop's development decision data.

    python -m scripts.dev.battery.tuning_dev_panel rebuild --out DIR
    python -m scripts.dev.battery.tuning_dev_panel evaluate --out DIR \
        --ev4-predictions DIR --run5-predictions DIR

EV4's contract and development conditions with the `ev4-dev-tuning` panel:
EV4's 100 recipes, Graphite run 5's 27 rebuilds and the 10 Track A
constructions (Test Lead GO, 2026-10-05). Every member predicts the same
inputs as EV4's panel, so the existing host-CPU rebuilds (SR-B1's EV4 panel,
#609's run-5 panel) are imported as they are, each checked against its recipe
digest and seed. Only the Track A constructions are rebuilt (`rebuild`).

`evaluate` uses EV4's committed decision references (checksum-verified)
overlaid by REF-RESOLVE-01 v1's settled references. DEVELOPMENT only: EV5's
files and verification split are not used. Nothing is spent.

`--contract carbon/battery/value/contracts/ev4-dev-proof-v1.json` runs the
same steps for SCORE-PROOF-01's panel: `rebuild` also rebuilds the
registered proof members (`proof-panel-l0-v1.json`), and `evaluate` imports
them, so their decision values come from the same contract, references and
overlay as every other member's.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-dev-tuning-v1.json"
EV4_REFERENCES = (
    ROOT / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
)
SETTLED = ROOT / "docs/development/evidence/ev4-dev-refined-v1/records.jsonl.gz"


def _proof_labels():
    from carbon.battery.value import panel as pn

    return {label for label, _strategy, _seeds in pn.PROOF_L0}


def rebuild(out, contract_path=CONTRACT):
    """The Track A constructions (and, under the proof contract, the
    registered proof members), rebuilt on this host's CPU."""
    from carbon.battery.value import panel as pn
    from carbon.battery.value.contract import load
    from carbon.battery.value.experiment import (
        bundle_bytes,
        member_bundle,
        panel_inputs,
    )
    from carbon.battery.worker import DirectBackend

    contract, _ = load(contract_path)
    kinds = pn.kinds(contract["panel"])
    proof = _proof_labels() if contract["panel"] == "ev4-dev-proof" else set()
    inputs = panel_inputs(contract, ROOT)
    backend = DirectBackend(str(ROOT))
    target = Path(out) / "attack-predictions"
    target.mkdir(parents=True, exist_ok=True)
    done = []
    proof_target = Path(out) / "proof-predictions"
    proof_target.mkdir(parents=True, exist_ok=True)
    for member, label, strategy, seed in pn.members(contract["panel"]):
        if label in proof:
            path = proof_target / f"{member}.json.gz"
        elif kinds[member] == "ATTACK_CONSTRUCTION":
            path = target / f"{member}.json.gz"
        else:
            continue
        if not path.exists():
            bundle, _state = member_bundle(backend, member, strategy, seed, inputs)
            path.write_bytes(bundle_bytes(bundle))
        done.append(member)
    return {"rebuilt": done}


def evaluate(out, ev4_predictions, run5_predictions, contract_path=CONTRACT):
    from carbon.battery.value import reference_policy
    from carbon.battery.value.experiment import Experiment

    out = Path(out)
    experiment = Experiment(out / "experiment", repository=ROOT)
    if not experiment.manifest_path.exists():
        experiment.freeze(str(contract_path))
    plain = gzip.decompress(EV4_REFERENCES.read_bytes())
    recorded = (EV4_REFERENCES.parent / "references.sha256").read_text().split()[0]
    if hashlib.sha256(plain).hexdigest() != recorded:
        raise SystemExit("EV4 decision references do not match references.sha256")
    unpacked = out / "ev4-decision-references.jsonl"
    unpacked.write_bytes(plain)
    experiment.import_references(unpacked)
    imported = {}
    sources = [ev4_predictions, run5_predictions, out / "attack-predictions"]
    if (out / "proof-predictions").exists():
        sources.append(out / "proof-predictions")
    for source in sources:
        imported[str(source)] = len(experiment.import_predictions(source)["imported"])
    references = reference_policy.overlay(
        experiment.reference_map(), reference_policy.settled(SETTLED)
    )
    experiment.evaluate(references)
    results = json.loads((out / "experiment/results/results.json").read_text())
    return {
        "imported": imported,
        "members": len(results["summary"]["members"]),
        "reference_policy": reference_policy.POLICY,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tuning_dev_panel")
    parser.add_argument("command", choices=("rebuild", "evaluate"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ev4-predictions", type=Path)
    parser.add_argument("--run5-predictions", type=Path)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    args = parser.parse_args(argv)
    if args.command == "rebuild":
        result = rebuild(args.out, args.contract)
    else:
        result = evaluate(
            args.out, args.ev4_predictions, args.run5_predictions, args.contract
        )
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
