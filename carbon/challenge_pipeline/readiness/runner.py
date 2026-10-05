"""Run the Graphite readiness gate for one challenge and level.

`run_gate` evaluates every item, combines each item's automated check with its
recorded review and any per-challenge condition, and returns a digest-bound
report. `append_history` records the run in the challenge's append-only
history so the lessons register's metrics come from data.

Fail closed: an exception in a check is a FAIL for that item. A missing,
malformed or mismatched review is REVIEW_REQUIRED, never PASS. The gate never
grants authority to run: the per-run launch checklist still applies.
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
from pathlib import Path

from . import checks as check_module
from .model import (
    CHALLENGE_TOKEN,
    FAIL,
    NOT_BUILT,
    PACKAGE,
    PASS,
    REPOSITORY,
    REVIEW_REQUIRED,
    RUNTIME,
    Result,
    digest,
    file_digest,
    load_items,
)

REPORT_SCHEMA = "carbon.challenge-pipeline.readiness-report.v1"
RUN_SCHEMA = "carbon.challenge-pipeline.readiness-run.v1"
REVIEW_SCHEMA = "carbon.challenge-pipeline.readiness-review.v1"
EVIDENCE_KINDS = ("pr", "decision", "file", "test")
#: Worst first: a combined item takes the first status any part has.
SEVERITY = (FAIL, NOT_BUILT, REVIEW_REQUIRED, PASS)
_SHA = re.compile(r"^sha256:[0-9a-f]{64}\Z")


class ReadinessRefused(ValueError):
    """The request itself is unusable (a malformed challenge token or level)."""


def check_request(challenge, level):
    if not (isinstance(challenge, str) and CHALLENGE_TOKEN.match(challenge)):
        raise ReadinessRefused("challenge_must_be_a_registered_token")
    if type(level) is not int or not 0 <= level <= 5:
        raise ReadinessRefused("level_must_be_a_ladder_level_0_to_5")


def challenge_directory(challenge, root=PACKAGE):
    return Path(root) / challenge


# -- reviews ------------------------------------------------------------------------------------
def load_review(challenge, level, item_id, root=PACKAGE):
    """The recorded review for an item as a Result: PASS or FAIL from a valid
    committed review, REVIEW_REQUIRED for a missing or malformed one."""
    path = challenge_directory(challenge, root) / "reviews" / f"{item_id}.json"
    if not path.is_file():
        return Result(REVIEW_REQUIRED, f"no recorded review (expected {path.name})")
    try:
        review = json.loads(path.read_bytes())
    except ValueError:
        return Result(REVIEW_REQUIRED, f"{path.name} is not valid JSON")
    problem = review_problem(review, challenge, level, item_id)
    if problem:
        return Result(REVIEW_REQUIRED, f"{path.name} is malformed: {problem}")
    evidence = (f"review:{file_digest(path)}", f"reviewer:{review['reviewer']}")
    status = PASS if review["decision"] == "PASS" else FAIL
    return Result(
        status,
        f"recorded review by {review['reviewer']} on {review['date']}: {review['decision']}",
        evidence,
    )


def review_problem(review, challenge, level, item_id):
    if not isinstance(review, dict):
        return "not an object"
    if review.get("schema") != REVIEW_SCHEMA:
        return "wrong schema"
    if review.get("challenge") != challenge:
        return "names another challenge"
    if review.get("level") != level or type(review.get("level")) is not int:
        return "names another level"
    if review.get("item") != item_id:
        return "names another item"
    if review.get("decision") not in ("PASS", "FAIL"):
        return "decision is not PASS or FAIL"
    reviewer = review.get("reviewer")
    if not (isinstance(reviewer, str) and reviewer.strip()):
        return "no reviewer"
    try:
        datetime.date.fromisoformat(str(review.get("date")))
    except ValueError:
        return "date is not ISO"
    evidence = review.get("evidence")
    if not (isinstance(evidence, list) and evidence):
        return "no evidence"
    for entry in evidence:
        if not (
            isinstance(entry, dict)
            and entry.get("kind") in EVIDENCE_KINDS
            and isinstance(entry.get("ref"), str)
            and entry["ref"].strip()
        ):
            return "evidence entry needs a kind and a ref"
        if "sha256" in entry and not (
            isinstance(entry["sha256"], str) and _SHA.match(entry["sha256"])
        ):
            return "evidence sha256 is malformed"
    return None


# -- conditions ---------------------------------------------------------------------------------
def load_conditions(challenge):
    document = json.loads((PACKAGE / "conditions.json").read_bytes())
    return [c for c in document["conditions"] if c["challenge"] == challenge]


def evaluate_condition(condition, repository=REPOSITORY):
    """A per-challenge condition on an item. `policy_registered`: the named
    policy version must be a key of a registry's `versions`."""
    if condition["type"] != "policy_registered":
        return Result(FAIL, f"unknown condition type {condition['type']!r}")
    try:
        registry = json.loads((Path(repository) / condition["registry"]).read_bytes())
        versions = registry["versions"]
    except (OSError, ValueError, KeyError):
        return Result(FAIL, f"condition {condition['id']}: registry unreadable")
    if condition["name"] in versions:
        return Result(
            PASS,
            f"condition {condition['id']}: {condition['name']} is registered",
            (f"{condition['name']}:{versions[condition['name']]}",),
        )
    return Result(
        FAIL,
        f"condition {condition['id']}: {condition['name']} is not registered; "
        f"{condition['note']}",
    )


# -- the run ------------------------------------------------------------------------------------
def _worst(results):
    for status in SEVERITY:
        if any(r.status == status for r in results):
            return status
    return FAIL


def _safe(function, *args):
    try:
        return function(*args)
    except Exception as error:  # noqa: BLE001 - a check that cannot run never passes
        return Result(FAIL, f"check raised {type(error).__name__}: {str(error)[:200]}")


def evaluate_item(item, ctx, root=PACKAGE):
    parts = []
    function = check_module.CHECKS.get(item["check"])
    if function is None:
        parts.append(Result(FAIL, f"unregistered check {item['check']!r}"))
    else:
        automated = _safe(function, item, ctx)
        if automated is not None:
            parts.append(automated)
    if item["kind"] in ("review", "auto+review"):
        parts.append(load_review(ctx.challenge, ctx.level, item["id"], root))
    for condition in load_conditions(ctx.challenge):
        if condition["item"] == item["id"]:
            parts.append(_safe(evaluate_condition, condition, ctx.repository))
    status = _worst(parts)
    detail = " | ".join(p.detail for p in parts if p.status != PASS) or "; ".join(
        p.detail for p in parts
    )
    evidence = [e for p in parts for e in p.evidence]
    return {
        "id": item["id"],
        "kind": item["kind"],
        "lesson": item["lesson"],
        "title": item["title"],
        "status": status,
        "detail": detail,
        "evidence": evidence,
        "evidence_digest": digest(evidence),
    }


def git_state(repository=REPOSITORY):
    def run(*args):
        try:
            done = subprocess.run(
                ["git", "-C", str(repository), *args],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return done.stdout.strip() if done.returncode == 0 else None

    sha = run("rev-parse", "HEAD")
    dirty = run("status", "--porcelain", "--untracked-files=no")
    return {
        "sha": sha or "unknown",
        "dirty": bool(dirty) if dirty is not None else None,
    }


def run_gate(challenge, level=0, *, only=None, repository=REPOSITORY, root=PACKAGE):
    """The report for one challenge at one level. Items run in gate order."""
    check_request(challenge, level)
    items = load_items()
    if only:
        unknown = set(only) - {i["id"] for i in items}
        if unknown:
            raise ReadinessRefused("unknown_item:" + ",".join(sorted(unknown)))
        items = [i for i in items if i["id"] in only]
    ctx = check_module.Context(
        challenge=challenge,
        level=level,
        repository=Path(repository),
        data=check_module.load_challenge_data(challenge),
    )
    rows = [evaluate_item(item, ctx, root) for item in items]
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in SEVERITY}
    git = git_state(repository)
    report = {
        "schema": REPORT_SCHEMA,
        "challenge": challenge,
        "level": level,
        "utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "git": git,
        "partial": bool(only),
        "items": rows,
        "counts": counts,
        "green": counts[PASS] == len(rows) and not only,
        "claims": {"authority_to_run": False, "live_run": False, "spend": False},
    }
    report["report_digest"] = digest(report)
    return report


def run_record(report):
    """The one history line for a run."""
    return {
        "schema": RUN_SCHEMA,
        "utc": report["utc"],
        "git_sha": report["git"]["sha"],
        "git_dirty": report["git"]["dirty"],
        "challenge": report["challenge"],
        "level": report["level"],
        "partial": report["partial"],
        "items": [
            {
                "id": r["id"],
                "status": r["status"],
                "evidence_digest": r["evidence_digest"],
            }
            for r in report["items"]
        ],
        "counts": report["counts"],
        "green": report["green"],
        "report_digest": report["report_digest"],
    }


def append_history(report, root=None):
    """Append the run to `<challenge>/history.jsonl` (append-only, one line)
    and write its digest-named report beside it, both under RUNTIME (outside
    `carbon/`)."""
    directory = challenge_directory(
        report["challenge"], RUNTIME if root is None else root
    )
    directory.mkdir(parents=True, exist_ok=True)
    line = json.dumps(run_record(report), sort_keys=True, separators=(",", ":")) + "\n"
    with open(directory / "history.jsonl", "a", encoding="utf-8", newline="\n") as out:
        out.write(line)
    name = report["report_digest"].split(":", 1)[1][:16]
    reports = directory / "reports"
    reports.mkdir(exist_ok=True)
    with open(reports / f"{name}.json", "w", encoding="utf-8", newline="\n") as out:
        json.dump(report, out, indent=1, sort_keys=True)
        out.write("\n")
    return directory / "history.jsonl"


def history_metrics(challenge, root=None):
    """The register's section 8 gate metrics, from the history file: items that
    failed (not PASS) on the first full run, and the date of the first green
    full run."""
    path = (
        challenge_directory(challenge, RUNTIME if root is None else root)
        / "history.jsonl"
    )
    if not path.is_file():
        return {"runs": 0, "first_run_not_passing": None, "first_green_utc": None}
    runs = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    full = [r for r in runs if not r["partial"]]
    first = full[0] if full else None
    green = next((r for r in full if r["green"]), None)
    return {
        "runs": len(runs),
        "first_run_not_passing": (
            sum(1 for i in first["items"] if i["status"] != PASS) if first else None
        ),
        "first_green_utc": green["utc"] if green else None,
    }


def render_text(report):
    lines = [
        (
            f"readiness: {report['challenge']} level {report['level']} "
            f"@ {report['git']['sha'][:12]}{' (dirty)' if report['git']['dirty'] else ''}"
        )
    ]
    for row in report["items"]:
        lines.append(
            f"{row['id']:<3} {row['status']:<16} [{row['kind']}] lesson {row['lesson']}"
        )
        lines.append(f"      {row['title'][:110]}")
        lines.append(f"      {row['detail'][:300]}")
        for entry in row["evidence"][:6]:
            lines.append(f"      evidence: {str(entry)[:160]}")
    c = report["counts"]
    lines.append(
        f"PASS {c[PASS]}  FAIL {c[FAIL]}  NOT_BUILT {c[NOT_BUILT]}  "
        f"REVIEW_REQUIRED {c[REVIEW_REQUIRED]}  green: {report['green']}  "
        f"digest {report['report_digest']}"
    )
    return "\n".join(lines)
