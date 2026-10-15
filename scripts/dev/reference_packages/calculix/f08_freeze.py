"""Freeze #787's f08 triage decks (REFERENCE-PACKAGES-01).

    python3 f08_freeze.py --out DIR
    python3 f08_freeze.py --observe DIR --out OBSERVED.json

Test Lead 2026-10-08: run on the operator host's free CPU (no spend), one
CPU per ccx process, costs recorded as CPU-s with the host profile. #787
reserves 58 launches (40 unbatched primaries, 10 witness studies, 8
controls and repeat); batching static/eigen/three damping sweeps into one
ccx process makes the panel 17 launches:

    primary (8)          every public geometry, h 3 mm, 48 modes
    witness_studies (6)  #787's long-flexible and relieved-tall, plus the
                         nominal geometry (the packet's full-rung case), at
                         h 2.25 and 1.7 mm
    controls (2)         the analytic oscillators; an unribbed, unrelieved
                         220 x 20 x 6 mm beam against Euler-Bernoulli
    cold_repeat (1)      the first primary again

The 12/24/48 mode ladder and the frequency refinement come from each launch's
stored mass-normalised basis (f08_proof demonstrates the truncations equal
ccx's own 12/24-mode runs). Nothing is generated on the run host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f08_deck as deck
import f08_proof as proof

#: Local rebuild of sources.lock.json (2026-10-15, OCI index digest; numerically
#: identical smoke/proof to the original d9ef68... build, calculix.json).
IMAGE = "sha256:16869c9cb7f14994f3bed3152809efdec14c5b3ec1849730d7b6c8f689d9642b"
ORIGINAL_IMAGE = (
    "sha256:d9ef68d016226a945c7eefcb6b2261c60a11249ee0f93458ae6c3aca956fd6f8"
)
H_PRIMARY, H_WITNESS, MODES = 3.0, (2.25, 1.7), 48
WITNESS_LABELS = ("long-flexible", "relieved-tall", "nominal")


def _digest(case_dir):
    files = sorted(p for p in Path(case_dir).rglob("*") if p.is_file())
    return {
        str(p.relative_to(case_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }


def freeze(out, image=IMAGE):
    out = Path(out)
    labels = [
        c["label"]
        for c in json.loads(deck.PANELS.read_text())["families"]["f08"]["public_cases"]
    ]
    plan = [(lb, "primary", H_PRIMARY, "primary") for lb in labels]
    plan += [
        (lb, f"h{h:g}", h, "witness_studies")
        for lb in WITNESS_LABELS
        for h in H_WITNESS
    ]
    plan += [("control-beam", "h2", 2.0, "controls")]
    plan += [(labels[0], "cold-repeat", H_PRIMARY, "cold_repeat")]
    entries = []
    for label, tag, h, reservation in plan:
        d = out / "f08" / (label if label.startswith("control") else f"{label}-{tag}")
        case = deck.BEAM_CONTROL if label == "control-beam" else deck.panel_case(label)
        size = deck.write_case(case, d, h, MODES)
        entries.append({"family": "f08", "case": d.name, "reservation": reservation, "command": deck.COMMAND,
                        "mesh": size, **deck.estimate(size["nodes"]), "files": _digest(d)})  # fmt: skip
    d = out / "f08" / "control-oscillators"
    d.mkdir(parents=True, exist_ok=True)
    (d / "case.inp").write_text(proof.oscillator_deck()[0])
    (d / "deck.json").write_text(json.dumps({"control": "oscillators"}) + "\n")
    entries.insert(len(labels), {"family": "f08", "case": d.name, "reservation": "controls",
                                 "command": deck.COMMAND, "estimate_cpu_s": 1.0, "estimate_wall_s": 5.0,
                                 "estimate_mem_mib": 64, "files": _digest(d)})  # fmt: skip
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "REFERENCE-PACKAGES-01",
        "authority": "Test Lead 2026-10-08: #787 f08 triage on local free CPU, no spend",
        "image": image,
        "mesh_image_f08": deck.MESH_IMAGE,
        "cases": entries,
        "counts": {
            r: sum(e["reservation"] == r for e in entries)
            for r in sorted({e["reservation"] for e in entries})
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest["counts"]


def cgroup_counters(text):
    """Parse the case's `grep -H` of its cgroup files (v2 cpu.stat/memory.peak or v1)."""
    cpu_s = peak = None
    for line in text.splitlines():
        path, _, value = line.partition(":")
        name = path.rsplit("/sys/fs/cgroup/", 1)[-1]
        if name == "cpu.stat" and value.startswith("usage_usec "):
            cpu_s = int(value.split()[1]) / 1e6
        elif name == "cpuacct/cpuacct.usage" and cpu_s is None:
            cpu_s = int(value) / 1e9
        elif name in ("memory.peak", "memory/memory.max_usage_in_bytes"):
            peak = int(value) / 2**20
    return {"cgroup_cpu_s": cpu_s, "cgroup_memory_peak_mib": peak}


def _cost(case_dir, ledger_rows):
    """Measured cost of one launch: ledger wall plus the container's cgroup counters."""
    row = ledger_rows.get(case_dir.name, {})
    cost = {
        k: row.get(k) for k in ("wall_s", "outcome", "children_cpu", "host_profile")
    }
    path = case_dir / "cgroup.txt"
    cost.update(cgroup_counters(path.read_text() if path.exists() else ""))
    return cost


def _finished(case_dir):
    """ccx wrote its output and the case command recorded its cgroup counters."""
    return (case_dir / "case.dat").exists() and (case_dir / "cgroup.txt").exists()


def observe_all(decks, out, ledger=None):
    decks = Path(decks)
    ledger_rows = {}
    if ledger and Path(ledger).exists():
        for line in Path(ledger).read_text().splitlines():
            row = json.loads(line)
            ledger_rows[row["case"]] = row
    rows = {}
    for d in sorted((decks / "f08").iterdir()):
        if not _finished(d):
            rows[d.name] = {
                "status": "NOT_RUN_OR_NO_OUTPUT",
                "cost": _cost(d, ledger_rows),
            }
            continue
        try:
            if d.name == "control-oscillators":
                steps = proof.parse_dat((d / "case.dat").read_text(errors="replace"))
                rows[d.name] = deck.oscillator_control(proof.oscillator_check(steps))
            else:
                obs = deck.observe(d)
                obs.pop("modal")  # recomputable from case.dat; keeps the summary small
                if d.name == "control-beam":
                    obs["beam_control"] = deck.beam_control(deck.observe(d))
                rows[d.name] = obs
        except (
            KeyError,
            IndexError,
            ValueError,
        ) as error:  # malformed output is a reference failure
            rows[d.name] = {"status": "OBSERVER_FAILED", "why": repr(error)}
        rows[d.name]["cost"] = _cost(d, ledger_rows)
    summary = {
        "cases": rows,
        "convergence": {},
        "bands_decision": deck.DECISION,
        "bands": deck.BANDS,
    }
    for label in WITNESS_LABELS:
        names = {
            H_PRIMARY: f"{label}-primary",
            **{h: f"{label}-h{h:g}" for h in H_WITNESS},
        }
        if all(_finished(decks / "f08" / n) for n in names.values()):
            rungs = {h: deck.observe(decks / "f08" / n) for h, n in names.items()}
            summary["convergence"][label] = deck.convergence(rungs)
        else:
            summary["convergence"][label] = {"status": "INCOMPLETE_LADDER"}
    summary["bank_mesh"] = bank_mesh(summary["convergence"])
    Path(out).write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


def bank_mesh(convergence):
    """V9: coarsest rung passing V1-V7 against h 1.7 on every witness geometry."""
    if any("rungs" not in c for c in convergence.values()):
        return {"h_mm": None, "status": "UNRESOLVED_INCOMPLETE_WITNESSES"}
    for h in (H_PRIMARY, *H_WITNESS[:-1]):
        if all(
            c["rungs"][f"h{h:g}"]["verdict"] == "PASS" for c in convergence.values()
        ):
            return {"h_mm": h, "status": "PASS"}
    return {
        "h_mm": H_WITNESS[-1],
        "status": "NO_COARSER_RUNG_PASSED_FINEST_USED_GAP_REPORTED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f08_freeze")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--observe", type=Path)
    parser.add_argument(
        "--ledger", type=Path, help="triage_run ledger for measured costs"
    )
    parser.add_argument(
        "--image", default=IMAGE, help="image id recorded in the manifest"
    )
    args = parser.parse_args(argv)
    if args.observe:
        summary = observe_all(args.observe, args.out, args.ledger)
        print(
            json.dumps(
                {
                    k: v.get(
                        "worst_dynamic_mm_per_n", v.get("verdict", v.get("status"))
                    )
                    for k, v in summary["cases"].items()
                },
                indent=1,
            )
        )
        print(json.dumps(summary["bank_mesh"]))
    else:
        print(json.dumps(freeze(args.out, args.image), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
