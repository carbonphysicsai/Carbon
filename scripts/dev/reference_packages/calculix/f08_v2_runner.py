"""The F08 2.0 per-job solve and observation harness: ONE plan job (inputs, alloy, mesh rung, fillet rung) to the five outputs
of the U / edge payload (`f08_v2_payload.py`), in the RESULTS.jsonl schema its judge reads.

    CARBON_F08_SOLVERS=<id> CARBON_F08_NATIVE_GMSH=1 python3 f08_v2_runner.py run SHARD.json --out DIR \\
        [--timeout-s S] [--parallel N] [--only JOB_ID ...] [--keep none|failed|all] [--alone]
    CARBON_F08_NATIVE_GMSH=1 python3 f08_v2_runner.py mesh-only SHARD.json --out DIR [--only JOB_ID ...]

SHARD.json is a payload shard (``{"jobs": [{"job_id", "cell", "kind", "case", "h_mm", "fillet_h_mm", "axis"}]}``). Each job is meshed
(`f08_deck_v2.gmsh_script_v2`, native Gmsh 4.15.2), written as the v2 deck (`f08_deck_v2.deck_text`, 48 modes, the case's own
damping), solved by the pinned CalculiX natively under `bulk_run.run_native` with RR-PACKS-07's per-case limits (one core; resident
memory per deck revision, `memory_bytes`: 28 GiB for the PaStiX revision, 9 GiB otherwise), and observed. The deck physics, the meshing and every observer function are `f08_deck_v2` / `f08_deck`'s, unchanged: this
module only chains them. The outputs, all per newton of the unit resultant:

- ``worst_dynamic_mm_per_n``  worst-band tip displacement (modal superposition at the case's damping, the registered dense grid);
- ``static_tip_mm_per_n``     the static step's tip displacement;
- ``cad_mass_kg``             density x the CAD volume (geometry only);
- ``static_fillet_stress_mpa_per_n``   the peak von Mises of the static step over the FILLET set (the safety constraint);
- ``dynamic_fillet_stress_mpa_per_n``  the worst-band dynamic von Mises at the fillet (the primary stress output).

The tip displacement is the z component at the tip node, as in 1.7; an angled load moves the participation factors (both load
components) but not which component is read. Statuses (typed): ``OK``; ``REFERENCE_INVALID`` (the solve ran or was refused on the
job's own merits: a deck refusal, a solver error, a missing or unobservable output, a non-finite or non-positive output, a
wrong mode count; the ``reasons`` name it); ``REFERENCE_TIMEOUT`` (the solve exceeded the timeout: it may be host capacity, not
the case's physics, so it counts for NOTHING until the job is rerun ALONE once with ``--alone``, where a repeat timeout is
``REFERENCE_INVALID`` with reason ``solver_timeout``; the judge treats a ``REFERENCE_TIMEOUT`` as missing, not as a failure);
``FAILED_INFRA`` (the job could not start, was stopped from outside, or passed the memory limit: retried, never judged). A MESHER that
cannot be launched (native Gmsh not importable, its shared library missing, a version other than the pinned one, the image runtime
failing to start) is the host's fault, never the case's: ``FAILED_INFRA`` with ``mesher_unavailable:<cause>`` (invariant 7); only a
mesh the launched mesher could not make is ``REFERENCE_INVALID`` ``mesh_failed``. Every record names the mesher that actually ran
(`mesher_identity`: native Gmsh with its version and the pinned ``GMSH_VERSION``, or the pinned image), the solver identity and the
deck and .dat digests. Nothing here decides a threshold: the judgement is custody's.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (HERE, HERE.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import f08_deck as v1
import f08_deck_v2 as v2
import f08_proof as proof

#: v2: the PaStiX deck revision (f08_deck_v2.DECK_REVISION) is recorded; v1 records are SPOOLES-era decks.
#: v3: an ``auxiliary`` block (`auxiliary`) beside the outputs on a solved job; the five graded outputs are unchanged.
RECORD_SCHEMA = "carbon.f08.v2-job-record.v3"
OUTPUTS = (
    "worst_dynamic_mm_per_n",
    "static_tip_mm_per_n",
    "cad_mass_kg",
    "static_fillet_stress_mpa_per_n",
    "dynamic_fillet_stress_mpa_per_n",
)
MODES = 48
MEMORY_BYTES = (
    9 * 2**30
)  # RR-PACKS-07's f08 case limit (the SPOOLES-era decks; 1.7 is unchanged)
#: Per deck revision, the per-case resident limit: the owner's RB 2.0 reference memory decision (2 Nov: up to 28 GiB, on the v2
#: PaStiX image only, 1.7 unchanged, a case over it a typed resource stop). A revision not named here keeps RR-PACKS-07's 9 GiB.
MEMORY_BYTES_BY_REVISION = {v2.DECK_REVISION: 28 * 2**30}


def memory_bytes(revision=v2.DECK_REVISION):
    """The per-case resident limit of a deck revision (`MEMORY_BYTES_BY_REVISION`, else `MEMORY_BYTES`)."""
    return MEMORY_BYTES_BY_REVISION.get(revision, MEMORY_BYTES)


JOB_KEYS = {"job_id", "cell", "kind", "case", "h_mm", "fillet_h_mm", "axis"}
TERMINAL = ("OK", "REFERENCE_INVALID")


class RunnerRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise RunnerRefused(code)


def _sha(text):
    raw = text if isinstance(text, bytes) else text.encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------- the mesher (infrastructure, never the case)


class MesherUnavailable(Exception):
    """The mesher could not be launched: the host's fault (FAILED_INFRA), never a reference verdict on the case."""

    def __init__(self, cause):
        super().__init__(cause)
        self.cause = cause


#: Text a launch failure leaves on stderr (the module or its shared library cannot load): the mesher never ran the job.
_LAUNCH_MARKERS = (
    "ModuleNotFoundError",
    "No module named",
    "ImportError",
    "cannot open shared object file",
    "Library not loaded",
)
#: Docker's own exit codes for a container that could not start (daemon error, not executable, not found).
_IMAGE_LAUNCH_EXITS = (125, 126, 127)


def _native():
    return os.environ.get("CARBON_F08_NATIVE_GMSH") == "1"


def mesher_identity():
    """The mesher this host will run: ``{"kind": "native_gmsh", "gmsh_version", "pinned_gmsh_version", "python"}`` (the Gmsh that
    ``python3`` imports, which must be the pinned ``GMSH_VERSION``), or ``{"kind": "image", "image", "pinned_gmsh_version"}``.
    `MesherUnavailable` when native Gmsh cannot be imported or is not the pinned version.
    """
    if not _native():
        return {
            "kind": "image",
            "image": v1.MESH_IMAGE,
            "pinned_gmsh_version": v1.GMSH_VERSION,
        }
    try:
        found = subprocess.run(
            ["python3", "-c", "import gmsh; print(gmsh.__version__)"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        raise MesherUnavailable("python3_not_launchable") from None
    if found.returncode != 0:
        raise MesherUnavailable("gmsh_not_importable")
    version = found.stdout.strip()
    if version != v1.GMSH_VERSION:
        raise MesherUnavailable("gmsh_version_not_pinned")
    return {
        "kind": "native_gmsh",
        "gmsh_version": version,
        "pinned_gmsh_version": v1.GMSH_VERSION,
        "python": shutil.which("python3"),
    }


def mesh_job(directory):
    """`f08_deck.mesh` (unchanged), with its launch failures typed as the host's: a mesher that cannot start raises
    `MesherUnavailable`; a mesh the running mesher could not make stays a ``CalledProcessError`` (the job's ``mesh_failed``).
    """
    try:
        v1.mesh(directory)
    except SystemExit:  # f08_deck.mesh: the native Gmsh is not the pinned version
        raise MesherUnavailable("gmsh_version_not_pinned") from None
    except OSError:
        raise MesherUnavailable("mesher_not_launchable") from None
    except subprocess.CalledProcessError as failed:
        command = list(failed.cmd) if isinstance(failed.cmd, (list, tuple)) else []
        if command[:2] == ["python3", "-c"]:  # f08_deck.mesh's own import check
            raise MesherUnavailable("gmsh_not_importable") from None
        if command[:1] == ["docker"] and failed.returncode in _IMAGE_LAUNCH_EXITS:
            raise MesherUnavailable("mesh_image_not_launchable") from None
        stderr = failed.stderr or b""
        text = (
            stderr.decode("utf-8", "replace")
            if isinstance(stderr, bytes)
            else str(stderr)
        )
        if any(marker in text for marker in _LAUNCH_MARKERS):
            raise MesherUnavailable("mesher_import_failed") from None
        raise


# ---------------------------------------------------------------- the job


def check_job(job):
    """The job's shape and its case (the deck's own validation, signed ranges); returns the case."""
    _need(type(job) is dict and set(job) == JOB_KEYS, "job_shape")
    _need(
        type(job["job_id"]) is str
        and job["job_id"]
        and "/" not in job["job_id"]
        and ".." not in job["job_id"],
        "job_id",
    )
    for key in ("h_mm", "fillet_h_mm"):
        _need(
            type(job[key]) in (int, float) and math.isfinite(job[key]) and job[key] > 0,
            f"job_{key}",
        )
    case = job["case"]
    _need(type(case) is dict, "job_case")
    v2.validate_case(case)
    return case


def prepare(job, directory, *, mesher, mesh=mesh_job, modes=MODES):
    """Write the job's mesh script, mesh it (``mesh(directory)``), write the v2 deck and ``deck.json``. Returns the mesh meta."""
    case = check_job(job)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    script = v2.gmsh_script_v2(case, job["h_mm"], job["fillet_h_mm"])
    v2.script_compiles(script)
    (directory / "make_mesh.py").write_text(script)
    mesh(directory)
    meta = json.loads((directory / "mesh.json").read_text())
    mat = v2.material(case["alloy"])
    deck = v2.deck_text(case, meta, mat, modes=modes)
    (directory / "case.inp").write_text(deck)
    pad = v1.face_weights(meta["pad_tri6"], meta["coords"])
    total = math.fsum(pad.values())
    (directory / "deck.json").write_text(
        json.dumps(
            {
                "job_id": job["job_id"],
                "case": case,
                "h_mm": job["h_mm"],
                "fillet_h_mm": job["fillet_h_mm"],
                "modes": modes,
                "loads": {str(n): w / total for n, w in sorted(pad.items())},
                "mesher": mesher,
                "deck_revision": v2.DECK_REVISION,
                "deck_sha256": _sha(deck),
            },
            indent=1,
            sort_keys=True,
        )
        + "\n"
    )
    return meta


# ---------------------------------------------------------------- the observation


def _shapes(step):
    """Per-mode ``{node: (uy, uz)}`` from a frequency step (both components: an angled load needs both)."""
    return [
        {n: (v[1], v[2]) for n, v in event[1].items()}
        for event in step["events"]
        if event[0] == "disp"
    ]


def modal_data(eig, shapes, loads, case, tip):
    """Per-mode omega, hz, the load participation ``phi . f`` over BOTH load components, and the tip z shape."""
    fy, fz = v2.load_components(case["load_angle_deg"])
    return [
        {
            "omega": mode["rad"],
            "hz": mode["hz"],
            "pf": sum(
                phi[n][0] * w * fy + phi[n][1] * w * fz for n, w in loads.items()
            ),
            "tip": phi[tip][1],
            "probe": 0.0,
        }
        for mode, phi in zip(eig, shapes, strict=True)
    ]


def parse(directory):
    """A solved job directory read ONCE (a production .dat is ~1.8 GB): the deck and mesh records, the .dat's steps
    (`f08_proof.parse_dat`) and its stress blocks per step (`f08_deck_v2.stress_blocks_by_step`). `observe` and `auxiliary`
    both read this, so the file is read once and parsed twice (steps, stress), never per observable.
    """
    directory = Path(directory)
    dat = (directory / "case.dat").read_text(errors="replace")
    return {
        "deck": json.loads((directory / "deck.json").read_text()),
        "meta": json.loads((directory / "mesh.json").read_text()),
        "steps": proof.parse_dat(dat),
        "by_step": v2.stress_blocks_by_step(dat),
    }


def observe(directory, parsed=None):
    """The five outputs of a solved job directory (``case.dat``, ``deck.json``, ``mesh.json``), or a RunnerRefused.
    ``parsed`` is `parse(directory)` when the caller has it (the same values either way).
    """
    parsed = parse(directory) if parsed is None else parsed
    deck, meta = parsed["deck"], parsed["meta"]
    case, modes = deck["case"], deck["modes"]
    mat = v2.material(case["alloy"])
    steps = parsed["steps"]
    _need(len(steps) == 3, "dat_steps")
    eig = steps[0]["eigen"]
    _need(len(eig) == modes, "mode_count")
    shapes = _shapes(steps[0])
    _need(len(shapes) == modes, "mode_shapes")
    tip = meta["tip_node"]
    loads = {int(n): w for n, w in deck["loads"].items()}
    modal = modal_data(eig, shapes, loads, case, tip)
    zeta = case["damping_ratio"]
    grid = v1.dense_grid([m["hz"] for m in modal], zeta)
    worst = v1.resolved_peak(lambda f: v1.response(modal, f, zeta, "tip"), grid)
    static = steps[2]["events"][0][1]
    static_tip = static[tip][2]
    # One FILLET stress block per mode in the frequency step, and exactly one in the static step. The steady-state step
    # names no *EL PRINT, so ccx keeps the frequency step's selection there ("if no *EL PRINT card is used within a step
    # the selections of the previous step apply"): its blocks, if any, are never read. 0034 (11-01) refused on the old
    # whole-file count of modes + 1; the refusal names the per-step counts.
    by_step = parsed["by_step"]
    counts = [len(blocks) for blocks in by_step]
    _need(
        len(by_step) == 3 and counts[0] == modes and counts[2] == 1,
        "stress_blocks:" + ",".join(map(str, counts)),
    )
    static_stress = v2.peak_von_mises(by_step[2][0])["peak_von_mises_mpa"]
    # The frequency step's blocks are the file's first ``modes`` blocks (a block before the first step is refused).
    _keys, tensors = v2.modal_stress_tensors_from_blocks(by_step[0], modes)
    dynamic = v2.worst_band_dynamic_stress(tensors, modal, zeta)
    outputs = {
        "worst_dynamic_mm_per_n": worst["mm_per_n"],
        "static_tip_mm_per_n": static_tip,
        "cad_mass_kg": mat["rho_t_per_mm3"] * meta["cad_volume_mm3"] * 1000.0,
        "static_fillet_stress_mpa_per_n": static_stress,
        "dynamic_fillet_stress_mpa_per_n": dynamic["dynamic_von_mises_mpa_per_n"],
    }
    _need(set(outputs) == set(OUTPUTS), "outputs")
    for name, value in outputs.items():
        _need(
            type(value) is float and math.isfinite(value), f"output_not_finite:{name}"
        )
        if name != "static_tip_mm_per_n":  # the static tip may be of either sign
            _need(value > 0, f"output_not_positive:{name}")
    return outputs


def auxiliary(directory, parsed=None):
    """The solve's other observables, RETAINED beside the five graded outputs for custody (never graded, never published
    here): every mode's natural frequency (Hz), every mode's peak fillet von Mises per unit (mass-normalised) modal
    coordinate, the static step's von Mises at every fillet integration point (element, point, MPa per N) and the static
    tip displacement vector (mm per N). The same parse as `observe` (`parse`: one read of the .dat).
    """
    parsed = parse(directory) if parsed is None else parsed
    deck, meta = parsed["deck"], parsed["meta"]
    case, modes = deck["case"], deck["modes"]
    steps = parsed["steps"]
    _need(len(steps) == 3, "dat_steps")
    eig = steps[0]["eigen"]
    _need(len(eig) == modes, "mode_count")
    shapes = _shapes(steps[0])
    tip = meta["tip_node"]
    loads = {int(n): w for n, w in deck["loads"].items()}
    modal = modal_data(eig, shapes, loads, case, tip)
    by_step = parsed["by_step"]
    _need(
        len(by_step) == 3 and len(by_step[0]) == modes and len(by_step[2]) == 1,
        "stress_blocks",
    )
    _keys, tensors = v2.modal_stress_tensors_from_blocks(by_step[0], modes)
    static = steps[2]["events"][0][1]
    out = {
        "modes_hz": [float(m["hz"]) for m in modal],
        "mode_fillet_von_mises_peak_mpa_per_unit_modal": [
            float(v) for v in v2._vm_rows(tensors).max(axis=1)
        ],
        "static_fillet_von_mises_mpa_per_n": [
            [element, point, v2.von_mises(stress)]
            for element, point, stress in by_step[2][0]
        ],
        "tip_static_displacement_mm_per_n": [float(v) for v in static[tip][:3]],
    }
    _need(
        all(
            math.isfinite(v)
            for v in (
                *out["modes_hz"],
                *out["mode_fillet_von_mises_peak_mpa_per_unit_modal"],
                *(row[2] for row in out["static_fillet_von_mises_mpa_per_n"]),
                *out["tip_static_displacement_mm_per_n"],
            )
        ),
        "auxiliary_not_finite",
    )
    return out


# ---------------------------------------------------------------- the solve and the record


def solve(directory, timeout_s, cores):
    """One job as RR-PACKS-07's native executor ran a rung: its run_native result, or {"stop_reason": "infra"}."""
    import bulk_run

    core = cores.get()
    try:
        with (
            (directory / "run.out").open("wb") as out,
            (directory / "run.err").open("wb") as err,
        ):
            return bulk_run.run_native(
                ["bash", "-c", v1.BANK_COMMAND],
                directory,
                bulk_run.native_env({}, directory),
                timeout_s,
                threading.Event(),
                rss_limit_bytes=memory_bytes(),
                cpus={core},
                stdout=out,
                stderr=err,
            )
    except OSError:
        return {"stop_reason": "infra", "exit": None, "wall_s": 0.0}
    finally:
        cores.put(core)


def classify(run, outputs, problem, *, alone=False):
    """``(status, reasons)`` from the run_native result, the outputs (or None) and the observation problem (or None). Pure.
    ``alone`` marks the single rerun of a timed-out job: a repeat timeout is then the case's own (``REFERENCE_INVALID``).
    """
    reason = run.get("stop_reason")
    code = run.get("exit")
    if reason == "not_run":  # refused or failed before any solve: the problem names it
        return "REFERENCE_INVALID", [problem]
    if reason == "memory":
        # a typed resource stop at the deck revision's limit: never judged, never a reference verdict
        return "FAILED_INFRA", [f"reference_memory_limit_{memory_bytes()}_bytes"]
    if reason in ("infra", "cancel") or (
        reason == "exit"
        and code is not None
        and (code == 120 or code >= 128 or code < 0)
    ):
        return "FAILED_INFRA", [
            f"the job could not start, was stopped or passed memory ({reason})"
        ]
    if reason == "timeout":
        if alone:
            return "REFERENCE_INVALID", ["solver_timeout"]
        return "REFERENCE_TIMEOUT", ["solver_timeout_unconfirmed"]
    if code != 0:
        return "REFERENCE_INVALID", ["solver_failed"]
    if outputs is None:
        return "REFERENCE_INVALID", [problem or "no_observable_output"]
    return "OK", []


def record_for(
    job,
    run,
    outputs,
    problem,
    *,
    mesh_meta,
    directory,
    solvers_id,
    mesher,
    alone=False,
    aux=None,
):
    status, reasons = classify(run, outputs, problem, alone=alone)
    if run.get("infra_cause"):
        reasons = [*reasons, run["infra_cause"]]
    directory = Path(directory)
    record = {
        "schema": RECORD_SCHEMA,
        "job_id": job["job_id"],
        "cell": job["cell"],
        "kind": job["kind"],
        "axis": job["axis"],
        "h_mm": job["h_mm"],
        "fillet_h_mm": job["fillet_h_mm"],
        "status": status,
        "reasons": reasons,
        "images": {"mesher": mesher, "solvers_id": solvers_id},
        "deck_revision": v2.DECK_REVISION,
        "alloy_table_sha256": v2.ALLOY_SHA256,
        "mesh": {
            key: mesh_meta.get(key)
            for key in ("nodes", "elements", "fillet_elements", "mesh_volume_mm3")
        },
        "run": {
            key: run.get(key)
            for key in (
                "stop_reason",
                "exit",
                "wall_s",
                "rusage_cpu_s",
                "sampled_group_rss_peak_bytes",
            )
        },
    }
    for name, label in (("case.inp", "deck_sha256"), ("case.dat", "dat_sha256")):
        if (directory / name).is_file():
            record[label] = _sha((directory / name).read_bytes())
    if status in TERMINAL and outputs is not None:
        record["outputs"] = outputs
        if aux is not None:
            record["auxiliary"] = aux
    return record


def run_job(
    job,
    work,
    *,
    timeout_s,
    cores,
    solvers_id,
    mesher,
    keep="none",
    mesh=mesh_job,
    solver=solve,
    alone=False,
):
    """Mesh, deck, solve and observe one job; returns its record. The job directory is removed unless ``keep`` says otherwise."""
    directory = Path(work) / job["job_id"]
    if directory.exists():
        raise RunnerRefused("job_directory_exists")
    meta, run, outputs, problem, aux = {}, {"stop_reason": "infra"}, None, None, None
    try:
        not_run = {"stop_reason": "not_run", "exit": None}
        try:
            meta = prepare(job, directory, mesh=mesh, mesher=mesher)
        except MesherUnavailable as lost:  # the host's mesher, never the case
            return record_for(
                job, {"stop_reason": "infra", "exit": None,
                      "infra_cause": f"mesher_unavailable:{lost.cause}"}, None, None,
                mesh_meta={}, directory=directory, solvers_id=solvers_id, mesher=mesher,
                alone=alone,
            )  # fmt: skip
        except (v2.Refused, RunnerRefused) as refusal:
            return record_for(
                job, not_run, None, f"deck_refused:{refusal}",
                mesh_meta={}, directory=directory, solvers_id=solvers_id, mesher=mesher,
                alone=alone,
            )  # fmt: skip
        except subprocess.CalledProcessError:
            return record_for(
                job, not_run, None, "mesh_failed",
                mesh_meta={}, directory=directory, solvers_id=solvers_id, mesher=mesher,
                alone=alone,
            )  # fmt: skip
        except OSError:  # the mesher could not even start: not the job's fault
            return record_for(
                job, {"stop_reason": "infra", "exit": None}, None, None,
                mesh_meta={}, directory=directory, solvers_id=solvers_id, mesher=mesher,
                alone=alone,
            )  # fmt: skip
        except (KeyError, ValueError):
            return record_for(
                job, not_run, None, "mesh_unreadable",
                mesh_meta={}, directory=directory, solvers_id=solvers_id, mesher=mesher,
                alone=alone,
            )  # fmt: skip
        run = solver(directory, timeout_s, cores)
        if run.get("exit") == 0 and (directory / "case.dat").is_file():
            try:
                parsed = parse(directory)
                outputs = observe(directory, parsed)
            except (RunnerRefused, v2.Refused) as refusal:
                problem = f"observation_refused:{getattr(refusal, 'code', refusal)}"
            except (KeyError, IndexError, ValueError, ZeroDivisionError):
                problem = "observation_failed"
            if outputs is not None:
                # Retained only: a failure here never changes the graded outputs or the status.
                try:
                    aux = auxiliary(directory, parsed)
                except (RunnerRefused, v2.Refused, KeyError, IndexError, ValueError):
                    aux = None
        return record_for(
            job,
            run,
            outputs,
            problem,
            mesh_meta=meta,
            directory=directory,
            solvers_id=solvers_id,
            mesher=mesher,
            alone=alone,
            aux=aux,
        )
    finally:
        status_ok = outputs is not None
        if directory.exists() and (keep == "none" or (keep == "failed" and status_ok)):
            shutil.rmtree(directory, ignore_errors=True)


def mesh_only(job, work, *, mesher, mesh=mesh_job):
    """The dry run: mesh and write the deck, report the sizes, solve nothing."""
    directory = Path(work) / job["job_id"]
    meta = prepare(job, directory, mesh=mesh, mesher=mesher)
    return {
        "schema": RECORD_SCHEMA,
        "job_id": job["job_id"],
        "status": "MESH_ONLY",
        "h_mm": job["h_mm"],
        "fillet_h_mm": job["fillet_h_mm"],
        "mesh": {
            key: meta.get(key)
            for key in (
                "nodes",
                "elements",
                "fillet_elements",
                "mesh_volume_mm3",
                "cad_volume_mm3",
            )
        },
        "images": {"mesher": mesher},
        "deck_revision": v2.DECK_REVISION,
        "deck_sha256": _sha((directory / "case.inp").read_bytes()),
    }


# ---------------------------------------------------------------- the command line


def load_jobs(path, only=None):
    document = json.loads(Path(path).read_text())
    jobs = document.get("jobs") if type(document) is dict else None
    _need(type(jobs) is list and jobs, "shard_jobs")
    ids = [j.get("job_id") for j in jobs]
    _need(len(set(ids)) == len(ids), "shard_job_ids_repeat")
    for job in jobs:
        check_job(job)
    if only:
        _need(set(only) <= set(ids), "only_job_unknown")
        jobs = [j for j in jobs if j["job_id"] in set(only)]
    return jobs


def _solvers():
    import f08_exam_runner as exam

    candidate = os.environ.get("CARBON_F08_CANDIDATE_ENVIRONMENT")
    solvers = exam.candidate_solvers(candidate) if candidate else exam.pinned_solvers()
    if os.environ.get("CARBON_F08_SOLVERS") != exam.solvers_id(solvers):
        raise SystemExit("CARBON_F08_SOLVERS must be the pinned F08 solver identity")
    if os.environ.get("CARBON_F08_NATIVE_GMSH") != "1":
        raise SystemExit("CARBON_F08_NATIVE_GMSH=1 is required (the verified build)")
    exam.check_host(solvers)
    return exam.solvers_id(solvers)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("run", "mesh-only"):
        p = sub.add_parser(name)
        p.add_argument("shard", type=Path)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--only", nargs="*")
        if name == "run":
            p.add_argument("--parallel", type=int, default=1)
            p.add_argument("--timeout-s", type=float, default=5400.0)
            p.add_argument("--keep", choices=("none", "failed", "all"), default="none")
            p.add_argument(
                "--alone",
                action="store_true",
                help="the single rerun of a timed-out job (one job, one core): a repeat timeout is REFERENCE_INVALID",
            )
    args = parser.parse_args(argv)
    jobs = load_jobs(args.shard, args.only)
    if args.cmd == "run" and args.alone and (len(jobs) != 1 or args.parallel != 1):
        raise SystemExit("--alone reruns exactly one job (--only ID) with --parallel 1")
    args.out.mkdir(parents=True, exist_ok=True)
    work = args.out / "work"
    work.mkdir(exist_ok=True)
    results = args.out / ("RESULTS.jsonl" if args.cmd == "run" else "MESH_ONLY.jsonl")
    if results.exists():
        raise SystemExit(f"{results} exists; refusing to overwrite")
    try:
        mesher = (
            mesher_identity()
        )  # once per run: every record names the mesher that ran
    except MesherUnavailable as lost:
        raise SystemExit(f"FAILED_INFRA: mesher_unavailable:{lost.cause}") from None
    if args.cmd == "mesh-only":
        if os.environ.get("CARBON_F08_NATIVE_GMSH") != "1":
            raise SystemExit(
                "CARBON_F08_NATIVE_GMSH=1 is required (the verified build)"
            )
        with results.open("x") as handle:
            for job in jobs:
                handle.write(
                    json.dumps(mesh_only(job, work, mesher=mesher), sort_keys=True)
                    + "\n"
                )
        return 0
    solvers_id = _solvers()
    cores = queue.Queue()
    available = sorted(os.sched_getaffinity(0))
    for core in available[: max(1, min(args.parallel, len(available)))]:
        cores.put(core)
    lock = threading.Lock()
    with results.open("x") as handle, ThreadPoolExecutor(cores.qsize()) as pool:

        def one(job):
            record = run_job(
                job, work, timeout_s=args.timeout_s, cores=cores,
                solvers_id=solvers_id, mesher=mesher, keep=args.keep, alone=args.alone,
            )  # fmt: skip
            with lock:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                handle.flush()
            return record["status"]

        statuses = list(pool.map(one, jobs))
    print(json.dumps({s: statuses.count(s) for s in sorted(set(statuses))}))
    return 0 if all(s == "OK" for s in statuses) else 2


if __name__ == "__main__":
    sys.exit(main())
