"""`python -m carbon.agent_campaign.graphite run-checked`: the supported way to
launch one live Graphite phase-3 or phase-4 session
(GRAPHITE-RUNNER-USABILITY-01 C9). It replaces hand-written launch scripts.

    python -m carbon.agent_campaign.graphite run-checked --phase 4 --root DIR \
        --challenge TOKEN --grant GRANT.json --credential-file PATH \
        --miner-profile PROFILE.json --miner-campaign ID [--session N] [--level N] [--plan]
    python -m carbon.agent_campaign.graphite run-checked --phase 3 --root DIR \
        --challenge TOKEN --grant GRANT.json --credential-file PATH \
        --miner-profile PROFILE.json --miner-campaign ID --code-ref SHA \
        --literature-snapshot SNAPSHOT.json [--allow-unchecked-cards] \
        (--runpod-key-file PATH | --compute carrier --image-manifest M) \
        [--session N] [--level N] [--plan]

A thin composition of the existing commands, run in this order:

1. **Gates**, stopping at the first refusal, before anything is spent.
   Phase 3: the grant (`phase3.load_grant`, provider `graphite`) and the code
   ref (`phase3.check_code_ref`), then the no-spend dry run (`phase3 run
   --dry-run`, which includes `pods.real_path_check`). Phase 4: `phase4
   prelive` (the grant is the committed one on main, HEAD is pushed and clean,
   and every real path runs up to the network boundary).
2. **Launch**: `phase3 run` or `phase4 run` with the same arguments.
3. **Post-run checks**, run whatever the launch's exit. Phase 3: `phase3
   reconcile` on the RunPod lane, then `phase3 status`. Phase 4: `phase4
   status` (an Attacker session launches no pod).

Each command prints its own output as before; after each step one JSON line
`{"run_checked_step": ..., "exit": ...}`, and a closing
`{"run_checked": ...}` record. `--plan` prints the steps and runs nothing.
Keys go by file path only (`--credential-file`, `--runpod-key-file`); no key
is read, printed or logged here. Nothing here decides a grant, a gate or a
result: each step is the existing command's own.
"""

from __future__ import annotations

import json
import sys

from .cli_usage import ChallengeParser, challenge_help

SCHEMA = "carbon.graphite.run-checked.v1"
PROG = "python -m carbon.agent_campaign.graphite"
#: Options only phase 3 takes. Phase 4 refuses them rather than ignore them.
PHASE3_ONLY = (
    ("--code-ref", "code_ref"),
    ("--literature-snapshot", "literature_snapshot"),
    ("--allow-unchecked-cards", "allow_unchecked_cards"),
    ("--compute", "compute"),
    ("--runpod-key-file", "runpod_key_file"),
    ("--image-manifest", "image_manifest"),
)


class Refused(SystemExit):
    """A typed refusal before any step runs (exit 2, as the phase runners)."""

    def __init__(self, code):
        print(json.dumps({"status": "REFUSED", "reason_code": code}))
        super().__init__(2)


def _step(name, stage, call, argv):
    return {"step": name, "stage": stage, "call": call, "argv": list(argv)}


def plan(args):
    """The ordered steps for `args`: gates, launch, post-run checks."""
    base = ["--root", args.root, "--challenge", args.challenge]
    session = ["--session", str(args.session), "--level", str(args.level)]
    common = [
        "--grant",
        args.grant,
        "--credential-file",
        args.credential_file,
        "--miner-profile",
        args.miner_profile,
        "--miner-campaign",
        args.miner_campaign,
    ]
    if args.phase == 4:
        given = [flag for flag, field in PHASE3_ONLY if getattr(args, field)]
        if given:
            raise Refused("phase_4_takes_no: " + ", ".join(given))
        return [
            _step(
                "gate.prelive",
                "gate",
                "phase4.main",
                ["prelive", *base, "--grant", args.grant],
            ),
            _step("launch", "launch", "phase4.main", ["run", *base, *common, *session]),
            _step(
                "post.status", "post", "phase4.main", ["status", "--root", args.root]
            ),
        ]
    compute = args.compute or "runpod"
    missing = [
        flag
        for flag, value in (
            ("--code-ref", args.code_ref),
            ("--literature-snapshot", args.literature_snapshot),
            ("--runpod-key-file", compute != "runpod" or args.runpod_key_file),
            ("--image-manifest", compute != "carrier" or args.image_manifest),
        )
        if not value
    ]
    if missing:
        raise Refused("required: " + ", ".join(missing))
    literature = ["--literature-snapshot", args.literature_snapshot]
    if args.allow_unchecked_cards:
        literature.append("--allow-unchecked-cards")
    lane = ["--compute", compute] + (
        ["--runpod-key-file", args.runpod_key_file]
        if compute == "runpod"
        else ["--image-manifest", args.image_manifest]
    )
    steps = [
        _step(
            "gate.grant_and_code_ref",
            "gate",
            "phase3.gate",
            ["--grant", args.grant, "--code-ref", args.code_ref],
        ),
        _step(
            "gate.dry_run",
            "gate",
            "phase3.main",
            ["run", *base, "--dry-run", "--level", str(args.level), *literature],
        ),
        _step(
            "launch",
            "launch",
            "phase3.main",
            [
                "run",
                *base,
                *common,
                "--code-ref",
                args.code_ref,
                *session,
                *literature,
                *lane,
            ],
        ),
    ]
    if compute == "runpod":
        steps.append(
            _step(
                "post.reconcile",
                "post",
                "phase3.main",
                [
                    "reconcile",
                    *base,
                    "--grant",
                    args.grant,
                    "--runpod-key-file",
                    args.runpod_key_file,
                    "--code-ref",
                    args.code_ref,
                ],
            )
        )
    steps.append(
        _step("post.status", "post", "phase3.main", ["status", "--root", args.root])
    )
    return steps


def phase3_gate(argv):
    """Phase 3's grant and code-ref checks, as `phase3 run` makes them, before
    the dry run and anything else."""
    from . import phase3

    grant_path, code_ref = (
        argv[argv.index("--grant") + 1],
        argv[argv.index("--code-ref") + 1],
    )
    grant = phase3.load_grant(grant_path)
    if grant.provider != "graphite":
        raise phase3.RunnerRefused("grant_provider_must_be_graphite")
    phase3.check_code_ref(code_ref)
    return 0


def call_step(step):
    """Run one step in this process with the existing command; its exit code."""
    from . import phase3, phase4

    calls = {
        "phase3.main": phase3.main,
        "phase4.main": phase4.main,
        "phase3.gate": phase3_gate,
    }
    try:
        code = calls[step["call"]](step["argv"])
    except SystemExit as stopped:
        code = stopped.code if isinstance(stopped.code, int) else 2
    sys.stdout.flush()
    return 0 if code is None else code


def execute(steps, call=call_step, emit=print):
    """Gates in order until one refuses; then the launch; then every post-run
    check whatever the launch's exit. Returns the closing record."""
    done, stopped_at, launch = [], None, None
    for step in steps:
        if stopped_at is not None and step["stage"] != "post":
            continue
        if step["stage"] == "post" and launch is None:
            continue  # nothing launched: nothing to check after it
        code = call(step)
        done.append({"step": step["step"], "exit": code})
        emit(json.dumps({"run_checked_step": step["step"], "exit": code}))
        if step["stage"] == "launch":
            launch = code
        elif step["stage"] == "gate" and code != 0:
            stopped_at = step["step"]
    post = [d["exit"] for d in done if d["step"].startswith("post.")]
    if stopped_at is not None:
        exit_code = done[-1]["exit"]
    else:
        exit_code = launch or next((c for c in post if c != 0), 0)
    return {
        "schema": SCHEMA,
        "steps": done,
        "stopped_at": stopped_at,
        "launched": launch is not None,
        "exit": exit_code,
    }


def parser():
    top = ChallengeParser(prog=PROG)
    sub = top.add_subparsers(dest="command", required=True)
    run = sub.add_parser(
        "run-checked",
        help="gates, then the launch, then the post-run checks, for one session",
    )
    run.add_argument("--phase", type=int, choices=(3, 4), required=True)
    run.add_argument("--root", required=True)
    run.add_argument("--challenge", required=True, help=challenge_help())
    run.add_argument("--grant", required=True)
    run.add_argument(
        "--credential-file",
        required=True,
        help="path of an owner-only file holding the Engy key (both phases)",
    )
    run.add_argument("--miner-profile", required=True)
    run.add_argument("--miner-campaign", required=True)
    run.add_argument("--session", type=int, default=1)
    run.add_argument("--level", type=int, default=0)
    run.add_argument("--code-ref", help="phase 3: the pushed, clean commit pods fetch")
    run.add_argument("--literature-snapshot", help="phase 3")
    run.add_argument("--allow-unchecked-cards", action="store_true", help="phase 3")
    run.add_argument("--compute", choices=("runpod", "carrier"), help="phase 3")
    run.add_argument(
        "--runpod-key-file", help="phase 3, RunPod lane: an owner-only key file"
    )
    run.add_argument("--image-manifest", help="phase 3, carrier lane")
    run.add_argument(
        "--plan", action="store_true", help="print the steps and run nothing"
    )
    return top


def main(argv=None, call=call_step):
    args = parser().parse_args(argv)
    steps = plan(args)
    if args.plan:
        print(
            json.dumps(
                {"schema": SCHEMA, "phase": args.phase, "plan": steps, "ran": False},
                indent=1,
            )
        )
        return 0
    record = {"phase": args.phase, **execute(steps, call)}
    print(json.dumps({"run_checked": record}, sort_keys=True))
    return record["exit"]
