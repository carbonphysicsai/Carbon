"""Check that a reference-solvers pod plan ships every module its scripts import.

A RunPod pod receives only the files its plan names (pod_control SOLVER_SHIP +
the plan's paths + its top-level "ship" list). This copies exactly that set to a
temp directory and imports each named module with a clean Python that has no
editable Carbon install, adding missing carbon/... files until imports pass.

    python scripts/dev/reference_packages/ship_check.py PLAN.json MODULE[,MODULE...] \
        [--python ~/.carbon-cleanpy/bin/python] [--write]

Prints the "ship" list the plan needs; --write stores it in the plan.
Without --write, checks the plan and file bytes at --ref (HEAD by default)
and fails if modules are missing. --write proposes a working-tree plan update
using code from that ref; it must be committed and checked again. Imports are
smoke checks, not coverage of lazy imports or runtime input resources.
No network, no spend.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.dev.exam_design.runpod import pod_control as pc


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def committed_bytes(ref, path):
    return subprocess.run(
        ["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, check=True
    ).stdout


def shipped(plan_path, doc, extra, tracked, ref):
    paths = pc.ship_paths(ref, [*pc.SOLVER_SHIP, *doc.get("ship", []), *extra])
    return list(dict.fromkeys(paths + pc.plan_paths(doc, tracked) + [plan_path]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("modules")
    ap.add_argument("--python", default=str(Path.home() / ".carbon-cleanpy/bin/python"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--ref", default="HEAD", help="immutable source revision to check")
    a = ap.parse_args(argv)
    ref = git("rev-parse", "--verify", f"{a.ref}^{{commit}}").strip()
    tracked = set(git("ls-tree", "-r", "--name-only", ref).splitlines())
    if a.plan not in tracked:
        print(
            json.dumps({"ok": False, "error": "plan is not tracked at ref", "ref": ref})
        )
        return 1
    committed_plan = committed_bytes(ref, a.plan)
    candidate_plan = (ROOT / a.plan).read_bytes() if a.write else committed_plan
    uncommitted_plan = candidate_plan != committed_plan
    doc = json.loads(candidate_plan)
    pc.public_pod_plan(doc)
    extra = []
    for _ in range(80):
        work = Path(tempfile.mkdtemp(prefix="ship-check-"))
        payload_paths = shipped(a.plan, doc, extra, tracked, ref)
        for rel in payload_paths:
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            (work / rel).write_bytes(committed_bytes(ref, rel))
        error = None
        for module in a.modules.split(","):
            run = subprocess.run(
                [a.python, "-c", f"import {module}"],
                check=False,
                cwd=work,
                capture_output=True,
                text=True,
                env={"PATH": os.environ["PATH"], "PYTHONPATH": str(work)},
            )
            if run.returncode:
                error = run.stderr.strip().splitlines()[-1]
                break
        shutil.rmtree(work)
        if error is None:
            ship = sorted(set(doc.get("ship", [])) | set(extra))
            ok = not extra or a.write
            print(
                json.dumps(
                    {
                        "ok": ok,
                        "ref": ref,
                        "ship": ship,
                        "missing_ship": extra,
                        "plan_source": "working-tree proposal" if a.write else "commit",
                        "modules_checked": a.modules.split(","),
                        "coverage": "top-level imports only; lazy imports and runtime resources are not checked",
                        "requires_commit": bool(
                            a.write and (extra or uncommitted_plan)
                        ),
                    },
                    indent=1,
                )
            )
            if a.write and extra:
                doc["ship"] = ship
                (ROOT / a.plan).write_text(json.dumps(doc, indent=1) + "\n")
            return 0 if ok else 1
        found = re.search(r"No module named '([\w.]+)'", error)
        named = re.search(
            r"cannot import name '(\w+)' from (?:partially initialized module )?'([\w.]+)'",
            error,
        )
        name = (
            found.group(1)
            if found
            else (f"{named.group(2)}.{named.group(1)}" if named else None)
        )
        added = False
        parts = (name or "").split(".")
        for i in range(1, len(parts) + 1):
            base = "/".join(parts[:i])
            for cand in (f"{base}/__init__.py", f"{base}.py"):
                if cand in tracked and cand not in extra and cand not in payload_paths:
                    extra.append(cand)
                    added = True
        if not added:
            print(json.dumps({"ok": False, "error": error}, indent=1))
            return 1
    print(json.dumps({"ok": False, "error": "too many iterations"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
