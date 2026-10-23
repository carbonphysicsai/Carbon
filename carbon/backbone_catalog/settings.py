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

import functools
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
    #: "v1": the pinned builds' own vocabulary; "v2": the catalog trainer v2 (build_v2_src), Carbon's limits removed.
    vocabulary: str = "v1"
    #: Exclusive upper bound of a seed candidate (the trainer's own: torch seeds up to 2**64 - 1, numpy up to 2**32 - 1).
    seed_limit: int = 2**32
    #: The physics-prior + residual build (`prior_src/build_prior.py`): also takes `configuration.prior` and `configuration.krr`.
    prior: bool = False


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
#: The coverage build returning float32 (the interface's `<f4`) for F08 1.4 and F02 2.3
#: (`codex-queue/inputs/physical_catalog_15/build_physical_packets.py`): the same one-backbone Adam vocabulary as
#: COVERAGE, its own build bytes (the float32 line); F08 and F02 share it (their sizes live in the registry).
COVERAGE_F32 = Schema(
    "carbon-candidate-coverage-float32-v1",
    "carbon_candidate/build.py",
    "sha256:2298eca5a18f25ccdaccd34044c71e03ea7822a9332f6806764d7d8d0d8e35bc",
    COVERAGE.configuration,
    COVERAGE.train_use,
)
#: Catalog trainer v2 (`build_v2_src/build.py` and `build_jax.py`; "No Carbon limits", step 3). One Torch and one JAX build for
#: every Challenge: the trainers follow the TRAIN's own dtype and the registry's POINTS, so no per-Challenge variant exists.
#: The digests are of the files as they are in `build_v2_src` (provisional until the Validator's review ends).
TORCH_V2 = Schema(
    "carbon-candidate-torch-v2",
    "carbon_candidate/build.py",
    "sha256:306568542bdff914113f8a8f942559debb4e5f32cf23ccd9a94ac5866d32f43a",
    frozenset({"learning_rate", "arch"}),
    LEVERS.train_use,
    vocabulary="v2",
    seed_limit=2**64,
)
JAX_V2 = Schema(
    "carbon-candidate-jax-v2",
    "carbon_candidate/build.py",
    "sha256:cd42478074e93e6e1adbb2e39250f7fd2514a81eef270a04821d4ff15851daad",
    frozenset({"learning_rate"}),
    LEVERS.train_use,
    vocabulary="v2",
    # jax.random.PRNGKey(seed) folds a seed >= 2**32 onto colliding keys without x64 (2**32 and 2**40 both give [0, 0]) and
    # raises OverflowError from 2**63 (measured on jax 0.10.2), so the JAX build keeps uint32 seeds.
    seed_limit=2**32,
)
#: Physics prior + learned residual (`prior_src/build_prior.py`, JAX; one Challenge-neutral build, the Challenge's prior is the
#: bundle's own `prior.py`): the catalog trainer v2 vocabulary for a residual backbone, plus the closed-form KRR settings.
JAX_PRIOR = Schema(
    "carbon-candidate-jax-prior-v1",
    "carbon_candidate/build.py",
    "sha256:8597f12df0483f87d0916e7f101b348d66d8aaa128317ca1d53146bc3c990304",
    frozenset({"learning_rate", "prior", "krr"}),
    LEVERS.train_use,
    vocabulary="v2",
    seed_limit=2**32,
    prior=True,
)
SCHEMAS = {
    s.schema_id: s
    for s in (
        COVERAGE,
        LEVERS,
        JAX_LEVERS,
        COOLING_LEVERS,
        F08_LEVERS,
        F02_LEVERS,
        COVERAGE_F32,
        TORCH_V2,
        JAX_V2,
        JAX_PRIOR,
    )
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
    COVERAGE_F32.schema_id: (
        "sha256:df1fdb3e4928c4db6ef114c251b478687647545439f509cb76c7c01a76b1ab7e"
    ),
    # The v2 Torch build's twin: `gpu_build.patched_source` applied to `build_v2_src/build.py` (the same one transform).
    TORCH_V2.schema_id: (
        "sha256:0b76ec5041512c272247aee2bc9bc77d90c7e1408cacd3cb026ef690efb71495"
    ),
}
#: The Torch entries whose spectral weights are complex64, so float64 is not offered to them (an external fact of the
#: library's spectral layers; measured by building each entry and listing its complex parameters).
COMPLEX_WEIGHTS = frozenset(
    {
        "lno.LNO1d",
        "neuralop.FNO",
        "neuralop.GINO",
        "neuralop.LocalNO",
        "neuralop.TFNO",
        "neuralop.UQNO",
        "thuml.FNO",
        "thuml.F_FNO",
        "thuml.GeoFNO",
        "thuml.MWT",
    }
)
#: Each levers build's accepted mixed-precision values.
PRECISIONS = {
    LEVERS.schema_id: ("bfloat16", "float16"),
    COOLING_LEVERS.schema_id: ("bfloat16", "float16"),
    F08_LEVERS.schema_id: ("bfloat16", "float16"),
    F02_LEVERS.schema_id: ("bfloat16", "float16"),
    JAX_LEVERS.schema_id: ("bfloat16", "float16", "float32"),
    TORCH_V2.schema_id: ("bfloat16", "float16", "float32", "float64"),
    JAX_V2.schema_id: ("bfloat16", "float16", "float32"),
    JAX_PRIOR.schema_id: ("bfloat16", "float16", "float32"),
}
#: The levers build's architecture settings, per backbone (its `ARCH`).
ARCH = {
    "neuralop.FNO": ("modes", "hidden", "layers"),
    "neuralop.TFNO": ("modes", "hidden", "layers", "rank"),
    "transolver": ("layers", "hidden", "heads", "slices"),
}
#: Entries whose library constructor the v2 trainer wraps to take architecture settings (its `HOOKED_ARCH`).
HOOKED_ARCH = {
    "neuralop.LocalNO": ("modes", "hidden", "layers"),
    "neuralop.SFNO": ("modes", "hidden", "layers"),
    "neuralop.UQNO": ("modes", "hidden", "layers"),
    "physicsnemo.FullyConnected": ("width", "layers"),
}
#: Library arguments the THUML library entries take as architecture settings in the v2 trainer (its `LIBRARY_ARCH`).
LIBRARY_ARCH = (
    "n_hidden",
    "n_layers",
    "n_heads",
    "modes",
    "mlp_ratio",
    "slice_num",
    "mwt_k",
    "dropout",
)


@functools.lru_cache(maxsize=None)
def interface_shape(challenge_id, version):
    """(inputs, outputs) of a registered Challenge version's interface; an entry is None when this process cannot resolve it.

    Read from the version's own served material, so a new Challenge or a changed interface needs no edit here: the practice
    bank's shapes for the physical Challenges, the sealed pack's width for Battery.
    """
    try:
        if challenge_id == "battery-fastcharge-ageing-development-v1":
            from carbon.challenge_kit import battery_pack

            return None, battery_pack.OUTPUT_WIDTH
        from carbon.challenge_kit import physical_material

        if not physical_material.is_registered(challenge_id, version):
            return None, None
        material = physical_material.bundle_material(challenge_id, version)
        return (
            int(material["practice_inputs"].shape[1]),
            int(material["expected_output_shape"][1]),
        )
    except (ImportError, ValueError):
        return None, None


def output_count(challenge_id, version):
    """The output width of a registered Challenge version's interface (None when this process cannot resolve it)."""
    return interface_shape(challenge_id, version)[1]


#: Choice lists per vocabulary: what the build implements.
CHOICES = {
    "v1": {
        "loss": ("mse", "huber", "l1", "relative_l2"),
        "optimizer": ("adam", "adamw", "sgd", "rmsprop", "lbfgs"),
        "schedule": ("none", "cosine", "step", "onecycle", "warmup_cosine"),
    },
    "v2": {
        "loss": ("mse", "huber", "l1", "relative_l2", "log_cosh"),
        "optimizer": (
            "adam",
            "adamw",
            "sgd",
            "rmsprop",
            "lbfgs",
            "adagrad",
            "nadam",
            "radam",
        ),
        "schedule": (
            "none",
            "cosine",
            "step",
            "onecycle",
            "warmup_cosine",
            "exponential",
            "polynomial",
            "cosine_restarts",
        ),
    },
}
COMBINES = ("mean", "stacking", "stacking_per_output", "best_per_output", "weights")
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


def arch_keys(backbone, vocabulary="v1"):
    """The architecture settings a backbone takes under a vocabulary."""
    if backbone in ARCH:
        return tuple(ARCH[backbone])
    if vocabulary == "v2" and backbone in HOOKED_ARCH:
        return HOOKED_ARCH[backbone]
    if vocabulary == "v2" and backbone.startswith("thuml."):
        return LIBRARY_ARCH
    return ()


def _arch(backbone, arch, where, vocabulary="v1"):
    keys = arch_keys(backbone, vocabulary)
    if not keys:
        if arch:
            raise CatalogRefused(
                "catalog_setting_unknown", f"{backbone} takes no {where} settings"
            )
        return
    _only(arch, keys, where)
    for key, value in arch.items():
        if key == "rank":
            _within(value, f"{where}.rank", 0, 1, low_open=True)
        elif key == "dropout":
            _within(value, f"{where}.dropout", 0, 1, high_open=True)
        else:
            _positive_int(value, f"{where}.{key}")
    if vocabulary != "v2" and backbone == "transolver":
        # The pinned v1 build refuses it. The v2 build does not: the vendored library builds and runs hidden 33 / heads 4.
        merged = {"hidden": 32, "heads": 4, **arch}  # the build's ARCH defaults
        if merged["hidden"] % merged["heads"]:
            raise CatalogRefused(
                "catalog_settings_inconsistent",
                "transolver hidden must be a multiple of heads",
            )


def _loss(spec, where, vocabulary="v1", n_out=None):
    keys = {"kind", "delta", "smoothness"} | (
        {"output_weights"} if vocabulary == "v2" else set()
    )
    _only(spec, keys, where)
    if "kind" in spec:
        _choice(spec["kind"], where + ".kind", CHOICES[vocabulary]["loss"])
    if "delta" in spec:
        _within(spec["delta"], where + ".delta", 0, None, low_open=True)
    if "smoothness" in spec:
        _within(spec["smoothness"], where + ".smoothness", 0, None)
    if "output_weights" in spec:
        weights = spec["output_weights"]
        if type(weights) is not list or not weights:
            _bad(where + ".output_weights", "a list with one weight per output")
        if n_out is not None and len(weights) != n_out:
            _bad(
                where + ".output_weights", f"a list of {n_out} weights, one per output"
            )
        for index, value in enumerate(weights):
            _within(value, f"{where}.output_weights[{index}]", 0, None)
        if not any(value > 0 for value in weights):
            _bad(where + ".output_weights", "weights with at least one above 0")


def _optimizer(spec, where, vocabulary="v1"):
    _only(spec, {"name", "weight_decay", "momentum"}, where)
    if "name" in spec:
        _choice(spec["name"], where + ".name", CHOICES[vocabulary]["optimizer"])
    if "weight_decay" in spec:
        _within(spec["weight_decay"], where + ".weight_decay", 0, None)
    if "momentum" in spec:
        _within(spec["momentum"], where + ".momentum", 0, 1, high_open=True)


def _schedule(spec, where, vocabulary="v1"):
    _only(
        spec,
        {"name", "gamma", "every", "warmup"}
        | ({"power"} if vocabulary == "v2" else set()),
        where,
    )
    if "name" in spec:
        _choice(spec["name"], where + ".name", CHOICES[vocabulary]["schedule"])
    if "gamma" in spec:
        _within(spec["gamma"], where + ".gamma", 0, None, low_open=True)
    if "power" in spec:
        _within(spec["power"], where + ".power", 0, None, low_open=True)
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


def _train_levers(
    use, where, precisions=("bfloat16", "float16"), vocabulary="v1", n_out=None
):
    """The levers one training run takes (also a search candidate's)."""
    if "loss" in use:
        _loss(use["loss"], where + ".loss", vocabulary, n_out)
    if "optimizer" in use:
        _optimizer(use["optimizer"], where + ".optimizer", vocabulary)
    if "schedule" in use:
        _schedule(use["schedule"], where + ".schedule", vocabulary)
    if "data" in use:
        _data(use["data"], where + ".data")
    if "precision" in use and use["precision"] is not None:
        _choice(use["precision"], where + ".precision", precisions)
        if use["precision"] == "float64" and where != "train_use":
            _bad(
                where + ".precision",
                "float64 for the whole build, set in train_use.precision",
            )
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
                _optimizer(stage["optimizer"], at + ".optimizer", vocabulary)
            if "schedule" in stage:
                _schedule(stage["schedule"], at + ".schedule", vocabulary)


def _members_v2(spec, where, n_out):
    """`ensemble.members` under the v2 trainer: a whole number, or a list of member specs covering every output."""
    members = spec.get("members", 3)
    if type(members) is int:
        _positive_int(members, where + ".members")
        return
    if type(members) is not list or not members:
        _bad(
            where + ".members",
            "a whole number, 1 or more, or a non-empty list of member specs",
        )
    covered = set()
    for index, member in enumerate(members):
        at = f"{where}.members[{index}]"
        _only(member, {"outputs"}, at)
        outputs = member.get("outputs")
        if outputs is None:
            covered.update(range(n_out or 0))
            continue
        if type(outputs) is not list or not outputs:
            _bad(at + ".outputs", "a non-empty list of output indices")
        for value in outputs:
            if (
                type(value) is not int
                or value < 0
                or (n_out is not None and value >= n_out)
            ):
                _bad(at + ".outputs", f"output indices from 0 to {(n_out or 1) - 1}")
        covered.update(outputs)
    if n_out is not None and covered != set(range(n_out)):
        missing = min(set(range(n_out)) - covered)
        raise CatalogRefused(
            "catalog_settings_inconsistent",
            f"{where}.members leave output {missing} covered by no member",
        )


def _levers(backbone, use, precisions=("bfloat16", "float16"), schema=None, n_out=None):
    vocabulary = schema.vocabulary if schema else "v1"
    seed_limit = schema.seed_limit if schema else 2**32
    _train_levers(use, "train_use", precisions, vocabulary, n_out)
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
                if type(candidate) is not int or not 0 <= candidate < seed_limit:
                    _bad(
                        at,
                        (
                            "a uint32 integer"
                            if seed_limit == 2**32
                            else "an integer from 0 to 2**64 - 1"
                        ),
                    )
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
                _arch(backbone, candidate["arch"], at + ".arch", vocabulary)
            _train_levers(candidate, at, precisions, vocabulary, n_out)
    if "ensemble" in use and vocabulary == "v2":
        spec = use["ensemble"]
        _only(
            spec, {"members", "combine", "weights", "validation"}, "train_use.ensemble"
        )
        _validation(spec, "train_use.ensemble")
        _members_v2(spec, "train_use.ensemble", n_out)
        if "combine" in spec:
            _choice(spec["combine"], "train_use.ensemble.combine", COMBINES)
        if spec.get("combine") == "weights" and type(spec.get("weights")) is not list:
            _bad("train_use.ensemble.weights", "a list with one entry per member")
        if "weights" in spec:
            if type(spec["weights"]) is not list:
                _bad("train_use.ensemble.weights", "a list with one entry per member")
            members = spec.get("members", 3)
            if len(spec["weights"]) != (
                members if type(members) is int else len(members)
            ):
                _bad("train_use.ensemble.weights", "a list with one entry per member")
            for index, entry in enumerate(spec["weights"]):
                at = f"train_use.ensemble.weights[{index}]"
                for item in entry if type(entry) is list else [entry]:
                    if not _number(item):
                        _bad(at, "a finite number or a list of finite numbers")
                if type(entry) is list and n_out is not None and len(entry) != n_out:
                    _bad(at, f"a list of {n_out} weights, one per output")
    elif "ensemble" in use:
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
        if (
            vocabulary == "v2"
        ):  # bits >= 2 is structural (one bit has no levels); no upper bound
            if "bits" in spec and (type(spec["bits"]) is not int or spec["bits"] < 2):
                _bad("train_use.quantize.bits", "a whole number, 2 or more")
        elif "bits" in spec and (
            type(spec["bits"]) is not int or not 2 <= spec["bits"] <= 16
        ):
            _bad("train_use.quantize.bits", "a whole number from 2 to 16")


KRR_KERNELS = ("rbf", "matern32", "matern52")
KRR_GROUP_KEYS = frozenset({"outputs", "kernel", "length_scales", "ridge", "log_space"})


def _prior_settings(item, configuration, train_use, n_in, n_out):
    """`configuration.prior` / `configuration.krr` of a physics-prior entry (mirror of `prior_src/build_prior.py`)."""
    if "prior" in configuration:
        _choice(configuration["prior"], "configuration.prior", ("analytic", "none"))
        if configuration["prior"] == "analytic" and not item.get("prior"):
            raise CatalogRefused(
                "catalog_setting_invalid",
                "this entry's bundle ships no prior, so configuration.prior can only be none",
            )
    krr_entry = item["backbone"] == "krr"
    if "krr" in configuration and not krr_entry:
        _bad("configuration.krr", "only for the closed-form krr backbone")
    if krr_entry and train_use:
        _bad("train_use", "empty: the krr fit takes no training levers")
    if not krr_entry:
        return
    spec = configuration.get("krr", {})
    _only(spec, (KRR_GROUP_KEYS - {"outputs"}) | {"groups"}, "configuration.krr")
    positive = tuple((item.get("prior") or {}).get("positive_outputs", ()))
    raw = spec.get("groups")
    if raw is None:
        raw = [{"outputs": [0, n_out]}] if n_out else []
    if type(raw) is not list or (raw == [] and "groups" in spec):
        _bad("configuration.krr.groups", "a non-empty list")
    at = 0
    for index, group in enumerate(raw):
        where = f"configuration.krr.groups[{index}]"
        _only(group, KRR_GROUP_KEYS, where)
        span = group.get("outputs")
        if (
            type(span) is not list
            or len(span) != 2
            or any(type(v) is not int for v in span)
            or not 0 <= span[0] < span[1]
            or (n_out is not None and span[1] > n_out)
        ):
            _bad(where + ".outputs", "[start, stop] inside the Challenge's outputs")
        if span[0] != at:
            raise CatalogRefused(
                "catalog_settings_inconsistent",
                f"{where}: krr groups must cover every output once, in order (output {at})",
            )
        at = span[1]
        for source in (spec, group):
            if "kernel" in source:
                _choice(source["kernel"], where + ".kernel", KRR_KERNELS)
            if "ridge" in source:
                _within(source["ridge"], where + ".ridge", 0, None, low_open=True)
            if "length_scales" in source:
                scales = source["length_scales"]
                listed = type(scales) is list
                if listed and n_in is not None and len(scales) != n_in:
                    _bad(where + ".length_scales", f"one number or {n_in} numbers")
                for value in scales if listed else [scales]:
                    _within(value, where + ".length_scales", 0, None, low_open=True)
            if "log_space" in source and type(source["log_space"]) is not bool:
                _bad(where + ".log_space", "true or false")
        logged = group.get("log_space", spec.get("log_space", False))
        if logged and not all(o in positive for o in range(*span)):
            raise CatalogRefused(
                "catalog_setting_invalid",
                where + ".log_space: only for outputs the prior declares positive",
            )
    if n_out is not None and at != n_out:
        raise CatalogRefused(
            "catalog_settings_inconsistent",
            f"configuration.krr.groups leave output {at} covered by no group",
        )


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
    vocabulary = schema.vocabulary
    if "arch" in configuration:
        _arch(backbone, configuration["arch"], "configuration.arch", vocabulary)
    if "steps" in train_use:
        _positive_int(train_use["steps"], "train_use.steps")
    if schema in (COVERAGE, COVERAGE_F32):
        if "loss" in train_use:
            _choice(train_use["loss"], "train_use.loss", ("mse", "derivative"))
        if "derivative_weight" in train_use:
            _within(
                train_use["derivative_weight"], "train_use.derivative_weight", 0, None
            )
    else:
        n_in = n_out = None
        if vocabulary == "v2":
            first = item["challenges"][0]
            n_in, n_out = interface_shape(first["id"], first["version"])
        if schema.prior:
            _prior_settings(item, configuration, train_use, n_in, n_out)
        if not (schema.prior and backbone == "krr"):
            _levers(backbone, train_use, PRECISIONS[schema.schema_id], schema, n_out)
        if train_use.get("precision") == "float64" and backbone in COMPLEX_WEIGHTS:
            raise CatalogRefused(
                "catalog_setting_invalid",
                backbone
                + ": float64 is not offered, its spectral weights are complex64",
            )
    defaults = item["defaults"]
    merged = {**defaults["configuration"], **configuration, "backbone": backbone}
    if "arch" in configuration and "arch" in defaults["configuration"]:
        merged["arch"] = {**defaults["configuration"]["arch"], **configuration["arch"]}
        _arch(backbone, merged["arch"], "configuration.arch", vocabulary)
    return merged, {**defaults["train_use"], **train_use}


def document(item):
    """What a miner reads about an entry's settings."""
    schema = SCHEMAS[item["settings_schema"]]
    return {
        "schema": schema.schema_id,
        "configuration": sorted(schema.configuration),
        "train_use": sorted(schema.train_use),
        "arch": list(arch_keys(item["backbone"], schema.vocabulary)),
        "defaults": item["defaults"],
        "fixed": {"backbone": item["backbone"]},
        "limits": "the rebuild's wall time is the only training limit; no step cap",
    }
