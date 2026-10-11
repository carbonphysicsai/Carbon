"""Read-only history/API capture; writes only the requested public reports."""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from carbon.challenge_pipeline.onboarding import metrics

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / "docs/development/challenge_pipeline/onboarding-metrics"


def write(name, value):
    (DIRECTORY / name).write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture-prs",
        action="store_true",
        help="read public gh metadata; no repository or PR writes",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--effort-log",
        type=Path,
        help="optional explicit active-duration events, not timestamp-derived labour",
    )
    args = parser.parse_args()
    if args.check and args.capture_prs:
        parser.error("check replays the retained capture, never refreshes it")
    sources = json.loads((DIRECTORY / "sources.json").read_text())
    observations = metrics.collect(ROOT, sources)
    if args.capture_prs:
        capture_started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        numbers = sorted(
            {o["publication_pr"] or o.get("pending_pr") for o in observations.values()}
            - {None}
        )
        if len(numbers) > 100:
            parser.error("public PR capture exceeds bound")
        prs, errors = {}, {}
        for number in numbers:
            try:
                result = subprocess.run(
                    [
                        "gh",
                        "pr",
                        "view",
                        str(number),
                        "--repo",
                        "carbonphysicsai/Carbon",
                        "--json",
                        "number,url,state,createdAt,closedAt,mergedAt,headRefOid,mergeCommit",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=30,
                )
                prs[str(number)] = json.loads(result.stdout)
            except (subprocess.SubprocessError, OSError, ValueError):
                errors[str(number)] = "API_UNAVAILABLE_NOT_ABSENCE"
        snapshot = {
            "schema": "carbon.onboarding.public-pr-capture.v1",
            "capture_started_at": capture_started_at,
            "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "prs": prs,
            "errors": errors,
        }
        write("pull-requests.json", snapshot)
    else:
        snapshot = json.loads((DIRECTORY / "pull-requests.json").read_text())
    events = json.loads(args.effort_log.read_text()) if args.effort_log else []
    report = metrics.summarize(
        observations,
        sources,
        snapshot["prs"],
        captured_at=snapshot["captured_at"],
        effort_events=events,
    )
    report["basis"] = {
        "sources_sha256": metrics.packet.digest(
            (DIRECTORY / "sources.json").read_bytes()
        ),
        "pr_snapshot_sha256": metrics.packet.digest(
            (DIRECTORY / "pull-requests.json").read_bytes()
        ),
        "effort_log_sha256": (
            metrics.packet.digest(args.effort_log.read_bytes())
            if args.effort_log
            else None
        ),
    }
    rendered = metrics.render(report)
    if args.check:
        if (
            json.loads((DIRECTORY / "report.json").read_text()) != report
            or (DIRECTORY / "report.md").read_text(encoding="utf-8") != rendered
        ):
            parser.error("retained report differs from pinned history/capture")
    else:
        write("report.json", report)
        (DIRECTORY / "report.md").write_text(rendered, encoding="utf-8", newline="\n")
    missing = [
        f"{c}/{s}: {o['path']}"
        for (c, s), o in observations.items()
        if o["coverage"] == "MISSING_OR_HISTORY_UNAVAILABLE"
    ]
    print(
        json.dumps(
            {
                "cohorts": report["cohorts"],
                "rows": len(report["rows"]),
                "missing_or_unavailable": missing,
                "slowest_recurring_observed_arrivals": report[
                    "slowest_recurring_observed_arrivals"
                ],
                "team_effort_hours": None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
