"""A40 acceptance harness for the released validator images (operator side).

Question (`docs/development/graphite/A40_ACCEPTANCE_BRIEF.md`): does the released
image, under the pinned determinism configuration, rebuild the same battery
recipes to the same digest within a host and across two A40 hosts, for JAX GPU
and for PyTorch GPU? Digest equality is the only comparison: no tolerance is
set here, and nothing in this module qualifies anything. DEVELOPMENT
infrastructure; not `validator_launch`; spend is booked privately, never in the
repository (`POD-LEDGER-PRIVATE-01`).

Subcommands (see `docs/development/graphite/A40_ACCEPTANCE_RUNBOOK.md`):

    select   analytic recipe selection (brief 2b) -> run record + sha256
    smoke    one rebuild on one pod; records measured seconds (spends)
    run      the acceptance run (spends); `--dry-run` plans without a pod,
             `--local-cpu-dry-run` runs the per-repeat flow on the CPU
    compare  offline comparison of fetched pod results

Provisioning goes through the operator layer (`operator_compute`:
`ComputeService`, `PodSpec`, `ProvisionRequest`), never Graphite. Credentials
are a key FILE path only: this module never reads, prints or exports a key and
puts no credential in an environment. Only digest-pinned released images are
accepted. No pod exists in `--dry-run`, `select`, `compare` or in tests.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[4]

#: Released images, pinned by digest (worker-images-v2, release run 37785049981).
ACCELERATOR_IMAGE = (
    "ghcr.io/carbonphysicsai/carbon-accelerator-worker@sha256:"
    "c34d579e37eeffee944b8b4b876289963a6b283ea825b91a404167d92d0124b4"
)
TORCH_IMAGE = (
    "ghcr.io/carbonphysicsai/carbon-torch-gpu-worker@sha256:"
    "28856fd628d46818741e028837f064fe1a6f9f19653091adca92a36ff5726fc1"
)
IMAGES = {"jax": ACCELERATOR_IMAGE, "pytorch": TORCH_IMAGE}
BACKENDS = ("jax", "pytorch")

GPU_TYPE = "NVIDIA A40"
TORCH_LOCK = ".devcontainer/torch/torch-cu130-py311.txt"
#: The grant's rate is the all-in pod ceiling (compute plus a 20 GB container
#: disk at 0.10 / GB-month over 730 h), read from the grant record below.
DISK_GB = 20
DISK_USD_PER_GB_MONTH = 0.10
GRANT_RECORD = ".agent/decisions/2026-10-06-OWNER-A40-ACCEPTANCE-GRANT-01.md"


def grant_terms(repository=REPOSITORY):
    """The pod-hour rate ceiling and the monetary cap, read from the committed
    grant record, never restated here. The record's table states the original
    terms; a later owner amendment line (`<date>, owner: ceiling <rate>/h, cap
    USD <cap>`) supersedes them, the last one winning."""
    import re

    text = (Path(repository) / GRANT_RECORD).read_text()
    found = re.search(r"\|\s*Rate ceiling\s*\|\s*USD\s+([0-9.]+)\s+per pod-hour", text)
    cap = re.search(r"\|\s*\*\*Monetary cap\*\*\s*\|\s*\*\*USD\s+([0-9.]+)\*\*", text)
    if found is None or cap is None:
        raise RuntimeError("the grant record names no rate ceiling or cap")
    ceiling, cap_usd = Decimal(found.group(1)), Decimal(cap.group(1))
    amendments = re.findall(
        r"^\d{4}-\d{2}-\d{2}, owner: ceiling ([0-9.]+)/h, cap USD ([0-9.]+)$",
        text,
        flags=re.MULTILINE,
    )
    if amendments:
        ceiling, cap_usd = (Decimal(value) for value in amendments[-1])
    return ceiling, cap_usd


def grant_rate(repository=REPOSITORY):
    """The all-in (compute plus disk) pod-hour ceiling in force."""
    return grant_terms(repository)[0]


RATE_CEILING_USD_PER_HR = grant_rate()
#: The compute-only rate is the all-in ceiling less the container disk's hour.
POD_RATE_USD_PER_HR = float(
    RATE_CEILING_USD_PER_HR
    - (Decimal(DISK_GB) * Decimal("0.10") / Decimal(730)).quantize(
        Decimal("0.000000001"), rounding=ROUND_HALF_EVEN
    )
)
CLEANUP_RESERVE_USD = Decimal("0.25")
DEFAULT_CAP_USD = grant_terms()[1]
PODS, REPLACEMENTS = 4, 2
DEADLINE_FACTOR = Decimal("1.5")
POLL_SECONDS = 15.0
#: Python-only start command, as Graphite's pods use (`pods.py`).
PYTHON = "/opt/carbon-worker/bin/python"

PHASE = "a40_acceptance"
PHASE_MODULE = "scripts.dev.exam_design.runpod.a40_pod_phase"
CAMPAIGN = "a40-acceptance"
SEED = 0
REPEATS = 2
#: Engineering bound for the smoke pod only: 15 min start-up, one rebuild,
#: export; it never sets the run's deadline (the measurement does).
SMOKE_DEADLINE_SECONDS = 2700

#: Public TRAIN v1 and OCV table, pinned by `carbon/battery/challenge.py`
#: (a test holds these equal): shipped with the code and passed as the
#: material root. No sealed, hidden or label material.
DATA_PATHS = (
    "docs/development/evidence/exam-design-2026-09-24/datasets/train-v1.jsonl.gz",
    "docs/development/evidence/exam-design-2026-09-24/ocv_table.json",
)
SHIPPED_FILES = (
    "scripts/dev/exam_design/runpod/a40_pod_phase.py",
    "scripts/dev/gpu_determinism_study/device_identity.py",
)
SHIP_TREES = ("carbon",)

RECORD_SCHEMA = "carbon.a40-acceptance.run-record.v1"
SMOKE_SCHEMA = "carbon.a40-acceptance.smoke-record.v1"
COMPARISON_SCHEMA = "carbon.a40-acceptance.comparison.v1"
CPU_LABEL = "harness-to-harness only; not comparable to capability-report state_sha256"
SKIP_DIRECTIONS = {
    "smallest": "toward larger n_params",
    "lower_median": "toward larger n_params",
    "largest": "toward smaller n_params",
}
NEURAL = ("mlp", "deeponet")
PANEL = "ev4"
SELECTION_RULE = (
    "brief 2b: pool = EV4 neural members (mlp, deeponet; knn excluded), n_params "
    "computed analytically from the compiled recipe and cross-checked against an "
    "actual CPU count; pick the smallest, the lower median (1-based position "
    "floor((n+1)/2) ascending) and the largest; ties by lexicographically "
    "smallest member id; a member that cannot compile on both jax and pytorch is "
    "skipped toward the next in the same direction (the smallest and the median "
    "toward larger n_params, the largest toward smaller); plus one PyTorch-only "
    "fno recipe at the contract's defaults"
)


def supported_cuda_versions(repository=None):
    """The host CUDA versions both released GPU images support and RunPod
    accepts, derived and never guessed. The accelerator lock pins the JAX CUDA
    plugin and `nvidia-cuda-runtime` (13.0.x); the torch-gpu lock pins
    `nvidia-cuda-runtime` (13.0.x, the cu130 torch build). Each image supports
    host CUDA from its runtime's MAJOR.MINOR (CUDA minor-version compatibility
    within the major) up to RunPod's REST schema ceiling, 13.0
    (`pods.RUNPOD_CUDA_CEILING`; EV4 created every pod with ["13.0"]). The
    answer is the intersection: today exactly ("13.0",), because both runtimes
    are 13.0 and RunPod accepts nothing above 13.0; a lower host CUDA cannot run
    the cu13 wheels, so there is nothing further to widen to."""
    import re

    from carbon.agent_campaign.graphite import pods

    repository = Path(repository or REPOSITORY)
    accelerator = pods.allowed_cuda_versions(repository)
    text = (repository / TORCH_LOCK).read_text()
    runtime = re.search(r"^nvidia-cuda-runtime==(\d+)\.(\d+)\.", text, re.MULTILINE)
    ceiling_major, ceiling_minor = pods.RUNPOD_CUDA_CEILING
    if runtime is None or int(runtime.group(1)) != ceiling_major:
        raise Refused("refused: the torch-gpu lock names no usable CUDA runtime")
    torch = tuple(
        f"{ceiling_major}.{m}" for m in range(int(runtime.group(2)), ceiling_minor + 1)
    )
    both = tuple(v for v in accelerator if v in torch)
    if not both:
        raise Refused("refused: no CUDA version serves both released images")
    return both


class Refused(RuntimeError):
    """The harness refuses to proceed; nothing was created."""


# ------------------------------------------------------------------ images and budget
def check_image(image):
    if not isinstance(image, str) or "@sha256:" not in image:
        raise Refused("refused: image is not pinned by digest: " + str(image)[:80])
    digest = image.split("@sha256:", 1)[1]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise Refused("refused: image digest is not a sha256")
    if image not in IMAGES.values():
        raise Refused("refused: image is not a released A40 acceptance image")
    return image


def hourly_rate():
    """Pod ceiling plus disk, from the constants above; must equal the grant."""
    disk = Decimal(DISK_GB) * Decimal(str(DISK_USD_PER_GB_MONTH)) / Decimal(730)
    # The grant states the rate to the nanodollar, rounded to nearest.
    rate = (Decimal(str(POD_RATE_USD_PER_HR)) + disk).quantize(
        Decimal("0.000000001"), rounding=ROUND_HALF_EVEN
    )
    if rate != RATE_CEILING_USD_PER_HR:
        raise Refused("pod rate constants no longer equal the grant's rate")
    return rate


def reservation_usd(deadline_seconds, rate=None):
    rate = hourly_rate() if rate is None else rate
    exact = Decimal(deadline_seconds) / Decimal(3600) * rate
    return exact.quantize(Decimal("0.000000001"), rounding=ROUND_CEILING)


def budget_gate(
    deadline_seconds,
    cap=DEFAULT_CAP_USD,
    *,
    pods=PODS,
    replacements=REPLACEMENTS,
    smoke_reserved=Decimal(0),
):
    """Refuse unless (pods + replacements) x deadline x rate + cleanup (+ the
    smoke pod's own reservation, when it has run) fits the cap. Each pod is
    booked at its full reservation."""
    rate = hourly_rate()
    worst = (
        reservation_usd(deadline_seconds, rate) * (pods + replacements)
        + CLEANUP_RESERVE_USD
        + Decimal(smoke_reserved)
    )
    if worst > Decimal(cap):
        raise Refused(
            f"refused: worst case {worst:.4f} exceeds the cap {Decimal(cap):.2f}: "
            f"({pods} pods + {replacements} replacements) x "
            f"{deadline_seconds / 3600:.4f} h x {rate} + cleanup {CLEANUP_RESERVE_USD}"
        )
    return {
        "worst_case_usd": str(worst.quantize(Decimal("0.0001"))),
        "cap_usd": str(Decimal(cap)),
        "pods": pods,
        "replacements": replacements,
        "deadline_seconds": int(deadline_seconds),
        "rate_usd_per_hr": str(rate),
        "per_pod_reservation_usd": str(reservation_usd(deadline_seconds, rate)),
    }


def pod_deadline_seconds(smoke, rebuilds):
    """Each pod's deadline: measured x 1.5. Measured is the smoke pod's
    start-up (create to first running phase) plus `rebuilds` times the
    measured wall seconds of one rebuild in a fresh interpreter."""
    measured = Decimal(str(smoke["startup_seconds"])) + rebuilds * Decimal(
        str(smoke["rebuild_wall_seconds"])
    )
    return int((measured * DEADLINE_FACTOR).to_integral_value(rounding=ROUND_CEILING))


# ------------------------------------------------------------------ recipe selection
def _strategy(backbone, parameters):
    from carbon.battery.value import panel

    return {
        "schema_version": "1.0",
        "challenge_id": panel.CHALLENGE_ID,
        "backbone": backbone,
        "parameters": parameters,
    }


def for_backend(strategy, backend):
    """A strategy as one backend rebuilds it (the recipe names its backend)."""
    out = copy.deepcopy(strategy)
    if backend == "pytorch":
        out["parameters"]["backend"] = "pytorch"
    return out


def compiled(strategy):
    """The compiled recipe, or None when the contract refuses it."""
    from carbon.battery.compile import compile_recipe
    from carbon.development_session.research_catalog import RecipeRejected

    try:
        return compile_recipe(strategy)[1]
    except RecipeRejected:
        return None


def pool_members(panel_name=PANEL):
    """Registered panel members, once per recipe label, neural families only."""
    from carbon.battery.value import panel

    seen = {}
    for label, strategy, _seeds in panel.PANELS[panel_name]:
        if panel.family(strategy) in NEURAL:
            seen.setdefault(label, strategy)
    return seen


def input_width(rich):
    import numpy as np

    from carbon.battery import recipes
    from carbon.battery.domain import INPUTS

    return int(recipes.features(np.ones((1, len(INPUTS))), rich).shape[1])


def analytic_n_params(family, settings):
    """Parameter count from the compiled recipe alone, in closed form.

    Dense stack over sizes s: sum of a*b + b. MLP: [n_in] + [width] * depth +
    [n_out] with n_out = nv + nt + 1 + k, or 2p + 1 + k with p PCA heads
    (`recipes.MLP.fit`, `recipes.Layout`). Battery DeepONet: branch
    [n_in] + [width] * d + [2 basis + 1 + k], trunk [1] + [width] * d +
    [2 basis], and the (nv + nt) trajectory bias (`recipes.MLP._network`).
    An ensemble is `ensemble_members` identical members.
    """
    from carbon.battery.domain import CAPACITY_CYCLES, GRID_POINTS

    s = dict(settings)

    def stack(sizes):
        return sum(a * b + b for a, b in itertools.pairwise(sizes))

    g, k = GRID_POINTS, len(CAPACITY_CYCLES)
    # `predict_v0 = not ocv_initial_voltage`; the layout predicts V(0) then.
    predict_v0 = not s["ocv_initial_voltage"]
    nv, nt = (g if predict_v0 else g - 1), g - 1
    n_in = input_width(s["arrhenius_features"])
    width = s["width"]
    if family == "mlp":
        pca = s.get("trajectory_components", 0)
        n_out = 2 * pca + 1 + k if pca else nv + nt + 1 + k
        one = stack([n_in] + [width] * s["depth"] + [n_out])
    elif family == "deeponet":
        basis, depth = s["basis_functions"], s["deeponet_depth"]
        one = (
            stack([n_in] + [width] * depth + [2 * basis + 1 + k])
            + stack([1] + [width] * depth + [2 * basis])
            + nv
            + nt
        )
    else:
        raise ValueError("no analytic count for family " + family)
    return one * s["ensemble_members"]


def pool_counts(panel_name=PANEL):
    """The pool, each member with its analytic n_params and whether it compiles
    on both backends; ascending by (n_params, id)."""
    rows = []
    for label, strategy in pool_members(panel_name).items():
        jax_recipe = compiled(for_backend(strategy, "jax"))
        torch_recipe = compiled(for_backend(strategy, "pytorch"))
        if jax_recipe is None:
            raise Refused(f"refused: registered member {label} does not compile (jax)")
        rows.append(
            {
                "id": label,
                "family": strategy["backbone"],
                "n_params": analytic_n_params(jax_recipe.family, jax_recipe.settings),
                "compiles": {"jax": True, "pytorch": torch_recipe is not None},
            }
        )
    return sorted(rows, key=lambda r: (r["n_params"], r["id"]))


def _eligible(row):
    return all(row["compiles"].values())


def choose(pool):
    """Smallest, lower median, largest by the brief's 2b rule over the sorted
    pool, skipping members that cannot compile on both backends in the rule's
    direction. Returns [(role, row)]; refuses if a direction runs out."""
    ascending = list(pool)
    n = len(ascending)
    if n == 0:
        raise Refused("refused: empty neural pool")
    median_at = (n + 1) // 2 - 1  # 1-based position floor((n+1)/2)
    # Largest n_params first; ties by smallest id.
    descending = sorted(pool, key=lambda r: (-r["n_params"], r["id"]))
    picks, taken = [], set()

    def first(rows, start=0):
        for row in rows[start:]:
            if _eligible(row) and row["id"] not in taken:
                taken.add(row["id"])
                return row
        raise Refused("refused: no eligible member in the rule's direction")

    picks.append(("smallest", first(ascending)))
    picks.append(("lower_median", first(ascending, median_at)))
    picks.append(("largest", first(descending)))
    return picks


def fno_strategy():
    """The one PyTorch-only recipe: the contract's own default for every fno
    field. The recipe must name its backend (`compile.rebuild_issues`); every
    other value is the registered default."""
    return _strategy("fno", {"backend": "pytorch"})


# -- the actual CPU count the analytic one is checked against
def _members(model):
    from carbon.battery import recipes

    if isinstance(model, recipes.Ensemble):
        member = dict(model.settings)
        member["steps"] = member["steps"] // model.k
        return [recipes.MLP(model.family, dict(member)) for _ in range(model.k)]
    return [model]


def _prepare(member, train):
    from carbon.battery import recipes

    member.layout = recipes.Layout(
        train.v.shape[1],
        train.q.shape[1],
        bounded_v=member.bounded_v,
        predict_v0=member.predict_v0,
        fade=member.fade,
    )
    n_out = member.layout.targets(train).shape[1]
    if member.pca:
        n_out = 2 * member.pca + 1 + train.q.shape[1]
    return input_width(member.rich), n_out


def actual_n_params(strategy, backend, train):
    """Parameters of the network the real backend builds for `strategy`, on the
    CPU, before any training: JAX's `_network` init, or PyTorch's
    `build_network`. Raises ImportError when the backend is not installed."""
    from carbon.battery.compile import build_model

    recipe = compiled(for_backend(strategy, backend))
    if recipe is None:
        raise Refused("refused: recipe does not compile on " + backend)
    total = 0
    for member in _members(build_model(recipe)):
        n_in, n_out = _prepare(member, train)
        if backend == "jax":
            import jax
            import numpy as np

            init, _apply = member._network(jax, np.float32, n_in, n_out)
            params = init(jax.random.PRNGKey(0))[1]
            total += sum(int(a.size) for a in jax.tree_util.tree_leaves(params))
        else:
            import torch

            from carbon.battery import torch_training

            net = torch_training.build_network(
                member, torch.Generator().manual_seed(0), n_in, n_out, torch.float32
            )
            total += sum(int(p.numel()) for p in net.params)
    return total


def build_record(panel_name=PANEL, *, root=".", counter=actual_n_params):
    """The run record: pool, picks, fno recipe, each pick cross-checked against
    an actual CPU count on every backend. Raises Refused on any mismatch or
    when a backend cannot be exercised (a skipped cross-check is not a pass)."""
    from carbon.battery.challenge import PublicMaterial

    pool = pool_counts(panel_name)
    picks = choose(pool)
    members = pool_members(panel_name)
    train = PublicMaterial.load(root).train
    out_picks, mismatches = [], []
    for role, row in picks:
        strategy = members[row["id"]]
        counts = {}
        for backend in BACKENDS:
            try:
                counts[backend] = counter(strategy, backend, train)
            except ImportError as missing:
                raise Refused(
                    f"refused: cannot cross-check n_params on {backend}: {missing}"
                ) from None
            if counts[backend] != row["n_params"]:
                mismatches.append(
                    f"{row['id']} {backend}: analytic {row['n_params']}, "
                    f"actual {counts[backend]}"
                )
        out_picks.append(
            {
                "role": role,
                "id": row["id"],
                "family": row["family"],
                "n_params_analytic": row["n_params"],
                "n_params_cpu_count": counts,
                "strategy": strategy,
            }
        )
    if mismatches:
        raise Refused("n_params cross-check failed: " + "; ".join(mismatches))
    fno = fno_strategy()
    fno_recipe = compiled(fno)
    if fno_recipe is None:
        raise Refused("refused: the fno default recipe does not compile")
    try:
        fno_count = counter(fno, "pytorch", train)
    except ImportError as missing:
        raise Refused(f"refused: cannot count the fno on pytorch: {missing}") from None
    record = {
        "schema": RECORD_SCHEMA,
        "brief": "docs/development/graphite/A40_ACCEPTANCE_BRIEF.md section 2b",
        "panel": panel_name,
        "rule": SELECTION_RULE,
        "pool": [
            {k: row[k] for k in ("id", "family", "n_params")}
            | {"compiles": row["compiles"]}
            for row in pool
        ],
        "picks": out_picks,
        "fno": {
            "id": "fno_defaults",
            "strategy": fno,
            "recipe": fno_recipe.document(),
            "n_params_cpu_count": {"pytorch": fno_count},
        },
        "skip_directions": SKIP_DIRECTIONS,
        "seed": SEED,
        "repeats": REPEATS,
    }
    record["recipes_by_backend"] = recipes_by_backend(record)
    return record


def recipes_by_backend(record):
    """What each backend's pods rebuild: the three picks on both, the fno on
    PyTorch only (the JAX leg records it as not applicable)."""
    shared = [(p["id"], p["strategy"]) for p in record["picks"]]
    return {
        "jax": [{"id": i, "strategy": for_backend(s, "jax")} for i, s in shared],
        "pytorch": [
            *({"id": i, "strategy": for_backend(s, "pytorch")} for i, s in shared),
            {"id": record["fno"]["id"], "strategy": record["fno"]["strategy"]},
        ],
    }


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=1) + "\n").encode()


def write_record(record, path):
    """The record and its sha256, written before any rebuild."""
    path = Path(path)
    body = canonical_bytes(record)
    path.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    sidecar_path(path).write_text(digest + "\n")
    return digest


def sidecar_path(path):
    return Path(str(path) + ".sha256")


def load_record(path):
    """The run record, refused unless it exists and matches its stored sha256."""
    path = Path(path)
    sidecar = sidecar_path(path)
    if not path.is_file() or not sidecar.is_file():
        raise Refused("refused: no run record (run `select` first)")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != sidecar.read_text().strip():
        raise Refused("refused: the run record does not match its stored sha256")
    record = json.loads(body)
    if record.get("schema") != RECORD_SCHEMA:
        raise Refused("refused: not an A40 acceptance run record")
    return record


# ------------------------------------------------------------------ the code ship
def is_protected(path):
    """A path the pod-ship guard names (`pods.FORBIDDEN_DATA`, by fragment)."""
    from carbon.agent_campaign.graphite import pods

    return any(fragment in path.lower() for fragment in pods.FORBIDDEN_DATA)


def ship_paths(ref, repository=REPOSITORY):
    """Every tracked file the pod needs. Code files the guard names (sealed
    confirmation sets, EV4 contracts, `private` directories) are not shipped;
    the rebuild path imports none of them (a test rebuilds without them). The
    guard itself is unchanged: a protected DATA path is still refused."""
    from carbon.agent_campaign.graphite import pods

    code = [
        path
        for path in pods.tracked(ref, SHIP_TREES, repository)
        if not {part.lower() for part in Path(path).parts[:-1]}
        & pods.UNSHIPPED_DIRECTORIES
        and not is_protected(path)
    ]
    for path in (*SHIPPED_FILES, *DATA_PATHS):
        if is_protected(path):
            raise Refused("refused: forbidden data path " + path)
    return list(dict.fromkeys(code + list(SHIPPED_FILES) + list(DATA_PATHS)))


def build_manifest(ref, repository=REPOSITORY):
    from carbon.agent_campaign.graphite import pods

    if type(ref) is not str or len(ref) != 40:
        raise Refused("refused: a 40-hex pushed commit is required")
    return pods.code_manifest(ref, ship_paths(ref, repository), repository)


# ------------------------------------------------------------------ the operator side
#: Capacity retry: the first round is immediate, then one round every 10
#: minutes until the window (default 60 minutes; `--retry-window-minutes`).
RETRY_SECONDS = 600
DEFAULT_RETRY_WINDOW_SECONDS = 3600
#: A round tries SECURE, then COMMUNITY (owner direction 2026-10-08), each at
#: the same rate ceiling, public images only.
CLOUDS = ("SECURE", "COMMUNITY")
DEFINITIVE_STATUSES = frozenset({400, 401, 403, 404, 422})


class LaunchFailed(Refused):
    """A refused create, with the provider's status and redacted message."""

    def __init__(
        self,
        *,
        status,
        message,
        intent_id,
        capacity,
        cloud,
        next_action="",
    ):
        self.status, self.message, self.intent_id = status, message, intent_id
        self.capacity, self.cloud = capacity, cloud
        super().__init__(
            f"launch failed on {cloud}: {message} (HTTP {status}); next={next_action}"
        )

    @classmethod
    def from_compute(cls, failure, intent_id, cloud):
        text = failure.failed.lower()
        status = failure.http_status
        return cls(
            status=status,
            message=failure.failed,
            intent_id=intent_id,
            capacity=status not in DEFINITIVE_STATUSES
            and (status is None or status >= 500 or "no instances" in text),
            cloud=cloud,
            next_action=failure.next_action,
        )


class NoA40(Refused):
    """Capacity never came within the window."""

    def __init__(self, window_seconds):
        self.result = f"NO_A40_AFTER_{window_seconds // 60}_MIN"
        super().__init__(self.result)


@dataclass
class Pod:
    label: str  # "A" or "B": the host within a backend pair
    backend: str
    intent_id: str
    pod_id: str
    token: str
    deadline_at: float
    deadline_seconds: int
    launched_at: float
    rate: str | None
    recipes: int
    replaces: str | None = None
    first_running: float | None = None
    stage: str | None = None
    identity: dict | None = None
    files: dict = field(default_factory=dict)
    outcome: str | None = None  # COMPLETE FAILED_INFRA FAILED TIMEOUT REPLACED
    finished: bool = False
    terminated: bool | None = None
    reason: str | None = None
    cloud: str | None = None
    probe: dict | None = None
    datacenter: str | None = None

    def summary(self):
        return {
            "label": self.label,
            "backend": self.backend,
            "intent_id": self.intent_id,
            "pod_id": self.pod_id,
            "replaces": self.replaces,
            "outcome": self.outcome,
            "reason": self.reason,
            "terminated_verified": self.terminated,
            "deadline_seconds": self.deadline_seconds,
            "booked_usd": str(reservation_usd(self.deadline_seconds)),
            "rate_usd_per_hr": self.rate,
            "datacenter": self.datacenter,
            "cloud": self.cloud,
            "driver_version": (self.identity or {}).get("driver_version"),
        }


class PodRunner:
    """Provision, poll, fetch and terminate-with-verification, on Carbon's own
    RunPod account through `operator_compute`. `transport` and `http` are
    injectable (tests use a mock; nothing here reaches a network then)."""

    def __init__(
        self,
        *,
        work_dir,
        key_file,
        code_ref,
        manifest,
        repository=REPOSITORY,
        clock=time.time,
        sleep=time.sleep,
        transport=None,
        http=None,
        post=None,
        retry_window_seconds=DEFAULT_RETRY_WINDOW_SECONDS,
        balance_floor=None,
        poll_seconds=POLL_SECONDS,
        run_id=None,
    ):
        from scripts.dev.exam_design.runpod.operator_compute import (
            ComputeService,
            ComputeStore,
            FileCredentialProvider,
            RunPodAdapter,
            UrllibTransport,
        )

        self.code_ref, self.manifest = code_ref, manifest
        self.repository = Path(repository)
        self.clock, self.sleep, self.poll_seconds = clock, sleep, poll_seconds
        self.run_id = run_id or secrets.token_hex(4)
        self.rate = hourly_rate()
        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.work = work
        self.store = ComputeStore(work / "compute", clock=clock)
        if self.store.campaign_status(CAMPAIGN) is None:
            self.store.start_campaign(CAMPAIGN)
        self.adapter = RunPodAdapter(
            FileCredentialProvider(Path(key_file)),
            transport or UrllibTransport(),
            clock=clock,
            sleep=sleep,
        )
        self.service = ComputeService(self.store, self.adapter, clock=clock)
        self.http = http or _https_get
        self.post = post or _https_post
        self.balance_floor = balance_floor
        self.cuda_versions = supported_cuda_versions(repository)
        self.boot = (
            self.repository / "scripts/dev/exam_design/runpod/bootstrap.py"
        ).read_text()
        self.pods: list[Pod] = []
        self.replacements_used = 0
        self.driver_problems: list[dict] = []
        self.launch_attempts: list[dict] = []
        self.retry_window_seconds = retry_window_seconds
        self._n = 0

    # -- launching
    def _env(self, backend, config, token, deadline_at):
        from carbon.agent_campaign.graphite import pods
        from scripts.dev.exam_design.runpod import pod_control

        env = {
            "PROBE_TOKEN": token,
            "PROBE_DEADLINE": str(int(deadline_at + 60)),
            "PROBE_CA_GZ_B64": pods._ca_bundle(),
            "CODE_REF": self.code_ref,
            **pod_control.manifest_env(self.manifest),
            "PHASE": PHASE,
            "PHASE_MODULE": PHASE_MODULE,
            "PHASE_CONFIG": json.dumps(config, sort_keys=True),
        }
        return tuple(sorted(env.items()))

    def _check_balance(self, reserve):
        balance, _seen = self.service.observe_balance(CAMPAIGN)
        floor = self.balance_floor() if self.balance_floor else None
        if floor is None:
            from carbon.agent_campaign.graphite import pods

            floor = pods.operator_balance_floor()
        if Decimal(str(balance)) - reserve < Decimal(str(floor)):
            raise Refused("refused: balance would fall below the floor")

    def _launch_once(
        self, backend, label, config, deadline_seconds, *, replaces=None, cloud="SECURE"
    ):
        from scripts.dev.exam_design.runpod.operator_compute import (
            ComputeError,
            PodSpec,
            ProvisionRequest,
        )

        image = check_image(IMAGES[backend])
        self._check_balance(reservation_usd(deadline_seconds, self.rate))
        [offer] = self.adapter.offers([GPU_TYPE], gpu_count=1, cloud_type=cloud)
        if (
            offer.usd_per_hr is None
            or Decimal(str(offer.usd_per_hr)) > Decimal(str(POD_RATE_USD_PER_HR))
            or not offer.stock_status
        ):
            raise LaunchFailed(
                status=None,
                message=f"no A40 {cloud} offer in stock at or below the rate ceiling",
                intent_id=None,
                capacity=True,
                cloud=cloud,
            )
        self._n += 1
        intent = f"a40-{self.run_id}-{backend}-{label.lower()}-{self._n}"
        token = secrets.token_urlsafe(24)
        deadline_at = self.clock() + deadline_seconds
        spec = PodSpec(
            image=image,
            gpu_type_id=GPU_TYPE,
            gpu_count=1,
            cloud_type=cloud,
            container_disk_gb=DISK_GB,
            ports=("8000/http",),
            env=self._env(backend, config, token, deadline_at),
            max_rate_usd_per_hr=POD_RATE_USD_PER_HR,
            storage_usd_per_gb_month=DISK_USD_PER_GB_MONTH,
            start_command=(PYTHON, "-I", "-c", self.boot),
            allowed_cuda_versions=self.cuda_versions,
        )
        launched_at = self.clock()
        try:
            resource = self.service.provision(
                ProvisionRequest(
                    tenant="carbon",
                    miner="carbon",
                    campaign_id=CAMPAIGN,
                    intent_id=intent,
                    spec=spec,
                    deadline_at=float(deadline_at),
                )
            )
        except ComputeError as failure:
            raise LaunchFailed.from_compute(failure, intent, cloud) from None
        pod = Pod(
            label=label,
            backend=backend,
            intent_id=intent,
            pod_id=resource.resource_id,
            token=token,
            deadline_at=deadline_at,
            deadline_seconds=deadline_seconds,
            launched_at=launched_at,
            rate=(
                None
                if resource.rate_usd_per_hr is None
                else str(resource.rate_usd_per_hr)
            ),
            recipes=len(config["recipes"]),
            replaces=replaces,
            cloud=cloud,
        )
        try:
            pod.datacenter = self.adapter.datacenter(pod.pod_id)
        except ComputeError:
            pod.datacenter = None
        self.pods.append(pod)
        return pod

    # -- talking to a pod
    def launch(self, backend, label, config, deadline_seconds, *, replaces=None):
        """One create in flight. Each round tries SECURE, then COMMUNITY (same
        ceiling); the first round is immediate and a capacity-type refusal
        (non-definitive 5xx, or no instances/offer) leads to another round every
        RETRY_SECONDS until the window closes (NoA40). Every failed create is
        recorded (cloud, status, redacted body) and printed to stderr, and its
        intent is reconciled by ownership tag; any other failure stops at once.
        Never widens the CUDA versions."""
        started = self.clock()
        while True:
            for cloud in CLOUDS:
                try:
                    return self._launch_once(
                        backend,
                        label,
                        config,
                        deadline_seconds,
                        replaces=replaces,
                        cloud=cloud,
                    )
                except LaunchFailed as failed:
                    self.launch_attempts.append(
                        {
                            "at": self.clock(),
                            "backend": backend,
                            "label": label,
                            "cloud": failed.cloud,
                            "status": failed.status,
                            "message": failed.message[:500],
                            "capacity": failed.capacity,
                        }
                    )
                    print(
                        f"[a40] create failed cloud={failed.cloud} "
                        f"status={failed.status} body={failed.message[:500]}",
                        file=sys.stderr,
                        flush=True,
                    )
                    if failed.intent_id:
                        self._reconcile_intent(failed.intent_id)
                    if not failed.capacity:
                        raise
            if self.clock() - started + RETRY_SECONDS > self.retry_window_seconds:
                raise NoA40(self.retry_window_seconds)
            self.sleep(RETRY_SECONDS)

    def _reconcile_intent(self, intent_id):
        """Recover the failed create by ownership tag; a pod that turned up is
        terminated (cancel_provisioning), so none is left or double-created."""
        from scripts.dev.exam_design.runpod.operator_compute import ComputeError

        try:
            self.service.cancel_provisioning(CAMPAIGN, intent_id)
        except ComputeError:
            pass  # unresolved until the grace period; recover again later

    def _get(self, pod, path, timeout=60):
        owned = self.service.owned(CAMPAIGN, pod.intent_id, pod.pod_id)
        base = self.adapter.connect_url(owned, 8000)
        return self.http(base + path, pod.token, timeout)

    def _small(self, pod, name):
        code, body = self._get(pod, "/file/" + urllib.parse.quote(name))
        return body if code == 200 else None

    def _poll(self, pod):
        if self.clock() >= pod.deadline_at:
            pod.outcome, pod.finished = "TIMEOUT", True
            return
        code, body = self._get(pod, "/status")
        if code != 200:
            return
        try:
            stage = json.loads(body).get("stage")
        except (ValueError, AttributeError):
            return
        pod.stage = stage
        if stage == "running_phase" and pod.first_running is None:
            pod.first_running = self.clock()
        if pod.identity is None and stage in ("running_phase", "phase_failed", "done"):
            raw = self._small(pod, "identity.json")
            if raw is not None:
                try:
                    pod.identity = json.loads(raw)
                except ValueError:
                    pod.identity = None
        if pod.probe is None and stage in ("running_phase", "phase_failed", "done"):
            pod.probe = _json(self._small(pod, "probe.json")) or None
        if stage == "done":
            pod.outcome, pod.finished = "DONE", True
        elif stage in ("phase_failed", "bootstrap_failed"):
            pod.outcome, pod.finished = "FAILED", True

    def _fetch(self, pod):
        """Every file the pod lists, each checked against its listed sha256."""
        from carbon.agent_campaign.graphite import pods
        from scripts.dev.exam_design.runpod import pod_control

        code, body = self._get(pod, "/files")
        if code != 200:
            return {}
        listing = pods.fetch_limits(json.loads(body))
        with tempfile.TemporaryDirectory() as directory:
            try:
                pod_control.fetch_files(
                    listing,
                    lambda p: self._get(pod, "/file/" + urllib.parse.quote(p), 600),
                    directory,
                )
            except SystemExit as refused:
                raise Refused("fetch refused: " + str(refused)) from None
            return {
                row["path"]: (Path(directory) / row["path"]).read_bytes()
                for row in listing
            }

    def terminate(self, pod):
        """Terminate and verify absence; record the result, never raise."""
        from scripts.dev.exam_design.runpod.operator_compute import ComputeError

        try:
            self.service.terminate(CAMPAIGN, pod.intent_id, pod.pod_id)
            pod.terminated = True
        except ComputeError:
            pod.terminated = False
        return pod.terminated

    def _finish(self, pod):
        try:
            pod.files = self._fetch(pod)
        except (Refused, ValueError):
            pod.files = {}
        failure = _json(pod.files.get("failure.json"))
        if pod.outcome == "DONE" and _complete(pod):
            pod.outcome = "COMPLETE"
        elif failure.get("stage") == "environment":
            pod.outcome = "FAILED_INFRA"
        elif pod.outcome == "DONE":
            pod.outcome = "FAILED"
        self.terminate(pod)

    def _replace(self, pod, config, *, reason):
        if self.replacements_used >= REPLACEMENTS:
            return None
        self.replacements_used += 1
        fresh = self.launch(
            pod.backend,
            pod.label,
            config,
            pod.deadline_seconds,
            replaces=pod.intent_id,
        )
        pod.reason = reason
        return fresh

    def _go(self, pods):
        """Release the barrier: only after both drivers were seen to match."""
        for pod in pods:
            owned = self.service.owned(CAMPAIGN, pod.intent_id, pod.pod_id)
            url = self.adapter.connect_url(owned, 8000) + "/go"
            code, _body = self.post(url, pod.token, 60)
            if code != 200:
                raise Refused("the barrier release was not accepted")

    def _pair_check(self, group, config):
        """Driver builds across the two hosts of a backend: the preflight of
        `compare_units`. A differing build is recorded, never hidden; one
        replacement may be taken (the grant) before the run proceeds."""
        from scripts.dev.gpu_determinism_study import compare_units

        problems = compare_units.preflight(
            [dict(p.identity, index=0) for p in group if p.identity]
        )
        if not problems:
            self._go(group)
            return []
        record = {
            "backend": group[0].backend,
            "problems": problems,
            "builds": sorted({p.identity.get("driver_version") for p in group}),
        }
        self.driver_problems.append(record)
        second = group[-1]
        if self.replacements_used < REPLACEMENTS and not second.finished:
            second.outcome, second.finished = "REPLACED_DRIVER_MISMATCH", True
            self.terminate(second)
            return [self._replace(second, config, reason="driver mismatch")]
        # No replacement left: nothing was released, so no rebuild ever ran.
        for pod in group:
            pod.outcome, pod.finished = "REFUSED_DRIVER_MISMATCH", True
            self.terminate(pod)
        return []

    def drive(self, group, config):
        """Poll `group` (one backend's pods) to the end; pair-check the drivers
        as soon as two identities exist; always terminate every pod."""
        active = [p for p in group if not p.finished]
        checked = False
        try:
            while active:
                for pod in list(active):
                    self._poll(pod)
                    if not pod.finished:
                        continue
                    active.remove(pod)
                    self._finish(pod)
                    if pod.outcome == "FAILED_INFRA":
                        fresh = self._replace(pod, config, reason="gpu probe")
                        if fresh is not None:
                            group.append(fresh)
                            active.append(fresh)
                            checked = False
                if not checked:
                    ready = [
                        p
                        for p in group
                        if p.identity
                        and p.probe
                        and p.probe.get("ok") is True
                        and p.outcome
                        not in ("FAILED_INFRA", "REPLACED_DRIVER_MISMATCH")
                    ]
                    if len(ready) >= 2:
                        checked = True
                        for fresh in self._pair_check(ready[:2], config):
                            group.append(fresh)
                            active.append(fresh)
                            checked = False
                        active = [p for p in active if not p.finished]
                if active:
                    self.sleep(self.poll_seconds)
        finally:
            for pod in self.pods:
                if pod.terminated is not True:
                    self.terminate(pod)

    # -- the end of a run
    def reconcile(self):
        """Operator layer's own check and the independent reconciler: nothing
        tagged Carbon may remain."""
        from scripts.dev.exam_design.runpod.operator_compute import reconcile

        report = reconcile(self.store, self.adapter, clock=self.clock)
        left = [
            item.resource_id
            for item in self.adapter.list_resources()
            if (item.name or "").startswith("carbon-")
        ]
        return {
            "reconcile": report.as_dict(),
            "carbon_tagged_pods_left": len(left),
            "clean": not left and not report.failures,
        }

    def close(self):
        self.store.close()


def _json(raw):
    try:
        value = json.loads(raw) if raw is not None else {}
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _complete(pod):
    return _json(pod.files.get("results.json")).get("complete") is True


def _https_get(url, token, timeout):
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url, headers={"X-Probe-Token": token, "User-Agent": "carbon-a40-acceptance/1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as refused:
        return refused.code, b""
    except Exception:  # noqa: BLE001 -- an unreachable pod is a typed status
        return 0, b""


def _https_post(url, token, timeout):
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={"X-Probe-Token": token, "User-Agent": "carbon-a40-acceptance/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as refused:
        return refused.code, b""
    except Exception:  # noqa: BLE001 -- an unreachable pod is a typed status
        return 0, b""


#: The PyTorch fno leg is skipped (`--skip-fno`) until the v3 images: it fails on
#: the GPU with a neuralop CPU/CUDA device mismatch. The run record is not
#: changed or re-hashed; the recipe is filtered where it is used.
SKIPPED_FNO = {
    "fno": {
        "skipped": True,
        "reason": "known GPU device bug (neuralop CPU/CUDA device mismatch); "
        "to be re-run on v3 images",
    }
}


def phase_config(backend, record, *, barrier=False, skip_fno=False):
    fno_id = record["fno"]["id"]
    return {
        "barrier": barrier,
        "backend": backend,
        "recipes": [
            r
            for r in record["recipes_by_backend"][backend]
            if not (skip_fno and r["id"] == fno_id)
        ],
        "repeats": record["repeats"],
        "seed": record["seed"],
    }


def smoke(runner, record, *, backend="jax", out, skip_fno=False):
    """One rebuild (the record's largest pick on `backend`) on one pod; records
    the measured start-up and wall seconds that set every later deadline."""
    config = phase_config(backend, record, skip_fno=skip_fno)
    # JAX: the largest pick. PyTorch: the single fno rebuild (the slowest),
    # or the largest MLP/DeepONet pick when the fno is skipped.
    target = (
        record["fno"]["id"]
        if backend == "pytorch" and not skip_fno
        else next(p for p in record["picks"] if p["role"] == "largest")["id"]
    )
    config["recipes"] = [r for r in config["recipes"] if r["id"] == target]
    config["repeats"] = 1
    deadline = SMOKE_DEADLINE_SECONDS
    budget_gate(deadline, pods=1, replacements=0, cap=DEFAULT_CAP_USD)
    pod = runner.launch(backend, "A", config, deadline)
    runner.drive([pod], config)
    row = (_json(pod.files.get("results.json")).get("rows") or [{}])[0]
    measured = {
        "schema": SMOKE_SCHEMA,
        "backend": backend,
        "recipe_id": target,
        "outcome": pod.outcome,
        "startup_seconds": round(
            (pod.first_running or runner.clock()) - pod.launched_at, 3
        ),
        "rebuild_wall_seconds": row.get("wall_seconds"),
        "rebuild_child_seconds": row.get("seconds"),
        "device": _json(pod.files.get("identity.json")) or None,
        "booked_usd": str(reservation_usd(deadline)),
        "pod": pod.summary(),
        "launch_attempts": runner.launch_attempts,
        "reconciliation": runner.reconcile(),
    }
    Path(out).write_text(json.dumps(measured, indent=1, sort_keys=True) + "\n")
    return measured


def load_smoke(path):
    smoke_record = json.loads(Path(path).read_text())
    if (
        smoke_record.get("schema") != SMOKE_SCHEMA
        or smoke_record.get("outcome") != "COMPLETE"
    ):
        raise Refused("refused: the smoke record is missing or did not complete")
    for key in ("startup_seconds", "rebuild_wall_seconds"):
        if not isinstance(smoke_record.get(key), int | float) or smoke_record[key] <= 0:
            raise Refused("refused: the smoke record has no measured " + key)
    return smoke_record


def plan(record, smokes, cap=DEFAULT_CAP_USD, skip_fno=False):
    """Each backend's deadline (its own smoke x 1.5) and budget, with no pod.
    The cap gate applies per backend with the 4 pods + 2 replacements
    arithmetic; refused unless every backend fits."""
    out = {}
    for backend in BACKENDS:
        recipes = phase_config(backend, record, skip_fno=skip_fno)["recipes"]
        rebuilds = len(recipes) * record["repeats"]
        smoke_record = smokes[backend]
        deadline = pod_deadline_seconds(smoke_record, rebuilds)
        gate = budget_gate(
            deadline,
            cap,
            smoke_reserved=Decimal(smoke_record.get("booked_usd", "0")),
        )
        out[backend] = {"rebuilds_per_pod": rebuilds, **gate}
    return out


def run_acceptance(runner, record, smokes, *, cap=DEFAULT_CAP_USD, skip_fno=False):
    """Two A40 hosts per backend. Backends one after the other (two pods at a
    time, the grant's concurrency). Returns the run summary and results."""
    budget = plan(record, smokes, cap, skip_fno)
    results = {}
    try:
        for backend in BACKENDS:
            deadline = budget[backend]["deadline_seconds"]
            config = phase_config(backend, record, barrier=True, skip_fno=skip_fno)
            config["go_timeout_seconds"] = deadline
            group = [
                runner.launch(backend, "A", config, deadline),
                runner.launch(backend, "B", config, deadline),
            ]
            runner.drive(group, config)
            results[backend] = [p for p in runner.pods if p.backend == backend]
    finally:
        for pod in runner.pods:
            if pod.terminated is not True:
                runner.terminate(pod)
    reconciliation = runner.reconcile()
    summary = {
        "budget": budget,
        "pods": [p.summary() for p in runner.pods],
        "replacements_used": runner.replacements_used,
        "driver_problems": runner.driver_problems,
        "launch_attempts": runner.launch_attempts,
        "reconciliation": reconciliation,
        "booked_usd": str(
            sum((reservation_usd(p.deadline_seconds) for p in runner.pods), Decimal(0))
        ),
    }
    if skip_fno:
        summary["skipped"] = SKIPPED_FNO
    return summary, results


# ------------------------------------------------------------------ comparison
def _digests(rows, recipe_id, key):
    return [r.get(key) for r in rows if r.get("recipe_id") == recipe_id]


def _host_cell(rows, recipe_id):
    p = _digests(rows, recipe_id, "params_sha256")
    q = _digests(rows, recipe_id, "predictions_sha256")
    ok = bool(p) and None not in p and None not in q
    return {
        "repeats": len(p),
        "complete": ok,
        "weights_equal": ok and len(set(p)) == 1,
        "predictions_equal": ok and len(set(q)) == 1,
        "params_sha256": sorted({x for x in p if x}),
        "predictions_sha256": sorted({x for x in q if x}),
    }


def compare(pod_results, *, deviation=None, cpu=None, skipped=None):
    """Per (backend, recipe): within-host equality, across-host equality, driver
    builds, device ids, and the CPU-vs-GPU record. Digest equality only; a
    driver difference between the compared hosts is REFUSED_DRIVER_MISMATCH
    (unless a deviation names exactly those builds, which is then recorded)."""
    from scripts.dev.gpu_determinism_study import compare_units

    cells = []
    backends = sorted({r["backend"] for r in pod_results})
    for backend in backends:
        hosts = [r for r in pod_results if r["backend"] == backend]
        identities = [dict(h["identity"], index=0) for h in hosts if h.get("identity")]
        builds = sorted(
            {i.get("driver_version") for i in identities if i.get("driver_version")}
        )
        devices = sorted({i.get("uuid") for i in identities if i.get("uuid")})
        problems = compare_units.preflight(identities)
        driver_mismatch = len(builds) > 1
        deviation_ok = bool(
            deviation is not None
            and driver_mismatch
            and deviation.builds == frozenset(builds)
        )
        recipe_ids = sorted({row["recipe_id"] for h in hosts for row in h["rows"]})
        for recipe_id in recipe_ids:
            within = {h["label"]: _host_cell(h["rows"], recipe_id) for h in hosts}
            if len(hosts) < 2 or len(devices) < 2:
                across = {"outcome": "REFUSED_ONE_UNIT"}
            elif driver_mismatch and not deviation_ok:
                across = {"outcome": "REFUSED_DRIVER_MISMATCH", "driver_builds": builds}
            elif not all(c["complete"] for c in within.values()):
                across = {"outcome": "INCOMPLETE"}
            elif not all(
                c["weights_equal"] and c["predictions_equal"] for c in within.values()
            ):
                across = {"outcome": "NO_SINGLE_DIGEST_WITHIN_A_HOST"}
            else:
                weights = {c["params_sha256"][0] for c in within.values()}
                preds = {c["predictions_sha256"][0] for c in within.values()}
                across = {
                    "outcome": (
                        "AGREE" if len(weights) == 1 and len(preds) == 1 else "DISAGREE"
                    ),
                    "weights_equal": len(weights) == 1,
                    "predictions_equal": len(preds) == 1,
                }
            if deviation_ok:
                across["deviation"] = {
                    "builds": sorted(deviation.builds),
                    "recorded_in": deviation.recorded_in,
                    "reason": deviation.reason,
                }
            cells.append(
                {
                    "backend": backend,
                    "recipe_id": recipe_id,
                    "within_host": within,
                    "within_host_equal": all(
                        c["weights_equal"] and c["predictions_equal"]
                        for c in within.values()
                    ),
                    "across_hosts": across,
                    "driver_builds": builds,
                    "device_ids": devices,
                    "datacenters": sorted(
                        {h.get("datacenter") for h in hosts if h.get("datacenter")}
                    ),
                    "clouds": sorted({h["cloud"] for h in hosts if h.get("cloud")}),
                    "preflight_problems": problems,
                }
            )
    document = {"schema": COMPARISON_SCHEMA, "cells": cells, "cpu_vs_gpu": []}
    if cpu is not None:
        document["cpu_vs_gpu"] = cpu_vs_gpu(cpu, pod_results)
    document["jax_fno"] = "not applicable: the fno is PyTorch-only"
    if skipped:
        document["skipped"] = skipped
    return document


def cpu_vs_gpu(cpu, pod_results):
    """Each recipe's CPU digest beside the first host's GPU digest: a record
    only, expected to differ, never an acceptance."""
    out = []
    for backend, document in sorted(cpu.items()):
        gpu_hosts = [r for r in pod_results if r["backend"] == backend]
        for recipe_id in document["recipes"]:
            cpu_cell = _host_cell(document["rows"], recipe_id)
            gpu_cell = (
                _host_cell(gpu_hosts[0]["rows"], recipe_id) if gpu_hosts else None
            )
            out.append(
                {
                    "backend": backend,
                    "recipe_id": recipe_id,
                    "label": CPU_LABEL,
                    "cpu": cpu_cell,
                    "gpu": gpu_cell,
                    "digests_equal": bool(
                        gpu_cell
                        and cpu_cell["complete"]
                        and gpu_cell["complete"]
                        and cpu_cell["params_sha256"] == gpu_cell["params_sha256"]
                        and cpu_cell["predictions_sha256"]
                        == gpu_cell["predictions_sha256"]
                    ),
                }
            )
    return out


def pod_results(pods):
    """Fetched results of finished pods in the comparator's shape."""
    out = []
    for pod in pods:
        if pod.outcome != "COMPLETE":
            continue
        results = _json(pod.files.get("results.json"))
        out.append(
            {
                "backend": pod.backend,
                "label": pod.label,
                "identity": _json(pod.files.get("identity.json")) or None,
                "datacenter": pod.datacenter,
                "cloud": pod.cloud,
                "rows": results.get("rows", []),
            }
        )
    return out


# ------------------------------------------------------------------ the local CPU dry run
def find_c03_image():
    """A c03 worker image already present locally, or None. Pulls nothing."""
    if shutil.which("docker") is None:
        return None
    try:
        listing = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        ).stdout.split()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return next((i for i in listing if i.startswith("carbon-c03-worker:")), None)


def _docker_has_torch(image):
    done = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            PYTHON,
            image,
            "-c",
            "import torch",
        ],
        capture_output=True,
        check=False,
        timeout=300,
    )
    return done.returncode == 0


def local_cpu_dry_run(
    record,
    out,
    *,
    repository=REPOSITORY,
    image=None,
    use_docker=True,
    backends=BACKENDS,
):
    """The per-repeat flow on the CPU (`JAX_PLATFORMS=cpu`): in the local c03
    image when docker and the image are already present and carry the backend,
    else in-process through the same code path. No pod, no network, no pull."""
    from scripts.dev.exam_design.runpod import a40_pod_phase

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    image = image or (find_c03_image() if use_docker else None)
    documents, modes = {}, {}
    for backend in backends:
        config = phase_config(backend, record)
        sub = out / backend
        sub.mkdir(parents=True, exist_ok=True)
        if image and (backend == "jax" or _docker_has_torch(image)):
            command = [
                "docker", "run", "--rm", "--network", "none", "--entrypoint", PYTHON,
                "--user", f"{os.getuid()}:{os.getgid()}",
                "-v", f"{repository}:/w:ro", "-v", f"{sub}:/out",
                "-e", "PHASE_CONFIG=" + json.dumps(config, sort_keys=True),
                "-e", "PYTHONPATH=/w", "-e", "PYTHONDONTWRITEBYTECODE=1",
                "-w", "/w", image, "-m", PHASE_MODULE, PHASE, "--out", "/out",
                "--cpu", "--root", "/w",
            ]  # fmt: skip
            subprocess.run(command, check=False, timeout=6 * 3600)
            results = sub / "results.json"
            if not results.is_file():
                raise Refused(f"the c03 image run for {backend} produced no results")
            documents[backend] = json.loads(results.read_text())
            modes[backend] = f"docker image {image}"
        else:
            documents[backend] = a40_pod_phase.local_cpu_run(config, repository, sub)
            modes[backend] = "in-process"
    return {"modes": modes, "documents": documents}


def cpu_summary(dry):
    """A readable per-recipe table of the dry run's own within-run equality."""
    rows = []
    for backend, document in sorted(dry["documents"].items()):
        for recipe_id in document["recipes"]:
            cell = _host_cell(document["rows"], recipe_id)
            rows.append({"backend": backend, "recipe_id": recipe_id, **cell})
    return rows


# ------------------------------------------------------------------ command line
def _cmd_select(args):
    try:
        record = build_record(args.panel, root=args.root)
    except Refused as refusal:
        print(str(refusal), file=sys.stderr)
        return 1
    if args.stdout:
        # The record's exact bytes, for an environment whose files do not
        # persist (the canonical wrapper's isolated copy); `sha256` follows.
        sys.stdout.write(canonical_bytes(record).decode())
        return 0
    digest = write_record(record, args.record)
    summary = {
        "record": str(args.record),
        "sha256": digest,
        "picks": [
            {k: p[k] for k in ("role", "id", "n_params_analytic", "n_params_cpu_count")}
            for p in record["picks"]
        ],
    }
    print(json.dumps(summary, indent=1))
    return 0


def _runner(args, record):
    manifest = build_manifest(args.code_ref, Path(args.repository))
    from scripts.dev.exam_design.runpod import pod_control

    if not pod_control.ref_is_pushed(args.code_ref):
        raise Refused("refused: the pod reads code from GitHub; push the commit first")
    if args.key_file is None or not Path(args.key_file).is_file():
        raise Refused("refused: --key-file must name the RunPod key file")
    return PodRunner(
        work_dir=args.work_dir,
        key_file=args.key_file,
        code_ref=args.code_ref,
        manifest=manifest,
        repository=Path(args.repository),
        retry_window_seconds=args.retry_window_minutes * 60,
    )


def _cmd_smoke(args):
    record = load_record(args.record)
    runner = _runner(args, record)
    try:
        measured = smoke(
            runner,
            record,
            backend=args.backend,
            out=args.smoke_record,
            skip_fno=args.skip_fno,
        )
    finally:
        runner.close()
    print(
        json.dumps(
            {
                k: measured[k]
                for k in ("outcome", "startup_seconds", "rebuild_wall_seconds")
            }
        )
    )
    return 0 if measured["outcome"] == "COMPLETE" else 1


def _cmd_run(args):
    record = load_record(args.record)
    if args.local_cpu_dry_run:
        dry = local_cpu_dry_run(
            record,
            args.work_dir,
            repository=Path(args.repository),
            use_docker=not args.no_docker,
            backends=tuple(args.backends or BACKENDS),
        )
        print(
            json.dumps({"modes": dry["modes"], "recipes": cpu_summary(dry)}, indent=1)
        )
        complete = all(d["complete"] for d in dry["documents"].values())
        return 0 if dry["documents"] and complete else 1
    if args.smoke_record is None:
        raise Refused("refused: --smoke-record is required (run `smoke` first)")
    if args.smoke_record_pytorch is None:
        raise Refused("refused: --smoke-record-pytorch is required")
    smoke_record = {
        "jax": load_smoke(args.smoke_record),
        "pytorch": load_smoke(args.smoke_record_pytorch),
    }
    cap = Decimal(args.cap)
    if args.dry_run:
        manifest = build_manifest(args.code_ref, Path(args.repository))
        print(json.dumps({"dry_run": True, "pods_created": 0, "images": IMAGES,
                          "code_files": len(manifest), "plan": plan(record, smoke_record, cap, args.skip_fno)}, indent=1))  # fmt: skip
        return 0
    plan(
        record, smoke_record, cap, args.skip_fno
    )  # refuse before touching the provider
    runner = _runner(args, record)
    try:
        summary, results = run_acceptance(
            runner, record, smoke_record, cap=cap, skip_fno=args.skip_fno
        )
        flat = pod_results([p for pods in results.values() for p in pods])
        document = compare(flat, skipped=SKIPPED_FNO if args.skip_fno else None)
        out = Path(args.work_dir)
        (out / "summary.json").write_text(
            json.dumps(summary, indent=1, sort_keys=True) + "\n"
        )
        (out / "comparison.json").write_text(
            json.dumps(document, indent=1, sort_keys=True) + "\n"
        )
    finally:
        runner.close()
    print(
        json.dumps(
            {
                "clean": summary["reconciliation"]["clean"],
                "cells": len(document["cells"]),
            }
        )
    )
    return 0 if summary["reconciliation"]["clean"] else 1


def _cmd_compare(args):
    from scripts.dev.gpu_determinism_study import compare_units

    flat = json.loads(Path(args.results).read_text())
    deviation = None
    if args.deviation:
        deviation = compare_units.DriverDeviation.read(
            json.loads(Path(args.deviation).read_text())
        )
    cpu = json.loads(Path(args.cpu).read_text()) if args.cpu else None
    print(
        json.dumps(
            compare(flat, deviation=deviation, cpu=cpu), indent=1, sort_keys=True
        )
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("select", help="analytic recipe selection (brief 2b)")
    s.add_argument("--record", type=Path, required=True)
    s.add_argument("--stdout", action="store_true", help="print the record only")
    s.add_argument("--panel", default=PANEL)
    s.add_argument("--root", default=str(REPOSITORY))
    s.set_defaults(handler=_cmd_select)
    for name, handler in (("smoke", _cmd_smoke), ("run", _cmd_run)):
        p = sub.add_parser(name)
        p.add_argument("--record", type=Path, required=True)
        p.add_argument("--smoke-record", type=Path, required=(name == "smoke"))
        p.add_argument("--work-dir", type=Path, required=True)
        p.add_argument(
            "--key-file",
            type=Path,
            help="RunPod key FILE path; never read here for display",
        )
        p.add_argument("--code-ref", default="")
        p.add_argument("--repository", default=str(REPOSITORY))
        p.add_argument("--cap", default=str(DEFAULT_CAP_USD))
        p.add_argument(
            "--retry-window-minutes",
            type=int,
            default=DEFAULT_RETRY_WINDOW_SECONDS // 60,
            help="minutes of capacity retries (rounds every 10 minutes)",
        )
        p.add_argument(
            "--skip-fno",
            action="store_true",
            help="skip the PyTorch fno leg (known GPU device bug) until the v3 images",
        )
        p.set_defaults(handler=handler)
        if name == "smoke":
            p.add_argument("--backend", choices=BACKENDS, default="jax")
        else:
            p.add_argument("--smoke-record-pytorch", type=Path)
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--local-cpu-dry-run", action="store_true")
            p.add_argument("--no-docker", action="store_true")
            p.add_argument("--backends", nargs="+", choices=BACKENDS)
    c = sub.add_parser("compare")
    c.add_argument("--results", type=Path, required=True)
    c.add_argument("--deviation", type=Path)
    c.add_argument("--cpu", type=Path)
    c.set_defaults(handler=_cmd_compare)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except NoA40 as none:
        print(json.dumps({"result": none.result}))
        return 3
    except Refused as refusal:
        print(str(refusal), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
