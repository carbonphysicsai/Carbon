"""The common runner's C5 stage (VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022).

    PYTHONPATH=REPO python3 decision_stage.py KEY CONFIG FINGERPRINT

Exports the sealed batch through the producer's own source, takes each case's
reference quantity, reads the Challenge's registered U (`exam_batch_qa.registered_u`)
and runs the Challenge's thin wrapper over `sealed_exam_common.decision_check`.
Prints one public line `{batch_digest, decision, failure}`; exit 0 passes, exit 10
means the batch is unusable (one redraw, then STOP; the runner treats it like a
straddle shortfall). Nothing hidden is printed. F02 and F08 here; Motor, Cooling
and Battery move to this stage at their next payload rebuild.
"""

import importlib
import importlib.util
import json
import sys
from pathlib import Path

KEYS = {
    "f02": {
        "cid": "f02",
        "wrapper": "carbon.f02.decision_check",
        "quantity": "peak_top_c",
        "value": lambda record: record["outputs"]["peak_top_c"],
    },
    "f08": {
        "cid": "f08-ribbed-bracket",
        "wrapper": "carbon.f08.decision_check",
        "quantity": "worst_dynamic_mm_per_n",
        "value": lambda record: record["outputs"]["worst_dynamic_mm_per_n"],
    },
}


def registered_u(cid, quantity):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "exam_batch_qa", root / "scripts/dev/challenge_pools/exam_batch_qa.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.registered_u(cid)[quantity]


def decide(key, exported, u):
    """The failure kind (or None) for an export; split out so it can be tested."""
    entry = KEYS[key]
    wrapper = importlib.import_module(entry["wrapper"])
    cells = []
    for case_id, record in sorted(exported["references"].items()):
        if record.get("status") != "OK":
            raise SystemExit("refused: a non-OK reference; the batch is not checkable")
        cells.append({"design_id": case_id, entry["quantity"]: entry["value"](record)})
    return wrapper.check(cells, u)


def main(key, config, fingerprint):
    from carbon.challenge_validator.producer import Producer

    entry = KEYS[key]
    exported = Producer.from_config(config)._source(entry["cid"]).export(fingerprint)
    failure = decide(key, exported, registered_u(entry["cid"], entry["quantity"]))
    print(json.dumps({"batch_digest": fingerprint, "decision": failure is None, "failure": failure}, sort_keys=True))
    return 0 if failure is None else 10


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in KEYS:
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:4]))
