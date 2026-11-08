"""Cooling data kit: generate your own Cooling practice data with Carbon's public reference.

Everything here wraps Carbon's own public Cooling code; nothing is
reimplemented where a public function exists:

- the case law: `carbon/cold_plate/domain.py` (inputs, bounds, derived flow);
- the TRAIN sampling law and its screen: `carbon/cold_plate/population.py`
  (uniform over the box, kept if the closed-form model keeps the hottest wall
  at most 95 C and the flow laminar), seeded from YOUR seed in the kit's own
  label domain, never a Carbon label;
- the OpenFOAM case writer and its commands: `carbon/cold_plate/openfoam.py`,
  with the options Carbon's TRAIN was solved with (`TRAIN_OPTIONS`);
- the reading of a solved case: `carbon/cold_plate/analysis.py`;
- the TRAIN layout: Carbon's law-safe encoded layout
  (`carbon/cold_plate/output_encoding.encode_targets`);
- the solver: the upstream OpenFOAM image, pulled by its pinned digest.

The kit shares the Motor kit's path refusal, output allow-list and file
helpers (`kits/motor/kit.py`). Results you make here may differ from Carbon's
pinned reference, which alone grades. Run `verify` before you train on your
own data. This module reads no Carbon pack, seed, key or private state; the
solver container runs with `--network none`.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

_CHECKOUT = Path(__file__).resolve().parents[2]
if str(_CHECKOUT) not in sys.path:
    sys.path.insert(0, str(_CHECKOUT))

import carbon
from carbon.cold_plate import analysis, domain, exam, openfoam, population
from kits.motor.kit import (
    OUTPUT_FILES,
    KitError,
    _npy,
    audit_output,
    read_npz,
    refuse_protected,
    write_output,
)

__all__ = [
    "OUTPUT_FILES",
    "KitError",
    "audit_output",
    "read_npz",
    "refuse_protected",
    "write_output",
]

#: The Carbon checkout whose public code this kit runs.
ROOT = Path(carbon.__file__).resolve().parents[1]

CHALLENGE_ID = "chip-cold-plate"
KIT_VERSION = "1.8"
#: The solver: OpenFOAM's upstream image, by its pinned digest (Carbon's own
#: reference image identity, `carbon.cold_plate.openfoam.IMAGE`).
IMAGE = openfoam.IMAGE
RECORD_SCHEMA = "carbon.cold-plate.reference-record.v1"
PROVENANCE_SCHEMA = "carbon.miner-kit-train.provenance.v1"
SCOPE = "MINER_GENERATED_PRACTICE_ONLY"
#: The options every record of Carbon's public Cooling TRAIN was solved with
#: (its `options` field; `carbon.cold_plate.challenge.TRAIN_PATH`).
TRAIN_OPTIONS = {"iterations": 2000}
#: The public encoded TRAIN whose numeric layout the parser writes (its
#: provenance is public; its numeric interface is copied, never edited).
TRAIN_PROVENANCE = (
    ROOT
    / "carbon"
    / "challenge_kit"
    / "data"
    / "cooling-dev-train-400-v2-encoded.provenance.json"
)
DOCKER_START_FAILURES = {125, 126, 127}
#: The kit's own draw domain (amendment A2).
LABEL_DOMAIN = f"miner-data-kit.v1|{CHALLENGE_ID}|{KIT_VERSION}|"
#: The fields a case record may carry (amendment A4).
RECORD_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "kind",
        "inputs",
        "options",
        "image",
        "source",
        "cost",
        "status",
        "reasons",
        "outputs",
        "checks",
        "diagnostics",
        "derived",
        "mesh",
    }
)
OUTPUT_WIDTH = 2 + domain.PROFILE_SEGMENTS


def allowed_record(record):
    extra = set(record) - RECORD_KEYS
    if extra:
        raise KitError(f"record fields outside the allow-list: {sorted(extra)}")
    return record


# --- generate: the cases ------------------------------------------------------


def label_for(seed):
    """Your draw label: the kit's domain plus your seed."""
    if type(seed) is not int or seed < 0:
        raise KitError("--seed must be a non-negative integer")
    return f"{LABEL_DOMAIN}seed={seed}"


def sample(n, seed):
    """`n` cases by Carbon's TRAIN law (uniform over the box, kept if the
    closed-form screen admits them), from your seed."""
    if type(n) is not int or n < 1:
        raise KitError("--n must be a positive integer")
    cases, _ = population.draw(population.public_rng(label_for(seed)), n)
    return [
        {"case_id": f"kit-{seed}-{i:04d}", "kind": "ordinary", "inputs": case}
        for i, case in enumerate(cases)
    ]


def nominal():
    """The design basis's nominal plate: a first run."""
    return [
        {"case_id": "kit-nominal", "kind": "nominal", "inputs": dict(domain.NOMINAL)}
    ]


def check_case(entry, *, screen=True):
    if type(entry) is not dict or type(entry.get("case_id")) is not str:
        raise KitError("each case needs a case_id and inputs")
    case_id = entry["case_id"]
    if not case_id or any(
        c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in case_id.lower()
    ):
        raise KitError(f"case_id {case_id!r}: use letters, digits, - and _ only")
    try:
        domain.check_inputs(entry.get("inputs"))
    except (ValueError, TypeError, AttributeError) as error:
        raise KitError(f"{case_id}: {error}") from error
    if screen:
        admitted, reasons, _ = population.screen(entry["inputs"])
        if not admitted:
            raise KitError(f"{case_id}: outside the population: {'; '.join(reasons)}")
    return entry


# --- generate: running a case ---------------------------------------------------


def _script():
    """Carbon's commands for one case, plus one line recording the container's
    peak memory (cgroup v2) for the cost record."""
    solve = "set -e; cd /case; " + "; ".join(openfoam.COMMANDS)
    peak = "cat /sys/fs/cgroup/memory.peak > /case/cost.memory_peak 2>/dev/null || true"
    return f"({solve}); rc=$?; {peak}; exit $rc"


def _cost(case_dir, wall, cpus):
    peak = None
    path = case_dir / "cost.memory_peak"
    if path.exists():
        try:
            peak = round(int(path.read_text().split()[0]) / 2**20, 1)
        except (ValueError, IndexError):
            peak = None
    return {"wall_s": round(wall, 1), "memory_peak_mib": peak, "cores": cpus}


def run_case(entry, out, *, cpus, timeout_s, image=IMAGE):
    case_id = entry["case_id"]
    case_dir = out / "cases" / case_id
    record = {
        "schema": RECORD_SCHEMA,
        "case_id": case_id,
        "kind": entry.get("kind", "ordinary"),
        "inputs": entry["inputs"],
        "options": dict(TRAIN_OPTIONS),
        "image": image,
        "source": "MINER_KIT",
    }
    openfoam.write_case(entry["inputs"], case_dir, **TRAIN_OPTIONS)
    name = f"carbon-cooling-kit-{case_id}"[:120]
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        "none",
        "--cpus",
        str(cpus),
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{case_dir.resolve()}:/case",
        image,
        "bash",
        "-lc",
        _script(),
    ]
    start = time.monotonic()
    status = None
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_s, check=False
        )
        if done.returncode in DOCKER_START_FAILURES:
            status, detail = "FAILED_INFRA", done.stderr.strip()[-2000:]
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
        status, detail = "REFERENCE_TIMEOUT", f"wall limit {timeout_s} s"
    except OSError as error:
        status, detail = "FAILED_INFRA", f"docker: {error}"
    record["cost"] = _cost(case_dir, time.monotonic() - start, cpus)
    if status is not None:
        record.update(status=status, reasons=[detail])
        return record
    result = analysis.analyze_case(case_dir)
    record.update(
        status=result["outcome"],
        reasons=result["reasons"],
        outputs=result.get("outputs"),
        checks=result.get("checks"),
        diagnostics=result.get("diagnostics"),
        derived=result["case"]["derived"],
        mesh=result["case"]["mesh"],
    )
    return record


def generate(
    cases,
    out,
    *,
    parallel=1,
    cpus=2.0,
    timeout_s=14400.0,
    image=IMAGE,
    keep=False,
    _bounds=None,
):
    """Run each case; append one record per case to OUT/records.jsonl.

    ``_bounds`` is internal to `verify`: the published verify designs may lie
    in the inner band just outside the internal range (R15), so the deck's
    bounds are widened to exactly the verify set's own points while it runs
    (and the closed-form screen, a sampling rule, is not applied to them)."""
    out = refuse_protected(out)
    with _widened(_bounds):
        cases = [check_case(c, screen=_bounds is None) for c in cases]
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise KitError("case ids must be unique")
    out.mkdir(parents=True, exist_ok=True)
    audit_output(out)
    if any((out / "cases" / i).exists() for i in ids):
        raise KitError("a case directory exists already; use a new --out")
    from concurrent.futures import ThreadPoolExecutor

    def one(entry):
        record = allowed_record(
            run_case(entry, out, cpus=cpus, timeout_s=timeout_s, image=image)
        )
        with (out / "records.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        case_dir = out / "cases" / entry["case_id"]
        if not keep and record["status"] == "OK" and case_dir.exists():
            shutil.rmtree(case_dir)
        cost = record["cost"]
        print(
            f"{entry['case_id']}: {record['status']} {cost['wall_s']} s, "
            f"{cost['memory_peak_mib']} MiB peak, {cost['cores']} cores",
            flush=True,
        )
        return record

    with _widened(_bounds), ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
        records = list(pool.map(one, cases))
    audit_output(out)
    return records


@contextlib.contextmanager
def _widened(bounds):
    """Temporarily widen the deck's input bounds to ``bounds`` (verify only)."""
    if not bounds:
        yield
        return
    saved = dict(domain.INPUT_BOUNDS)
    try:
        for name, (low, high) in bounds.items():
            old_low, old_high = saved[name]
            domain.INPUT_BOUNDS[name] = (min(old_low, low), max(old_high, high))
        yield
    finally:
        domain.INPUT_BOUNDS.clear()
        domain.INPUT_BOUNDS.update(saved)


# --- the TRAIN-format parser ------------------------------------------------


def numeric_interface():
    """Carbon's public encoded TRAIN numeric interface for Cooling (verbatim)."""
    return json.loads(TRAIN_PROVENANCE.read_text(encoding="utf-8"))["numeric_interface"]


def native_row(outputs):
    """A record's outputs as Carbon's native 32-value row."""
    profile = outputs.get("profile_c")
    if type(profile) is not list or len(profile) != domain.PROFILE_SEGMENTS:
        raise KitError(f"the profile must hold {domain.PROFILE_SEGMENTS} values")
    return [
        _finite(outputs.get("peak_c")),
        *(_finite(v) for v in profile),
        _finite(outputs.get("pressure_drop_pa")),
    ]


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise KitError("a record holds a missing or non-finite number")
    return float(value)


def _npz(inputs, targets):
    """The container Carbon's public TRAIN uses (stored, fixed dates)."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, rows, width in (
            ("inputs", inputs, len(domain.INPUTS)),
            ("targets", targets, OUTPUT_WIDTH),
        ):
            member = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o600 << 16
            with archive.open(member, "w", force_zip64=True) as stream:
                stream.write(_npy(rows, width))
    return output.getvalue()


def parse(records_path):
    """Turn records.jsonl into (npz bytes, provenance) in Cooling 1.8's TRAIN
    layout: the law-safe encoded targets of Carbon's own `encode_targets`.
    Only OK records inside the internal range are kept; every other record
    (a design whose fluid passes the coolant model's 99 C, for one) is
    counted, never used."""
    from carbon.cold_plate.output_encoding import ENCODING, encode_targets

    records_path = refuse_protected(records_path)
    inputs, natives, case_ids, skipped = [], [], [], {}
    for line in Path(records_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        status = row.get("status")
        if row.get("schema") != RECORD_SCHEMA or status != "OK":
            skipped[status or "unknown"] = skipped.get(status or "unknown", 0) + 1
            continue
        check_case(
            {"case_id": row.get("case_id"), "inputs": row.get("inputs")}, screen=False
        )
        natives.append(native_row(row.get("outputs") or {}))
        inputs.append([_finite(row["inputs"][name]) for name in domain.INPUTS])
        case_ids.append(row["case_id"])
    if not case_ids:
        raise KitError("no OK records to parse")
    try:
        targets = encode_targets(natives).tolist()
    except ValueError as error:
        raise KitError(f"a record cannot be encoded: {error}") from error
    raw = _npz(inputs, targets)
    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "scope": SCOPE,
        "challenge": {"id": CHALLENGE_ID, "kit_version": KIT_VERSION},
        "reference": (
            "your own run of Carbon's public Cooling reference recipe; it may "
            "differ from Carbon's pinned reference, which alone grades"
        ),
        "encoding": ENCODING,
        "source_schema": RECORD_SCHEMA,
        "train_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "case_ids": case_ids,
        "skipped": dict(sorted(skipped.items())),
        "numeric_interface": numeric_interface(),
    }
    return raw, provenance


# --- verify ------------------------------------------------------------------

#: The published verify set (amendment A1): Cooling 1.8's 6 designs with
#: Carbon's pinned truths and U, outside every sealed set, digest receipted by
#: the Carbon Validator (7 Nov, board 12:43).
VERIFY_SET = Path(__file__).with_name("verify_set.json")
#: The receipted sha256 of that file; `verify` refuses any other bytes.
VERIFY_SET_SHA256 = "59dabd83e1484cac28e3ad811aac2cba325d3d8ffc994e37b2e0c78063a15bb0"
HUMAN_INPUT = "HUMAN_INPUT"
#: The graded quantities' registered measurement uncertainty U, as published
#: for Cooling 1.6 (docs/MINING.md): die peak 0.037 C, hydraulic power 3 % of
#: the value. The verify set file carries Cooling 1.8's own U.
U_COOLING_16 = {"die_peak_c": {"abs": 0.037}, "hydraulic_w": {"rel": 0.03}}


def quantities(case, outputs):
    """Die peak and hydraulic power, from the exam's own reading
    (`carbon.cold_plate.exam.feasibility`)."""
    values = exam.feasibility(case, outputs, die_limit_c=0.0, hydraulic_limit_w=0.0)
    return {"die_peak_c": values["die_peak_c"], "hydraulic_w": values["hydraulic_w"]}


def _limit(u, want):
    if set(u) == {"abs"} and type(u["abs"]) in (int, float):
        return u["abs"]
    if set(u) == {"rel"} and type(u["rel"]) in (int, float):
        return u["rel"] * abs(want)
    raise KitError("the verify set's U is not registered yet (HUMAN_INPUT)")


def verify_compare(verify_set, records):
    """Pass only when every verify design is OK and within U on every graded
    quantity."""
    u = verify_set.get("u")
    if type(u) is not dict or set(u) != set(U_COOLING_16):
        raise KitError("the verify set's U is not registered yet (HUMAN_INPUT)")
    mine = {r["case_id"]: r for r in records}
    rows, passed = [], True
    with _widened(verify_bounds(verify_set["designs"])):
        for design in verify_set["designs"]:
            record = mine.get(design["case_id"])
            if record is None or record.get("status") != "OK":
                rows.append(
                    {
                        "case_id": design["case_id"],
                        "status": None if record is None else record["status"],
                        "pass": False,
                    }
                )
                passed = False
                continue
            got = quantities(design["inputs"], record["outputs"])
            want = quantities(design["inputs"], design["truth"])
            row = {"case_id": design["case_id"], "status": "OK"}
            ok = True
            for name in sorted(U_COOLING_16):
                limit = _limit(u[name], want[name])
                delta = abs(got[name] - want[name])
                row[name] = {
                    "yours": got[name],
                    "carbon": want[name],
                    "delta": delta,
                    "u": limit,
                }
                ok = ok and delta <= limit
            row["pass"] = ok
            passed = passed and ok
            rows.append(row)
    return {"pass": passed, "designs": rows}


def verify_bounds(designs):
    """The verify set's own per-input span: the only widening `verify` uses."""
    bounds = {}
    for design in designs:
        inputs = design.get("inputs")
        if type(inputs) is not dict or set(inputs) != set(domain.INPUTS):
            raise KitError("a verify design needs exactly the nine inputs")
        for name in domain.INPUTS:
            value = inputs[name]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise KitError("a verify design holds a non-finite input")
            low, high = bounds.get(name, (value, value))
            bounds[name] = (min(low, value), max(high, value))
    return bounds


def load_verify_set(path=VERIFY_SET, expected_sha256=VERIFY_SET_SHA256):
    """The published verify set, only at its receipted digest."""
    path = refuse_protected(path)
    if expected_sha256 is None:
        raise KitError(
            "no verify set is published for this version yet (it awaits its "
            "exclusion rerun and digest receipt)"
        )
    if not path.exists():
        raise KitError(f"the verify set is missing: {path}")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise KitError("the verify set's bytes differ from the receipted digest")
    document = json.loads(raw)
    if (
        document.get("challenge") != CHALLENGE_ID
        or type(document.get("designs")) is not list
        or not document["designs"]
    ):
        raise KitError("the verify set is not a Cooling verify set")
    with _widened(verify_bounds(document["designs"])):
        for design in document["designs"]:
            check_case(design, screen=False)
            native_row(design.get("truth") or {})
    return document


def verify(out, *, path=VERIFY_SET, expected_sha256=VERIFY_SET_SHA256, **run):
    """Run the verify set through `generate` and compare within U."""
    verify_set = load_verify_set(path, expected_sha256)
    designs = [
        {"case_id": d["case_id"], "kind": "verify", "inputs": d["inputs"]}
        for d in verify_set["designs"]
    ]
    records = generate(
        designs, out, _bounds=verify_bounds(verify_set["designs"]), **run
    )
    report = verify_compare(verify_set, records)
    write_output(out, "verify.json", json.dumps(report, indent=1) + "\n")
    return report


# --- score: the practice score, by the grade's own code --------------------------

#: The grading commit (amendment A6): every grade module the practice score
#: imports, with its sha256 at the commit this kit is built against.
GRADE_MODULES = {
    "carbon/cold_plate/exam.py": "ffb9e94ae17a8b403c5d95f4e4985ef989a81d7ed35c2a45af062cff6cac17be",
    "carbon/cold_plate/output_encoding.py": "dc6bcc475cf8f368063afe31b0d9202aa5295ff1f130b9934f52b2427a7249d1",
    "carbon/scoring/cooling_dual_measurement.py": "3c8a031f611744b1b7b7c4de0ff603943a1b4a1662090cb474d9ef63bdb8d325",
    "carbon/scoring/cooling_dual_pack.py": "9e4eef3caeee8e34b9dcc691756492667ba34a4f2e197574c57c47e8d82b5002",
}
SCORE_LABEL = "practice score"
NOT_EVALUATED = "not evaluated locally"


def grade_pin():
    """The grade modules' sha256 in this checkout (CRLF read as LF)."""
    return {
        rel: hashlib.sha256(
            (ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        for rel in GRADE_MODULES
    }


def score(records, predictions):
    """The practice score of a model's predictions on YOUR kit cases.

    ``predictions`` maps case_id to the model's 32-value row in Cooling 1.8's
    TRAIN layout (encoded). Each part is the grade's own code, imported, never
    copied: the row is decoded (`output_encoding.decode_row`); the native
    per-case gates (`carbon.cold_plate.exam.evaluate_case`); the per-case
    errors on peak, profile and pressure (`exam.case_components`, scaled by
    the official TRAIN's `exam.scales_from_train`); and the accuracy part
    A = min over the three of 1 / (1 + mean error / A_scale)
    (`carbon.scoring.cooling_dual_measurement._benefit`, Cooling's registered
    A_scale). Sealed minimums, design value on hidden targets, the information
    budget and the speed gate on the validator's machine are NOT evaluated
    here and are never defaulted (amendment A5). A practice score, never a
    grade."""
    from carbon.cold_plate import challenge
    from carbon.cold_plate.output_encoding import decode_row
    from carbon.scoring import cooling_dual_measurement as cdm
    from carbon.scoring import cooling_dual_pack

    if grade_pin() != GRADE_MODULES:
        raise KitError(
            "this checkout's grade code differs from the kit's pinned grading "
            "commit; update the checkout or the kit together"
        )
    if not isinstance(predictions, dict):
        raise KitError("predictions must map case_id to a 32-value encoded row")
    train = challenge.PublicMaterial.load(ROOT).train
    scales = exam.scales_from_train(train)
    a_scale = cooling_dual_pack._MEASUREMENT["A_scale"]
    rows, errors, gate_failed = [], [], []
    for record in records:
        case_id = record.get("case_id")
        if record.get("status") != "OK" or case_id not in predictions:
            continue
        try:
            prediction = decode_row(predictions[case_id])
        except (ValueError, TypeError) as error:
            raise KitError(f"{case_id}: {error}") from error
        verdict = exam.evaluate_case(prediction, record)
        row = {"case_id": case_id, "state": verdict["state"], "gates": verdict["gates"]}
        if verdict["state"] == exam.SCORABLE:
            components = exam.case_components(prediction, record, scales)
            errors.append(components)
            row["components"] = components
        else:
            gate_failed.append(case_id)
        rows.append(row)
    if not rows:
        raise KitError("no OK kit case has a prediction")
    means = (
        {c: sum(e[c] for e in errors) / len(errors) for c in exam.COMPONENTS}
        if errors
        else None
    )
    return {
        "label": SCORE_LABEL,
        "challenge": {"id": CHALLENGE_ID, "kit_version": KIT_VERSION},
        "cases": len(rows),
        "gates": {
            "native_per_case": "FAIL" if gate_failed else "PASS",
            "gate_failed_cases": gate_failed,
            "speed": NOT_EVALUATED,
            "physics_laws_on_hidden_probes": NOT_EVALUATED,
        },
        "accuracy": {
            "mean_errors": means,
            "a_scale": a_scale,
            "benefit": (
                None
                if means is None
                else min(cdm._benefit(e, a_scale) for e in means.values())
            ),
        },
        "design_value": NOT_EVALUATED,
        "minimums": NOT_EVALUATED,
        "information_budget": NOT_EVALUATED,
        "grade_modules_sha256": grade_pin(),
        "cases_detail": rows,
        "note": (
            "A practice score on your own cases: never an exam score or grade. "
            "Your cases may differ from Carbon's pinned reference, which alone "
            "grades."
        ),
    }


# --- the published rules (sampled region) --------------------------------------


def internal_range():
    return {
        "inputs": {name: list(domain.INPUT_BOUNDS[name]) for name in domain.INPUTS},
        "constraint": (
            "carbon.cold_plate.population.screen: the closed-form model keeps "
            f"the hottest wetted wall at most {population.SCREEN['max_wall_c']:g} C "
            f"and the Reynolds number at most {population.SCREEN['re_max']:g}"
        ),
        "sampling_law": population.__doc__.split("**Sampling law.**")[1]
        .split("\n\n")[0]
        .strip(),
    }
