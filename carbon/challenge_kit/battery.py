"""The battery challenge's own case draw and pinned reference, for miners.

What this is: a command a miner runs on their own machine
(OWNER-MINER-OWN-MACHINE-01) to make as much battery data as they like. It
draws cases uniformly over the published input box (the practice population
`battery_research_practice`) with the validator's own draw rule
(`carbon.battery.seeds.draw_inputs`), from seed roots of the miner's own. It
then labels them with the pinned PyBaMM reference (DFN, OKane2022) in the pinned
truth image (`carbon.battery.truth.TRUTH_IMAGE` plus its hash-locked overlay),
through the same no-network, read-only container run the validator uses
(`carbon.battery.truth_env.solve_command`). Every case ends in one typed
status: OK, REFERENCE_SOLVER_FAILED, REFERENCE_TIMEOUT or FAILED_INFRA (retried
on the next run). The OK records have TRAIN v1's exact shape, so
`carbon.battery.domain.TrainingData.from_records` reads them.

What it is not: the exam. Final evaluation cases come from Carbon's private
root, which never leaves the validator, and nothing here can produce them;
what this shares with the exam is the published input box, which was already
public. Everything a miner computes with it is self-reported, and a miner
artifact is never a grading reference. Submissions are still rebuilt on the
Challenge's one pinned TRAIN version: generated data is for research, testing
and iteration. It runs on the miner's machine, not inside the research
sandbox; adding it there is a later, separately reviewed step.

    python -m carbon.challenge_kit.battery draw --root-hex <64 hex> \\
        --count 100 --out cases.json [--role train|validation|test]
    python -m carbon.challenge_kit.battery generate --root-hex <64 hex> \\
        --count 100 --workdir runs/train-a --out train-a.jsonl [--workers 4]

`generate` needs Docker and, once, network to fetch the locked wheels; the
solves themselves run with no network. A case takes about a minute of one CPU
core.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from carbon.battery import seeds, truth, truth_env
from carbon.battery.domain import INPUTS
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin

#: The miner's own draw roles. Each is a separate stream under one root.
ROLES = ("train", "validation", "test")
#: The deciding scoring rule the pin binds draws to (OD-2, frozen).
SCORING_RULE = "v1"
REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_OVERLAY = Path.home() / ".carbon" / "battery-truth-overlay"
JOBS_SCHEMA = "carbon.challenge-kit.battery.jobs.v1"


class KitRefused(ValueError):
    """The kit will not run as asked; nothing was solved."""


def pin(repository=REPOSITORY) -> dict:
    """The seed pin a deployment of this checkout commits with the deciding
    rule: this Challenge, the reference generator's identity and the rule."""
    from carbon.battery.daemon import rule_digest
    from carbon.battery.exam import RULES

    return seeds.seed_pin(
        seeds.generator_digest(repository), rule_digest(RULES[SCORING_RULE])
    )


def context(root: bytes, *, repository=REPOSITORY) -> MockContext:
    """A generation context for the miner's own 32-byte root."""
    if type(root) is not bytes or len(root) != 32:
        raise ValueError("a seed root is exactly 32 bytes")
    p = pin(repository)
    return MockContext(
        MockEntropy(root),
        SeedPin(
            ChallengeKey(*p["challenge"]),
            p["generator_version"],
            p["generator_digest"],
            p["scoring_version"],
            p["scoring_digest"],
            EvaluationBinding(bytes.fromhex(p["evaluation_binding"])),
        ),
    )


def draw(root: bytes, count: int, *, role: str = "train", repository=REPOSITORY):
    """`count` cases, uniform over the published input box: the solver jobs."""
    if role not in ROLES or type(count) is not int or count < 1:
        raise ValueError("a role of train, validation or test and a positive count")
    ctx = context(root, repository=repository)
    return [
        {"case_id": f"{role}-{i:05d}", **seeds.draw_inputs(ctx, role, i)}
        for i in range(count)
    ]


def jobs_document(jobs) -> dict:
    """What the truth service solves: the jobs and their fingerprint."""
    body = json.dumps(jobs, sort_keys=True, separators=(",", ":"))
    return {
        "schema": JOBS_SCHEMA,
        "fingerprint": "sha256:" + hashlib.sha256(body.encode()).hexdigest(),
        "jobs": jobs,
    }


def _workdir(path, document):
    """An owner-only work directory holding exactly these jobs. A directory
    from another draw is refused, so records are never mixed."""
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise KitRefused("the work directory must be owner-only")
    jobs_path = path / "jobs.json"
    if jobs_path.exists():
        held = json.loads(jobs_path.read_bytes())
        if held.get("fingerprint") != document["fingerprint"]:
            raise KitRefused("the work directory holds another draw; use a new one")
    else:
        fd = os.open(jobs_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(document, handle, sort_keys=True)
    return path


def label(
    jobs,
    workdir,
    *,
    overlay=DEFAULT_OVERLAY,
    wheels_dir=None,
    workers=1,
    timeout_s=1200.0,
    repository=REPOSITORY,
    runner=subprocess.run,
    prepare=True,
):
    """Solve `jobs` with the pinned reference in the pinned truth image.

    Builds and verifies the overlay (once; both are idempotent), then runs the
    validator's own solve container over the work directory. Resumable: OK and
    reference-failure records are kept, FAILED_INFRA is retried. Returns the
    records for these jobs, latest record per case.
    """
    document = jobs_document(list(jobs))
    path = _workdir(workdir, document)
    if prepare:
        truth_env.materialize(overlay, repository=repository, wheels_dir=wheels_dir)
        truth_env.verify(overlay, repository=repository, runner=runner)
    result = runner(
        truth_env.solve_command(
            overlay,
            path,
            repository=repository,
            workers=workers,
            timeout_s=timeout_s,
        ),
        check=False,
    )
    if result.returncode != 0:
        raise KitRefused("the truth container did not finish; see its output above")
    return records(path, document["jobs"])


def records(workdir, jobs):
    """The latest record for each job, checked against the job's own inputs."""
    path = Path(workdir) / "records.jsonl"
    latest = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                latest[record["case_id"]] = record
    out = []
    for job in jobs:
        record = latest.get(job["case_id"])
        if record is None:
            continue
        if record.get("inputs") != {k: job[k] for k in INPUTS}:
            raise KitRefused("a record does not match its job: " + job["case_id"])
        out.append(record)
    return out


def summary(jobs, found) -> dict:
    counts = {s: 0 for s in (*sorted(truth.TERMINAL), truth.FAILED_INFRA)}
    for record in found:
        counts[record["status"]] += 1
    return {
        "jobs": len(jobs),
        "unsolved": len(jobs) - len(found),
        "counts": counts,
    }


def write_dataset(found, out) -> int:
    """The OK records, in TRAIN v1's shape (.jsonl, or .jsonl.gz)."""
    body = "".join(
        json.dumps(r, sort_keys=True) + "\n" for r in found if r["status"] == truth.OK
    ).encode()
    out = Path(out)
    out.write_bytes(gzip.compress(body, mtime=0) if out.suffix == ".gz" else body)
    return body.count(b"\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (
        ("draw", "Draw cases (inputs only) into a jobs file"),
        ("generate", "Draw cases and label them with the pinned reference"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("--root-hex", required=True)
        command.add_argument("--count", type=int, required=True)
        command.add_argument("--role", choices=ROLES, default="train")
        command.add_argument("--out", type=Path, required=True)
    make = commands.choices["generate"]
    make.add_argument("--workdir", type=Path, required=True)
    make.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    make.add_argument("--wheels-dir", type=Path)
    make.add_argument("--workers", type=int, default=1)
    make.add_argument("--timeout-s", type=float, default=1200.0)
    args = parser.parse_args(argv)
    try:
        root = bytes.fromhex(args.root_hex)
        jobs = draw(root, args.count, role=args.role)
    except ValueError as refused:
        print(json.dumps({"refused": str(refused)}), file=sys.stderr)
        return 2
    if args.command == "draw":
        args.out.write_text(json.dumps(jobs_document(jobs), sort_keys=True, indent=1))
        print(json.dumps({"jobs": len(jobs), "out": str(args.out)}))
        return 0
    try:
        found = label(
            jobs,
            args.workdir,
            overlay=args.overlay,
            wheels_dir=args.wheels_dir,
            workers=args.workers,
            timeout_s=args.timeout_s,
        )
    except (KitRefused, truth_env.TruthEnvironmentError) as refused:
        print(json.dumps({"refused": str(refused)}), file=sys.stderr)
        return 2
    written = write_dataset(found, args.out)
    print(json.dumps({**summary(jobs, found), "written": written}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
