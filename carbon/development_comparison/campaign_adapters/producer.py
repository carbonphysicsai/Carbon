"""Data Collection's campaign stages: battery v3, motor 10p/12s and f02 reference
and TRAIN (EVIDENCE-PRODUCER-STAGES-01).

    python -m carbon.development_comparison.campaign_adapters.producer --context FILE --output DIR

The campaign runner (#1080) calls this module for each `reference` or `train`
task. The frozen contract is
`docs/development/challenge_pipeline/evidence-producer-stages.md`:

- **Context.** A PUBLIC_DEVELOPMENT stage context for a registered family and
  phase, one shard, the runner's entrypoint registration digest. The vCPU
  allotment is the runner's `OMP_NUM_THREADS`. Unknown inputs are refused.
- **Steps.** Only the registered entrypoints (`scripts.dev.evidence_runs.*`,
  byte-pinned by `campaign_entrypoints`) and the helper files pinned in
  `PINNED` run. Each step's exit and wall go to the stage summary.
- **Metering.** Every solver container runs under one cgroup-v2 parent
  (`--cgroup-parent`, set through `CARBON_STAGE_CGROUP_PARENT`). The receipt's
  `core_s` is that parent's CPU usage plus this process's host children;
  `peak_ram_bytes` is the parent's memory peak plus the largest host child.
- **Outputs.** Single JSON documents under the runner's 32 MB input bound:
  the sealed solved-panel export, chunked raw records, the kit TRAIN rows and
  a stage summary, each with its role. Then the stage-result receipt.

Exit 2 is a refusal before or at a registered check (PRODUCER_REFUSED). Exit 1
is an infrastructure or reference failure (FAILED_INFRA), never a candidate
result. Nothing here grants spend, qualification or LIVE use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = "carbon.development-evidence-campaign.v1.stage-context"
STAGE_RESULT = "carbon.development-evidence-campaign.v1.stage-result"
RECORDS = "carbon.development-evidence-campaign.producer-records.v1"
TRAIN = "carbon.development-evidence-campaign.producer-train.v1"
SUMMARY = "carbon.development-evidence-campaign.producer-summary.v1"
FAILURE = "carbon.development-evidence-campaign.producer-failure.v1"
CGROUP_ENV = "CARBON_STAGE_CGROUP_PARENT"
CHUNK_BYTES = 16 * 1024 * 1024
PY = sys.executable
FAMILIES = {
    "battery-v3": {"entry": "scripts.dev.evidence_runs.battery_v3", "min_vcpus": 2},
    "motor": {"entry": "scripts.dev.evidence_runs.motor_10p12s", "min_vcpus": 3},
    "f02": {"entry": "scripts.dev.evidence_runs.f02", "min_vcpus": 2},
}
#: run directories a battery reuse bundle may fill (tiers 1-4, rung 3, #965)
BATTERY_DIRS = (
    "bfeas", "bfeas-t2", "bfeas-t2r", "bfeas-t3", "bfeas-t3r", "bfeas-t4a", "bfeas-t4b",
    "bfeas-t4r", "bfeas-t5r", "bfeas-t6r3", "bmid-a", "bmid-r2", "bmid-r3",
)  # fmt: skip
#: the motor reference panel solves into one run directory (stages 1-3's cases)
MOTOR_DIRS = ("motor-ref",)
REUSE_INPUT = re.compile(r"reuse_records_[0-9]{3}\Z")
#: every helper file a stage runs or imports, beyond the registered entrypoints
PINNED = {
    "carbon/battery/truth_env.py": "fee4a30b260d518d8bf4056e3f662f56a2747b4b3b3149c441eacb45c216bd8a",
    "scripts/dev/battery/feasibility02.py": "b4d974c4a2865871cd599f49b1365ced6c2e3f330334b687af1c1b06e8b256be",
    "scripts/dev/battery/guarded_reference.py": "791d23fa3e1a7aa69980e6e6c446bd36e40a1b7c397d9ca0eb6214f9061c0d45",
    "scripts/dev/score_lab/guarded419_t9.py": "e7136fd31b441139e0d342862d65ef07a83c2beddee025c9ee29442428cc9f09",
    "scripts/dev/battery/feasibility02_tier4.py": "997763fdc78c6b81372fe4109323591a38003af5d12c22142727531793416aa6",
    "scripts/dev/battery/feasibility02_v2.py": "17235eaddf8d505113999b5fd12585d94750e3f3166f1c846e941e6a347ac44c",
    "scripts/dev/battery/middle_bands.py": "de3a1523ea66f8c77c72d5a804bfe61a84225487ca60c0ea4c5296fded8023a3",
    "scripts/dev/battery/middle_bands_refine.py": "7c19f736465e17b2e17966db8269039cb1d04a16b97d9a184d0b0bdaa8fa84fe",
    "scripts/dev/battery/v3_panel_export.py": "c99ccd31f36dd185b3f83114a388b393f6d0d17f6878a77a3b387263118c1402",
    "scripts/dev/evidence_runs/comparison_inputs.py": "8837c5d1d2c97767e8ae62d12ee9f06923b8420823cf2e1c57d3392f6b9559d6",
    "scripts/dev/evidence_runs/common.py": "9d6b1cc835f1e6cb0593bf01c0d3ebd03385c0ee5bc1d5eee44519eac756bf19",
    "scripts/dev/evidence_runs/settlement.py": "a2e7af4ba2405284a4cd466124ea1d53032d2ecc9ce80b3dbceda74fe5345f75",
    "scripts/dev/motor/feasibility02/panel_export.py": "8ebd7be2be7ca9dd83ce8364d7e318b96071ad4667fcb6512ba73cbd506380ed",
    "scripts/dev/motor/feasibility02/run.py": "bf34864c82a939fcdde0042299f0ed9e5944c27fccde28b2b1e80e70dee594e6",
    "scripts/dev/reference_packages/elmer/f02_baselines.py": "1ae03bf7aeb498a45f161e7a518fccad54b7c427df9e356ed6ff69414be7516a",
    "scripts/dev/reference_packages/elmer/f02_deck.py": "80a7bf5f937cce64dab99afcec209418e99ec89d2eb80886e2ad88b3911af123",
    "scripts/dev/reference_packages/elmer/f02_export.py": "b9e1ce939cd0d024704baba5b1fb8882a5b3e16ce36aac8676f06be1e9def222",
    "scripts/dev/reference_packages/elmer/f02_menu.py": "9cce4f466101077e7aad04012fcc247fcdb5ecdbdd054653919069d18577f76d",
}


class Refused(Exception):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class Failed(Exception):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _registration():
    from carbon.development_comparison import campaign_entrypoints

    return campaign_entrypoints


def load_context(path, *, root=ROOT, environ=os.environ):
    """The validated context plus the vCPU allotment; refuses anything else."""
    entrypoints = _registration()
    context = json.loads(Path(path).read_text(encoding="utf-8"))
    fields = {"schema", "plan_digest", "entrypoint_registration_digest", "scope", "family", "phase",
              "shard", "shards", "inputs", "prior", "prior_receipts"}  # fmt: skip
    # #1131 adds the runner's explicit `vcpus`; a context without it is the #1080 shape
    if (
        type(context) is not dict
        or set(context) not in (fields, fields | {"vcpus"})
        or context["schema"] != CONTEXT
    ):
        raise Refused("STAGE_CONTEXT_INVALID")
    if context["scope"] != "PUBLIC_DEVELOPMENT":
        raise Refused("PUBLIC_DEVELOPMENT_ONLY")
    family, phase = context["family"], context["phase"]
    if family not in FAMILIES:
        raise Refused("FAMILY_NOT_PRODUCER", str(family))
    if phase not in ("reference", "train"):
        raise Refused("PHASE_NOT_PRODUCER", str(phase))
    if context["shard"] != 0 or context["shards"] != 1:
        raise Refused("SHARDING_NOT_REGISTERED")
    if context["entrypoint_registration_digest"] != entrypoints.digest():
        raise Refused("REGISTRATION_DIGEST_MISMATCH")
    if entrypoints.ENTRYPOINTS[family][phase] is None:
        raise Refused("ENTRYPOINT_NOT_REGISTERED", f"{family}/{phase}")
    if (
        entrypoints.inspect(root)[family][phase]
        != "REGISTERED_FILES_ONLY_IMAGE_NOT_CHECKED"
    ):
        raise Refused("ENTRYPOINT_PIN_MISMATCH", f"{family}/{phase}")
    for rel, pin in PINNED.items():
        target = Path(root) / rel
        if (
            not target.is_file()
            or hashlib.sha256(target.read_bytes()).hexdigest() != pin
        ):
            raise Refused("HELPER_PIN_MISMATCH", rel)
    reuse = []
    for name, descriptor in sorted(context["inputs"].items()):
        allowed = (
            phase == "reference"
            and family in ("battery-v3", "motor")
            and REUSE_INPUT.fullmatch(name)
        )
        if not allowed or descriptor.get("role") != "HELDOUT_REFERENCE":
            raise Refused("UNREGISTERED_INPUT", name)
        raw = Path(descriptor["path"]).read_bytes()
        if _sha(raw) != descriptor["sha256"]:
            raise Refused("INPUT_PIN_MISMATCH", name)
        reuse.append(_reuse_chunk(json.loads(raw), family))
    if family == "battery-v3" and phase == "reference" and not reuse:
        raise Refused("REUSE_RECORDS_REQUIRED", "the five-band export needs tiers 1-4")
    try:
        vcpus = int(environ.get("OMP_NUM_THREADS", ""))
    except ValueError:
        raise Refused("VCPU_ALLOTMENT_REQUIRED") from None
    if "vcpus" in context and (
        type(context["vcpus"]) is not int or context["vcpus"] != vcpus
    ):
        raise Refused(
            "VCPU_CONTEXT_MISMATCH",
            f"context {context['vcpus']!r}, environment {vcpus}",
        )
    if vcpus < FAMILIES[family]["min_vcpus"]:
        raise Refused("VCPU_ALLOTMENT_TOO_SMALL", str(vcpus))
    return context, vcpus, reuse


def _reuse_chunk(body, family):
    if (
        type(body) is not dict
        or set(body) != {"schema", "family", "chunk", "records"}
        or body["schema"] != RECORDS
        or body["family"] != family
        or type(body["records"]) is not list
    ):
        raise Refused("REUSE_RECORDS_INVALID")
    dirs = (
        BATTERY_DIRS
        if family == "battery-v3"
        else MOTOR_DIRS if family == "motor" else ()
    )
    for row in body["records"]:
        if (
            type(row) is not dict
            or set(row) != {"dir", "record"}
            or row["dir"] not in dirs
        ):
            raise Refused("REUSE_RECORDS_INVALID", "unregistered run directory")
    return body


def chunks(rows, prefix, family, schema=RECORDS):
    """[(file name, document)] in order, each document under CHUNK_BYTES."""
    out, current, size = [], [], 0
    for row in rows:
        n = len(json.dumps(row, sort_keys=True)) + 2
        if current and size + n > CHUNK_BYTES:
            out.append(current)
            current, size = [], 0
        current.append(row)
        size += n
    out.append(current)
    return [(f"{prefix}-{i:03d}.json", {"schema": schema, "family": family, "chunk": i, "records": part})
            for i, part in enumerate(out)]  # fmt: skip


def train_document(family, jsonl_path, record_schema, summary):
    raw = Path(jsonl_path).read_bytes()
    rows = [json.loads(x) for x in raw.decode().splitlines() if x.strip()]
    if "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode() != raw:
        raise Failed("TRAIN_EXPORT_NOT_CANONICAL")
    return {"schema": TRAIN, "family": family, "record_schema": record_schema,
            "jsonl_sha256": hashlib.sha256(raw).hexdigest(), "records": rows, "export": summary}  # fmt: skip


def _jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def _complete(expected_ids, rows, key, step):
    seen = {r[key] for r in rows}
    missing = [c for c in expected_ids if c not in seen]
    if missing:
        raise Failed(
            "RESULTS_INCOMPLETE", f"{step}: {len(missing)} missing, first {missing[0]}"
        )


class Meter:
    """One cgroup-v2 parent for every solver container of this stage."""

    def __init__(self, image, run=subprocess.run):
        self.image, self.run = image, run
        self.label = uuid.uuid4().hex[:16]
        self.name = f"carbon-stage-meter-{self.label}"
        self.parent = self.directory = self.driver = None

    def _out(self, argv):
        done = self.run(argv, capture_output=True, text=True, check=False)
        if done.returncode:
            raise Failed("METER_UNAVAILABLE", " ".join(argv[:3]))
        return done.stdout.strip()

    def __enter__(self):
        self.driver = self._out(["docker", "info", "--format", "{{.CgroupDriver}}"])
        if self._out(["docker", "info", "--format", "{{.CgroupVersion}}"]) != "2":
            raise Failed("METER_REQUIRES_CGROUP_V2")
        self.parent = (
            f"carbon-stage-{self.label}.slice"
            if self.driver == "systemd"
            else f"/carbon-stage-{self.label}"
        )
        self._out(["docker", "run", "-d", "--rm", "--name", self.name, "--network", "none",
                   "--cgroup-parent", self.parent, "--cpus", "0.05", "--memory", "32m",
                   "--entrypoint", "sleep", self.image, "infinity"])  # fmt: skip
        pid = self._out(["docker", "inspect", "-f", "{{.State.Pid}}", self.name])
        line = Path(f"/proc/{pid}/cgroup").read_text().strip().splitlines()[-1]
        self.directory = Path("/sys/fs/cgroup" + line.split("::", 1)[1]).parent
        return self

    def read(self):
        usage = next(
            int(x.split()[1])
            for x in (self.directory / "cpu.stat").read_text().splitlines()
            if x.startswith("usage_usec ")
        )
        peak = self.directory / "memory.peak"
        if not peak.exists():
            raise Failed("METER_MEMORY_PEAK_UNAVAILABLE")
        return usage / 1e6, int(peak.read_text().strip())

    def reap(self):
        """Stop every container left under this parent, the sentinel last."""
        ids = self.run(
            ["docker", "ps", "-q"], capture_output=True, text=True, check=False
        ).stdout.split()
        for cid in ids:
            parent = self.run(["docker", "inspect", "-f", "{{.HostConfig.CgroupParent}}", cid],
                              capture_output=True, text=True, check=False).stdout.strip()  # fmt: skip
            if parent == self.parent:
                self.run(["docker", "rm", "-f", cid], capture_output=True, check=False)

    def __exit__(self, *exc):
        self.reap()
        return False


def _watchdog(parent, pid):
    """Detached: after the stage process dies (a runner kill), stop its containers."""
    while True:
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(2)
    meter = Meter("")
    meter.parent = parent
    meter.reap()
    return 0


class Stage:
    def __init__(self, context, vcpus, reuse, output, run=subprocess.run):
        self.context, self.vcpus, self.reuse, self.output, self.run = (
            context,
            vcpus,
            reuse,
            Path(output),
            run,
        )
        self.family, self.phase = context["family"], context["phase"]
        self.work = self.output / "work"
        self.steps, self.counts, self.artifacts = [], {}, {}
        self.env = dict(os.environ)
        registration = _registration().ENTRYPOINTS[self.family][self.phase]
        self.row = registration
        self.entry = FAMILIES[self.family]["entry"]

    # -- steps ---------------------------------------------------------------
    def step(self, name, argv):
        log = self.output / "logs" / f"{len(self.steps):02d}-{name}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        begin = time.monotonic()
        with log.open("w") as handle:
            done = self.run(
                argv,
                cwd=ROOT,
                env=self.env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        self.steps.append({"step": name, "argv": [str(a) for a in argv[1:]], "returncode": done.returncode,
                           "wall_s": round(time.monotonic() - begin, 3)})  # fmt: skip
        if done.returncode == 2:
            raise Refused("PRODUCER_CHECK_REFUSED", name)
        if done.returncode:
            raise Failed("STEP_FAILED", name)

    def entry_step(self, name, *args):
        self.step(name, [PY, "-m", self.entry, *args])

    def script(self, name, rel, *args):
        self.step(name, [PY, str(ROOT / rel), *args])

    # -- artifacts -----------------------------------------------------------
    def emit(self, name, document, role):
        target = self.output / name
        target.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        raw = target.read_bytes()
        if len(raw) > 32 * 1024 * 1024:
            raise Failed("ARTIFACT_TOO_LARGE", name)
        self.artifacts[Path(name).stem] = {
            "path": name,
            "sha256": _sha(raw),
            "role": role,
        }

    def emit_chunks(self, prefix, rows, role):
        for name, document in chunks(rows, prefix, self.family):
            self.emit(name, document, role)

    def emit_export(self, path):
        from carbon.design_search import producer_panels

        export = json.loads(Path(path).read_text())
        try:
            producer_panels.adapt_export(export)
        except ValueError as exc:
            raise Failed("EXPORT_REFUSED_BY_MAIN", str(exc)) from None
        if export["family"] != self.family:
            raise Failed("EXPORT_FAMILY_MISMATCH")
        self.counts["export_digest"] = export["export_digest"]
        self.emit("panel-export.json", export, "HELDOUT_REFERENCE")
        return export

    def comparison_inputs(self, export_path, ledger_args):
        """The candidate view (PUBLIC_INPUT, for the TRAIN stage's model), the
        measured cost ledger and, for a plain export, the replay bindings."""
        tool = "scripts/dev/evidence_runs/comparison_inputs.py"
        view = self.work / "candidate-view.json"
        self.script("candidate-view", tool, "view", export_path, view)
        self.emit("candidate-view.json", json.loads(view.read_text()), "PUBLIC_INPUT")
        ledger = self.work / "cost-ledger.json"
        self.script("cost-ledger", tool, *ledger_args, ledger)
        self.emit(
            "cost-ledger.json", json.loads(ledger.read_text()), "HELDOUT_REFERENCE"
        )
        if self.family in ("f02", "motor"):
            bindings = self.work / "bindings.json"
            self.script("bindings", tool, "bindings", export_path, bindings)
            self.emit(
                "bindings.json", json.loads(bindings.read_text()), "HELDOUT_REFERENCE"
            )

    def model_predictions(self, jsonl):
        """The Carbon arm's registered default recipe on this registered TRAIN,
        queried on the reference stage's candidate view (never its values)."""
        views = [
            artifacts["candidate-view"]
            for key, artifacts in self.context["prior"].items()
            if key.startswith(f"{self.family}/reference/")
            and "candidate-view" in artifacts
        ]
        if not views:
            raise Failed(
                "CANDIDATE_VIEW_REQUIRED", "the reference stage's candidate view"
            )
        view = views[0]
        if (
            view.get("role") != "PUBLIC_INPUT"
            or _sha(Path(view["path"]).read_bytes()) != view["sha256"]
        ):
            raise Failed("CANDIDATE_VIEW_PIN_MISMATCH")
        pred, receipt = (
            self.work / "carbon-predictions.json",
            self.work / "carbon-receipt.json",
        )
        # motor's kit needs its panel designs' geometry, read from the registered reference plan
        extra = (
            [_registration().ENTRYPOINTS["motor"]["reference"]["plan"]]
            if self.family == "motor"
            else []
        )
        self.script("model", "scripts/dev/evidence_runs/comparison_inputs.py", "predict", self.family,
                    view["path"], jsonl, pred, receipt, *extra)  # fmt: skip
        self.emit("carbon-predictions.json", json.loads(pred.read_text()), "MODEL")
        self.emit("carbon-receipt.json", json.loads(receipt.read_text()), "MODEL")

    # -- families --------------------------------------------------------------
    def overlay(self, meter):
        from carbon.battery import truth_env

        target = self.work / "overlay"
        truth_env.materialize(target, repository=str(ROOT))

        def runner(argv, **kw):
            kw.pop("check", None)
            return subprocess.run(
                [*argv[:3], "--cgroup-parent", meter.parent, *argv[3:]],
                check=False,
                **kw,
            )

        truth_env.verify(target, repository=str(ROOT), runner=runner)
        return target

    def battery_reference(self, meter):
        runs = self.work / "runs"
        for chunk in self.reuse:
            for row in chunk["records"]:
                path = runs / row["dir"] / "records.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a") as handle:
                    handle.write(json.dumps(row["record"], sort_keys=True) + "\n")
        self.entry_step("check", "check", "--kind", "panel-a")
        overlay = self.overlay(meter)
        workers = str(self.vcpus - 1)
        self.entry_step("solve-stage-a", "solve", "--kind", "panel-a", "--overlay", overlay,
                        "--out", runs / "bmid-a", "--workers", workers)  # fmt: skip
        plan = json.loads((ROOT / self.row["plan"]).read_text())
        _complete(
            [j["case_id"] for j in plan["jobs"]],
            _jsonl(runs / "bmid-a/records.jsonl"),
            "case_id",
            "stage-a",
        )
        for rung, out in (("rung2", "bmid-r2"), ("rung3", "bmid-r3")):
            plan_path = self.work / f"{rung}-plan.json"
            self.script(
                f"plan-{rung}",
                "scripts/dev/battery/middle_bands_refine.py",
                rung,
                runs,
                plan_path,
            )
            jobs = json.loads(plan_path.read_text())["jobs"]
            self.counts[f"{rung}_jobs"] = len(jobs)
            self.counts[f"{rung}_plan_sha256"] = _sha(plan_path.read_bytes())
            if jobs:
                self.step(f"solve-{rung}", [PY, "-m", "scripts.dev.battery.feasibility02", "run", plan_path,
                                            "--overlay", overlay, "--out", runs / out, "--workers", workers,
                                            "--cpus", workers])  # fmt: skip
                _complete(
                    [j["case_id"] for j in jobs],
                    _jsonl(runs / out / "records.jsonl"),
                    "case_id",
                    rung,
                )
        export = self.work / "panel-export.json"
        self.script(
            "export",
            "scripts/dev/battery/v3_panel_export.py",
            "--campaign",
            runs,
            export,
        )
        self.emit_export(export)
        self.comparison_inputs(export, ("ledger-battery", export, runs))
        rows = [
            {"dir": d.name, "record": r}
            for d in sorted(runs.iterdir())
            for r in _jsonl(d / "records.jsonl")
        ]
        self.counts["records"] = len(rows)
        self.counts["not_ok"] = sum(r["record"].get("status") != "OK" for r in rows)
        self.emit_chunks("reference-records", rows, "HELDOUT_REFERENCE")

    def f02_reference(self, meter):
        root = self.work / "f02"
        parallel = str(self.vcpus - 1)
        self.entry_step("plan", "plan", "--kind", "menu", "--root", root)
        self.entry_step(
            "solve", "solve", "--kind", "menu", "--root", root, "--parallel", parallel
        )
        self._f02_complete(root, "menu")
        menu = "scripts/dev/reference_packages/elmer/f02_menu.py"
        self.script("plan-refine", menu, "plan-refine", root)
        self.script(
            "solve-refine",
            menu,
            "run",
            root,
            "--parallel",
            parallel,
            "--image",
            self.row["image_digest"],
        )
        self._f02_complete(root, "refine")
        baselines = self.work / "f02-baselines"
        self.script(
            "plan-baselines",
            "scripts/dev/reference_packages/elmer/f02_baselines.py",
            "plan",
            baselines,
        )
        registered = (
            ROOT
            / "docs/development/evidence/reference-packages-01/f02-menu-v2/baseline-decks-manifest.json"
        )
        if (baselines / "manifest.json").read_bytes() != registered.read_bytes():
            raise Refused("BASELINE_DECKS_DIFFER_FROM_REGISTERED")
        self.script(
            "solve-baselines",
            menu,
            "run",
            baselines,
            "--parallel",
            parallel,
            "--image",
            self.row["image_digest"],
        )
        self._f02_complete(baselines, "baselines")
        export = self.work / "panel-export.json"
        self.script(
            "export", "scripts/dev/reference_packages/elmer/f02_export.py", root, export
        )
        self.emit_export(export)
        self.comparison_inputs(export, ("ledger-f02", export, root))
        materials = self.work / "comparator"
        self.script("comparator-materials", "scripts/dev/evidence_runs/comparison_inputs.py", "f02-materials",
                    export, root, baselines, materials)  # fmt: skip
        for path in sorted(materials.glob("*.json")):
            self.emit(path.name, json.loads(path.read_text()), "HELDOUT_REFERENCE")
        ledger = _jsonl(root / "ledger.jsonl")
        self.counts["records"] = len(ledger)
        self.counts["not_completed"] = sum(
            r.get("outcome") != "COMPLETED" for r in ledger
        )
        self.emit_chunks(
            "reference-records",
            [{"dir": "ledger", "record": r} for r in ledger],
            "HELDOUT_REFERENCE",
        )

    def motor_reference(self, meter):
        runs = self.work / "runs" / "motor-ref"
        runs.mkdir(parents=True, exist_ok=True)
        for chunk in self.reuse:
            with (runs / "records.jsonl").open("a") as handle:
                for row in chunk["records"]:
                    handle.write(json.dumps(row["record"], sort_keys=True) + "\n")
        self.entry_step("check", "check", "--kind", "reference-panel")
        parallel = str(max(1, (self.vcpus - 1) // 2))  # two CPUs per motor case
        self.entry_step(
            "solve",
            "solve",
            "--kind",
            "reference-panel",
            "--out",
            runs,
            "--parallel",
            parallel,
        )
        plan = ROOT / self.row["plan"]
        cases = json.loads(plan.read_text())["cases"]
        _complete(
            [c["case_id"] for c in cases],
            _jsonl(runs / "records.jsonl"),
            "case_id",
            "reference",
        )
        export = self.work / "panel-export.json"
        self.step("export", [PY, "-m", "scripts.dev.motor.feasibility02.panel_export", "--runs", runs,
                             "--plan", plan, "--out", export, "--campaign"])  # fmt: skip
        self.emit_export(export)
        self.comparison_inputs(export, ("ledger-motor", export, runs))
        curves = self.work / "comparator-materials.json"
        self.script("comparator-materials", "scripts/dev/evidence_runs/comparison_inputs.py", "motor-curves",
                    export, runs, plan, curves)  # fmt: skip
        self.emit(
            "comparator-materials.json",
            json.loads(curves.read_text()),
            "HELDOUT_REFERENCE",
        )
        rows = [
            {"dir": "motor-ref", "record": r} for r in _jsonl(runs / "records.jsonl")
        ]
        self.counts["records"] = len(rows)
        self.counts["not_ok"] = sum(r["record"].get("status") != "OK" for r in rows)
        self.emit_chunks("reference-records", rows, "HELDOUT_REFERENCE")

    def _f02_complete(self, root, step):
        cases = [
            e["case"] for e in json.loads((root / "manifest.json").read_text())["cases"]
        ]
        _complete(cases, _jsonl(root / "ledger.jsonl"), "case", step)

    def train(self, meter):
        out = self.work / "train"
        jsonl = self.work / "train.jsonl"
        kind = self.row["kind"]
        par = str(self.vcpus - 1)
        if self.family == "f02":
            self.entry_step("plan", "plan", "--kind", kind, "--root", out)
            self.entry_step(
                "solve", "solve", "--kind", kind, "--root", out, "--parallel", par
            )
            self._f02_complete(out, "train")
            diagnostics = self.work / "train-diagnostics.jsonl"
            self.entry_step(
                "export-train",
                "export-train",
                "--root",
                out,
                "--out",
                jsonl,
                "--diagnostics",
                diagnostics,
            )
            raw = _jsonl(out / "ledger.jsonl")
            self.emit_chunks("train-diagnostics", _jsonl(diagnostics), "PUBLIC_TRAIN")
            schema = "carbon.f02.train-record.v1"
        else:
            self.entry_step("check", "check", "--kind", kind)
            if self.family == "battery-v3":
                overlay = self.overlay(meter)
                self.entry_step(
                    "solve",
                    "solve",
                    "--kind",
                    kind,
                    "--overlay",
                    overlay,
                    "--out",
                    out,
                    "--workers",
                    par,
                )
                schema = "carbon.battery-v3.train-record.v1"
                jobs = json.loads((ROOT / self.row["plan"]).read_text())["jobs"]
            else:
                parallel = str(max(1, (self.vcpus - 1) // 2))  # two CPUs per motor case
                self.entry_step(
                    "solve",
                    "solve",
                    "--kind",
                    kind,
                    "--out",
                    out,
                    "--parallel",
                    parallel,
                )
                schema = "carbon.motor-10p12s.train-record.v1"
                jobs = json.loads((ROOT / self.row["plan"]).read_text())["cases"]
            raw = _jsonl(out / "records.jsonl")
            _complete([j["case_id"] for j in jobs], raw, "case_id", "train")
            self.entry_step(
                "export-train", "export-train", "--runs", out, "--out", jsonl
            )
        rows = _jsonl(jsonl)
        self.counts.update({"train_records": len(raw), "train_rows": len(rows)})
        self.emit("train.json", train_document(self.family, jsonl, schema, {"rows": len(rows), "raw": len(raw)}),
                  "PUBLIC_TRAIN")  # fmt: skip
        self.emit_chunks(
            "train-records",
            [{"dir": "train", "record": r} for r in raw],
            "PUBLIC_TRAIN",
        )
        self.model_predictions(jsonl)

    # -- the stage -------------------------------------------------------------
    def execute(self):
        import resource

        self.work.mkdir(parents=True, exist_ok=True)
        with Meter(self.row["image_digest"], self.run) as meter:
            self.env[CGROUP_ENV] = meter.parent
            subprocess.Popen([PY, "-m", __spec__.name, "--watchdog", meter.parent, str(os.getpid())],
                             cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)  # fmt: skip
            if self.phase == "train":
                self.train(meter)
            elif self.family == "battery-v3":
                self.battery_reference(meter)
            elif self.family == "f02":
                self.f02_reference(meter)
            else:
                self.motor_reference(meter)
            # Every solve step has returned; read before the sentinel leaves,
            # since an empty systemd slice may be collected.
            container_s, container_peak = meter.read()
        children = resource.getrusage(resource.RUSAGE_CHILDREN)
        host_s = children.ru_utime + children.ru_stime
        host_peak = children.ru_maxrss * 1024
        meter_row = {"method": "cgroup-v2 parent of every solver container", "cgroup_driver": meter.driver,
                     "container_core_s": container_s, "container_memory_peak_bytes": container_peak,
                     "host_children_core_s": host_s, "host_children_maxrss_bytes": host_peak}  # fmt: skip
        self.emit("stage-summary.json", {"schema": SUMMARY, "family": self.family, "phase": self.phase,
                                         "entrypoint": self.row, "vcpus": self.vcpus, "steps": self.steps,
                                         "counts": self.counts, "meter": meter_row}, "ANALYSIS")  # fmt: skip
        receipt = {
            "schema": STAGE_RESULT, "plan_digest": self.context["plan_digest"], "family": self.family,
            "phase": self.phase, "shard": 0, "status": "OK", "core_s": round(container_s + host_s, 3),
            "peak_ram_bytes": int(container_peak + host_peak), "artifacts": self.artifacts,
        }  # fmt: skip
        (self.output / "receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        )
        return receipt


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--watchdog"]:
        return _watchdog(argv[1], int(argv[2]))
    parser = argparse.ArgumentParser(
        prog="campaign_adapters.producer", description=__doc__.split("\n")[0]
    )
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    try:
        context, vcpus, reuse = load_context(args.context)
        Stage(context, vcpus, reuse, args.output).execute()
        return 0
    except (Refused, Failed) as stop:
        (args.output / "failure.json").write_text(
            json.dumps(
                {
                    "schema": FAILURE,
                    "kind": type(stop).__name__,
                    "code": stop.code,
                    "detail": str(stop),
                }
            )
            + "\n"
        )
        return 2 if isinstance(stop, Refused) else 1


if __name__ == "__main__":
    sys.exit(main())
