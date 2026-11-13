"""The motor reference batch, RECORDING MORE (owner 5 Nov 14:19: "record now, grade later").

Same arguments and the same run as `run_batch.py`, which stays byte-identical: it and `carbon/motor/getdp.py` are pinned
by the counted Motor decision study (`carbon/motor/customer_decision.CODE_PATHS`), so the extra outputs are added here,
around them, instead of in them. Per rotor position, every record gains a ``record_now`` section beside its unchanged
``outputs`` (which views and kits copy; ``record_now`` is never put there) and graded by nothing yet:

- ``coil_a_integral_wbm``: each coil region's integral of A_z (Wb m), which GetDP already prints to ``res/coil_a_<k>``;
- ``coil_flux_linkage_wb``: each coil side's flux linkage, turns x stack length x its mean A_z (the integral over the
  region's MESH area from ``mesh.json``: the mesh is in metres);
- ``phase_flux_linkage_wb``: per phase, the winding-signed sum of its sides (`getdp.winding`);
- ``magnet_min_b_t``: the least |b| over the magnet elements, from ONE added GetDP print of |b| on every magnet
  element (Gmsh's native scalar-triangle ``.pos``, as the MMS rungs read it). The solve itself is unchanged.

A missing or non-finite extra output fails the case by name (REFERENCE_SOLVER_FAILED / REFERENCE_INVALID), so no
record silently lacks it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[3]
RECORD_NOW_SCHEMA = "carbon.motor.reference-record-now.v1"
#: Validator (exam science) 5 Nov 14:44 condition (3): a wrapper run's wall_s includes the extra prints, so it is never a
#: speed-ceiling or t_ref input without a note.
WALL_S_BASIS = "record-now runner"
BMAG_QUANTITY = (
    "  { Name bmag; Value { Local { [ Norm[{d a}] ]; In Magnets; Jacobian Vol; } } }"
)
BMAG_PRINT = (
    '  Print[ bmag, OnElementsOf Magnets, File StrCat["res/bmag_",'
    ' Sprintf["%g", STEP], ".pos"] ];'
)
_POST_PROCESSING_END = "} } }\nPostOperation {"
_POST_OPERATION_END = "} } }\n"
_TRIANGLES = re.compile(r"ST\([^)]+\)\{([^}]+)\}")


def _load_run_batch():
    spec = importlib.util.spec_from_file_location(
        "motor_run_batch_record_now_base", HERE / "run_batch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pro_text(original):
    """`getdp.pro_text` plus the |b| quantity and its print on the magnet elements; everything else byte-identical."""

    def text(p, *, nonlinear=None):
        base = original(p, nonlinear=nonlinear)
        if base.count(_POST_PROCESSING_END) != 1 or not base.endswith(
            _POST_OPERATION_END
        ):
            raise ValueError("motor .pro layout changed: record_now cannot add |b|")
        base = base.replace(
            _POST_PROCESSING_END, BMAG_QUANTITY + "\n" + _POST_PROCESSING_END
        )
        return (
            base[: -len(_POST_OPERATION_END)] + BMAG_PRINT + "\n" + _POST_OPERATION_END
        )

    return text


def _coil_a(case_dir, k, slots):
    path = case_dir / "res" / f"coil_a_{k}.txt"
    if not path.exists():
        return None
    values = [
        float(line.split()[-1])
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    return values if len(values) == slots else None


def _magnet_min_b(case_dir, k):
    path = case_dir / "res" / f"bmag_{k}.pos"
    if not path.exists():
        return None
    values = [
        float(v)
        for field in _TRIANGLES.findall(path.read_text())
        for v in field.split(",")
    ]
    return min(values) if values else None


def record_now(case_dir, p, positions, getdp):
    """``(record_now, reasons)`` for one solved case: ``record_now`` is None with a reason when an output is missing."""
    slots = p["slots"]
    coil_a, min_b = [], []
    for k in p["steps"][:positions]:
        step_a = _coil_a(case_dir, k, slots)
        if step_a is None:
            return None, [f"no coil flux at step {k}"]
        step_b = _magnet_min_b(case_dir, k)
        if step_b is None:
            return None, [f"no magnet field at step {k}"]
        coil_a.append(step_a)
        min_b.append(step_b)
    try:
        areas = json.loads((case_dir / "mesh.json").read_text())["areas"]
        coil_mm2 = [float(areas[str(getdp.REGIONS["coil0"] + j)]) for j in range(slots)]
    except (OSError, ValueError, KeyError, TypeError):
        return None, ["no coil areas in mesh.json"]
    per_side = [p["turns"] * p["length"] * 1e-3 / (a * 1e-6) for a in coil_mm2]
    linkage = [[per_side[j] * step[j] for j in range(slots)] for step in coil_a]
    table = getdp.winding(slots, p["poles"])
    phases = {
        phase: [
            sum(
                sign * step[j]
                for j, (named, sign) in enumerate(table)
                if named == phase
            )
            for step in linkage
        ]
        for phase in ("A", "B", "C")
    }
    kept = {
        "schema": RECORD_NOW_SCHEMA,
        "coil_a_integral_wbm": coil_a,
        "coil_flux_linkage_wb": linkage,
        "phase_flux_linkage_wb": phases,
        "magnet_min_b_t": min_b,
    }
    finite = all(math.isfinite(v) for step in coil_a for v in step) and all(
        math.isfinite(v) for v in min_b
    )
    return kept, ([] if finite else ["non-finite coil flux or magnet field"])


def analyze(original, getdp):
    """`run_batch.analyze` unchanged, then the ``record_now`` section for the same rotor positions as torque_nm."""

    def run(case_dir, p):
        result, reasons = original(case_dir, p)
        if result is None:
            return result, reasons
        kept, extra = record_now(
            case_dir, p, len(result["outputs"]["torque_nm"]), getdp
        )
        if kept is None:
            return None, extra
        return {**result, "record_now": kept}, reasons + extra

    return run


def runner_provenance():
    """Validator (exam science) 5 Nov 14:44 condition (2): every record names THIS runner and its file sha, and the
    pinned runner it wraps with its sha; a wrapper record never claims the pinned runner produced it.
    """

    def named(path):
        return {
            "file": path.relative_to(REPOSITORY).as_posix(),
            "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    return {
        "name": "record-now",
        **named(Path(__file__).resolve()),
        "wraps": named(HERE / "run_batch.py"),
    }


def finish(original, runner):
    """``run_batch._finish`` with the runner's provenance and the wall-time mark on every record."""

    def run(record, *args, **kwargs):
        record["runner"] = runner
        if "wall_s" in record:
            record["wall_s_basis"] = WALL_S_BASIS
        return original(record, *args, **kwargs)

    return run


def install(run_batch):
    """Wrap ``run_batch``'s .pro writer, analysis and record writer in place (its own code is not changed)."""
    getdp = run_batch.getdp
    shim = types.ModuleType(getdp.__name__)
    shim.__dict__.update(getdp.__dict__)
    shim.pro_text = pro_text(getdp.pro_text)
    run_batch.getdp = shim
    run_batch.analyze = analyze(run_batch.analyze, getdp)
    run_batch._finish = finish(run_batch._finish, runner_provenance())
    return run_batch


def main(argv=None):
    return install(_load_run_batch()).main(argv)


if __name__ == "__main__":
    sys.exit(main())
