"""The settings a catalog entry accepts: its pinned build's own vocabulary.

Each schema mirrors one exact `carbon_candidate/build.py` (bound by its
sha256; `pipeline.verify` checks every entry's source against it), so a
setting the build would refuse is refused here first, at the door, with a
typed code (`entries.CatalogRefused`), before anything is built or charged.

Bounds are the build's own (positive step counts, rates in (0, 1], fractions
in their open intervals, enums); Carbon adds no cap of its own. Step counts
have none: the rebuild wall time is the only training limit
(OWNER-REBUILD-TIME-LIMIT-01). The catalog id fixes the backbone: no setting,
search candidate or teacher may name another.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .entries import CatalogRefused


@dataclass(frozen=True)
class Schema:
    schema_id: str
    build_member: str
    build_sha256: str
    configuration: frozenset
    train_use: frozenset


#: The coverage build: one backbone trained fresh with Adam (the DeepXDE and
#: THUML baselines).
COVERAGE = Schema(
    "carbon-candidate-coverage-v1",
    "carbon_candidate/build.py",
    "sha256:cf414ed958ad6a88f5b7672665d86d7e2d51b878483599e4acf2a31621294688",
    frozenset({"learning_rate"}),
    frozenset({"steps", "loss", "derivative_weight"}),
)
#: The levers build: every training lever the Motor stress set exercised.
LEVERS = Schema(
    "carbon-candidate-levers-v1",
    "carbon_candidate/build.py",
    "sha256:eb4c80b4399c510b909e3cb6facbde3f4df20cda360674d3037c937a6a395fb4",
    frozenset({"learning_rate", "arch"}),
    frozenset(
        {
            "steps",
            "loss",
            "optimizer",
            "schedule",
            "data",
            "stages",
            "early_stopping",
            "averaging",
            "search",
            "seeds",
            "ensemble",
            "distill",
            "prune",
            "quantize",
            "precision",
        }
    ),
)
#: The JAX (foundax / jNO) levers build: the same levers, no architecture
#: settings, and float32 as a precision too (JAX's FFT refuses bfloat16).
JAX_LEVERS = Schema(
    "carbon-candidate-jax-levers-v1",
    "carbon_candidate/build.py",
    "sha256:944d004c9c973d15a942f7d6fdc4314385fbe6a6e298d32c55a9d120e1e90f83",
    frozenset({"learning_rate"}),
    LEVERS.train_use,
)
#: The levers build resized to Cooling's 32 outputs (60 -> 32 in its
#: Transolver curve; `codex-queue/inputs/cooling_catalog/
#: build_cooling_packets.py`): the same vocabulary as the levers build, its
#: own build bytes, each entry with its own Cooling pair-identity receipt.
COOLING_LEVERS = Schema(
    "carbon-candidate-levers-cooling-v1",
    "carbon_candidate/build.py",
    "sha256:c017c4e6c0f65bd9ae7548ce66cde43f9bde51875a8c4cbf4962744033e23c4a",
    LEVERS.configuration,
    LEVERS.train_use,
)
#: The levers build resized to F08 1.4's 7 outputs and F02 2.3's 1 output,
#: each returning float32 as its interface declares (`<f4`;
#: `codex-queue/inputs/physical_catalog_14/build_physical_packets.py`): the
#: Cooling levers vocabulary, their own build bytes, each entry with its own
#: pair-identity receipt (PAIR_IDENTITY_PX14_20261022).
F08_LEVERS = Schema(
    "carbon-candidate-levers-f08-v1",
    "carbon_candidate/build.py",
    "sha256:a130ac2817701d855ec9400b66d5f4be570f6617395848d3a4ff8a87b2db2171",
    LEVERS.configuration,
    LEVERS.train_use,
)
F02_LEVERS = Schema(
    "carbon-candidate-levers-f02-v1",
    "carbon_candidate/build.py",
    "sha256:45b1f8ca422fa95f893703a2b7955c288a39728390ad5eb49ee9a64ec89bc30a",
    LEVERS.configuration,
    LEVERS.train_use,
)
SCHEMAS = {
    s.schema_id: s
    for s in (COVERAGE, LEVERS, JAX_LEVERS, COOLING_LEVERS, F08_LEVERS, F02_LEVERS)
}
#: Each Torch schema's GPU (`torch-cu130-py311`) build, the one deterministic
#: transform of its CPU build (`gpu_build`, U58): the same vocabulary, its own
#: build bytes. A schema accepts both builds; the CPU hash stays its own.
GPU_BUILDS = {
    COVERAGE.schema_id: (
        "sha256:e4ae4ddf484f10ab35d92868139f888033eab66f9d06c5fd428212b1014e2f3a"
    ),
    LEVERS.schema_id: (
        "sha256:ee4c81994543975bb2b51248c2a6a359ddb0c296e6b2fc8ee75f77107bc7968d"
    ),
    COOLING_LEVERS.schema_id: (
        "sha256:a5b0b8a8deee166275aa606659f829d4a4c07e7f5e57254785b4f27166cf7163"
    ),
    F08_LEVERS.schema_id: (
        "sha256:299063aaa3a536b43e46bb6e31ce7e9ad89ec1960ae3f7864072f98f1bbc6186"
    ),
    F02_LEVERS.schema_id: (
        "sha256:0116f966f3e41f151bb3da64da4f778688a44d9c474e4534eb19d2031f53a842"
    ),
}
#: Each levers build's accepted mixed-precision values.
PRECISIONS = {
    LEVERS.schema_id: ("bfloat16", "float16"),
    COOLING_LEVERS.schema_id: ("bfloat16", "float16"),
    F08_LEVERS.schema_id: ("bfloat16", "float16"),
    F02_LEVERS.schema_id: ("bfloat16", "float16"),
    JAX_LEVERS.schema_id: ("bfloat16", "float16", "float32"),
}
#: The levers build's architecture settings, per backbone (its `ARCH`).
ARCH = {
    "neuralop.FNO": ("modes", "hidden", "layers"),
    "neuralop.TFNO": ("modes", "hidden", "layers", "rank"),
    "transolver": ("layers", "hidden", "heads", "slices"),
}
#: Levers a search candidate may set (the build's `TRAIN_LEVERS`).
TRAIN_LEVERS = (
    "loss",
    "optimizer",
    "schedule",
    "data",
    "stages",
    "averaging",
    "precision",
)


def build_hashes(schema_id):
    """The build hashes a schema accepts: its CPU build, and its GPU build
    when it has one."""
    schema = SCHEMAS[schema_id]
    gpu = GPU_BUILDS.get(schema_id)
    return (schema.build_sha256,) if gpu is None else (schema.build_sha256, gpu)


def schema_for_build(sha256):
    for schema in SCHEMAS.values():
        if sha256 in build_hashes(schema.schema_id):
            return schema.schema_id
    raise CatalogRefused(
        "catalog_library_not_pinned", "no settings schema mirrors this build"
    )


def _bad(where, what):
    raise CatalogRefused("catalog_setting_invalid", f"{where} must be {what}")


def _only(value, allowed, where):
    if type(value) is not dict:
        _bad(where, "an object")
    extra = sorted(set(value) - set(allowed))
    if extra:
        refused = CatalogRefused(
            "catalog_setting_unknown",
            f"{where} has no setting {extra[0]!r}; it has {', '.join(sorted(allowed)) or 'none'}",
        )
        # The settings this place does take, Carbon's own names, so a door
        # can list them (M1 E2E R9-1: an agent never learned what was wrong).
        refused.allowed = tuple(sorted(allowed))
        raise refused


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _positive_int(value, where):
    if type(value) is not int or value < 1:
        _bad(where, "a whole number, 1 or more")


def _within(value, where, low, high, *, low_open=False, high_open=False):
    ok = _number(value) and (value > low if low_open else value >= low)
    ok = ok and (high is None or (value < high if high_open else value <= high))
    if not ok:
        left = "(" if low_open else "["
        right = ")" if high_open else "]"
        _bad(
            where,
            f"a number in {left}{low}, {'no cap' if high is None else high}{right}",
        )


def _choice(value, where, choices):
    if value not in choices:
        _bad(where, "one of " + ", ".join(choices))


def _rate(value, where):
    _within(value, where, 0, 1, low_open=True)


def _arch(backbone, arch, where):
    if backbone not in ARCH:
        if arch:
            raise CatalogRefused(
                "catalog_setting_unknown", f"{backbone} takes no {where} settings"
            )
        return
    _only(arch, ARCH[backbone], where)
    for key, value in arch.items():
        if key == "rank":
            _within(value, f"{where}.rank", 0, 1, low_open=True)
        else:
            _positive_int(value, f"{where}.{key}")
    if backbone == "transolver":
        merged = {"hidden": 32, "heads": 4, **arch}  # the build's ARCH defaults
        if merged["hidden"] % merged["heads"]:
            raise CatalogRefused(
                "catalog_settings_inconsistent",
                "transolver hidden must be a multiple of heads",
            )


def _loss(spec, where):
    _only(spec, {"kind", "delta", "smoothness"}, where)
    if "kind" in spec:
        _choice(spec["kind"], where + ".kind", ("mse", "huber", "l1", "relative_l2"))
    if "delta" in spec:
        _within(spec["delta"], where + ".delta", 0, None, low_open=True)
    if "smoothness" in spec:
        _within(spec["smoothness"], where + ".smoothness", 0, None)


def _optimizer(spec, where):
    _only(spec, {"name", "weight_decay", "momentum"}, where)
    if "name" in spec:
        _choice(
            spec["name"], where + ".name", ("adam", "adamw", "sgd", "rmsprop", "lbfgs")
        )
    if "weight_decay" in spec:
        _within(spec["weight_decay"], where + ".weight_decay", 0, None)
    if "momentum" in spec:
        _within(spec["momentum"], where + ".momentum", 0, 1, high_open=True)


def _schedule(spec, where):
    _only(spec, {"name", "gamma", "every", "warmup"}, where)
    if "name" in spec:
        _choice(
            spec["name"],
            where + ".name",
            ("none", "cosine", "step", "onecycle", "warmup_cosine"),
        )
    if "gamma" in spec:
        _within(spec["gamma"], where + ".gamma", 0, None, low_open=True)
    for key in ("every", "warmup"):
        if key in spec:
            _positive_int(spec[key], f"{where}.{key}")


def _data(spec, where):
    _only(
        spec,
        {"subset", "batch", "order", "curriculum", "reweight", "mixup", "noise"},
        where,
    )
    if "subset" in spec:
        _within(spec["subset"], where + ".subset", 0, 1, low_open=True)
    if "batch" in spec and spec["batch"] is not None:
        _positive_int(spec["batch"], where + ".batch")
    if "order" in spec:
        _choice(spec["order"], where + ".order", ("random", "easy_first"))
    if "curriculum" in spec:
        _only(spec["curriculum"], {"start", "ramp"}, where + ".curriculum")
        if "start" in spec["curriculum"]:
            _within(spec["curriculum"]["start"], where + ".curriculum.start", 0, 1)
        if "ramp" in spec["curriculum"]:
            _within(
                spec["curriculum"]["ramp"],
                where + ".curriculum.ramp",
                0,
                None,
                low_open=True,
            )
    if "reweight" in spec:
        _choice(spec["reweight"], where + ".reweight", ("none", "hard_mining"))
    for key in ("mixup", "noise"):
        if key in spec:
            _within(spec[key], f"{where}.{key}", 0, None)


def _validation(spec, where):
    if "validation" in spec:
        _within(
            spec["validation"],
            where + ".validation",
            0,
            1,
            low_open=True,
            high_open=True,
        )


def _train_levers(use, where, precisions=("bfloat16", "float16")):
    """The levers one training run takes (also a search candidate's)."""
    if "loss" in use:
        _loss(use["loss"], where + ".loss")
    if "optimizer" in use:
        _optimizer(use["optimizer"], where + ".optimizer")
    if "schedule" in use:
        _schedule(use["schedule"], where + ".schedule")
    if "data" in use:
        _data(use["data"], where + ".data")
    if "precision" in use and use["precision"] is not None:
        _choice(use["precision"], where + ".precision", precisions)
    if "averaging" in use:
        spec = use["averaging"]
        _only(spec, {"kind", "decay", "start"}, where + ".averaging")
        if "kind" in spec:
            _choice(spec["kind"], where + ".averaging.kind", ("ema", "swa"))
        if "decay" in spec:
            _within(spec["decay"], where + ".averaging.decay", 0, 1, high_open=True)
        if "start" in spec:
            _within(spec["start"], where + ".averaging.start", 0, 1)
    if "stages" in use:
        if type(use["stages"]) is not list or not use["stages"]:
            _bad(where + ".stages", "a non-empty list")
        for index, stage in enumerate(use["stages"]):
            at = f"{where}.stages[{index}]"
            _only(stage, {"steps", "optimizer", "schedule", "learning_rate"}, at)
            if "steps" in stage:
                _positive_int(stage["steps"], at + ".steps")
            if "learning_rate" in stage:
                _rate(stage["learning_rate"], at + ".learning_rate")
            if "optimizer" in stage:
                _optimizer(stage["optimizer"], at + ".optimizer")
            if "schedule" in stage:
                _schedule(stage["schedule"], at + ".schedule")


def _levers(backbone, use, precisions=("bfloat16", "float16")):
    _train_levers(use, "train_use", precisions)
    if "early_stopping" in use:
        spec = use["early_stopping"]
        _only(spec, {"validation", "every", "patience"}, "train_use.early_stopping")
        _validation(spec, "train_use.early_stopping")
        for key in ("every", "patience"):
            if key in spec:
                _positive_int(spec[key], f"train_use.early_stopping.{key}")
    for lever in ("search", "seeds"):
        if lever not in use:
            continue
        spec = use[lever]
        where = "train_use." + lever
        _only(spec, {"candidates", "trial_steps", "validation"}, where)
        _validation(spec, where)
        if "trial_steps" in spec:
            _positive_int(spec["trial_steps"], where + ".trial_steps")
        candidates = spec.get("candidates")
        if type(candidates) is not list or not candidates:
            _bad(where + ".candidates", "a non-empty list")
        for index, candidate in enumerate(candidates):
            at = f"{where}.candidates[{index}]"
            if lever == "seeds":
                if type(candidate) is not int or not 0 <= candidate < 2**32:
                    _bad(at, "a uint32 integer")
                continue
            if type(candidate) is dict and "backbone" in candidate:
                raise CatalogRefused(
                    "catalog_setting_invalid",
                    f"{at} cannot name another backbone: the catalog id fixes it",
                )
            _only(candidate, {"learning_rate", "arch", *TRAIN_LEVERS}, at)
            if "learning_rate" in candidate:
                _rate(candidate["learning_rate"], at + ".learning_rate")
            if "arch" in candidate:
                _arch(backbone, candidate["arch"], at + ".arch")
            _train_levers(candidate, at, precisions)
    if "ensemble" in use:
        spec = use["ensemble"]
        _only(spec, {"members", "combine", "validation"}, "train_use.ensemble")
        _validation(spec, "train_use.ensemble")
        if "members" in spec:
            _positive_int(spec["members"], "train_use.ensemble.members")
        if "combine" in spec:
            _choice(spec["combine"], "train_use.ensemble.combine", ("mean", "stacking"))
    if "distill" in use:
        spec = use["distill"]
        _only(spec, {"teacher", "teacher_steps", "alpha"}, "train_use.distill")
        teacher = spec.get("teacher") or {}
        if type(teacher) is dict and "backbone" in teacher:
            raise CatalogRefused(
                "catalog_setting_invalid",
                "train_use.distill.teacher cannot name another backbone: the catalog id fixes it",
            )
        _arch(backbone, teacher, "train_use.distill.teacher")
        if "teacher_steps" in spec:
            _positive_int(spec["teacher_steps"], "train_use.distill.teacher_steps")
        if "alpha" in spec:
            _within(spec["alpha"], "train_use.distill.alpha", 0, 1)
    if "prune" in use:
        spec = use["prune"]
        _only(spec, {"fraction", "finetune_steps"}, "train_use.prune")
        if "fraction" in spec:
            _within(
                spec["fraction"],
                "train_use.prune.fraction",
                0,
                1,
                low_open=True,
                high_open=True,
            )
        if "finetune_steps" in spec and (
            type(spec["finetune_steps"]) is not int or spec["finetune_steps"] < 0
        ):
            _bad("train_use.prune.finetune_steps", "a whole number, 0 or more")
    if "quantize" in use:
        spec = use["quantize"]
        _only(spec, {"bits"}, "train_use.quantize")
        if "bits" in spec and (
            type(spec["bits"]) is not int or not 2 <= spec["bits"] <= 16
        ):
            _bad("train_use.quantize.bits", "a whole number from 2 to 16")


def resolve(item, configuration, train_use):
    """The bundle's configuration and train_use for catalog entry `item`: the
    miner's settings checked by the entry's schema over the tested baseline's
    defaults. Raises `CatalogRefused`."""
    schema = SCHEMAS.get(item["settings_schema"])
    if schema is None:
        raise CatalogRefused(
            "catalog_library_not_pinned", "the entry's settings schema is not served"
        )
    _only(configuration, schema.configuration, "configuration")
    _only(train_use, schema.train_use, "train_use")
    backbone = item["backbone"]
    if "learning_rate" in configuration:
        _rate(configuration["learning_rate"], "configuration.learning_rate")
    if "arch" in configuration:
        _arch(backbone, configuration["arch"], "configuration.arch")
    if "steps" in train_use:
        _positive_int(train_use["steps"], "train_use.steps")
    if schema is COVERAGE:
        if "loss" in train_use:
            _choice(train_use["loss"], "train_use.loss", ("mse", "derivative"))
        if "derivative_weight" in train_use:
            _within(
                train_use["derivative_weight"], "train_use.derivative_weight", 0, None
            )
    else:
        _levers(backbone, train_use, PRECISIONS[schema.schema_id])
    defaults = item["defaults"]
    merged = {**defaults["configuration"], **configuration, "backbone": backbone}
    if "arch" in configuration and "arch" in defaults["configuration"]:
        merged["arch"] = {**defaults["configuration"]["arch"], **configuration["arch"]}
        _arch(backbone, merged["arch"], "configuration.arch")
    return merged, {**defaults["train_use"], **train_use}


def document(item):
    """What a miner reads about an entry's settings."""
    schema = SCHEMAS[item["settings_schema"]]
    return {
        "schema": schema.schema_id,
        "configuration": sorted(schema.configuration),
        "train_use": sorted(schema.train_use),
        "arch": list(ARCH.get(item["backbone"], ())),
        "defaults": item["defaults"],
        "fixed": {"backbone": item["backbone"]},
        "limits": "the rebuild's wall time is the only training limit; no step cap",
    }
