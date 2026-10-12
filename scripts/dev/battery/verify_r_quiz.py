"""VERIFY-R legs on the battery tuning quiz, for the score proof (registry v8).

    python -m scripts.dev.battery.verify_r_quiz --work W --quiz Q

Reads the members' stored quiz predictions (`W/quiz-predictions/`, written
by `challenge_validator.tuning predict` before any reference was read) and
the quiz's settled references (`Q`), adds the panel's synthetic controls as
`score_quiz` does, and writes `W/verify-r.json` (owner-only): each member's
VERIFY-R leg at k = 1, 3 and 5 (`carbon.battery.value.verify_quiz`) and the
replay diagnostics. Nothing is solved. Prints the diagnostics only.

Then `score_proof ... --verify-r W/verify-r.json`. DEVELOPMENT only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA = "carbon.battery.verify-r-quiz.v1"


def legs(work, quiz_dir):
    """`{schema, quiz_digest, legs, diagnostics}` for every member with
    stored quiz predictions, plus the synthetic controls."""
    from carbon.battery import quiz_stratum as qs
    from carbon.battery.value import panel as pn
    from carbon.battery.value import verify_quiz as vq
    from carbon.challenge_validator import tuning

    document = tuning.load_quiz(quiz_dir)
    quiz_digest = qs.digest(document)
    contract = qs.contract(tuning.REPOSITORY)
    refs = tuning.quiz_references(quiz_dir, document, contract)
    predictions = {}
    folder = Path(work) / "quiz-predictions"
    for path in sorted(folder.glob("*.json")) if folder.exists() else ():
        bundle = tuning._read_private(path)
        if bundle.get("quiz_digest") != quiz_digest:
            raise SystemExit("refused: tuning_quiz_predictions_stale")
        predictions[bundle["member"]] = bundle["predictions"]
    if not predictions:
        raise SystemExit("refused: no stored quiz predictions")
    for kind in pn.CONTROLS:
        predictions["control-" + kind] = pn.control_predictions(kind, refs)
    by_leg, diagnostics = vq.member_scores(
        contract, document["q3"], predictions, refs, quiz_digest
    )
    return {
        "schema": SCHEMA,
        "quiz_digest": quiz_digest,
        "legs": by_leg,
        "diagnostics": diagnostics,
        "state": "DEVELOPMENT_TUNING",
        "audience": "operator only; never an agent or miner",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="verify_r_quiz")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--quiz", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="default: WORK/verify-r.json")
    args = parser.parse_args(argv)
    result = legs(args.work, args.quiz)
    out = args.out or args.work / "verify-r.json"
    if out.exists():
        out.unlink()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(result, handle, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"written": str(out), "diagnostics": result["diagnostics"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
