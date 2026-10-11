"""Retain the automatic public artifact timeline as JSON and a readable table."""

import argparse
import json
import sys
from pathlib import Path

from carbon.challenge_pipeline.onboarding import status

ROOT = Path(__file__).resolve().parents[3]


def render(report):
    lines = [
        f"# {report['challenge']} — recorded artifact timeline",
        "",
        f"Pinned basis: HEAD `{report['basis']['head']}`, main `{report['basis']['main']}`.",
        "",
        "Creation and main integration are **not** stage entry/exit. Git committer times below are not GitHub mergedAt API timestamps. Author times and full identities are retained in JSON. Versions are listed separately; no retrospective requalification.",
        "",
        "| Stage | Artifact | First commit UTC | First main integration UTC | Coverage |",
        "|---|---|---|---|---|",
    ]
    for stage in report["stages"]:
        for artifact in stage["artifacts"]:
            first, main = artifact.get("first_recorded"), artifact.get(
                "first_main_integration"
            )
            lines.append(
                f"| {stage['id']} | `{artifact['path']}` | {first['committed_utc'] if first else 'UNKNOWN'} | {main['committed_utc'] if main else 'UNKNOWN'} | {artifact['coverage']} |"
            )
    lines.extend(
        [
            "",
            "Stage cycle time, brief-to-tested completion, person-hours, blocked time and human effort saved: **UNKNOWN**. A runbook or grant is not a sealed bank or a run. S10 definition creation is not a tested Challenge.",
            "",
            *[f"- {limit}" for limit in report["limits"]],
            "",
        ]
    )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument(
        "--out", type=Path, help="new development report JSON (also writes .md)"
    )
    args = parser.parse_args(argv)
    report = status.generate(ROOT, args.challenge, main_ref=args.main_ref)[
        "artifact_timeline"
    ]
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out:
        target = args.out.resolve()
        directory = ROOT / "docs/development/challenge_pipeline/onboarding-timeline"
        if not target.is_relative_to(directory.resolve()) or target.suffix != ".json":
            parser.error("output must be a development onboarding-timeline JSON report")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        target.with_suffix(".md").write_text(
            render(report), encoding="utf-8", newline="\n"
        )
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
