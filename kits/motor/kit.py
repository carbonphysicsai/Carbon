"""Motor data kit: generate your own Motor practice data with Carbon's public reference.

Everything here wraps Carbon's own public Motor code; nothing is reimplemented
where a public function exists:

- the case law and buildability rule: `carbon/motor/domain.py`;
- the TRAIN sampling law: `carbon/motor/population.py` (uniform over the box,
  kept if buildable), seeded from YOUR seed, never a Carbon label;
- the case writer, rotor currents, run script and reading of the torque:
  `scripts/dev/motor/reference/run_batch.py` (`case_params`, `currents`,
  `analyze`, `REFERENCE_CHECKS`), the runner Carbon itself used;
- the GetDP formulation `carbon/motor/getdp.py` and the mesher
  `carbon/motor/mesh.py`;
- the solver image is built by you from `scripts/dev/motor/reference/Dockerfile`.

Results you make here may differ from Carbon's pinned reference, which alone
grades. Run `verify` before you train on your own data.

This module reads no Carbon pack, seed, key or private state, and opens no
network connection; the solver container runs with `--network none`.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path

_CHECKOUT = Path(__file__).resolve().parents[2]
if str(_CHECKOUT) not in sys.path:
    sys.path.insert(0, str(_CHECKOUT))

import carbon
from carbon.motor import domain, exam, getdp, population

#: The Carbon checkout whose public code this kit runs.
ROOT = Path(carbon.__file__).resolve().parents[1]

CHALLENGE_ID = "electric-motor-magnetics"
KIT_VERSION = "1.7"
RECIPE = ROOT / "scripts" / "dev" / "motor" / "reference" / "Dockerfile"
RUNNER = ROOT / "scripts" / "dev" / "motor" / "reference" / "run_batch.py"
MESH = ROOT / "carbon" / "motor" / "mesh.py"
IMAGE = "carbon-motor-kit:local"
RECORD_SCHEMA = "carbon.motor.reference-record.v1"
PROVENANCE_SCHEMA = "carbon.miner-kit-train.provenance.v1"
SCOPE = "MINER_GENERATED_PRACTICE_ONLY"
#: The public TRAIN file whose numeric layout the parser writes (its
#: provenance is public; its numeric interface is copied, never edited).
TRAIN_PROVENANCE = (
    ROOT
    / "carbon"
    / "challenge_kit"
    / "data"
    / "motor-dev-train-150-v1.provenance.json"
)
DOCKER_START_FAILURES = {125, 126, 127}


def recipe_sources():
    """The upstream downloads the recipe names: {ARG name: URL}, read from it."""
    sources = {}
    for line in RECIPE.read_text(encoding="utf-8").splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] == "ARG" and "_URL=" in parts[1]:
            key, url = parts[1].split("=", 1)
            sources[key] = url.strip()
    return sources


def unreachable_hosts(log_lines):
    """The recipe's download hosts that a failed build's curl lines name."""
    hosts = {url.split("/")[2] for url in recipe_sources().values()}
    return sorted(
        host
        for host in hosts
        if any("curl: (" in line and host in line for line in log_lines)
    )


class KitError(ValueError):
    """A refused kit input, with a plain reason."""


#: Path parts the kit refuses to read or write (amendment A3): Carbon's packs,
#: custody and private material never pass through a kit command.
PROTECTED_PARTS = (
    "custody",
    "sealed",
    "case_bank",
    "evaluation_pack",
    "validator_host_classes",
    ".carbon-local",
    "secrets",
)
PROTECTED_NAMES = ("packs", "pack")
PROTECTED_PREFIXES = ("ops_20",)


def refuse_protected(path):
    """Refuse a pack, custody or private path; return the resolved path."""
    resolved = Path(path).expanduser().resolve()
    for part in resolved.parts:
        low = part.lower()
        if (
            any(m in low for m in PROTECTED_PARTS)
            or low in PROTECTED_NAMES
            or low.startswith(PROTECTED_PREFIXES)
        ):
            raise KitError(
                f"{path} looks like a Carbon pack, custody or private "
                "path; the kit never reads or writes those"
            )
    return resolved


#: Everything a kit command may write into its output directory (amendment A4).
OUTPUT_FILES = frozenset(
    {
        "records.jsonl",
        "train.npz",
        "train.provenance.json",
        "verify.json",
        "score.json",
        "cases",
    }
)
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
        "derived",
        "checks",
    }
)


def allowed_record(record):
    extra = set(record) - RECORD_KEYS
    if extra:
        raise KitError(f"record fields outside the allow-list: {sorted(extra)}")
    return record


def write_output(out, name, data):
    """Write one allow-listed output file."""
    if name not in OUTPUT_FILES or name == "cases":
        raise KitError(f"{name} is not an allow-listed kit output")
    path = Path(out) / name
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path


def audit_output(out):
    """Every entry of an output directory is allow-listed."""
    extra = sorted(p.name for p in Path(out).iterdir() if p.name not in OUTPUT_FILES)
    if extra:
        raise KitError(f"unexpected files in the output directory: {extra}")


def _runner():
    """Carbon's own Motor runner module, loaded from its file."""
    spec = importlib.util.spec_from_file_location("_carbon_motor_run_batch", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- generate: the cases ------------------------------------------------------


#: The kit's own draw domain (amendment A2). Every kit label starts with it, so a
#: kit draw can never reproduce a Carbon draw (Carbon's public labels start
#: "carbon."; its private draws use an operator-held root, never a label).
LABEL_DOMAIN = f"miner-data-kit.v1|{CHALLENGE_ID}|{KIT_VERSION}|"


def label_for(seed):
    """Your draw label: the kit's domain plus your seed."""
    if type(seed) is not int or seed < 0:
        raise KitError("--seed must be a non-negative integer")
    return f"{LABEL_DOMAIN}seed={seed}"


def sample(n, seed):
    """`n` cases by Carbon's TRAIN law (uniform over the box, kept if
    buildable), from your seed."""
    if type(n) is not int or n < 1:
        raise KitError("--n must be a positive integer")
    cases, _ = population.draw(population.public_rng(label_for(seed)), n)
    return [
        {"case_id": f"kit-{seed}-{i:04d}", "kind": "ordinary", "inputs": case}
        for i, case in enumerate(cases)
    ]


def nominal():
    """The GRUCAD benchmark's published case: a quick first run."""
    return [
        {"case_id": "kit-nominal", "kind": "nominal", "inputs": dict(domain.NOMINAL)}
    ]


def check_case(entry):
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
    reasons = domain.validity(entry["inputs"])
    if reasons:
        raise KitError(f"{case_id}: not buildable: {'; '.join(reasons)}")
    return entry


# --- generate: running a case ---------------------------------------------------


def _script(runner, p):
    """The run script Carbon's runner uses for one case, plus one line that
    records the container's peak memory (cgroup v2) for the cost record."""
    calls = ["python3 mesh.py params.json . > log.mesh 2>&1"]
    for k in p["steps"]:
        ia, ib, ic = runner.currents(p, k)
        calls.append(
            f"getdp machine.pro -msh rotor_{k}.msh -setnumber STEP {k}"
            f" -setnumber IA {ia!r} -setnumber IB {ib!r} -setnumber IC {ic!r}"
            f" -solve MagSta -pos MagSta -v 2 >> log.getdp 2>&1"
        )
    solve = "set -e; " + calls[0] + "; " + " && ".join(calls[1:])
    peak = "cat /sys/fs/cgroup/memory.peak > cost.memory_peak 2>/dev/null || true"
    return f"({solve}); rc=$?; {peak}; exit $rc"


def write_case(runner, entry, case_dir):
    p = runner.case_params(entry["inputs"], {})
    (case_dir / "res").mkdir(parents=True)
    shutil.copy(MESH, case_dir / "mesh.py")
    (case_dir / "params.json").write_text(json.dumps(p, indent=1))
    p_pro = {**p, "coil_area_mm2": domain.coil_area_mm2(entry["inputs"])}
    (case_dir / "machine.pro").write_text(getdp.pro_text(p_pro, nonlinear=getdp.BRAUER))
    return p


def run_case(runner, entry, out, *, cpus, timeout_s, image=IMAGE):
    case_id = entry["case_id"]
    case_dir = out / "cases" / case_id
    record = {
        "schema": RECORD_SCHEMA,
        "case_id": case_id,
        "kind": entry.get("kind", "ordinary"),
        "inputs": entry["inputs"],
        "options": {},
        "image": image,
        "source": "MINER_KIT",
    }
    p = write_case(runner, entry, case_dir)
    name = f"carbon-motor-kit-{case_id}"[:120]
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
        "-e",
        "OMP_NUM_THREADS=1",
        "-e",
        "OPENBLAS_NUM_THREADS=1",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{case_dir.resolve()}:/w",
        "-w",
        "/w",
        image,
        "bash",
        "-c",
        _script(runner, p),
    ]
    start = time.monotonic()
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_s, check=False
        )
        status = None
        if done.returncode in DOCKER_START_FAILURES:
            status, detail = "FAILED_INFRA", done.stderr.strip()[-2000:]
        else:
            detail = f"exit {done.returncode}"
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
        status, detail = "REFERENCE_TIMEOUT", f"wall limit {timeout_s} s"
    except OSError as error:
        status, detail = "FAILED_INFRA", f"docker: {error}"
    wall = time.monotonic() - start
    record["cost"] = _cost(case_dir, wall, cpus)
    if status is not None:
        record.update(status=status, reasons=[detail])
        return record
    result, reasons = runner.analyze(case_dir, p)
    if result is None:
        record.update(status="REFERENCE_SOLVER_FAILED", reasons=reasons)
    else:
        record.update(
            status="REFERENCE_INVALID" if reasons else "OK", reasons=reasons, **result
        )
    return record


def _cost(case_dir, wall, cpus):
    peak = None
    path = case_dir / "cost.memory_peak"
    if path.exists():
        try:
            peak = round(int(path.read_text().split()[0]) / 2**20, 1)
        except (ValueError, IndexError):
            peak = None
    return {"wall_s": round(wall, 1), "memory_peak_mib": peak, "cores": cpus}


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
    bounds are widened to exactly the verify set's own points while it runs."""
    out = refuse_protected(out)
    with _widened(_bounds):
        cases = [check_case(c) for c in cases]
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise KitError("case ids must be unique")
    out.mkdir(parents=True, exist_ok=True)
    audit_output(out)
    if any((out / "cases" / i).exists() for i in ids):
        raise KitError("a case directory exists already; use a new --out")
    runner = _runner()
    from concurrent.futures import ThreadPoolExecutor

    def one(entry):
        record = allowed_record(
            run_case(runner, entry, out, cpus=cpus, timeout_s=timeout_s, image=image)
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
    """Carbon's public TRAIN numeric interface for Motor (copied verbatim)."""
    return json.loads(TRAIN_PROVENANCE.read_text(encoding="utf-8"))["numeric_interface"]


def _npy(rows, width):
    """A C-order little-endian float64 .npy (format 1.0), from the standard
    library: byte-identical to numpy's own writer for the same array."""
    shape = f"({len(rows)}, {width})"
    header = "{'descr': '<f8', 'fortran_order': False, 'shape': " + shape + ", }"
    pad = 64 - (10 + len(header) + 1) % 64
    header = header + " " * (pad % 64) + "\n"
    head = (
        b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header.encode("latin1")
    )
    body = b"".join(struct.pack(f"<{width}d", *row) for row in rows)
    return head + body


def _npz(inputs, targets):
    """The same container Carbon's public TRAIN uses (stored, fixed dates)."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, rows, width in (
            ("inputs", inputs, len(domain.INPUTS)),
            ("targets", targets, domain.ANGLE_STEPS),
        ):
            member = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o600 << 16
            with archive.open(member, "w", force_zip64=True) as stream:
                stream.write(_npy(rows, width))
    return output.getvalue()


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise KitError("a record holds a non-finite number")
    return float(value)


def parse(records_path):
    """Turn records.jsonl into (npz bytes, provenance). Only OK records with
    a buildable in-box case and a finite 60-value curve are kept; every other
    record is counted, never silently used."""
    records_path = refuse_protected(records_path)
    inputs, targets, case_ids, skipped = [], [], [], {}
    for line in Path(records_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        status = row.get("status")
        if row.get("schema") != RECORD_SCHEMA or status != "OK":
            skipped[status or "unknown"] = skipped.get(status or "unknown", 0) + 1
            continue
        check_case({"case_id": row.get("case_id"), "inputs": row.get("inputs")})
        curve = row.get("outputs", {}).get("torque_nm")
        if type(curve) is not list or len(curve) != domain.ANGLE_STEPS:
            raise KitError(
                f"{row['case_id']}: the torque curve must hold {domain.ANGLE_STEPS} values"
            )
        inputs.append([_finite(row["inputs"][name]) for name in domain.INPUTS])
        targets.append([_finite(v) for v in curve])
        case_ids.append(row["case_id"])
    if not case_ids:
        raise KitError("no OK records to parse")
    raw = _npz(inputs, targets)
    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "scope": SCOPE,
        "challenge": {"id": CHALLENGE_ID, "kit_version": KIT_VERSION},
        "reference": "your own run of Carbon's public Motor reference recipe; it may differ from Carbon's pinned reference, which alone grades",
        "source_schema": RECORD_SCHEMA,
        "train_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "case_ids": case_ids,
        "skipped": dict(sorted(skipped.items())),
        "numeric_interface": numeric_interface(),
    }
    return raw, provenance


def read_npz(path):
    """Read a kit or Carbon TRAIN npz back with the standard library:
    {name: (shape, rows)}."""
    result = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            data = archive.read(name)
            if data[:6] != b"\x93NUMPY":
                raise KitError(f"{name} is not a .npy")
            length = struct.unpack("<H", data[8:10])[0]
            header = data[10 : 10 + length].decode("latin1")
            if "'<f8'" not in header or "False" not in header:
                raise KitError(f"{name}: expected C-order float64")
            shape = tuple(
                int(x)
                for x in header.split("(")[1].split(")")[0].split(",")
                if x.strip()
            )
            body = data[10 + length :]
            n, width = shape
            values = struct.unpack(f"<{n * width}d", body)
            result[name.removesuffix(".npy")] = (
                shape,
                [list(values[i * width : (i + 1) * width]) for i in range(n)],
            )
    return result


# --- verify ------------------------------------------------------------------

#: Where the published verify set will sit (amendment A1). It is NOT shipped
#: yet: the set (inputs plus Carbon's pinned truths, R15: inner half of the
#: band, at least 0.10 from every sealed case, and in every later exclusion set)
#: needs the exclusion rerun and the Validator's digest receipt first.
VERIFY_SET = Path(__file__).with_name("verify_set.json")
#: The receipted sha256 of that file; `verify` refuses any other bytes.
VERIFY_SET_SHA256 = None
HUMAN_INPUT = "HUMAN_INPUT"
#: The graded quantities' registered measurement uncertainty U. Motor 1.5's
#: published values (docs/MINING.md); the verify set file carries Motor 1.7's
#: own U, which the Motor owner registers.
U_MOTOR_15 = {"mean_torque_nm": 0.0052, "ripple_fraction": 0.026}


def quantities(curve):
    """Mean torque and ripple fraction (peak-to-peak / mean), from the
    exam's own feasibility reading (`carbon.motor.exam.feasibility`)."""
    values = exam.feasibility(
        {"torque_nm": curve}, min_torque_nm=0.0, max_ripple_fraction=0.0
    )
    mean = values["mean_nm"]
    return {
        "mean_torque_nm": mean,
        "ripple_fraction": values["ripple_pk_pk_nm"] / mean if mean > 0 else math.inf,
    }


def verify_compare(verify_set, records):
    """Compare your records with Carbon's truths. Pass only when every verify
    design is OK and within U on every graded quantity."""
    u = verify_set.get("u")
    if type(u) is not dict or any(
        type(u.get(k)) not in (int, float) for k in U_MOTOR_15
    ):
        raise KitError("the verify set's U is not registered yet (HUMAN_INPUT)")
    mine = {r["case_id"]: r for r in records}
    rows, passed = [], True
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
        got = quantities(record["outputs"]["torque_nm"])
        want = quantities(design["truth"]["torque_nm"])
        row = {"case_id": design["case_id"], "status": "OK"}
        ok = True
        for name in sorted(U_MOTOR_15):
            limit = u[name]
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
            raise KitError("a verify design needs exactly the eight inputs")
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
        raise KitError("the verify set is not a Motor verify set")
    with _widened(verify_bounds(document["designs"])):
        for design in document["designs"]:
            check_case(design)
            curve = design.get("truth", {}).get("torque_nm")
            if type(curve) is not list or len(curve) != domain.ANGLE_STEPS:
                raise KitError(f"{design['case_id']}: the truth curve is malformed")
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
#: imports, with its sha256 at the commit this kit is built against. A change
#: to any of them fails the kit's CI test until the kit is re-pinned.
GRADE_MODULES = {
    "carbon/motor/exam.py": "d663ce2e78a2664cc7725908385b516418a83c635bccff4288b6da63a8eef8c9",
    "carbon/motor/score_candidates.py": "9464467a058ebf1104411b35b088930120ca796095fecb5a422cff2a946092e1",
    "carbon/scoring/motor_dual_measurement.py": "0546b29351695c1f4ed0179af3ceb755bac1d079a1b445f16c079491d6b914cb",
    "carbon/scoring/motor_dual_pack.py": "2b77ba5465bd3c46e9e308b7becf7fd332092a12dfa5286780c8586795ae9bda",
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

    Each part is the grade's own code, imported, never copied: the native
    per-case gates (`carbon.motor.exam.evaluate_case`); the per-case accuracy
    f0 = (mean + shape) / 2 (`carbon.motor.score_candidates.components`, with
    scales from the official TRAIN); the accuracy benefit 1 / (1 + f0 /
    f0_scale) (`carbon.scoring.motor_dual_measurement._benefit`, Motor's
    registered f0_scale); and |error| / U on the graded quantities. Sealed
    minimums, design value on hidden targets, the information budget and the
    speed gate on the validator's machine are NOT evaluated here and are never
    defaulted (amendment A5). This is a practice score, never a grade."""
    from carbon.motor import challenge
    from carbon.motor import score_candidates as candidates
    from carbon.scoring import motor_dual_measurement as mdm
    from carbon.scoring import motor_dual_pack

    if grade_pin() != GRADE_MODULES:
        raise KitError(
            "this checkout's grade code differs from the kit's pinned grading "
            "commit; update the checkout or the kit together"
        )
    if not isinstance(predictions, dict):
        raise KitError("predictions must map case_id to a 60-value torque curve")
    train = challenge.PublicMaterial.load(ROOT).train
    scales = candidates.scales(train)
    f0_scale = motor_dual_pack._definition_values()["f0_scale"]
    rows, f0s, gate_failed = [], [], []
    for record in records:
        case_id = record.get("case_id")
        if record.get("status") != "OK" or case_id not in predictions:
            continue
        prediction = {"torque_nm": [float(v) for v in predictions[case_id]]}
        verdict = exam.evaluate_case(prediction, record)
        row = {"case_id": case_id, "state": verdict["state"], "gates": verdict["gates"]}
        if verdict["state"] == exam.SCORABLE:
            parts = candidates.components(prediction, record, scales)
            f0 = (parts["mean"] + parts["shape"]) / 2
            f0s.append(f0)
            got = quantities(prediction["torque_nm"])
            want = quantities(record["outputs"]["torque_nm"])
            row["f0"] = f0
            row["error_over_u"] = {
                name: abs(got[name] - want[name]) / U_MOTOR_15[name]
                for name in sorted(U_MOTOR_15)
            }
        else:
            gate_failed.append(case_id)
        rows.append(row)
    if not rows:
        raise KitError("no OK kit case has a prediction")
    mean_f0 = sum(f0s) / len(f0s) if f0s else None
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
            "mean_f0": mean_f0,
            "f0_scale": f0_scale,
            "benefit": None if mean_f0 is None else mdm._benefit(mean_f0, f0_scale),
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
        "constraint": "carbon.motor.domain.validity: the slot is at least 1 mm wide where the coil starts, the opening is narrower than the slot behind it by 0.2 mm, and the slot is at least 1 mm deep",
        "sampling_law": population.__doc__.split("**Sampling law:**")[1]
        .split("\n\n")[0]
        .strip(),
    }
