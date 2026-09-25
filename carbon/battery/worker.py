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
from pathlib import Path

from .practice import STAGED_MODULES, _canonical, _pinned

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
except Exception as failure:  # the candidate's own construction failed
    (out / "failure.json").write_text(
        json.dumps({"stage": "reconstruct", "error": type(failure).__name__})
    )
else:
    (out / "state.npz").write_bytes(state)
    (out / "fit.json").write_text(json.dumps({k: stats[k] for k in sorted(stats)}))
'''

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


def _code_files():
    here = Path(__file__).parent
    return {
        staged: (here / module).read_bytes()
        for staged, module in STAGED_MODULES.items()
    }


def reconstruct_files(root, recipe, seed):
    """Every byte the reconstruction worker receives."""
    from .challenge import (
        OCV_TABLE_PATH,
        OCV_TABLE_SHA256,
        TRAIN_V1_PATH,
        TRAIN_V1_SHA256,
    )

    files = _code_files()
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
        self, ledger, image, *, root=".", seconds=600, runner=None, identity=None
    ):
        from carbon.development_session.research_carrier import _run

        self.ledger, self.image, self.root = ledger, image, Path(root)
        self.seconds = seconds
        self.runner = _run if runner is None else runner
        self.identity = identity or {
            "backend": "ISOLATED_CARRIER",
            "validator_path": True,
            "image": getattr(image, "image_id", None),
        }

    def _snapshot(self, result, names):
        snapshot = self.ledger.root / result["operation"] / "snapshot"
        failure = snapshot / "failure.json"
        if failure.is_file() and not failure.is_symlink():
            if _digest(failure.read_bytes()) != result["files"].get("failure.json"):
                raise WorkerFailure("output_changed", candidate=False)
            reported = json.loads(failure.read_bytes()[:4096])
            raise WorkerFailure(
                f"{reported.get('stage')}_failed:{reported.get('error')}",
                candidate=True,
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

    def _call(self, identity, source, files, names):
        try:
            result = self.runner(
                self.ledger,
                owner=self.OWNER,
                identity=identity,
                source=source,
                files=files,
                image=self.image,
                seconds=self.seconds,
                provenance="BATTERY_VALIDATOR",
                extra_resources={},
                phase="final",
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

    def reconstruct(self, identity, recipe, seed):
        out = self._call(
            identity,
            RECONSTRUCT_PROGRAM,
            reconstruct_files(self.root, recipe, seed),
            {"state.npz": 256 * 1024**2, "fit.json": 65536},
        )
        return out["state.npz"], json.loads(out["fit.json"])

    def infer(self, identity, state, inputs):
        out = self._call(
            identity,
            INFER_PROGRAM,
            infer_files(state, inputs),
            {"predictions.json": 64 * 1024**2},
        )
        return json.loads(out["predictions.json"])


class DirectBackend:
    """The same programs' logic in this process; local and tests only."""

    identity = DIRECT

    def __init__(self, root="."):
        from .challenge import PublicMaterial

        self.root = Path(root)
        self.material = PublicMaterial.load(self.root)
        self.calls = {"reconstruct": 0, "infer": 0}

    def reconstruct(self, identity, recipe, seed):
        from .compile import rebuild
        from .recipes import state_bytes

        self.calls["reconstruct"] += 1
        try:
            model, stats = rebuild(recipe, self.material, seed)
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
