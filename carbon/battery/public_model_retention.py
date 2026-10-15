"""Opt-in, miner-owned public Graphite test inventory; never an upload/admission.

The fixed public practice stages and programs define the accessible material.
This module grants no evaluator access and never loads a model on the host.
Original weights missing from an older run cannot be recovered by this path.
"""

from __future__ import annotations

import json
import re
from functools import wraps
from pathlib import Path

from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_workspace import ResearchWorkspace

OPT_IN_FILE = "public-model-retention-opt-in.json"
OPT_IN_SCHEMA = "carbon.battery.public-model-retention-opt-in.v1"
PROGRAM_VERSION = "carbon.battery.public-graphite-model-retention.v1"
INVENTORY_SCHEMA = "carbon.battery.public-graphite-model-inventory.v1"
STATE_FILE = "state.npz"
SIDECAR_FILE = "model-retention.json"
STAGED_FILE = "public-model-retention.json"
MAX_STATE_BYTES = 64 * 1024**2
CHALLENGE = "battery-fastcharge-ageing-development-v1"
_FIELDS = {"schema", "campaign_id", "scope", "program_version", "source_commit"}


def _descriptor(value, campaign_id, agent):
    if (
        type(value) is not dict
        or set(value) != _FIELDS
        or value.get("schema") != OPT_IN_SCHEMA
        or value.get("campaign_id") != campaign_id
        or type(campaign_id) is not str
        or not campaign_id
        or value.get("scope") != "PUBLIC_GRAPHITE_TEST"
        or value.get("program_version") != PROGRAM_VERSION
        or agent != "graphite"
        or type(value.get("source_commit")) is not str
        or re.fullmatch(r"[0-9a-f]{40}", value["source_commit"]) is None
    ):
        raise ValueError("exact public Graphite test retention opt-in required")
    return dict(value)


def launch_opt_in(root, *, campaign_id, agent):
    """Read only the named local opt-in, before a new campaign is frozen.

    Absent means the old behavior. A malformed/present opt-in fails closed.
    Resumes use the immutable campaign manifest, not a mutable local switch.
    """
    path = Path(root) / OPT_IN_FILE
    if path.is_symlink():
        raise ValueError("retention opt-in symlink rejected")
    if not path.exists():
        return {}
    if not path.is_file() or not 0 < path.stat().st_size <= 4096:
        raise ValueError("bounded local retention opt-in required")
    value = _descriptor(json.loads(path.read_bytes()), campaign_id, agent)
    return {"public_model_retention": value}


def frozen_opt_in(manifest, *, owner):
    """An explicit test opt-in bound to this miner/campaign/Challenge only."""
    value = manifest.get("public_model_retention")
    if value is None:
        return None
    if (
        manifest.get("owner") != owner
        or manifest.get("challenge", {}).get("id") != CHALLENGE
        or manifest.get("provider", {}).get("agent") != "graphite"
    ):
        raise ValueError("retention opt-in campaign binding differs")
    return _descriptor(value, manifest.get("campaign_id"), manifest.get("agent"))


# Appended to a NEW program identity. Existing CPU/GPU program bytes and
# registered program versions remain unchanged, including historical pins.
_WRITER = r"""
import hashlib, importlib.metadata, platform, time

_retention_wall = time.monotonic()
_retention_cpu = time.process_time()
_retention_state = recipes.state_bytes(model)
if not 0 < len(_retention_state) <= 64 * 1024**2:
    raise ValueError("public test model exceeds retained-state bound")
(out / "state.npz").write_bytes(_retention_state)
def _retention_sha(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()
_retention_packages = {}
for _package in ("numpy", "jax", "jaxlib", "torch"):
    try:
        _retention_packages[_package] = importlib.metadata.version(_package)
    except importlib.metadata.PackageNotFoundError:
        pass
_retention = json.loads((work / "public-model-retention.json").read_bytes())
_retention.update({
    "schema": "carbon.battery.public-graphite-model-artifact.v1",
    "state_schema": recipes.STATE_SCHEMA,
    "state": {"file": "state.npz", "sha256": _retention_sha(_retention_state),
              "bytes": len(_retention_state)},
    "recipe_digest": recipe["recipe_digest"],
    "seed": recipe["seed"],
    "params_sha256": stats.get("params_sha256"),
    "files": {name: _retention_sha((out / name).read_bytes())
              for name in ("predictions.json", "fit.json")},
    "runtime": {"python": platform.python_version(), "packages": _retention_packages,
                "machine": platform.machine()},
    "fit_cost": _retention_fit_cost,
    "prediction_cost": _retention_prediction_cost,
    "retention_cost": {"wall_s": time.monotonic() - _retention_wall,
                       "cpu_s": time.process_time() - _retention_cpu,
                       "state_bytes": len(_retention_state)},
})
(out / "model-retention.json").write_text(
    json.dumps(_retention, sort_keys=True, separators=(",", ":"), allow_nan=False)
)
"""


def retained_program(source, files, *, opt_in, identity, image):
    """Wrap only the known public practice programs and closed public stage.

    The carrier still owns all output parsing, resource admission and accounting.
    There is no host path, network destination or hidden input parameter.
    """
    from carbon.development_session.battery_gpu import GPU_PROGRAM, TORCH_GPU_PROGRAM

    from .challenge import OCV_TABLE_SHA256, TRAIN_V1_SHA256
    from .domain import CAPACITY_CYCLES, GRID_POINTS, GRID_STEP_S, INPUTS, OUTPUTS
    from .practice import (
        FEEDBACK_SCHEMA,
        PRACTICE_SOURCE_SHA256,
        PROGRAM,
        STAGED_MODULES,
    )

    opt_in = _descriptor(
        opt_in, opt_in.get("campaign_id") if type(opt_in) is dict else None, "graphite"
    )
    if type(image) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", image) is None:
        raise ValueError("retention requires an exact worker image identity")

    allowed = {
        *STAGED_MODULES,
        "train-v1.jsonl.gz",
        "ocv-table.json",
        "practice-inputs.json",
        "recipe.json",
    }
    if source not in (PROGRAM, GPU_PROGRAM, TORCH_GPU_PROGRAM) or set(files) != allowed:
        raise ValueError("retention requires the fixed public battery practice stage")
    if digest(files["train-v1.jsonl.gz"]) != "sha256:" + TRAIN_V1_SHA256:
        raise ValueError("retention requires pinned public TRAIN")
    inputs = json.loads(files["practice-inputs.json"])
    if (
        type(inputs) is not dict
        or type(inputs.get("cases")) is not list
        or any(
            type(case) is not dict or set(case) != {"case_id", "inputs"}
            for case in inputs["cases"]
        )
    ):
        raise ValueError("retention requires public practice inputs without labels")
    fit = 'stats = model.fit(train, structure, recipe["seed"])\n'
    predict = (
        'cases = json.loads((work / "practice-inputs.json").read_text())["cases"]\n'
    )
    prediction_end = 'predictions = recipes.to_predictions(model.predict(x), [c["case_id"] for c in cases])\n'
    if any(source.count(line) != 1 for line in (fit, predict, prediction_end)):
        raise ValueError("public practice retention instrumentation seam differs")
    program = (
        source.replace(
            fit,
            """import time
_retention_fit_wall, _retention_fit_cpu = time.monotonic(), time.process_time()
"""
            + fit
            + """_retention_fit_cost = {
    "wall_s": time.monotonic() - _retention_fit_wall,
    "host_process_cpu_s": time.process_time() - _retention_fit_cpu,
}
""",
        )
        .replace(
            predict,
            """_retention_prediction_wall, _retention_prediction_cpu = time.monotonic(), time.process_time()
"""
            + predict,
        )
        .replace(
            prediction_end,
            prediction_end + """_retention_prediction_cost = {
    "wall_s": time.monotonic() - _retention_prediction_wall,
    "host_process_cpu_s": time.process_time() - _retention_prediction_cpu,
    "includes_input_conversion": True,
}
""",
        )
        + _WRITER
    )
    provenance = {
        "opt_in": dict(opt_in),
        "trial_identity": identity,
        "image": image,
        "program_version": PROGRAM_VERSION,
        "program_sha256": digest(program.encode()),
        "base_program_sha256": digest(source.encode()),
        "staged": {name: digest(body) for name, body in sorted(files.items())},
        "public_material": {
            "train_source_sha256": "sha256:" + TRAIN_V1_SHA256,
            "ocv_source_sha256": "sha256:" + OCV_TABLE_SHA256,
            "practice_source_sha256": "sha256:" + PRACTICE_SOURCE_SHA256,
        },
        "semantics": {
            "inputs": list(INPUTS),
            "outputs": list(OUTPUTS),
            "grid_step_s": GRID_STEP_S,
            "grid_points": GRID_POINTS,
            "capacity_cycles": list(CAPACITY_CYCLES),
            "feedback_schema": FEEDBACK_SCHEMA,
            "scope": "original battery public practice; no cooling/switch outputs",
        },
    }
    return program, {**files, STAGED_FILE: canonical(provenance)}, provenance


def _snapshot_file(ledger, worker, name, maximum, *, owner=None):
    operation = worker.get("operation")
    if (
        type(operation) is not str
        or re.fullmatch(r"operation-[0-9a-f]{64}", operation) is None
    ):
        raise ValueError("retention operation binding differs")
    folder = ledger.root / operation
    snapshot = folder / "snapshot"
    path = snapshot / name
    if any(p.is_symlink() for p in (folder, snapshot, path)):
        raise ValueError("retained model symlink rejected")
    if not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise ValueError("bounded retained model artifact required")
    body = path.read_bytes()
    if digest(body) != worker.get("files", {}).get(name):
        if owner is not None:
            from carbon.development_session.research_carrier import record_output_tamper

            record_output_tamper(
                ledger,
                owner=owner,
                operation=operation,
                name=name,
                expected=worker.get("files", {}).get(name),
                observed=digest(body),
            )
        raise ValueError("retained model output digest differs")
    return body


def record_trial(function):
    """Journal the whole opted-in callback, including compile/worker failures."""

    @wraps(function)
    def recorded(self, identity, strategy):
        opt_in = getattr(self, "model_retention", None)
        if opt_in is None:
            return function(self, identity, strategy)
        trial = Trial(self.ledger, self.owner, identity, strategy, opt_in)
        try:
            result = function(self, identity, strategy, retention_trial=trial)
            trial.completed(result)
            return result
        except BaseException as error:
            trial.failed(error)
            raise

    return recorded


class Trial:
    """One record per trial, written before compile; selection cannot filter it.

    Model bytes stay in the accounted operation snapshot. The small inventory
    is in the existing owner-only workspace and carries only local references.
    A crash leaves INCOMPLETE, rather than pretending a model was retained.
    """

    def __init__(self, ledger, owner, identity, strategy, opt_in):
        opt_in = _descriptor(
            opt_in,
            opt_in.get("campaign_id") if type(opt_in) is dict else None,
            "graphite",
        )
        self.ledger = ledger
        self.workspace = ResearchWorkspace(ledger, owner)
        self.name = "trial-" + digest(identity.encode())[7:39] + "-public-model.json"
        manifest = ledger.root / "campaign-manifest.json"
        if manifest.is_symlink():
            raise ValueError("retention campaign manifest symlink rejected")
        self.record = {
            "schema": INVENTORY_SCHEMA,
            "campaign_id": opt_in["campaign_id"],
            "trial_identity": identity,
            "requested_strategy_sha256": digest(canonical(strategy)),
            "opt_in": dict(opt_in),
            "campaign_manifest_sha256": (
                digest(manifest.read_bytes()) if manifest.is_file() else None
            ),
            "status": "INCOMPLETE",
            "stage": "compile",
            "selected": None,
            "state": {"status": "NOT_RETAINED"},
            "official_eligible": False,
            "scientific_qualification": False,
            "evidence": "PUBLIC_ADAPTIVELY_SEEN_DEVELOPMENT",
        }
        previous = self.workspace.current_digest(self.name)
        if previous is not None:
            existing = json.loads(self.workspace.get(self.name))
            if any(
                existing.get(k) != self.record[k]
                for k in (
                    "schema",
                    "campaign_id",
                    "trial_identity",
                    "requested_strategy_sha256",
                    "opt_in",
                    "campaign_manifest_sha256",
                )
            ):
                raise ValueError("retention trial identity reused with another request")
            self.record = existing
        else:
            self._save()

    def _save(self):
        self.workspace.put(
            self.name,
            canonical(self.record),
            expected_digest=self.workspace.current_digest(self.name),
        )

    def dispatch(self, provenance, recipe):
        if any(
            key in self.record and self.record[key] != value
            for key, value in (("provenance", provenance), ("recipe", recipe))
        ):
            raise ValueError("retention trial immutable provenance differs")
        if self.record["status"] == "COMPLETED":
            return
        self.record.update(stage="worker", provenance=provenance, recipe=recipe)
        self._save()

    def collect(self, worker, provenance):
        def checked(name, maximum):
            return _snapshot_file(
                self.ledger, worker, name, maximum, owner=self.workspace.owner
            )

        sidecar_body = checked(SIDECAR_FILE, 65536)
        sidecar = json.loads(sidecar_body)
        state = checked(STATE_FILE, MAX_STATE_BYTES)
        if (
            type(sidecar) is not dict
            or sidecar.get("schema")
            != "carbon.battery.public-graphite-model-artifact.v1"
            or sidecar.get("state_schema") != "carbon.battery.model-state.v1"
            or any(sidecar.get(k) != v for k, v in provenance.items())
            or sidecar.get("state")
            != {"file": STATE_FILE, "sha256": digest(state), "bytes": len(state)}
        ):
            raise ValueError("retained model provenance differs")
        recipe = self.record["recipe"]
        if (
            sidecar.get("recipe_digest") != recipe["recipe_digest"]
            or sidecar.get("seed") != recipe["seed"]
        ):
            raise ValueError("retained model recipe differs")
        for name, maximum in (("predictions.json", 16 * 1024**2), ("fit.json", 65536)):
            body = checked(name, maximum)
            if sidecar.get("files", {}).get(name) != digest(body):
                raise ValueError("retained model prediction/fit binding differs")
        fit = json.loads(checked("fit.json", 65536))
        if sidecar.get("params_sha256") != fit.get("params_sha256"):
            raise ValueError("retained model parameter digest differs")
        if self.record["status"] == "COMPLETED":
            return
        operation = worker["operation"]
        self.record.update(
            stage="feedback",
            state={
                "status": "RETAINED",
                "path": f"{operation}/snapshot/{STATE_FILE}",
                "sha256": digest(state),
                "bytes": len(state),
            },
            artifacts={
                name: {"path": f"{operation}/snapshot/{name}", "sha256": sha}
                for name, sha in worker["files"].items()
                if name
                in {
                    STATE_FILE,
                    SIDECAR_FILE,
                    "predictions.json",
                    "fit.json",
                    "runtime.json",
                }
            },
            worker={
                k: worker.get(k) for k in ("operation", "output_digest", "provenance")
            },
            artifact_provenance=sidecar,
        )
        self._save()

    def completed(self, feedback):
        if self.record["status"] == "COMPLETED":
            if self.record["feedback"]["sha256"] != digest(canonical(feedback)):
                raise ValueError("retention trial feedback identity differs")
            return
        self.record.update(
            status="COMPLETED",
            stage="complete",
            feedback={
                "schema": feedback["schema"],
                "workspace_name": "trial-"
                + digest(self.record["trial_identity"].encode())[7:23]
                + "-battery-practice.json",
                "sha256": digest(canonical(feedback)),
                "summary": feedback["summary"],
                "backend": feedback["backend"],
            },
        )
        self._save()

    def failed(self, error):
        # A failed replay cannot rewrite historical successful evidence.
        if self.record["status"] == "COMPLETED":
            return
        self.record.update(status="FAILED", failure_type=type(error).__name__)
        self._save()


def inventory(ledger, *, owner):
    """All opted-in trials, including failures/incomplete, without model loading.

    This is local producer inventory; Root supplies actual bytes to ScoreLab.
    It does not create a ScoreLab cohort, truth join, or accepted model label.
    """
    workspace = ResearchWorkspace(ledger, owner)
    return [
        json.loads(workspace.get(row["name"]))
        for row in workspace.inventory()
        if row["name"].startswith("trial-")
        and row["name"].endswith("-public-model.json")
    ]
