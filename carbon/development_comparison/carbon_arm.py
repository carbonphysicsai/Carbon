"""The Carbon arm of a development evidence pack: one registered default recipe,
trained only on a pinned TRAIN set through Carbon's shared trainers, predicting
every physical row of a solved-panel export (MODEL-PREDICTIONS-FOR-EVIDENCE-01).

`evidence_pipeline` judges these predictions afresh and accepts no claimed
decision. This module produces only what its Carbon role needs:
- `carbon.development-prediction-input.v1`, one row per deduplicated export
  physical row; and
- a receipt naming the model, TRAIN, code, environment and measured fit and
  inference cost (`carbon.development-carbon-arm-receipt.v1`), whose digest
  the prediction document carries as `source_receipt_digest`.

**Rules:**
- **TRAIN only.** The panel's reference values are never read: rows are
  mapped to inputs from their actions and band alone.
- **The recipe is the kit's registered default,** fixed before any panel is
  inspected. Nothing here selects among recipes.
- **Unsupported interpolation abstains.** A row outside TRAIN's support (per
  input, its observed range; for a categorical input, its observed values)
  is an explicit abstention (`values: null`), never an extrapolated guess.
  A kit with a registered TRAIN domain (`domain`, the TRAIN plan's own
  sampling domain) uses that domain as its support instead. Every TRAIN record
  must lie in it, and every panel row must too, or the run is refused
  (`PANEL_OUTSIDE_TRAIN_DOMAIN`, `domain_gaps`).
- **A synthetic fixture stays a fixture.** A TRAIN set marked as a fixture
  can produce only `SYNTHETIC_FIXTURE` predictions.

**The network.** A dense network from the scaled inputs to the standardized
outputs, trained by `carbon.battery.training.train` (JAX) or
`carbon.battery.torch_training.train` (PyTorch), with Carbon's seed. Every
trainer setting is the battery default (`TRAINER_DEFAULTS`).

DEVELOPMENT only. It makes no claim of physical validity, qualification or
value.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import time
from dataclasses import dataclass

import numpy as np

PREDICTIONS = "carbon.development-prediction-input.v1"
RECEIPT = "carbon.development-carbon-arm-receipt.v1"
SCOPES = ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
TRAINER = "carbon.development-carbon-arm.trainer.v1"

#: Every setting of the shared trainer, at the battery defaults
#: (`carbon.battery.compile`'s defaults for `mlp`), except the batch, which is
#: the whole TRAIN set.
TRAINER_DEFAULTS = {
    "activation": "gelu",
    "adam_epsilon": 1e-08,
    "beta1": 0.9,
    "beta2": 0.999,
    "clip_norm": 0.0,
    "curriculum": "none",
    "depth": 3,
    "ema_decay": 0.99,
    "ensemble_members": 1,
    "h1_weight": 0.0,
    "h2_weight": 0.0,
    "hard_example_weight": 0.0,
    "inference_weights": "params",
    "initialization": "he_normal",
    "learning_rate": 0.002,
    "learning_rate_curve": "cosine",
    "microbatches": 1,
    "min_learning_rate_ratio": 0.0,
    "normalization": "none",
    "optimizer_family": "adam",
    "polish_steps": 0,
    "precision": "float64",
    "relative_loss": False,
    "spectral_weight": 0.0,
    "steps": 6000,
    "tail_averaging": 0.0,
    "time_weighting": "uniform",
    "warmup_steps": 0,
    "weight_decay": 0.0,
    "weight_decay_mask": "all",
    "width": 256,
}


class ArmRefused(ValueError):
    """A typed refusal; the code names the cause, never a payload."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


# -- the kit --------------------------------------------------------------------------------
@dataclass(frozen=True)
class Kit:
    """What one family's arm needs: its inputs (name -> scaling bounds), the
    names of the categorical ones, its observables, the TRAIN record schema
    and the map from an export physical row to its inputs.

    A kit whose model predicts something other than the observables (a
    curve, say) names its model `outputs`, the model `queries` one row needs
    and the `reduce` from their predictions to the row's observables. A row
    abstains when any of its queries is outside TRAIN's support."""

    kit_id: str
    family: str
    train_schema: str
    inputs: tuple  # ((name, (low, high)), ...)
    categorical: frozenset
    observables: tuple
    row_inputs: object  # callable(physical row) -> {name: value}
    model_id: str
    outputs: tuple = ()  # the model's outputs; empty: the observables
    queries: object = None  # callable(row) -> [{name: value}, ...]
    reduce: object = None  # callable(row, [{output: value}, ...]) -> observables
    onehot: tuple = ()  # ((name, (value, ...)), ...): one-hot encoded inputs
    domain: object = None  # callable(inputs) -> bool: the registered TRAIN domain

    @property
    def names(self):
        return tuple(name for name, _ in self.inputs) + tuple(
            name for name, _ in self.onehot
        )

    def valid_inputs(self, inputs):
        """Finite numbers for the scaled inputs, a listed value for each
        one-hot input."""
        listed = dict(self.onehot)
        return all(
            (
                inputs[name] in listed[name]
                if name in listed
                else type(inputs[name]) in (int, float) and math.isfinite(inputs[name])
            )
            for name in self.names
        )

    @property
    def targets(self):
        return self.outputs or self.observables

    def row_queries(self, row):
        return self.queries(row) if self.queries else [self.row_inputs(row)]

    def row_values(self, row, predicted):
        return self.reduce(row, predicted) if self.reduce else predicted[0]


@dataclass(frozen=True)
class Train:
    records: tuple
    sha256: str
    fixture: bool
    excluded: int


def load_train(kit, data, expected_sha256):
    """TRAIN from JSONL bytes pinned by their sha256. A record whose outputs
    are not all finite is excluded and counted, never repaired."""
    if sha256(data) != expected_sha256:
        raise ArmRefused("TRAIN_SHA256_MISMATCH")
    records, excluded, fixture = [], 0, set()
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if (
            type(record) is not dict
            or record.get("schema") != kit.train_schema
            or set(record.get("inputs", ())) != set(kit.names)
            or set(record.get("outputs", ())) != set(kit.targets)
        ):
            raise ArmRefused("TRAIN_RECORD_SHAPE")
        if not kit.valid_inputs(record["inputs"]):
            raise ArmRefused("TRAIN_INPUTS_NOT_FINITE")
        if kit.domain is not None and not kit.domain(record["inputs"]):
            raise ArmRefused("TRAIN_OUTSIDE_REGISTERED_DOMAIN")
        fixture.add(bool(record.get("fixture", False)))
        if any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in record["outputs"].values()
        ):
            excluded += 1
            continue
        records.append(record)
    if len(fixture) > 1:
        raise ArmRefused("TRAIN_MIXES_FIXTURE_AND_PUBLIC")
    if len(records) < 2:
        raise ArmRefused("TRAIN_TOO_SMALL")
    return Train(tuple(records), expected_sha256, fixture == {True}, excluded)


def sources(train):
    """The `source` labels TRAIN's records carry (a DEVELOPMENT stand-in
    names itself), sorted; empty when none does."""
    return sorted({r["source"] for r in train.records if "source" in r})


# -- the network ----------------------------------------------------------------------------
class Network:
    """The default recipe: a dense network on Carbon's shared trainer."""

    def __init__(self, kit, *, backend="jax", settings=None):
        if backend not in ("jax", "pytorch"):
            raise ArmRefused("BACKEND_UNKNOWN")
        self.kit, self.backend = kit, backend
        self.settings = {**TRAINER_DEFAULTS, **(settings or {})}

    def _x(self, rows):
        out = []
        for name, (low, high) in self.kit.inputs:
            v = np.asarray([float(r[name]) for r in rows])
            if name in self.kit.categorical:
                v = np.log2(v)
                low, high = math.log2(low), math.log2(high)
            out.append(2 * (v - low) / (high - low) - 1)
        for name, values in self.kit.onehot:
            for value in values:
                out.append(np.asarray([float(r[name] == value) for r in rows]))
        return np.stack(out, axis=1)

    def fit(self, train, seed):
        if type(seed) is not int or seed < 0:
            raise ArmRefused("SEED_REQUIRED")
        records = train.records
        x = self._x([r["inputs"] for r in records])
        y = np.asarray(
            [[r["outputs"][q] for q in self.kit.targets] for r in records], float
        )
        self.mu, self.sd = y.mean(0), y.std(0) + 1e-9
        z = (y - self.mu) / self.sd
        self.support = (
            "the registered TRAIN domain"
            if self.kit.domain is not None
            else {
                **{
                    name: (
                        sorted({float(r["inputs"][name]) for r in records})
                        if name in self.kit.categorical
                        else (
                            min(float(r["inputs"][name]) for r in records),
                            max(float(r["inputs"][name]) for r in records),
                        )
                    )
                    for name, _ in self.kit.inputs
                },
                **{
                    name: sorted({r["inputs"][name] for r in records}, key=str)
                    for name, _ in self.kit.onehot
                },
            }
        )
        n, k = z.shape
        s = dict(self.settings, batch_size=n)
        args = (x, z, np.ones(n), np.full(k, 1.0 / k), np.arange(n))
        wall, cpu = time.perf_counter(), time.process_time()
        leaves = (
            self._fit_torch(s, seed, *args)
            if self.backend == "pytorch"
            else (self._fit_jax(s, seed, *args))
        )
        blob = b"".join(np.ascontiguousarray(a).tobytes() for a in leaves)
        return {
            "fit_wall_s": time.perf_counter() - wall,
            "fit_cpu_s": time.process_time() - cpu,
            "params_sha256": hashlib.sha256(blob).hexdigest(),
            "n_params": int(sum(a.size for a in leaves)),
            "train_records": n,
        }

    def _fit_jax(self, s, seed, f, z, sw, gw, order):
        import jax

        from carbon.battery.training import apply_stack, dense_stack, train

        sizes = [f.shape[1]] + [s["width"]] * s["depth"] + [z.shape[1]]

        def init(key):
            return dense_stack(jax, key, sizes, s["initialization"], np.float64)

        def apply(p, x):
            return apply_stack(jax, p, x, s["activation"], s["normalization"])

        with jax.enable_x64(True):
            self.params = train(
                init=init,
                apply=apply,
                f=f,
                z=z,
                sw=sw,
                gw=gw,
                trajectory=lambda out: (out,),
                settings=s,
                seed=seed,
                order=order,
            )
        self._apply = apply
        return [np.asarray(a) for a in jax.tree_util.tree_leaves(self.params)]

    def _fit_torch(self, s, seed, f, z, sw, gw, order):
        import torch

        from carbon.battery import torch_training as tt

        dtype = tt.torch_dtype(s["precision"])
        device = tt.rebuild_device()
        with tt._determinism(device):
            generator = torch.Generator().manual_seed(seed)
            network = tt.mlp_network(
                generator, s, s["width"], s["depth"], f.shape[1], z.shape[1], dtype
            )
            params = tt.train(
                network=network,
                f=f,
                z=z,
                sw=sw,
                gw=gw,
                trajectory=lambda out: (out,),
                settings=s,
                seed=seed,
                order=order,
                dtype=dtype,
                device=device,
            )
        self.params = [p.detach().cpu().numpy() for p in params]
        self._network = network
        return self.params

    def _outputs(self, x):
        if self.backend == "pytorch":
            import torch

            from carbon.battery import torch_training as tt

            dtype = tt.torch_dtype(self.settings["precision"])
            with tt.deterministic(), torch.no_grad():
                params = [torch.tensor(a, dtype=dtype) for a in self.params]
                return self._network(params, torch.tensor(x, dtype=dtype)).numpy()
        import jax

        with jax.enable_x64(True):
            return np.asarray(self._apply(self.params, x))

    def supported(self, inputs):
        if not self.kit.valid_inputs(inputs):
            return False
        if self.kit.domain is not None:
            return bool(self.kit.domain(inputs))
        for name, _ in self.kit.onehot:
            if inputs[name] not in self.support[name]:
                return False
        for name, _ in self.kit.inputs:
            v = float(inputs[name])
            if name in self.kit.categorical:
                if v not in self.support[name]:
                    return False
            else:
                low, high = self.support[name]
                if not low <= v <= high:
                    return False
        return True

    def predict(self, rows):
        """Observable values per input row; None where TRAIN does not
        support the row (an explicit abstention)."""
        out = [None] * len(rows)
        kept = [i for i, r in enumerate(rows) if self.supported(r)]
        if kept:
            z = self._outputs(self._x([rows[i] for i in kept]))
            y = z * self.sd + self.mu
            for i, values in zip(kept, y):
                out[i] = {q: float(v) for q, v in zip(self.kit.targets, values)}
        return out


# -- the arm --------------------------------------------------------------------------------
def _gaps(kit, physical, per_row):
    return [
        {
            "band": row["band"],
            "candidate": row["candidate"],
            "condition": row["condition"],
        }
        for row, queries in zip(physical, per_row)
        if not all(kit.valid_inputs(q) and kit.domain(q) for q in queries)
    ]


def domain_gaps(kit, export):
    """The export's physical rows the kit's registered TRAIN domain does not
    cover (empty: the plan covers every panel row). Reads actions, bands and
    conditions only, never reference values."""
    from carbon.development_comparison import cheap_baselines as cb

    if kit.domain is None:
        raise ArmRefused("KIT_HAS_NO_REGISTERED_DOMAIN")
    physical = cb._physical_rows(export)
    return _gaps(kit, physical, [kit.row_queries(row) for row in physical])


def _environment():
    import importlib.metadata as md

    versions = {}
    for name in ("numpy", "jax", "jaxlib", "optax", "torch"):
        try:
            versions[name] = md.version(name)
        except md.PackageNotFoundError:
            versions[name] = None
    return {"python": platform.python_version(), "packages": versions}


def run(kit, export, train, *, scope, seed=0, backend="jax", code=None, settings=None):
    """`(predictions, receipt)` for every physical row of `export`."""
    from carbon.development_comparison import cheap_baselines as cb

    if scope not in SCOPES:
        raise ArmRefused("SCOPE_UNKNOWN")
    if train.fixture and scope != "SYNTHETIC_FIXTURE":
        raise ArmRefused("FIXTURE_TRAIN_CANNOT_BE_PUBLIC")
    if export.get("family") != kit.family:
        raise ArmRefused("EXPORT_FAMILY_MISMATCH")
    network = Network(kit, backend=backend, settings=settings)
    fit = network.fit(train, seed)
    physical = cb._physical_rows(export)
    if any(set(row["values"]) != set(kit.observables) for row in physical):
        raise ArmRefused("OBSERVABLE_INVENTORY_MISMATCH")
    per_row = [kit.row_queries(row) for row in physical]
    if kit.domain is not None and _gaps(kit, physical, per_row):
        raise ArmRefused("PANEL_OUTSIDE_TRAIN_DOMAIN")
    inputs = [q for queries in per_row for q in queries]
    timings, runs = [], []
    for _ in range(2):  # cold (includes tracing and compilation), then warm
        wall, cpu = time.perf_counter(), time.process_time()
        predicted, values, at = network.predict(inputs), [], 0
        for row, queries in zip(physical, per_row):
            part = predicted[at : at + len(queries)]
            at += len(queries)
            values.append(
                None if any(p is None for p in part) else kit.row_values(row, part)
            )
        runs.append(values)
        timings.append((time.perf_counter() - wall, time.process_time() - cpu))
    if runs[0] != runs[1]:
        raise ArmRefused("PREDICTION_NOT_REPEATABLE")
    values = runs[1]
    query = {
        "rows": len(physical),
        "model_queries": len(inputs),
        "predicted": sum(v is not None for v in values),
        "cold_wall_s": timings[0][0],
        "cold_cpu_s": timings[0][1],
        "wall_s": timings[1][0],
        "cpu_s": timings[1][1],
        "unit": "one batched call over every supported physical row; cold "
        "includes tracing and compilation, the warm call is the query cost",
    }
    receipt = {
        "schema": RECEIPT,
        "scope": scope,
        "kit": kit.kit_id,
        "model_id": kit.model_id,
        "export_digest": export["export_digest"],
        "selection": "the kit's registered default recipe, fixed before the "
        "panel was inspected; no recipe was chosen on panel results",
        "train": {
            "sha256": train.sha256,
            "records": len(train.records),
            "excluded_non_finite": train.excluded,
            "fixture": train.fixture,
            "sources": sources(train),
            "support": network.support,
        },
        "recipe": {
            "family": "mlp",
            "backend": backend,
            "trainer": TRAINER,
            "settings": network.settings,
            "seed": seed,
        },
        "code": code,
        "environment": _environment(),
        "cost": {"fit": fit, "inference": query},
        "abstained": query["rows"] - query["predicted"],
    }
    receipt_digest = sha256(canonical(receipt))
    predictions = {
        "schema": PREDICTIONS,
        "scope": scope,
        "export_digest": export["export_digest"],
        "model_id": kit.model_id,
        "source_receipt_digest": receipt_digest,
        "rows": [
            {
                "band": row["band"],
                "candidate": row["candidate"],
                "condition": row["condition"],
                "values": value,
            }
            for row, value in zip(physical, values)
        ],
    }
    return predictions, receipt


# -- the command ----------------------------------------------------------------------------
def kits():
    """The registered kits, by export family: each a function of the kit's
    material bytes (None when it needs none)."""
    from . import motor_10p12s_kit
    from .battery_v3_kit import KIT as BATTERY_V3
    from .f02_kit import KIT as F02

    return {
        BATTERY_V3.family: lambda material: BATTERY_V3,
        F02.family: lambda material: F02,
        motor_10p12s_kit.FAMILY: motor_10p12s_kit.kit_from_bytes,
    }


def _code_identity():
    """The commit and the bytes of the code that trained and predicted."""
    import subprocess
    from pathlib import Path

    here = Path(__file__).resolve()
    root = here.parents[2]
    files = {
        "carbon_arm.py": here,
        "battery_v3_kit.py": here.with_name("battery_v3_kit.py"),
        "motor_10p12s_kit.py": here.with_name("motor_10p12s_kit.py"),
        "f02_kit.py": here.with_name("f02_kit.py"),
        "battery/training.py": root / "carbon/battery/training.py",
        "battery/torch_training.py": root / "carbon/battery/torch_training.py",
    }
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {
        "commit": commit,
        "files": {name: sha256(path.read_bytes()) for name, path in files.items()},
    }


def main(argv=None):
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("family", choices=sorted(kits()))
    parser.add_argument("--export", required=True)
    parser.add_argument("--export-sha256", required=True)
    parser.add_argument("--train", required=True)
    parser.add_argument("--train-sha256", required=True)
    parser.add_argument("--material", help="the kit's material (motor: the sidecar)")
    parser.add_argument("--material-sha256")
    parser.add_argument("--scope", required=True, choices=SCOPES)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--backend", choices=("jax", "pytorch"), default="jax")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    out = Path(args.output_dir)
    try:
        if out.exists():
            raise ArmRefused("OUTPUT_EXISTS")
        raw = Path(args.export).read_bytes()
        if sha256(raw) != args.export_sha256:
            raise ArmRefused("EXPORT_SHA256_MISMATCH")
        material = None
        if args.material is not None:
            material = Path(args.material).read_bytes()
            if sha256(material) != args.material_sha256:
                raise ArmRefused("MATERIAL_SHA256_MISMATCH")
        kit = kits()[args.family](material)
        train = load_train(kit, Path(args.train).read_bytes(), args.train_sha256)
        predictions, receipt = run(
            kit,
            json.loads(raw),
            train,
            scope=args.scope,
            seed=args.seed,
            backend=args.backend,
            code=_code_identity(),
        )
    except ArmRefused as refused:
        print(json.dumps({"status": "REFUSED", "reason": refused.code}))
        return 2
    out.mkdir(parents=True)
    pins = {}
    for name, document in (
        ("receipt.json", receipt),
        ("predictions.json", predictions),
    ):
        body = canonical(document)
        (out / name).write_bytes(body)
        pins[name] = sha256(body)
    print(
        json.dumps(
            {"status": "COMPLETED", "pins": pins, "abstained": receipt["abstained"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
