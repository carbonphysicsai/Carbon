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


def legs(work, quiz_dir, ext_dir=None):
    """`{schema, quiz_digest, legs, diagnostics}` for every member with
    stored quiz predictions, plus the synthetic controls."""
    from carbon.battery import quiz_stratum as qs
    from carbon.battery.value import panel as pn
    from carbon.battery.value import verify_quiz as vq
    from carbon.challenge_validator import tuning

    contract = qs.contract(tuning.REPOSITORY)

    def one(quiz, folder_name):
        document = tuning.load_quiz(quiz)
        digest = qs.digest(document)
        refs = tuning.quiz_references(quiz, document, contract)
        found = {}
        folder = Path(work) / folder_name
        for path in sorted(folder.glob("*.json")) if folder.exists() else ():
            bundle = tuning._read_private(path)
            if bundle.get("quiz_digest") != digest:
                raise SystemExit("refused: tuning_quiz_predictions_stale")
            found[bundle["member"]] = bundle["predictions"]
        return document, digest, refs, found

    document, quiz_digest, refs, predictions = one(quiz_dir, "quiz-predictions")
    scenarios = list(document["q3"])
    ext_digest = None
    if ext_dir is not None:
        # QUIZ-EXTEND-01: the extension's scenarios join VERIFY-R only; a
        # member must have predicted both, or its legs stay unscored.
        ext, ext_digest, ext_refs, ext_predictions = one(
            ext_dir, "quiz-ext-predictions"
        )
        if not ext["role"].endswith(tuning.QUIZ_EXT_ROLE_SUFFIX):
            raise SystemExit("refused: tuning_quiz_ext_not_an_extension")
        scenarios += ext["q3"]
        refs = {**refs, **ext_refs}
        predictions = {
            m: {**p, **ext_predictions.get(m, {})} for m, p in predictions.items()
        }
    if not predictions:
        raise SystemExit("refused: no stored quiz predictions")
    for kind in pn.CONTROLS:
        predictions["control-" + kind] = pn.control_predictions(kind, refs)
    by_leg, diagnostics = vq.member_scores(
        contract, scenarios, predictions, refs, quiz_digest
    )
    return {
        "schema": SCHEMA,
        "quiz_digest": quiz_digest,
        "quiz_ext_digest": ext_digest,
        "legs": by_leg,
        "diagnostics": diagnostics,
        "state": "DEVELOPMENT_TUNING",
        "audience": "operator only; never an agent or miner",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="verify_r_quiz")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--quiz", type=Path, required=True)
    parser.add_argument(
        "--quiz-ext",
        type=Path,
        help="the Q3 extension's work directory (QUIZ-EXTEND-01), optional",
    )
    parser.add_argument("--out", type=Path, help="default: WORK/verify-r.json")
    args = parser.parse_args(argv)
    result = legs(args.work, args.quiz, args.quiz_ext)
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
