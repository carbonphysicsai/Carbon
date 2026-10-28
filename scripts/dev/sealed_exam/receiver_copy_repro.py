"""Run a failing receiver step ONCE on a COPY of its state and print the full traceback.

A live receiver logs only the exception TYPE of a background failure (by design: no private
content in the log) and an auto-grade marker holds a code. This copies the receiver's state
directory, points a copy of its config at the copy (another loopback port, a scratch pool store,
no other effect), starts the same ``direct_receiver.serve`` start-up on the copy, replaces the
background loops with ONE call, and prints what it raised. The live state is only read.

    # the advance step (the intake's `advance()`)
    python -B scripts/dev/sealed_exam/receiver_copy_repro.py advance \
        --config <live receiver.json> --scratch /tmp/repro-advance
    # the auto-grade of one task (`retain_result`: bank custody, the selected pack's evaluation,
    # the counted bank grade on a sealed pack, the Ladder, KOTH)
    python -B scripts/dev/sealed_exam/receiver_copy_repro.py grade \
        --config <live receiver.json> --scratch /tmp/repro-grade --task rtsk_<64 hex>

Grade mode also records every failed PRODUCER check and goes on past it (a later step may then fail for the same
root cause; the first listed is the root), and prints the values behind the producer / train / bank binding of the
selected pack (digests only) with this host's per-file producer hashes (``grade_explain.py``; ``--no-explain`` turns
it off). Nothing it patches is written; the grade it drives still decides only what the receiver's code decides.

Run it as the receiver's own user with the receiver's checkout. ``--dry-run`` prints what would be
copied and the config paths OUTSIDE the state directory (shared with the live receiver; only read)
and exits. The grade mode really runs the grade's inference on this host (it needs the same
images), so run it when the host is not grading.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import threading
import traceback
from pathlib import Path

try:  # run as a script (this directory is on the path) or imported from the repository root
    import grade_explain
except ImportError:  # pragma: no cover - the import style differs, not the code
    from scripts.dev.sealed_exam import grade_explain

REPRO_PORT = 18799
TASK = re.compile(r"rtsk_[0-9a-f]{64}\Z")


def _paths(value, found=None):
    found = [] if found is None else found
    if isinstance(value, dict):
        for item in value.values():
            _paths(item, found)
    elif isinstance(value, list):
        for item in value:
            _paths(item, found)
    elif isinstance(value, str) and value.startswith("/"):
        found.append(value)
    return found


def rewritten(config, live_root, copy_root, *, mode, pool_store=None):
    """The config for the copy: its root, a private port; advance mode drops auto_grade, grade
    mode keeps it with a scratch pool store."""
    live = str(live_root).rstrip("/")

    def remap(value):
        if isinstance(value, dict):
            return {key: remap(item) for key, item in value.items()}
        if isinstance(value, list):
            return [remap(item) for item in value]
        if isinstance(value, str) and (value == live or value.startswith(live + "/")):
            return str(copy_root) + value[len(live) :]
        return value

    result = remap(json.loads(json.dumps(config)))
    result["root"] = str(copy_root)
    result["port"] = REPRO_PORT
    result["host"] = "127.0.0.1"
    result["lifetime_seconds"] = 3600
    if mode == "advance":
        result.pop("auto_grade", None)
    else:
        result["auto_grade"] = (
            {} if pool_store is None else {"pool_store": str(pool_store)}
        )
    return result


def _print_failure(failure):
    traceback.print_exception(failure)
    code = getattr(failure, "code", None)
    if code is not None:
        print("code:", getattr(code, "value", code))
    diagnostic = getattr(failure, "private_diagnostic", None)
    if type(diagnostic) is bytes and diagnostic:
        print("private diagnostic (worker output, truncated):")
        print(diagnostic[:16384].decode("utf-8", "replace"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("mode", choices=("advance", "grade"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--task")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-explain",
        action="store_true",
        help="grade mode: do not record-and-continue past failed producer checks or print the binding values",
    )
    args = parser.parse_args(argv)
    if args.mode == "grade" and (args.task is None or TASK.match(args.task) is None):
        parser.error("grade needs --task rtsk_<64 hex>")

    config = json.loads(args.config.read_bytes())
    live_root = Path(config["root"])
    copy_root = args.scratch / "root"
    outside = sorted(
        {
            p
            for p in _paths(config)
            if not p.startswith(str(live_root).rstrip("/") + "/")
        }
        - {str(live_root)}
    )
    print(f"live state   {live_root}  (read only)")
    print(f"copy state   {copy_root}")
    print("config paths outside the state directory (shared, read by the step):")
    for path in outside:
        print("   ", path)
    if args.dry_run:
        print("dry run: nothing copied")
        return 0
    if copy_root.exists():
        raise SystemExit(f"{copy_root} exists; use a fresh --scratch")
    args.scratch.mkdir(parents=True, mode=0o700)
    shutil.copytree(live_root, copy_root, symlinks=True)
    pool_store = None
    if args.mode == "grade":
        from carbon.battery.pool_store import PoolStore

        pool_store = args.scratch / "scratch-pool.sqlite3"
        PoolStore(pool_store)
    from carbon.development_session.profile import canonical

    copy_config = args.scratch / "receiver-copy.json"
    copy_config.write_bytes(
        canonical(
            rewritten(
                config, live_root, copy_root, mode=args.mode, pool_store=pool_store
            )
        )
    )
    copy_config.chmod(0o600)

    from carbon.challenge_validator import direct_intake, direct_receiver

    stop = threading.Event()

    def one_advance(intake, stop_event, work=None):
        try:
            print(f"advance() returned {intake.advance()!r}: no exception on this copy")
        except Exception as failure:  # noqa: BLE001 - this is the diagnostic
            print("advance() RAISED:")
            _print_failure(failure)
        finally:
            stop_event.set()

    def one_grade(grader, stop_event, work=None):
        try:
            result = grader.intake.retain_result(
                args.task,
                artifact_directory=grader.artifacts,
                entry_directory=grader.entries,
                pool_store=grader._pool(),
            )
            print("retain_result returned (keys only):", sorted(result))
            for key in ("private_evaluation_state", "private_evaluation_reason"):
                if key in result:
                    print(f"{key}: {result[key]}")
        except Exception as failure:  # noqa: BLE001 - this is the diagnostic
            print("retain_result RAISED:")
            _print_failure(failure)
        finally:
            if args.mode == "grade" and not args.no_explain:
                grade_explain.report()
            stop_event.set()

    if args.mode == "grade" and not args.no_explain:
        grade_explain.install()
    if args.mode == "advance":
        direct_intake._advance_loop = one_advance
        direct_intake._grade_loop = lambda *a, **k: None
    else:
        direct_intake._advance_loop = (
            lambda intake, stop_event, work=None: stop_event.wait()
        )
        direct_intake._grade_loop = one_grade
    direct_receiver.serve(
        copy_config, stop=stop, ready=lambda item: print("copy receiver ready")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
