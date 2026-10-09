"""Battery reconstruction and inference for the validator, kept apart.

Two fixed programs, each run in its own isolated worker:
- **reconstruct** sees public TRAIN v1, the OCV table, the compiled recipe and
  Carbon's seed. It exports the trained model state and fit statistics. It
  never sees a query input.
- **infer** sees one retained model state and the query inputs (case ids and
  the four inputs). It exports predictions. It never sees a label, a
  reference record or a seed.

Neither program is miner code. A miner supplies only a declarative recipe, and
Carbon's own recipe bytes (`domain.py`, `recipes.py`, `training.py`) are
staged exactly. Reference answers stay on the trusted host, and the scorer
reads them there.

Backends:
- `CarrierBackend` runs both programs through the existing isolated carrier
  (`research_carrier._run`): no network, read-only root, dropped capabilities,
  bounded memory and wall clock, exported through the bounded output stream.
  It holds one pinned worker image per reconstruction backend
  (OWNER-PYTORCH-BACKEND-01): the C-03 JAX image, and the PyTorch image when
  the deployment names one. A recipe is rebuilt, and its state predicts, in
  the image of the backend it names.
  Its work ledger is the validator's own (`WorkLedger`), so a completed run
  replays its stored result after a restart, and an unresolved run is never
  dispatched twice.
- `DirectBackend` runs the same code in this process. It exists for local
  development and tests, and every result it produces says
  `DIRECT_TRUSTED_PROCESS` and `validator_path: false`.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from .practice import _canonical, _pinned, staged_modules

RECONSTRUCT_PROGRAM = r'''"""Carbon battery validator reconstruction: train one compiled recipe.

Fixed by Carbon. No query input is staged; the output is the model state.
"""
import gzip, json, shutil, sys
from pathlib import Path

import numpy as np

work = Path.cwd()
out = work.parent / "output"
lab = work / "carbon_battery_lab"
lab.mkdir()
(lab / "__init__.py").write_text("")
for staged, module in (
    ("battery-domain.py", "domain.py"),
    ("battery-recipes.py", "recipes.py"),
    ("battery-training.py", "training.py"),
    ("battery-torch-training.py", "torch_training.py"),
    ("battery-torch-families.py", "torch_families.py"),
):
    shutil.copyfile(work / staged, lab / module)
sys.path.insert(0, str(work))

from carbon_battery_lab import recipes  # noqa: E402
from carbon_battery_lab.domain import TrainingData  # noqa: E402

recipe = json.loads((work / "recipe.json").read_text())
train = TrainingData.from_records(
    [
        json.loads(line)
        for line in gzip.decompress((work / "train-v1.jsonl.gz").read_bytes()).splitlines()
        if line.strip()
    ]
)
table = json.loads((work / "ocv-table.json").read_text())
structure = recipes.Structure(
    np.asarray(table["soc"], float), np.asarray(table["ocv_v"], float)
)
try:
    model = recipes.build(recipe["family"], recipe["settings"])
    stats = model.fit(train, structure, recipe["seed"])
    state = recipes.state_bytes(model)
except ImportError as missing:  # this image lacks the recipe's backend: Carbon's
    (out / "failure.json").write_text(
        json.dumps({"stage": "environment", "error": type(missing).__name__})
    )
except Exception as failure:  # the candidate's own construction failed
    (out / "failure.json").write_text(
        json.dumps({"stage": "reconstruct", "error": type(failure).__name__})
    )
else:
    (out / "state.npz").write_bytes(state)
    (out / "fit.json").write_text(json.dumps({k: stats[k] for k in sorted(stats)}))
'''


def level1_reconstruct_program():
    """The reconstruction program for a Level-1 recipe: Level 0's program with
    its one build line replaced by the Level-1 build (`level1_worker`). Level
    0's program is unchanged."""
    import textwrap

    from . import level1_worker

    # The build line sits inside the program's `try:`, indented four spaces.
    build = '    model = recipes.build(recipe["family"], recipe["settings"])\n'
    if RECONSTRUCT_PROGRAM.count(build) != 1:
        raise RuntimeError("the reconstruction program's build line moved")
    return RECONSTRUCT_PROGRAM.replace(
        build, textwrap.indent(level1_worker._LEVEL1_BUILD, "    ")
    )


def _rebuild_development(recipe, record, material, seed):
    """In-process development rebuild (Levels 1-3) on pinned public TRAIN v1,
    as `compile.rebuild` rebuilds Level 0."""
    from . import development_rebuild
    from .compile import with_state
    from .recipes import Structure

    model = development_rebuild.build_in_process(recipe, record)
    train = development_rebuild.training_data(record, material.train)
    stats = model.fit(train, Structure(material.ocv_soc, material.ocv_v), seed)
    return model, {
        **with_state(model, stats),
        "trainer": development_rebuild.kind(record),
    }


INFER_PROGRAM = r'''"""Carbon battery validator inference: predict query inputs from a state.

Fixed by Carbon. Only a retained model state and query inputs are staged.
"""
import json, shutil, sys
from pathlib import Path

import numpy as np

work = Path.cwd()
out = work.parent / "output"
lab = work / "carbon_battery_lab"
lab.mkdir()
(lab / "__init__.py").write_text("")
for staged, module in (
    ("battery-domain.py", "domain.py"),
    ("battery-recipes.py", "recipes.py"),
    ("battery-training.py", "training.py"),
    ("battery-torch-training.py", "torch_training.py"),
    ("battery-torch-families.py", "torch_families.py"),
):
    shutil.copyfile(work / staged, lab / module)
sys.path.insert(0, str(work))

from carbon_battery_lab import recipes  # noqa: E402
from carbon_battery_lab.domain import INPUTS  # noqa: E402

model = recipes.model_from_bytes((work / "state.npz").read_bytes())
cases = json.loads((work / "query.json").read_text())["cases"]
x = np.array([[case["inputs"][k] for k in INPUTS] for case in cases], float)
try:
    predictions = recipes.to_predictions(
        model.predict(x), [c["case_id"] for c in cases]
    )
except Exception as failure:  # the candidate's own prediction failed
    (out / "failure.json").write_text(
        json.dumps({"stage": "infer", "error": type(failure).__name__})
    )
else:
    (out / "predictions.json").write_text(json.dumps(predictions))
'''

DIRECT = {"backend": "DIRECT_TRUSTED_PROCESS", "validator_path": False}


def _digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _code_files(implementation=None):
    return staged_modules(implementation)


def reconstruct_files(root, recipe, seed, *, implementation=None):
    """Every byte the reconstruction worker receives."""
    from .challenge import (
        OCV_TABLE_PATH,
        OCV_TABLE_SHA256,
        TRAIN_V1_PATH,
        TRAIN_V1_SHA256,
    )

    files = _code_files(implementation)
    files["train-v1.jsonl.gz"] = _pinned(
        Path(root) / TRAIN_V1_PATH, TRAIN_V1_SHA256, "train_v1"
    )
    table = json.loads(
        _pinned(Path(root) / OCV_TABLE_PATH, OCV_TABLE_SHA256, "ocv_table")
    )
    files["ocv-table.json"] = _canonical({"soc": table["soc"], "ocv_v": table["ocv_v"]})
    files["recipe.json"] = _canonical(
        {
            "family": recipe.family,
            "settings": recipe.settings,
            "recipe_digest": recipe.recipe_digest,
            "seed": seed,
        }
    )
    return files


def infer_files(state, inputs):
    """Every byte the inference worker receives: code, state and inputs only."""
    from .challenge import INPUTS

    files = _code_files()
    files["state.npz"] = state
    files["query.json"] = _canonical(
        {
            "schema": "carbon.battery.validator-query.v1",
            "cases": [
                {"case_id": c, "inputs": {k: float(inputs[c][k]) for k in INPUTS}}
                for c in sorted(inputs)
            ],
        }
    )
    return files


def state_backend(state):
    """The reconstruction backend a stored model state was trained in.

    Reads the state's JSON header only; never imports a numerical runtime.
    A state without the field (the nearest-neighbour family, or one from
    before OWNER-PYTORCH-BACKEND-01) is JAX's.
    """
    import io

    import numpy as np

    with np.load(io.BytesIO(state), allow_pickle=False) as data:
        header = json.loads(bytes(data["__header__"]).decode())
    member = header.get("member") or (header.get("members") or [{}])[0]
    return member.get("backend", "jax")


class WorkerFailure(RuntimeError):
    """A worker run that produced no usable output.

    `candidate` separates a failure of the candidate's own construction (its
    training diverged, it produced no state) from infrastructure (the worker
    or host failed). Only infrastructure is retried.
    """

    def __init__(self, code, *, candidate):
        super().__init__(code)
        self.code, self.candidate = code, candidate


class WorkLedger:
    """The validator's durable operation ledger for isolated runs.

    It provides exactly what the carrier needs (`root`, `reserve`, `finish`,
    `status`) with the carrier's semantics:
    - a new identity is dispatched once;
    - a finished identity replays its stored result;
    - an identity still RESERVED after a crash is never dispatched again
      until it is reconciled.
    Operations live in the validator state (`PoolStore`), beside the pool.
    """

    def __init__(self, store, root):
        self.store, self.root = store, Path(root)
        self.root.mkdir(mode=0o700, exist_ok=True)
        # Runs stage private case inputs here: the directory must be the
        # operator's alone, whoever created it.
        info = os.lstat(self.root)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise PermissionError("the work directory must be an owner-only directory")

    def reserve(self, identity, *, owner, phase, request, resources):
        body = _canonical(
            {"owner": owner, "phase": phase, "request": request, "resources": resources}
        ).decode()
        with self.store.transaction() as db:
            row = db.execute(
                "SELECT state, body FROM operations WHERE op_id=?", ("run:" + identity,)
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO operations VALUES(?, 'worker', 'RESERVED', ?)",
                    ("run:" + identity, body),
                )
                return {"dispatch": True, "state": "RESERVED"}
            stored = json.loads(row[1])
            if {k: stored[k] for k in ("owner", "phase", "request", "resources")} != (
                json.loads(body)
            ):
                raise ValueError("operation identity reused with another request")
            return {"dispatch": False, "state": row[0], "result": stored.get("result")}

    def finish(self, identity, *, owner, state, actual, result):
        with self.store.transaction() as db:
            row = db.execute(
                "SELECT state, body FROM operations WHERE op_id=?", ("run:" + identity,)
            ).fetchone()
            if row is None:
                raise ValueError("operation unavailable")
            stored = json.loads(row[1])
            if row[0] != "RESERVED":
                if stored.get("result") == result and row[0] == state:
                    return
                raise ValueError("terminal conflict")
            stored.update(result=result, actual=actual)
            db.execute(
                "UPDATE operations SET state=?, body=? WHERE op_id=?",
                (state, _canonical(stored).decode(), "run:" + identity),
            )

    def status(self, *, owner):
        with self.store.db() as db:
            rows = db.execute(
                "SELECT op_id, state, body FROM operations WHERE kind='worker'"
            ).fetchall()
        return {
            "operations": [
                {"id": op[4:], "state": state, **json.loads(body)}
                for op, state, body in rows
            ]
        }

    def unresolved(self):
        return [
            op["id"]
            for op in self.status(owner=None)["operations"]
            if op["state"] == "RESERVED"
        ]

    def abandon(self, identity):
        """Reconcile a run left RESERVED by a crash: its exact container is
        removed by the caller first; the run is then FAILED_INFRA, and the
        retry uses a new attempt identity."""
        with self.store.transaction() as db:
            db.execute(
                "UPDATE operations SET state='FAILED_INFRA' WHERE op_id=? "
                "AND state='RESERVED'",
                ("run:" + identity,),
            )


class CarrierBackend:
    """Both programs through the isolated carrier (the validator path)."""

    OWNER = "battery-validator"

    def __init__(
        self,
        ledger,
        image,
        *,
        torch_image=None,
        root=".",
        seconds=600,
        runner=None,
        identity=None,
        device=None,
    ):
        from carbon.development_session.research_carrier import _run

        self.ledger, self.image, self.root = ledger, image, Path(root)
        # VALIDATOR-27: a GPU deployment scores on the host's recorded device,
        # only for a device class a hardware acceptance has passed. Its
        # identity names the device kind, so its scores are labelled
        # `gpu:<kind>` and never ranked with CPU scores.
        self.accelerator, gpu = None, {}
        if device not in (None, "cpu", "gpu"):
            raise ValueError("device is cpu or gpu")
        if device == "gpu":
            from carbon.development_session import research_carrier
            from carbon.reconstruction import torch_profile
            from carbon.reconstruction.hardware_acceptance import require_accepted

            record = research_carrier._gpu_device()
            require_accepted(record.device_kind, research_carrier._gpu_profile_id())
            if torch_image is not None:
                # PyTorch on the validator's GPU (slice 2) is the PyTorch GPU
                # worker (TORCH-GPU-01), never the CPU one, and its class needs
                # its own acceptance under the PyTorch GPU profile.
                if torch_image.lock_digest != torch_profile.GPU_LOCK_DIGEST:
                    raise ValueError(
                        "a GPU validator's PyTorch image is the GPU worker"
                    )
                require_accepted(record.device_kind, torch_profile.GPU_PROFILE_ID)
            self.accelerator = research_carrier.VALIDATOR_GPU
            gpu = {"device_kind": record.device_kind, "device_record": record.digest}
        self.images = {"jax": image, "pytorch": torch_image}
        # The C-03 JAX image is the carrier's own; PyTorch is served only
        # where the deployment names its image.
        self.backends = ("jax",) if torch_image is None else ("jax", "pytorch")
        self.seconds = seconds
        self.runner = _run if runner is None else runner
        self.identity = identity or {
            "backend": "ISOLATED_CARRIER",
            "validator_path": True,
            "image": getattr(image, "image_id", None),
            # Only a deployment that serves PyTorch names a second image, so a
            # JAX-only deployment's identity is what it was.
            **(
                {}
                if torch_image is None
                else {"pytorch_image": getattr(torch_image, "image_id", None)}
            ),
            # Absent for a CPU deployment, so its identity is what it was.
            **gpu,
        }

    def _snapshot(self, result, names):
        if type(result) is not dict or "operation" not in result:
            # A replayed run that ended without a result (FAILED_INFRA after
            # reconciliation): infrastructure. The caller retries under a new
            # attempt identity.
            raise WorkerFailure("run_without_result", candidate=False)
        snapshot = self.ledger.root / result["operation"] / "snapshot"
        failure = snapshot / "failure.json"
        if failure.is_file() and not failure.is_symlink():
            if _digest(failure.read_bytes()) != result["files"].get("failure.json"):
                raise WorkerFailure("output_changed", candidate=False)
            reported = json.loads(failure.read_bytes()[:4096])
            raise WorkerFailure(
                f"{reported.get('stage')}_failed:{reported.get('error')}",
                # A worker image without the recipe's backend is the
                # validator's own state, never the candidate's.
                candidate=reported.get("stage") != "environment",
            )
        out = {}
        for name, maximum in names.items():
            path = snapshot / name
            # The fixed programs always write their outputs or failure.json,
            # so a missing or oversized output is Carbon's or the host's
            # failure, never a judgement of the candidate.
            if not path.is_file() or path.is_symlink():
                raise WorkerFailure("output_missing", candidate=False)
            body = path.read_bytes()
            if not 0 < len(body) <= maximum:
                raise WorkerFailure("output_bounds", candidate=False)
            if _digest(body) != result["files"].get(name):
                raise WorkerFailure("output_changed", candidate=False)
            out[name] = body
        return out

    def _image(self, backend):
        if backend not in self.backends:
            # Admission refuses a backend this validator does not serve, so
            # this is Carbon's own state, never the candidate's.
            raise WorkerFailure("backend_not_served:" + str(backend), candidate=False)
        return self.images[backend]

    def _call(self, identity, source, files, names, backend):
        try:
            result = self.runner(
                self.ledger,
                owner=self.OWNER,
                identity=identity,
                source=source,
                files=files,
                image=self._image(backend),
                seconds=self.seconds,
                provenance="BATTERY_VALIDATOR",
                extra_resources={},
                phase="final",
                # Only a GPU deployment asks; a CPU call is what it was.
                **(
                    {}
                    if self.accelerator is None
                    else {"accelerator": self.accelerator}
                ),
            )
        except WorkerFailure:
            raise
        except Exception as failure:  # noqa: BLE001 - infrastructure
            # A program failure is reported inside the output (failure.json).
            # Anything that prevents an output - host, Docker, a kill at the
            # memory or wall-clock bound, cleanup, cancellation - is
            # infrastructure and never a judgement of the candidate.
            raise WorkerFailure(
                "worker_infrastructure:" + type(failure).__name__, candidate=False
            ) from None
        return self._snapshot(result, names)

    def reconstruct(self, identity, recipe, seed, development=None):
        program, files = RECONSTRUCT_PROGRAM, reconstruct_files(self.root, recipe, seed)
        # A development recipe (Levels 1-3): the same program with its one
        # build line replaced, and its record staged (`development_rebuild`).
        from . import development_rebuild

        program, files, trainer = development_rebuild.stage(
            development, program, files, level1_program=level1_reconstruct_program
        )
        out = self._call(
            identity,
            program,
            files,
            {"state.npz": 256 * 1024**2, "fit.json": 65536},
            recipe.settings.get("backend", "jax"),
        )
        stats = json.loads(out["fit.json"])
        if trainer is not None:
            stats["trainer"] = trainer
        return out["state.npz"], stats

    def infer(self, identity, state, inputs):
        out = self._call(
            identity,
            INFER_PROGRAM,
            infer_files(state, inputs),
            {"predictions.json": 64 * 1024**2},
            state_backend(state),
        )
        return json.loads(out["predictions.json"])


class DirectBackend:
    """The same programs' logic in this process; local and tests only."""

    identity = DIRECT

    def __init__(self, root="."):
        import importlib.util

        from .challenge import PublicMaterial

        # In process, a backend is served only where its stack is installed;
        # a missing one is refused at admission, never blamed on a candidate.
        torch_ready = all(
            importlib.util.find_spec(m) is not None for m in ("torch", "neuralop")
        )
        self.backends = ("jax", "pytorch") if torch_ready else ("jax",)
        self.root = Path(root)
        self.material = PublicMaterial.load(self.root)
        self.calls = {"reconstruct": 0, "infer": 0}

    def reconstruct(self, identity, recipe, seed, development=None):
        from .compile import rebuild
        from .recipes import state_bytes

        self.calls["reconstruct"] += 1
        try:
            if development is None:
                model, stats = rebuild(recipe, self.material, seed)
            else:
                model, stats = _rebuild_development(
                    recipe, development, self.material, seed
                )
        except ImportError as missing:  # Carbon's environment, never the candidate
            raise WorkerFailure(
                "environment_failed:" + (str(missing) or type(missing).__name__),
                candidate=False,
            ) from None
        except Exception as failure:  # noqa: BLE001 - the candidate's own build
            raise WorkerFailure(
                "reconstruction_failed:" + type(failure).__name__, candidate=True
            ) from None
        return state_bytes(model), stats

    def infer(self, identity, state, inputs):
        import numpy as np

        from .challenge import INPUTS
        from .recipes import model_from_bytes, to_predictions

        self.calls["infer"] += 1
        model = model_from_bytes(state)
        ids = sorted(inputs)
        x = np.array([[inputs[c][k] for k in INPUTS] for c in ids], float)
        try:
            return json.loads(json.dumps(to_predictions(model.predict(x), ids)))
        except Exception as failure:  # noqa: BLE001 - the candidate's prediction
            raise WorkerFailure(
                "prediction_failed:" + type(failure).__name__, candidate=True
            ) from None
