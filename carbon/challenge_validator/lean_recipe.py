"""DEVELOPMENT-only ConstructionRecipe adapter over the durable direct tasks.

The signed validator door authenticates and strictly screens the request. This
adapter binds the registered Challenge material and sends the recipe to the
existing per-owner direct task provider. That provider owns source/image
resolution, C-03 build, frozen source-free inference, durable child operations
and reconciliation. No scorer or promotion is installed here.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path

from carbon.development_session.construction_recipe import (
    SCHEMA as RECIPE_SCHEMA,
)
from carbon.development_session.construction_recipe import bind_recipe
from carbon.reconstruction.served_recipe_contract import registered

from .interface import (
    ChallengeAdapter,
    SameRecipeAlreadySubmitted,
    Unavailable,
    digest,
)

OUTCOME_SCHEMA = "carbon.lean-recipe-development-outcome.v1"
#: How many fresh re-runs one recipe may get on one pack set after
#: infrastructure failures (invariant 7): an engineering bound on retries of our
#: own failures, never a scientific value. Past it the door is unavailable.
MAX_INFRA_RERUNS = 16
#: A miner's own withdrawal of its queued, not-yet-building submission (owner GO 15 Nov 2026 via the Lead: "those 3 are
#: fine."): the durable cancellation id the provider keeps for it is this prefix + the task id, so a withdrawn task is told
#: apart from a receiver stop's cancellation (``mcp-cancel-``) after any restart.
WITHDRAW_PREFIX = "miner-withdraw-"
#: The public failure code a withdrawn task projects with (never ``direct_task_cancelled``, which the kit resubmits).
WITHDRAWN_CODE = "withdrawn_by_miner"


#: The operator's build re-arm requests and their applied outcomes (`infra_requeue rebuild`), in the receiver's
#: ``auto-grade/requeued`` beside the grade requeues.
REBUILD_REQUESTS = "rebuild-requests.jsonl"
REBUILD_APPLIED = "rebuild-applied.jsonl"
#: The builds the receiver's own stop cancelled (`OwnerProviders.cancel`), one line each: re-run at the next start by
#: `_apply_rebuild_requests` (CARBON-CUT REQUEUE, V2 18 Nov 2026), once each, like an operator rebuild request.
STOP_CANCELLED = "stop-cancelled.jsonl"
#: The ruling an automatic stop-cancel re-run is logged under (there is no operator receipt: V2's standing ruling)
STOP_CANCEL_RULING = "carbon-cut-stop-cancel"
#: Every build re-run the door made (`LeanRecipeAdapter._requeue_failed_build`), append-only: ``{from_task, new_task,
#: chain_root, code, at_ns}``; the caps below count it.
BUILD_RETRIES = "build-retries.jsonl"
#: OWNER D16 (18 Nov 2026: "automatic re-runs of Carbon-side failures ... capped at 3 per failure code and 5 per task,
#: then the owed list"), for builds as for grades (`auto_retry`): re-runs of one failure code within one task's chain (the
#: miner's task and every door re-run of it), and re-runs of the chain in all.
BUILD_CODE_RETRIES = 3
BUILD_CHAIN_RETRIES = 5
#: The owed-list feed a spent cap writes to (`auto_retry.ALERT_NAME`, beside it).
BUILD_ALERTS = "auto-retry-alerts.jsonl"


def _jsonl(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for raw in text.splitlines():
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        if type(line) is dict:
            out.append(line)
    return out


#: Held by the one advance round applying the operator's rebuild requests (`_apply_rebuild_requests`).
_REBUILD_APPLY = threading.Lock()


def _append_line(path, line):
    """Append one JSON line to ``path`` (its directory made private if missing)."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as log:
        log.write(json.dumps(line, sort_keys=True) + "\n")


def _build_failure_code(task):
    """The failure code a build re-run is counted under: its terminal receipt's refusal code, else its state's."""
    receipt = getattr(task, "terminal_receipt", None)
    code = getattr(receipt, "refusal_code", None)
    if type(code) is str and code:
        return code
    return "direct_task_" + task.state.value.lower()


def _failure_class(provider, task_id):
    """The closed failure class (`infra_diagnosis.classify`) of a FAILED_INFRA / UNRESOLVED task from its retained
    diagnosis, or None when it has none (a task from before diagnoses, a stop's cancellation) or it cannot be read.
    """
    from carbon.development_session import infra_diagnosis

    read = getattr(provider, "private_infra_diagnosis", None)
    if read is None:
        return None
    try:
        record = read(task_id)
    except Exception:  # noqa: BLE001 - unreadable: counted as before
        return None
    return None if record is None else infra_diagnosis.classify(record)


def _class_refusal(failure_class, chain):
    """Why a build of ``failure_class`` gets no automatic rebuild after ``chain`` door rebuilds in its chain, or None
    (OWNER G-LEAD-10, replacing the 3x requeue + D16 cap for builds): a proven Carbon-side class gets exactly ONE; an
    unknown one (no class, or `UNCLASSIFIED`) none; a recipe-side one none."""
    from carbon.development_session import infra_diagnosis

    if failure_class is None or failure_class == infra_diagnosis.UNCLASSIFIED:
        return "unknown_no_rebuild"
    if failure_class in infra_diagnosis.RECIPE_CLASSES:
        return "recipe_side"
    if chain >= infra_diagnosis.RETRIES.get(failure_class, 0):
        return "one_rebuild_spent"
    return None


class _RebuildIdentities:
    """``identity -> bool`` for `remote_gpu_build.set_healthy_only`: whether an op is the build of one of this door's
    class rebuilds (`rebuild_build_identities`), re-read only when `BUILD_RETRIES` changes (size and mtime).
    """

    def __init__(self, ledger_path):
        self.ledger_path = ledger_path
        self._seen = None
        self._identities = frozenset()

    def __call__(self, identity):
        path = Path(self.ledger_path).parent / "auto-grade" / "requeued" / BUILD_RETRIES
        try:
            info = path.stat()
            seen = (info.st_size, info.st_mtime_ns)
        except OSError:
            return False
        if seen != self._seen:
            self._identities = rebuild_build_identities(self.ledger_path)
            self._seen = seen
        return identity in self._identities


def rebuild_build_identities(ledger_path):
    """The build op identities of the door's class rebuilds (`BUILD_RETRIES` lines marked ``healthy_box``): each takes
    its slot only on a healthy box (`remote_gpu_build.set_healthy_only`, owner G-LEAD-10).
    """
    from carbon.development_session.bundle_construction_worker import (
        direct_child_identity,
    )

    path = Path(ledger_path).parent / "auto-grade" / "requeued" / BUILD_RETRIES
    return frozenset(
        direct_child_identity(line["new_task"], "build")
        for line in _jsonl(path)
        if line.get("healthy_box") is True and type(line.get("new_task")) is str
    )


def _build_retry_counts(directory, task, code):
    """``(chain_root, re-runs in the chain, re-runs of ``code`` in it)`` from `BUILD_RETRIES`: the chain is the miner's
    task and every door re-run made from it (each line names its chain's root)."""
    lines = _jsonl(Path(directory) / BUILD_RETRIES)
    root = next(
        (line.get("chain_root") for line in lines if line.get("new_task") == task), None
    )
    root = task if type(root) is not str else root
    chain = [line for line in lines if line.get("chain_root") == root]
    return root, len(chain), sum(1 for line in chain if line.get("code") == code)


#: The task's refusal code when its build or build-pipeline inference child settled FAILED_MINER through
#: `research_carrier._settle_miner_failure` (`research_tasks._run_queued_task`): the only REFUSED end that is the
#: candidate's own program (a campaign limit, a refused graph or a capability gap carry other codes).
RECIPE_FAILED_REFUSAL = "candidate_program_failed"
#: G-LEAD-10 row 1's closed code: a build that ended on the candidate's own failure, its daily spot used.
RECIPE_SPOT_CODE = "recipe_build_failed"


def recipe_spot_code(provider, owner, task_id, task):
    """`RECIPE_SPOT_CODE` when ``task_id``'s build (``task``, its task view as the provider returns it) ended on the
    candidate's OWN structured failure, else None (read-only).

    ALL must hold (V2 part (1) (a): only the existing structured recipe-side ends): the task is REFUSED with
    `RECIPE_FAILED_REFUSAL`; its build or build-pipeline inference child settled FAILED_MINER (the carrier's
    `_settle_miner_failure`: a program failure, WORKER_MEMORY_LIMIT_REACHED, or the build wall on a QUIET box: the
    carrier types a busy box's wall Carbon's before any child settles, and a GPU-lane build's other failures end
    FAILED_INFRA, never REFUSED); and it is NOT the door's CPU worker wall (`_cpu_wall_refusal`, Carbon's class
    carbon_cpu_worker_wall). Anything unreadable: None.
    """
    try:
        from carbon.development_session.bundle_construction_worker import (
            direct_child_identity,
        )
        from carbon.research import DirectTaskStateV3

        receipt = task.terminal_receipt
        if (
            task.state is not DirectTaskStateV3.REFUSED
            or receipt is None
            or receipt.refusal_code != RECIPE_FAILED_REFUSAL
        ):
            return None
        if _cpu_wall_refusal(provider, owner, task_id):
            return None
        with provider.ledger.db() as db:
            for phase in ("build", "inference"):
                row = db.execute(
                    "SELECT state FROM operations WHERE id=? AND owner=?",
                    (direct_child_identity(task_id, phase), owner),
                ).fetchone()
                if row is not None and row[0] == "FAILED_MINER":
                    return RECIPE_SPOT_CODE
        return None
    except Exception:  # noqa: BLE001 - unproven: never the candidate's
        return None


def _cpu_wall_refusal(provider, owner, task_id):
    """Whether ``task_id``'s build-pipeline INFERENCE child settled FAILED_MINER on the worker wall (the deadline code):
    a model too slow for the door's one-process CPU inference, which per-case processes now runs in workers (Live ops /
    case-procs, 17 Nov: 603 s of 648 on GPUYard's CPU worker after an A100 build). Read-only; anything unreadable is no.
    """
    try:
        from carbon.development_session.bundle_construction_worker import (
            direct_child_identity,
        )
        from carbon.reconstruction.worker.model import WorkerCode

        child = direct_child_identity(task_id, "inference")
        with provider.ledger.db() as db:
            row = db.execute(
                "SELECT state, result FROM operations WHERE id=? AND owner=?",
                (child, owner),
            ).fetchone()
        if row is None or row[0] != "FAILED_MINER":
            return False
        return json.loads(row[1]).get("failure_code") == WorkerCode.DEADLINE.value
    except Exception:  # noqa: BLE001 - unreadable: never a re-run
        return False


#: `LeanRecipeAdapter.withdraw`'s closed answers.
WITHDRAWN = "WITHDRAWN"
ALREADY_WITHDRAWN = "ALREADY_WITHDRAWN"
WITHDRAW_TOO_LATE = "TOO_LATE"
WITHDRAW_UNKNOWN = "UNKNOWN"
_SOURCE_PATHS = (
    "carbon/challenge_validator/lean_recipe.py",
    "carbon/development_session/construction_recipe.py",
    "carbon/development_session/research_tasks.py",
    "carbon/development_session/direct_graph_construction_worker.py",
    "carbon/development_session/bundle_construction_worker.py",
    "carbon/development_session/library_bundles.py",
    "carbon/development_session/library_overlay_prep.py",
    "carbon/development_session/synthetic_graph_adapter.py",
    "carbon/development_session/physical_graph_adapter.py",
    "carbon/development_session/physical_graph_state.py",
    "carbon/development_session/physical_graph_trainer.py",
    # Battery's graph adapter (the Validator's ruling (a)) and the Battery
    # modules it stages unchanged into its build and inference children.
    "carbon/development_session/graph_adapters.py",
    "carbon/development_session/battery_graph_adapter.py",
    "carbon/development_session/build_refusal.py",
    "carbon/battery/domain.py",
    "carbon/battery/recipes.py",
    "carbon/battery/training.py",
    "carbon/battery/direct_graph.py",
    # Graph route v2's adapter, state, trainer and refusal classes.
    "carbon/development_session/physical_graph_adapter_v2.py",
    "carbon/development_session/physical_graph_state_v2.py",
    "carbon/development_session/physical_graph_trainer_v2.py",
    "carbon/development_session/physical_graph_trainer_v3.py",
    "carbon/development_session/build_refusal_v2.py",
    "carbon/development_session/bundle_graph_state.py",
    "carbon/reconstruction/served_recipe_contract.py",
    "carbon/challenge_kit/physical_material.py",
    "carbon/challenge_kit/physical_pack.py",
    "carbon/challenge_kit/physical_public.py",
    "carbon/challenge_kit/physical_public_train.py",
    "carbon/challenge_kit/version_registry.py",
)


def _source_identity() -> str:
    """Bind the adapter and every repository module staged into its workers."""
    from carbon.development_session.bundle_construction_worker import (
        STAGED_MODULES as BUNDLE_STAGED_MODULES,
    )
    from carbon.development_session.direct_graph_construction_worker import (
        STAGED_MODULES as GRAPH_STAGED_MODULES,
    )

    root = Path(__file__).resolve().parents[2]
    observed = {}
    staged = {
        module.replace(".", "/") + ".py"
        for module in (*BUNDLE_STAGED_MODULES, *GRAPH_STAGED_MODULES)
    }
    for name in sorted(set(_SOURCE_PATHS) | staged):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("served recipe source unavailable")
        observed[name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return digest({"schema": "carbon.lean-recipe-source-binding.v1", "files": observed})


def _implementation_identity() -> str:
    return digest(
        {
            "schema": OUTCOME_SCHEMA,
            "recipe_schema": RECIPE_SCHEMA,
            "task_schema": "direct_start_task_request_v3",
            "source_boundary": "C03_BUILD_THEN_SOURCE_FREE_INFERENCE",
            "source_identity": _source_identity(),
        }
    )


def _withdrawn_cancellation(provider, task_value):
    """Whether the provider's durable cancellation id of ``task_value`` is its owner's withdrawal (`WITHDRAW_PREFIX`)."""
    cancellation = getattr(provider, "_cancellations", {}).get(task_value)
    return type(cancellation) is str and cancellation == WITHDRAW_PREFIX + task_value


#: OPERATIONAL, not science: how often a parallel build round samples its host (as `AutoGrader`'s grade samples).
BUILD_PROBE_SECONDS = 5.0


@contextlib.contextmanager
def _build_wall_guard(claims):
    """A19 (V2 F-A19): while a door runs parallel build rounds (``claims``: its `grade_sequencer.OwnerClaims`), each build
    samples its host (Carbon worker containers, foreign GPU compute) and a wall stop is the candidate's only when every
    sample saw at most its own container and no foreign GPU compute (`research_carrier.BUILD_WALL_GUARD`). A build on a
    REMOTE lane samples its BOX instead, on the box (`host_quiet.box_counters`, CV-Motor L12624 (b) + (c)); a build whose
    lane is not the one its probe watched is never quiet. A build on a remote lane is guarded so even without claims
    (one build round). Without claims on this host: nothing, as before.
    """
    from carbon.challenge_validator import host_quiet
    from carbon.development_session import research_carrier
    from carbon.reconstruction import remote_lane

    # a REMOTE GPU build slot's op (`remote_gpu_build`) samples ITS box for its own life, whatever the claims
    remote_token = research_carrier.REMOTE_BUILD_GUARD.set(_remote_gpu_build_guard)
    try:
        if claims is None and remote_lane.current() is None:
            yield
            return
        with _host_build_wall_guard(claims, host_quiet, research_carrier, remote_lane):
            yield
    finally:
        research_carrier.REMOTE_BUILD_GUARD.reset(remote_token)


def _quiet_samples(probe):
    """Every in-run sample answered and saw at most the build's own container and no foreign GPU compute."""
    samples, gpu = list(probe.samples), list(probe.gpu_samples)
    return bool(
        samples
        and gpu
        and all(sample is not None and sample <= 1 for sample in samples)
        and all(value == 0 for value in gpu)
    )


def _remote_gpu_build_guard(binding):
    """`research_carrier.REMOTE_BUILD_GUARD` for one REMOTE GPU build op: a box probe on its slot's box (CV-Motor L12624
    (b) + (c): sampled there, in-run samples required). Returns ``(quiet, stop)``."""
    from carbon.challenge_validator import host_quiet

    count, gpu = host_quiet.box_counters(binding)
    probe = host_quiet.Probe(
        lock_held=True,
        containers=count,
        gpu=gpu,
        seconds=BUILD_PROBE_SECONDS,
        require_samples=True,
    ).start()
    # stop: end the sampling only (no stop samples over a link that may be down, with the slot still held)
    return (lambda: _quiet_samples(probe)), probe._stop.set


@contextlib.contextmanager
def _host_build_wall_guard(claims, host_quiet, research_carrier, remote_lane):
    """The A19 guard for a build round with claims: the Carbon containers on its lane's own cores (on its box for a remote
    GRADE lane), or this whole host when the round holds no lane; see `_build_wall_guard`.
    """

    from carbon.reconstruction import grade_lanes

    def count():
        ids = host_quiet.worker_containers()
        return None if ids is None else len(ids)

    watched = remote_lane.current()
    own = grade_lanes.current()
    if watched is not None:
        _box, gpu = host_quiet.box_counters(watched)
    else:
        gpu = host_quiet.foreign_gpu_compute
    if own is not None:
        # owner, 17 Nov 2026 (lane core pinning is the timing protection; Lead: builds too): a build round on a lane
        # counts the Carbon containers on ITS OWN cores only (on its box for a remote lane), as a grade does
        cpuset = own.cpuset

        def count():
            return host_quiet.count_lane_containers(cpuset, watched)

    elif watched is not None:
        count = _box
    probe = host_quiet.Probe(
        lock_held=True,
        containers=count,
        gpu=gpu,
        seconds=BUILD_PROBE_SECONDS,
    ).start()

    def quiet():
        # the round still on the lane (and box) its probe watched: else the samples read other cores
        if remote_lane.current() != watched or grade_lanes.current() != own:
            return False
        samples, gpu = list(probe.samples), list(probe.gpu_samples)
        return bool(
            samples
            and gpu
            and all(sample is not None and sample <= 1 for sample in samples)
            and all(value == 0 for value in gpu)
        )

    token = research_carrier.BUILD_WALL_GUARD.set(quiet)
    try:
        yield
    finally:
        research_carrier.BUILD_WALL_GUARD.reset(token)
        probe.verdict()  # ends the sampling thread


#: The one build-requeue refusal that may clear in the same process (its ledger rows not all written yet); every other
#: refusal is remembered (`_requeue_failed_build`).
_REQUEUE_RETRYABLE = frozenset({"incomplete"})
#: The shortest interval between two requeue asks of one task (`_requeue_failed_build`).
REQUEUE_ASK_SECONDS = 300
#: The owner refusals an advance pass skips (that task only), never the end of the pass.
_SKIPPED_OWNER_CODES = frozenset(
    {"direct_provider_registration_unavailable", "direct_provider_owner_set_aside"}
)


def _group_mates(adapter, hotkey, group):
    """The hotkeys of ``hotkey``'s allowance group ``group`` (``hotkey`` itself always among them), sorted, or None when
    the installed grouping has no snapshot window (then the caller reads every hotkey's group, as before).

    The members come from the grouping's latest snapshot: a hotkey the snapshot cannot resolve is in no shared group
    (`allowance_groups.Grouping`: its own ``h:`` group, or refused), so the group's other hotkeys are exactly the
    snapshot's members whose group is ``group``. The ``{group: members}`` map is built once per (snapshot, funder map)
    and kept on the adapter (memory only, one entry); `group_of` itself is unchanged.
    """
    from carbon.challenge_validator import exam_cap

    grouping = exam_cap.GROUPING
    window = getattr(grouping, "window", None)
    if window is None:
        return None
    try:
        from carbon.battery.intake import grading_snapshot

        # the SAME snapshot bound as `allowance_groups.Grouping` (one epoch, over-broad audit #10): members and groups agree
        snapshot = grading_snapshot(window)
        funder = getattr(grouping, "funder_map", None)
        current = funder() if callable(funder) else None
        participants = tuple(snapshot.participants)
    except Exception:  # noqa: BLE001 - unreadable now: the old read decides
        return None
    key = (id(snapshot), getattr(snapshot, "finalized_block", None), id(current))
    cached = getattr(adapter, "_group_mates_cache", None)
    if cached is None or cached[0] != key:
        groups = {}
        for member in participants:
            name = getattr(member, "hotkey", None)
            if type(name) is not str:
                continue
            try:
                groups.setdefault(exam_cap.group_of(name), []).append(name)
            except exam_cap.ExamCapRefused:
                continue
        cached = (key, groups)
        adapter._group_mates_cache = cached
    return sorted({hotkey, *cached[1].get(group, ())})


class LeanRecipeAdapter(ChallengeAdapter):
    """One registered kit; provider instances remain bound to signer owners."""

    strategy_schema = RECIPE_SCHEMA
    disclosure_fields = frozenset({"task_id", "state_digest", "predictions_digest"})

    def __init__(
        self,
        discovery,
        provider_for: Callable,
        ledger,
        *,
        measure_query: bool = False,
        copy_hotkey: str | None = None,
        speed_sample_key: bytes | None = None,
    ):
        from carbon.challenge_validator.ledger import AttemptLedger
        from carbon.development_session.research_service import DirectFixtureDiscovery
        from carbon.transport.models import MAX_BODY

        if (
            type(discovery) is not DirectFixtureDiscovery
            or type(ledger) is not AttemptLedger
            or not callable(provider_for)
            or type(measure_query) is not bool
        ):
            raise TypeError(
                "verified discovery, owner provider and attempt ledger required"
            )
        info, _manifest = discovery._checked(discovery.info.challenge_key)
        contract = registered(
            info.challenge_key.challenge_id, info.challenge_key.version
        )
        if discovery._material["construction_kit"] != contract.construction_kit:
            raise ValueError("served recipe material differs from registered kit")
        self.discovery = discovery
        self.provider_for = provider_for
        self.ledger = ledger
        self._measure_query = measure_query
        # This validator's hotkey: a sealed pack is accepted only as its copy for
        # this hotkey (traceable copies; None = no copy header required).
        self.copy_hotkey = copy_hotkey
        # The custody copy key the speed-sample seed is derived under (pool versions' single-design call timing,
        # `single_call_timing.sample_seed`); None = a pool grade has no speed evidence (typed unavailable).
        self.speed_sample_key = speed_sample_key
        #: Validator-derived tasks (the crown's averaging rebuilds) in flight, task id -> host owner, in memory only
        #: and only while `deriving` holds them: never a miner's, never persisted, never in the ledger's intents.
        self._derived_owners: dict[str, str] = {}
        self.challenge_id = contract.challenge_id
        self.challenge_version = contract.version
        self.contract_digest = contract.digest
        self._evidence_label = contract.evidence_label
        self.max_strategy_bytes = MAX_BODY
        self._kit = dict(contract.construction_kit)
        self._identities = self._bound_identities(contract)
        # OWNER G-LEAD-10: this door's class rebuilds take their build slot only on a healthy box
        path = getattr(ledger, "path", None)
        if path is not None:
            from carbon.reconstruction import remote_gpu_build

            remote_gpu_build.set_healthy_only(_RebuildIdentities(path))

    def _bound_identities(self, contract):
        from carbon.development_session.profile import canonical
        from carbon.development_session.profile import digest as sha
        from carbon.research import canonical_digest

        key = self.discovery.info.challenge_key
        info, manifest = self.discovery._checked(key)
        material = self.discovery._material
        policy = material["construction_limits_document"][
            "reconstruction_resource_policy"
        ]
        rule = {"schema": "carbon.lean-recipe-score-binding.v1", "score_pack": None}
        if self._measure_query:
            rule = {
                "schema": "carbon.lean-recipe-score-binding.v2",
                "score_pack": None,
                "measurement_profile": "COLD_QUERY_V2",
            }
        return {
            "schema": "carbon.lean-recipe-adapter-identities.v1",
            "contract_digest": contract.digest,
            "rule_digest": digest(rule),
            "implementation_digest": _implementation_identity(),
            "construction_kit_digest": sha(canonical(self._kit)),
            "challenge_info_digest": canonical_digest(info),
            "manifest_digest": canonical_digest(manifest),
            "resource_policy_digest": sha(canonical(policy)),
            "allowlist_digest": contract.allowlist_digest,
        }

    def identities(self):
        return json.loads(json.dumps(self._identities))

    def validate_strategy(self, strategy):
        """Strict recipe and exact Challenge binding before any worker
        reservation. A catalog recipe is returned as the Carbon bundle recipe
        it names (`backbone_catalog.served.expand`), its settings checked by
        that bundle's own door; it then runs as that bundle."""
        recipe = bind_recipe(
            strategy,
            challenge_id=self._kit["id"],
            challenge_version=self._kit["version"],
            train_digest=self._kit["train_digest"],
            interface_digest=self._kit["interface_digest"],
            construction_limits_digest=self._kit["construction_limits_digest"],
        )
        if recipe.to_dict()["source"]["kind"] == "bundle":
            # a smoke-only GPU build is practice only: refuse it before anything is reserved
            from carbon.backbone_catalog.served import refuse_unreproducible_runtime

            refuse_unreproducible_runtime(recipe.to_dict()["source"]["bundle_ref"])
        if recipe.to_dict()["source"]["kind"] == "catalog":
            from carbon.backbone_catalog.served import expand_official
            from carbon.development_session.construction_recipe import (
                ConstructionRecipe,
            )

            # The grading rebuild: the entry's official-grade GPU twin on a GPU worker this receiver holds.
            # No official GPU receipt is a typed refusal (catalog_gpu_receipt_pending), never a CPU rebuild
            # (OWNER-GPU-ONLY-REPEAT-TOLERANCE-01).
            expanded, _runtime = expand_official(recipe.to_dict(), self._gpu_runtimes())
            return ConstructionRecipe.from_dict(expanded)
        return recipe

    def _gpu_runtimes(self):
        """The GPU build runtimes this receiver's construction parents serve (none for a CPU
        receiver, and for a provider source that does not say)."""
        found = getattr(self.provider_for, "gpu_runtimes", None)
        return tuple(found()) if callable(found) else ()

    def check_served_source(self):
        """The served sources this door was started with (its ``implementation_digest``, computed at start) are still
        byte-for-byte the installed ones, else ``served_recipe_source_changed``. V2's ruling (18 Nov 2026): checked at
        door start and right before a build or a grade runs (`_advance_one`, `lean_recipe_retention`'s grade entries),
        never on a lookup (`owner`, `_provider`, the claim and advance scans, status reads): those run no code.
        """
        identities = getattr(self, "_identities", None)
        if identities is None:
            # `__init__` always binds the start identity: an adapter without one was built some other way (a one-shot
            # tool, a test double) and has no start identity to compare, exactly as `_provider` never read one for it
            return
        if identities["implementation_digest"] != _implementation_identity():
            raise Unavailable("served_recipe_source_changed")

    def _provider(self, hotkey):
        from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

        provider = self.provider_for(hotkey)
        if (
            type(provider) is not DirectDevelopmentTasksV3
            or provider.owner != hotkey
            or provider.discovery is not self.discovery
            or provider.evaluation_pack_digest != self.discovery.evaluation_pack_digest
        ):
            raise Unavailable("direct_provider_binding_unavailable")
        return provider

    def _request(
        self, hotkey, recipe, *, evaluation_pack_digest=None, rerun=0, rebuild=None
    ):
        """The task request; ``rerun`` n > 0 is the n-th fresh task for the same
        recipe after infrastructure failures (generation 0 is unchanged). ``rebuild`` is the label of a
        validator-derived averaging rebuild (`crown_average`); it makes the task its own identity, and without it
        the identity is exactly what it always was."""
        from carbon.development_session.profile import canonical
        from carbon.development_session.profile import digest as sha
        from carbon.research import DirectStartTaskRequestV3

        info = self.discovery.info
        task_binding = hotkey + "\0" + self.contract_digest + "\0" + recipe.digest
        if self._measure_query:
            task_binding += "\0" + self._identities["rule_digest"]
        if evaluation_pack_digest is not None:
            task_binding += "\0EVALUATION_PACK\0" + evaluation_pack_digest
        if rerun:
            task_binding += "\0INFRA_RERUN\0" + str(rerun)
        if rebuild is not None:
            task_binding += "\0CROWN_REBUILD\0" + rebuild
        identity = hashlib.sha256(task_binding.encode("utf-8")).hexdigest()
        return DirectStartTaskRequestV3(
            info.challenge_key,
            "lean-recipe-" + identity,
            recipe.to_dict(),
            self._identities["challenge_info_digest"],
            self._identities["manifest_digest"],
            self._identities["construction_kit_digest"],
            info.public_train_digest,
            info.practice_inputs_digest,
            info.interface_digest,
            info.construction_limits_digest,
            sha(
                canonical(
                    self.discovery._material["construction_limits_document"][
                        "reconstruction_resource_policy"
                    ]
                )
            ),
        )

    def require_registered_pool(self):
        """Fail closed (Validator WIRING_CHANNEL_AND_LOOKUP_P0_RULING_20261030, item b): an
        OFFICIAL submission on a registered Challenge version with no registered pool exam is
        refused, so the older allowlist-v7 versions (F08 1.3/1.4, F02 2.2/2.3, Cooling 1.2,
        Motor 1.3) grade nothing. Practice is not routed here and stays open. A version the
        version registry does not know is refused by its own door, not by this one."""
        from carbon.challenge_kit import version_registry
        from carbon.challenge_registry import published_exam

        kit = getattr(self, "_kit", None)
        if kit is None:  # no bound kit: validate_strategy refuses it next
            return
        key = (kit["id"], kit["version"])
        try:
            version_registry.entry(*key)
        except version_registry.UnregisteredVersion:
            return
        if published_exam.registered_pool(*key) is None:
            raise Unavailable("official_version_without_pool")

    def evaluate(self, submission):
        from carbon.development_session.construction_recipe import (
            RecipeRefused,
            graph_envelope_from_workspace,
        )
        from carbon.research.errors import ResearchServiceErrorCode
        from carbon.research.lifecycle import ResearchTaskProviderError

        self.require_registered_pool()
        from carbon.challenge_validator import crown_average

        if submission.hotkey == crown_average.HOST_OWNER:
            # the host-owned owner of the crown average's derived rebuilds is never a submitter
            raise Unavailable("direct_owner_reserved")
        from carbon.challenge_validator import step_timing

        with step_timing.step("validate"):
            recipe = self.validate_strategy(submission.strategy)
        with step_timing.step("provider"):
            provider = self._provider(submission.hotkey)
        # The durable task provider owns source inspection and admitted
        # environment preparation. A missing preinstalled image is not a
        # separate construction-admission rule at the signed door.
        # Generation 0 is the recipe's task. One that ended on our own
        # infrastructure (the task, or its grading released as FAILED_INFRA)
        # is never the miner's result (invariant 7): the next generation is a
        # fresh task, graded in the miner's next slot.
        earlier_generations = []
        with step_timing.step("generations"):
            for rerun in range(MAX_INFRA_RERUNS + 1):
                request = self._request(
                    submission.hotkey,
                    recipe,
                    evaluation_pack_digest=provider.evaluation_pack_digest,
                    rerun=rerun,
                )
                task_id = provider._task_id(request)
                if self._already_graded(submission.hotkey, task_id.value, provider):
                    raise SameRecipeAlreadySubmitted(self.outcome(task_id.value))
                if not self._ended_on_infra(submission.hotkey, task_id, provider):
                    break
                earlier_generations.append(task_id.value)
            else:
                raise Unavailable("direct_infra_rerun_limit_reached")
        with step_timing.step("spent_round"):
            self._refuse_spent_round(submission, task_id.value, provider)
        # One waiting submission per coldkey (`coldkey_waiting`): checked, and its place held, until the task is started
        with contextlib.ExitStack() as placed:
            step_timing.enter(
                placed,
                "coldkey_place",
                self._coldkey_place(submission.hotkey, task_id.value),
            )
            source = recipe.to_dict()["source"]
            if source["kind"] == "graph":
                try:
                    with step_timing.step("workspace"):
                        graph_envelope_from_workspace(
                            provider.ledger, provider.owner, recipe
                        )
                except RecipeRefused as refused:
                    raise Unavailable(refused.code) from None
            from carbon.research import canonical_bytes

            self.ledger.record_recipe_task_intent(
                self.contract_digest,
                task_id.value,
                submission.hotkey,
                "sha256:" + hashlib.sha256(canonical_bytes(request)).hexdigest(),
            )
            self._give_back_queue_place(
                earlier_generations, task_id.value, submission.hotkey
            )
            if submission.strategy.get("source", {}).get("kind") == "catalog":
                from carbon.backbone_catalog.served import submission_document

                self.ledger.record_catalog_submission(
                    self.contract_digest,
                    task_id.value,
                    submission_document(submission.strategy, recipe.to_dict()),
                )
            try:
                with step_timing.step("start_task"):
                    task = provider.start_research_task(
                        request, measure_query=self._measure_query
                    ).task
            except ResearchTaskProviderError as refused:
                if refused.code in (
                    ResearchServiceErrorCode.REFERENCE_NOT_FOUND,
                    ResearchServiceErrorCode.REFERENCE_MISMATCH,
                    ResearchServiceErrorCode.BOUND_EXCEEDED,
                ):
                    raise Unavailable("direct_" + refused.code.value.lower()) from None
                raise Unavailable("direct_provider_unavailable") from None
        if task.task_id != task_id:
            raise RuntimeError("direct task identity changed after owner intent")
        return self._project(task, provider)

    def _already_graded(self, hotkey, submission_id, provider):
        """Validator ruling (a): this hotkey's recipe already graded on this
        pack set. The task identity binds hotkey, contract, recipe and pack,
        so its exam-cap row is the earlier grading; a rotated pack set is a
        new task. Without a pack nothing is graded, so nothing is refused."""
        if provider.evaluation_pack_digest is None:
            return False
        from carbon.challenge_validator.exam_cap import ExamCap

        return ExamCap(self.ledger).holds_slot(
            hotkey=hotkey,
            challenge_id=self.challenge_id,
            challenge_version=self.challenge_version,
            exam_key=provider.evaluation_pack_digest,
            submission_id=submission_id,
        )

    @contextlib.contextmanager
    def _coldkey_place(self, hotkey, task_id):
        """One waiting submission per coldkey (`coldkey_waiting`), or per hotkey when the row says ``"per": "hotkey"``,
        when the receiver installed the guard and the version registers a limit: refuse now, before any intent or build,
        if this hotkey's coldkey (or the hotkey itself) already has that many submissions waiting; otherwise hold the
        guard's lock FOR THAT COLDKEY (or hotkey) until the body (the task's start) is done, so two submissions of it can
        never both pass. Off (no guard,
        no limit): nothing is checked or held.
        """
        from carbon.challenge_validator import coldkey_waiting

        guard = getattr(self, "coldkey_waiting", None)
        rule = (
            None
            if guard is None
            else coldkey_waiting.rule_for(self.challenge_id, self.challenge_version)
        )
        if rule is None:
            yield
            return
        limit, per = rule
        # this coldkey's (or hotkey's) lock only, never one for the whole door (LOCK + CACHE AUDIT #14)
        with guard.lock_for(guard.key_of(hotkey, per)):
            refused = guard.refusal(
                hotkey=hotkey, task_id=task_id, limit=limit, per=per
            )
            if refused is not None:
                code, message = refused
                raise Unavailable(code, retry={"message": message})
            yield

    def _refuse_spent_round(self, submission, task_id, provider):
        """One graded exam per Challenge per round: a hotkey whose graded exam already holds this
        epoch's slot (or whose day's allowance is used) is told so now, before any build, in plain
        words with the next round's block and time. Read-only: no slot, no row, no grade, no
        allowance used (`ExamCap.admission_refusal`); `reserve` still decides at grading time.
        """
        if provider.evaluation_pack_digest is None:
            return
        from carbon.challenge_validator.exam_cap import ExamCap

        receipt = submission.receipt if type(submission.receipt) is dict else {}
        refusal = ExamCap(
            self.ledger, cadence=getattr(self, "exam_cadence", None)
        ).admission_refusal(
            hotkey=submission.hotkey,
            challenge_id=self.challenge_id,
            challenge_version=self.challenge_version,
            exam_key=provider.evaluation_pack_digest,
            submission_id=task_id,
            block=receipt.get("block"),
            pending_blocks=lambda: self._pending_group_blocks(
                submission.hotkey, task_id, receipt.get("block")
            ),
        )
        if refusal is not None:
            raise Unavailable(
                refusal["code"],
                retry={k: v for k, v in refusal.items() if k != "code"},
            )

    def _pending_group_blocks(self, hotkey, task_id, block):
        """The receipt blocks of the ``hotkey``'s allowance group's EARLIER accepted submissions to this door (a receipt
        block before ``block``, in its daily window) that hold no exam slot yet, are not a re-queued grade, and are QUEUED
        or RUNNING (A20, Lead 16 Nov 2026), for the admission check (`ExamCap.admission_refusal`): each will take a slot
        of that window when graded. Read-only and best effort: the group's hotkeys first, then only their receipts; a
        provider read only for the group's own unslotted ones inside the window; anything unreadable is left out (never a
        refusal from a guess). A built task waiting for its grade (SUCCEEDED) is not counted (its state cannot tell a
        later refusal apart): the check errs toward admitting."""
        from carbon.challenge_validator import exam_cap
        from carbon.research import (
            DirectGetTaskRequestV3,
            DirectTaskStateV3,
            ResearchTaskId,
        )

        if type(block) is not int:
            return ()
        try:
            group = exam_cap.group_of(hotkey)
        except exam_cap.ExamCapRefused:
            return ()
        low = exam_cap.epoch_of(block) - exam_cap.DAY_EPOCHS
        # LOCK + CACHE AUDIT #2b (19 Nov 2026): the group's hotkeys from the latest snapshot's members (`_group_mates`,
        # built once per snapshot and funder map), never `group_of` over every hotkey this door ever saw, and the rows
        # on a read snapshot, never the ledger's write lock
        read = getattr(self.ledger, "_read", None)
        with read() if callable(read) else self.ledger._db() as db:
            mine = _group_mates(self, hotkey, group)
            if mine is None:
                # a grouping with no snapshot window (a test double, or none installed): every hotkey's group, as before
                hotkeys = [
                    row[0]
                    for row in db.execute(
                        "SELECT DISTINCT hotkey FROM attempts WHERE kind='OUTCOME' "
                        "AND contract_digest=? AND hotkey IS NOT NULL",
                        (self.contract_digest,),
                    ).fetchall()
                ]
                mine = []
                for owner in hotkeys:
                    try:
                        if owner == hotkey or exam_cap.group_of(owner) == group:
                            mine.append(owner)
                    except exam_cap.ExamCapRefused:
                        continue
            if not mine:
                return ()
            marks = ",".join("?" * len(mine))
            rows = db.execute(
                "SELECT submission_id, hotkey, receipt FROM attempts WHERE kind='OUTCOME' "
                f"AND contract_digest=? AND submission_id IS NOT NULL AND hotkey IN ({marks}) "
                "AND submission_id NOT IN (SELECT submission_id FROM exam_graded WHERE kind='GRADED') "
                "AND submission_id NOT IN (SELECT submission_id FROM exam_requeues) "
                "ORDER BY seq",
                (self.contract_digest, *mine),
            ).fetchall()
        first = {}
        for other, owner, raw in rows:
            if other not in first:
                first[other] = (owner, raw)
        # Live 116, 19 Nov 2026 (no construction-submit completed for an hour: this check runs under the intake's one
        # admission lock and opened every group-mate's provider, lazily RESTORING each, and waited on each mate's own
        # lock while its build ran): a task a LAZY owner holds is terminal by definition (`OwnerProviders.lazy_tasks`),
        # so never pending here; an OPEN mate's task is read from its view without its lock (as `_building_views`
        # reads). Same blocks as before; a task with no such view (a mate neither open nor lazy, or an open mate's
        # view that does not hold it) is read as before.
        provider_for = getattr(self, "provider_for", None)
        # the group's lazy owners' tasks only (never every lazy owner's: LOCK + CACHE AUDIT #2b)
        lazy_of = getattr(provider_for, "lazy_tasks_of", None)
        lazy_tasks = getattr(provider_for, "lazy_tasks", None)
        try:
            if callable(lazy_of):
                lazy = frozenset(lazy_of({owner for owner, _raw in first.values()}))
            else:
                lazy = frozenset(lazy_tasks()) if callable(lazy_tasks) else frozenset()
        except Exception:  # noqa: BLE001 - unreadable: every mate read as before
            lazy = frozenset()
        opened = getattr(provider_for, "_providers", None)
        opened = opened if type(opened) is dict else {}
        challenge_key = self.discovery.info.challenge_key
        blocks = []
        for other, (owner, raw) in first.items():
            if other == task_id:
                continue
            try:
                other_block = json.loads(raw).get("block") if raw else None
                if (
                    type(other_block) is not int
                    or other_block >= block
                    or exam_cap.epoch_of(other_block) <= low
                ):
                    continue
                if other in lazy:
                    continue  # a lazy owner's task: terminal, never pending, never opened
                views = getattr(opened.get(owner), "_views", None)
                view = views.get(other) if type(views) is dict else None
                if view is not None:
                    # read from the open view (no owner lock); a view it does not hold falls through to the old read
                    # (V2: this block is the probing bound, so nothing unread is ever skipped)
                    if getattr(
                        view, "challenge_key", None
                    ) == challenge_key and getattr(view, "state", None) in (
                        DirectTaskStateV3.QUEUED,
                        DirectTaskStateV3.RUNNING,
                    ):
                        blocks.append(other_block)
                    continue
                task = (
                    self._provider(owner)
                    .get_research_result(
                        DirectGetTaskRequestV3(
                            self.discovery.info.challenge_key, ResearchTaskId(other)
                        )
                    )
                    .task
                )
            except Exception:  # noqa: BLE001, S112 - unreadable: left out
                continue
            if task.state in (DirectTaskStateV3.QUEUED, DirectTaskStateV3.RUNNING):
                blocks.append(other_block)
        return tuple(blocks)

    def _ended_on_infra(self, hotkey, task_id, provider):
        """Whether this task exists and ended on Carbon's infrastructure: its
        task state, or its grading released as FAILED_INFRA. Anything else
        (absent, running, reconstructed, the candidate's own failure) is not."""
        from carbon.research import DirectGetTaskRequestV3, DirectTaskStateV3
        from carbon.research.errors import ResearchServiceErrorCode
        from carbon.research.lifecycle import ResearchTaskProviderError

        try:
            task = provider.get_research_result(
                DirectGetTaskRequestV3(self.discovery.info.challenge_key, task_id)
            ).task
        except ResearchTaskProviderError as missing:
            if missing.code is ResearchServiceErrorCode.TASK_NOT_FOUND:
                return False
            raise
        if task.state in (
            DirectTaskStateV3.FAILED_INFRA,
            DirectTaskStateV3.UNRESOLVED,
            # A miner's own withdrawal (`withdraw`) is CANCELLED too: the same recipe submitted again is the next
            # generation, so each withdraw uses one of the MAX_INFRA_RERUNS generations of a recipe on a pack.
            DirectTaskStateV3.CANCELLED,
        ):
            return True
        if provider.evaluation_pack_digest is None:
            return False
        from carbon.challenge_validator.exam_cap import ExamCap

        return ExamCap(self.ledger).released_on_infra(
            hotkey=hotkey,
            challenge_id=self.challenge_id,
            challenge_version=self.challenge_version,
            exam_key=provider.evaluation_pack_digest,
            submission_id=task_id.value,
        )

    def _project(self, task, provider):
        from carbon.research import DirectTaskStateV3

        state = task.state
        outcome = {
            "schema": OUTCOME_SCHEMA,
            "submission_id": task.task_id.value,
            "challenge": {"id": self.challenge_id, "version": self.challenge_version},
            "state": "ADMITTED",
            "evidence": self._evidence_label,
            "qualification": False,
            "reward": False,
            "task_id": task.task_id.value,
        }
        if state is DirectTaskStateV3.SUCCEEDED:
            evidence = provider.public_result(task)
            if (
                type(evidence) is not dict
                or evidence.get("official_eligible") is not False
                or evidence.get("predictions_digest")
                != task.terminal_receipt.predictions_digest
            ):
                raise RuntimeError("direct task success evidence differs")
            outcome["state"] = "RECONSTRUCTED"
            outcome["state_digest"] = task.terminal_receipt.state_digest
            outcome["predictions_digest"] = evidence["predictions_digest"]
        elif state is DirectTaskStateV3.REFUSED:
            outcome["state"] = "RECONSTRUCTION_FAILED"
            outcome["failure"] = {"code": task.terminal_receipt.refusal_code}
        elif state in (
            DirectTaskStateV3.FAILED_INFRA,
            DirectTaskStateV3.UNRESOLVED,
            DirectTaskStateV3.CANCELLED,
        ):
            outcome["state"] = "FAILED_INFRA"
            outcome["failure"] = {
                "code": (
                    task.terminal_receipt.refusal_code
                    if state is DirectTaskStateV3.UNRESOLVED
                    and task.terminal_receipt.refusal_code is not None
                    else (
                        # the miner's own withdrawal: its own code, so a kit never resubmits it as a stop's cancellation
                        WITHDRAWN_CODE
                        if state is DirectTaskStateV3.CANCELLED
                        and _withdrawn_cancellation(provider, task.task_id.value)
                        else "direct_task_" + state.value.lower()
                    )
                )
            }
            if state is DirectTaskStateV3.FAILED_INFRA:
                advisory = provider.public_result(task)
                if advisory is not None:
                    outcome["failure"]["issues"] = [
                        {
                            "reason_code": advisory["reason_code"],
                            "failed_stage": advisory["failed_stage"],
                            "diagnostic_provenance": advisory["diagnostic_provenance"],
                            "reported_operation": advisory["reported_operation"],
                            "next_step": advisory["next_step"],
                        }
                    ]
        return outcome

    def failure_class(self, submission_id):
        """The closed failure class (`infra_diagnosis.classify`) of ``submission_id``'s FAILED_INFRA / UNRESOLVED task
        from its retained diagnosis, or None (no diagnosis, another state, unreadable).
        """
        from carbon.research import ResearchTaskId

        owner = self.owner(submission_id)
        if owner is None:
            return None
        return _failure_class(self._provider(owner), ResearchTaskId(submission_id))

    @contextlib.contextmanager
    def deriving(self, task_value, host_owner):
        """Hold a validator-derived task's host owner for the span of one evidence-only retention, so the retention
        helpers that ask `owner` find it. Nothing else does: it is not a ledger intent (the advance pass never sees
        it), not persisted, and gone when the block ends."""
        if task_value in self._derived_owners:
            raise RuntimeError("derived task already held")
        self._derived_owners[task_value] = host_owner
        try:
            yield
        finally:
            self._derived_owners.pop(task_value, None)

    def owner(self, submission_id):
        # (an adapter built without __init__, as several tests do, holds no derived task)
        derived = getattr(self, "_derived_owners", {}).get(submission_id)
        if derived is not None:
            return derived
        owner = self.ledger.owned_outcome(self.contract_digest, submission_id)
        if owner is None:
            return None
        from carbon.development_session.construction_recipe import ConstructionRecipe

        provider = self._provider(owner)
        retained = provider._requests.get(submission_id)
        if retained is None:
            return None
        recipe = ConstructionRecipe.from_dict(retained.recipe)
        expected = next(
            (
                request
                for request in (
                    self._request(
                        owner,
                        recipe,
                        evaluation_pack_digest=provider.evaluation_pack_digest,
                        rerun=rerun,
                    )
                    for rerun in range(MAX_INFRA_RERUNS + 1)
                )
                if request == retained
            ),
            None,
        )
        if (
            expected is None
            or provider._task_id(expected).value != submission_id
            or (submission_id in provider._measured_tasks) != self._measure_query
        ):
            return None
        return owner

    def outcome(self, submission_id):
        from carbon.research import DirectGetTaskRequestV3, ResearchTaskId

        owner = self.owner(submission_id)
        if owner is None:
            raise LookupError("unknown_submission")
        provider = self._provider(owner)
        task = provider.get_research_result(
            DirectGetTaskRequestV3(
                self.discovery.info.challenge_key, ResearchTaskId(submission_id)
            )
        ).task
        return self._project(task, provider)

    def failed_child(self, submission_id):
        """``(phase, observation)`` of this task's child that failed on the candidate's own account (FAILED_MINER,
        `research_carrier._settle_miner_failure`): phase ``build`` or ``inference``, and the result's closed
        observation; ``(None, None)`` when none did. Read from the owner's ledger; no measured value leaves here.
        """
        from carbon.development_session.bundle_construction_worker import (
            direct_child_identity,
        )

        owner = self.owner(submission_id)
        if owner is None:
            return None, None
        provider = self._provider(owner)
        with provider.ledger.db() as db:
            for phase in ("build", "inference"):
                row = db.execute(
                    "SELECT state, result FROM operations WHERE id=? AND owner=?",
                    (direct_child_identity(submission_id, phase), owner),
                ).fetchone()
                if row is None or row[0] != "FAILED_MINER":
                    continue
                try:
                    result = json.loads(row[1])
                except (TypeError, ValueError):
                    result = None
                observation = (
                    result.get("observation") if type(result) is dict else None
                )
                return phase, observation if type(observation) is str else None
        return None, None

    #: The marker code of a task a receiver stop cancelled (`cancelled_markers`, 14 Nov 2026).
    STOP_CANCELLED_CODE = "cancelled_by_carbon_stop"

    def _stop_cancelled(self, task_id):
        """Whether ``task_id`` carries the terminal marker of a task a receiver STOP cancelled (state FAILED, code
        ``cancelled_by_carbon_stop``, in the door's auto-grade marker directory), read only.
        """
        path = getattr(self.ledger, "path", None)
        if path is None or re.fullmatch(r"rtsk_[0-9a-f]{64}", str(task_id)) is None:
            return False
        marker = Path(path).parent / "auto-grade" / "markers" / (task_id + ".json")
        try:
            body = json.loads(marker.read_bytes())
        except (OSError, ValueError):
            return False
        return (
            type(body) is dict
            and body.get("state") == "FAILED"
            and body.get("code") == self.STOP_CANCELLED_CODE
        )

    def _give_back_queue_place(self, earlier_generations, new_task, hotkey):
        """Owner ruling 14 Nov 2026 ("give them their queue place"): a resubmission of the identical recipe of a task a receiver
        stop cancelled (its terminal marker is ``cancelled_by_carbon_stop``) takes that task's ORIGINAL arrival place in the
        queue, once per cancelled task and only for the same hotkey (`AttemptLedger.grant_queue_place`). Only the
        resubmission that arrives AFTER this runs; a queue already formed is never re-ordered. An unmarked earlier generation
        (a miner's own cancel, an infrastructure failure) changes nothing. Never fails the submission: the place is an
        ordering courtesy, and any error leaves the task at the back as before."""
        if not earlier_generations or not hasattr(self.ledger, "grant_queue_place"):
            return
        try:
            for earlier in earlier_generations:
                if not self._stop_cancelled(earlier):
                    continue
                result = self.ledger.grant_queue_place(
                    self.contract_digest,
                    from_task=earlier,
                    new_task=new_task,
                    hotkey=hotkey,
                )
                from carbon.challenge_validator.koth_journal import note

                note(
                    "queue_place_" + result,
                    from_task=earlier,
                    new_task=new_task,
                )
                if result in ("granted", "already_granted"):
                    return
        except Exception:  # noqa: BLE001 - never fails a submission
            return

    def _ended_unbuilt(self):
        """The task ids whose build ENDED without success (REFUSED / UNRESOLVED / FAILED_INFRA / CANCELLED), read from the
        open providers' views and the lazy owners' index (`OwnerProviders.lazy_index`), never opening an owner: they
        never get a grade marker and never need a queue place. A task in neither is not listed (looked at as before).
        """
        from carbon.research import DirectTaskStateV3

        ended = {
            DirectTaskStateV3.REFUSED,
            DirectTaskStateV3.UNRESOLVED,
            DirectTaskStateV3.FAILED_INFRA,
            DirectTaskStateV3.CANCELLED,
        }
        names = {state.value for state in ended}
        provider_for = getattr(self, "provider_for", None)
        found = set()
        opened = getattr(provider_for, "_providers", None)
        if type(opened) is dict:
            for provider in tuple(opened.values()):
                views = getattr(provider, "_views", None)
                if type(views) is not dict:
                    continue
                for task, view in tuple(views.items()):
                    if getattr(view, "state", None) in ended:
                        found.add(task)
        lazy = getattr(provider_for, "lazy_index", None)
        if callable(lazy):
            try:
                entries = lazy()
            except Exception:  # noqa: BLE001 - unreadable: looked at as before
                entries = {}
            for task, entry in entries.items():
                if type(entry) in (tuple, list) and entry and entry[0] in names:
                    found.add(task)
        return found

    def settle_stop_cancelled_places(self):
        """The one-shot for miners who ALREADY resubmitted (owner ruling 14 Nov 2026, the Lead's): for every task whose terminal
        marker is ``cancelled_by_carbon_stop``, find its resubmission (the next generation of the same owner, recipe and
        pack: the SAME deterministic task identity `evaluate` and `owner` derive) and, if that resubmission is not yet
        settled (it carries no marker of its own), give it the cancelled task's original arrival place
        (`AttemptLedger.grant_queue_place`: once per cancelled task, same hotkey by construction since the owner is part of
        the identity). Idempotent: a task that already gave its place, or has no resubmission yet, changes nothing; the
        resubmissions that arrive later are handled at their own `evaluate`. Read-only on markers; the only write is the
        ledger's grant row. Returns the number of marked tasks it could not look at yet (their owner's registration was
        unavailable); the caller asks again until it is 0. Never raises for one task: that task is left for the next call.
        """
        path = getattr(self.ledger, "path", None)
        if path is None or not hasattr(self.ledger, "grant_queue_place"):
            return 0
        directory = Path(path).parent / "auto-grade" / "markers"
        try:
            marked = sorted(
                entry.stem
                for entry in directory.glob("rtsk_*.json")
                if self._stop_cancelled(entry.stem)
            )
        except OSError:
            return 0
        from carbon.development_session.construction_recipe import ConstructionRecipe

        # Live 116, 19 Nov 2026 07:47-08:0xZ: this opened EVERY marked task's owner (a lazy owner's full restore, the
        # public TRAIN derived again) in the incumbent's steps after each start, ~350 owners one after another, and no
        # grade was claimed meanwhile. Two ledger reads now skip what can need no place, before any owner is opened:
        # a task that already gave its place (granted once per task), and an owner with no submitted task still
        # waiting (no marker): a resubmission is the same owner's later submitted, unmarked task, so none can exist.
        try:
            given = self.ledger.queue_place_from_tasks(self.contract_digest)
            with os.scandir(directory) as entries:
                settled = {
                    entry.name[: -len(".json")]
                    for entry in entries
                    if entry.name.endswith(".json")
                }
            # unmarked is not waiting: a build that ended REFUSED / FAILED / CANCELLED never gets a marker (live 116,
            # 19 Nov 2026 11:2xZ: this still opened 66+ lazy owners one by one); such a task is known from the open
            # views and the lazy owners' index without opening any owner
            dead = self._ended_unbuilt()
            waiting = {
                self.ledger.owned_outcome(self.contract_digest, other)
                for other in self.ledger.submitted_outcomes(self.contract_digest)
                if other not in settled and other not in dead
            }
        except (AttributeError, OSError, sqlite3.Error):
            given, waiting = set(), None  # unreadable: look at every task, as before
        unresolved, left = 0, []
        for task in marked:
            if task in given:
                continue
            try:
                owner = self.ledger.owned_outcome(self.contract_digest, task)
                if owner is None:
                    continue
                if waiting is not None and owner not in waiting:
                    continue  # nothing of this owner waits: no resubmission to place, no owner opened
                provider = self._provider(owner)
                retained = provider._requests.get(task)
                if retained is None:
                    continue
                recipe = ConstructionRecipe.from_dict(retained.recipe)
                chain = [
                    provider._task_id(
                        self._request(
                            owner,
                            recipe,
                            evaluation_pack_digest=provider.evaluation_pack_digest,
                            rerun=rerun,
                        )
                    ).value
                    for rerun in range(MAX_INFRA_RERUNS + 1)
                ]
                if task not in chain:
                    continue
                for successor in chain[chain.index(task) + 1 :]:
                    if (
                        self.ledger.owned_outcome(self.contract_digest, successor)
                        != owner
                    ):
                        continue  # never submitted
                    if (directory / (successor + ".json")).exists():
                        continue  # settled (a later stop's marker, a grade, a failure): needs no place
                    result = self.ledger.grant_queue_place(
                        self.contract_digest,
                        from_task=task,
                        new_task=successor,
                        hotkey=owner,
                    )
                    from carbon.challenge_validator.koth_journal import note

                    note("queue_place_" + result, from_task=task, new_task=successor)
                    break
            except Exception:  # noqa: BLE001 - asked again next call
                unresolved += 1
                left.append(task)
        self.queue_places_unresolved = tuple(
            left
        )  # for the caller's give-up journal line
        return unresolved

    def _active_owner(self, submission_id):
        try:
            return self.owner(submission_id)
        except Unavailable as unavailable:
            if unavailable.code not in _SKIPPED_OWNER_CODES:
                raise
            # Retained cleanup custody is not fresh dispatch authority; an owner set aside at this start is skipped,
            # never the end of the whole pass (live 116, 18 Nov 2026: every advance pass died at its first task)
            return None

    def advance(self):
        self._apply_rebuild_requests()
        moved = 0
        # A19 (Lead, 16 Nov 2026): a door with N lanes runs N advance rounds at once; each takes the first queued task
        # whose owner no other round holds (`grade_sequencer.OwnerClaims`: one owner's ledger lease is non-blocking).
        claims = getattr(self, "owner_claims", None)
        not_queued = self._not_queued_views()
        for submission_id in self.ledger.submitted_outcomes(self.contract_digest):
            if submission_id in not_queued:
                continue
            owner = self._active_owner(submission_id)
            if owner is None:
                continue
            if self._grade_first_holds(owner):
                # grade first (Lead + owner, 18 Nov 2026): a build holds its owner for its whole run, and a grade of that
                # owner (and every later grade of its commit group) waits for it; so a NEW build never takes an owner
                # whose built task waits to grade. The grade takes it; this build comes after.
                continue
            if claims is not None and not claims.try_claim(owner):
                continue
            try:
                outcome = self._advance_one(owner, submission_id)
            finally:
                if claims is not None:
                    claims.release(owner)
            if outcome is None:
                continue
            moved += outcome
            # One operator pass dispatches at most one construction. The
            # existing carrier enforces its per-child resource limits;
            # this adapter never fans out a backlog on one call.
            break
        return moved

    #: V2 (18 Nov 2026): grade first holds an owner's next build at most this long (its built task may not be
    #: claimable: a crown hold, a copy wait), then the build goes on.
    GRADE_FIRST_MAX_SECONDS = 600

    def _grade_first_holds(self, owner):
        """Whether grade first holds ``owner``'s next build now (`_built_waits_to_grade`), bounded per owner by
        `GRADE_FIRST_MAX_SECONDS` of the time the owner is FREE with its built task unclaimed; the bound resets once
        nothing of the owner waits, and while another round holds the owner (live 116, 19 Nov 2026 05:1xZ: the bound ran
        through each owner's long build, so the moment the build ended the owner's NEXT build took it again, and 31
        built tasks waited with every grade lane idle, ``owner_busy``).
        """
        import time

        since = self.__dict__.setdefault("_grade_first_since", {})
        if not self._built_waits_to_grade(owner):
            since.pop(owner, None)
            return False
        claims = getattr(self, "owner_claims", None)
        if claims is not None and owner in claims.held():
            # another round holds it (its build, or a grade): no grade could take it, so no grade-first time is spent
            since.pop(owner, None)
            return True
        now = time.monotonic()
        first = since.setdefault(owner, now)
        return now - first < self.GRADE_FIRST_MAX_SECONDS

    def _built_waits_to_grade(self, owner):
        """Whether ``owner``'s open provider holds a SUCCEEDED (built) task with no grade marker yet (`grade_marked`, set
        by the door's grader). False without that hook, or without an open provider for ``owner`` (unchanged).
        """
        marked = getattr(self, "grade_marked", None)
        opened = getattr(getattr(self, "provider_for", None), "_providers", None)
        if marked is None or type(opened) is not dict:
            return False
        views = getattr(opened.get(owner), "_views", None)
        if type(views) is not dict:
            return False
        from carbon.research import DirectTaskStateV3

        try:
            return any(
                getattr(view, "state", None) is DirectTaskStateV3.SUCCEEDED
                and not marked(task)
                for task, view in tuple(views.items())
            )
        except Exception:  # noqa: BLE001 - a hint for build order, never a failure
            return False

    def _not_queued_views(self):
        """The task ids the door's already-open providers hold in a state other than QUEUED: nothing for `advance` to
        start, so a pass skips them before the owner check and the read (`get_research_result` verifies a SUCCEEDED
        task's evidence from disk; `owner` reads the ledger and hashes every served source, `_source_identity`). Live
        116, 18 Nov 2026: the first pass after every restart did that for every finished task the door ever took (~84
        GB read, ~25 min before the first build), its ledger reads queued with every grade's. The views are the ones
        `get_research_result` returns, read with no
        ledger access; a task not here (no open provider, no view) is read as before.
        """
        from carbon.research import DirectTaskStateV3

        opened = getattr(getattr(self, "provider_for", None), "_providers", None)
        if type(opened) is not dict:
            return frozenset()
        skipped = set()
        for provider in tuple(opened.values()):
            views = getattr(provider, "_views", None)
            if type(views) is not dict:
                continue
            resumable = getattr(provider, "_resumable", ())
            for task, view in tuple(views.items()):
                if getattr(view, "state", None) is not DirectTaskStateV3.QUEUED and (
                    # a task a start left RUNNING to resume (its remote build ran on): taken at its place
                    task
                    not in resumable
                ):
                    skipped.add(task)
        # a lazy owner's tasks (not opened yet, every one terminal: `OwnerProviders.restore`) are never QUEUED either
        lazy = getattr(self.provider_for, "lazy_tasks", None)
        if callable(lazy):
            skipped |= lazy()
        return frozenset(skipped)

    #: A19: this adapter's advance takes owners through `owner_claims`, so a door may run one advance round per lane.
    PARALLEL_ADVANCE = True

    def _advance_one(self, owner, submission_id):
        """Start ``submission_id`` if it is QUEUED: 1 (started and run), or None (nothing to do for it now)."""
        from carbon.research import (
            DirectGetTaskRequestV3,
            DirectTaskStateV3,
            ResearchTaskId,
        )
        from carbon.research.errors import ResearchServiceErrorCode
        from carbon.research.lifecycle import ResearchTaskProviderError

        provider = self._provider(owner)
        task_id = ResearchTaskId(submission_id)
        try:
            task = provider.get_research_result(
                DirectGetTaskRequestV3(self.discovery.info.challenge_key, task_id)
            ).task
        except ResearchTaskProviderError as missing:
            if missing.code is ResearchServiceErrorCode.TASK_NOT_FOUND:
                # An intent can precede a refused or interrupted start.
                # The owner may retry the same signed recipe idempotently.
                return None
            raise
        if task.state is DirectTaskStateV3.QUEUED:
            # a build starts here: the served sources are checked before it runs (V2, 18 Nov)
            self.check_served_source()
            try:
                with _build_wall_guard(getattr(self, "owner_claims", None)):
                    provider.run_queued_task(task_id)
            except ResearchTaskProviderError as refused:
                if (
                    refused.code is ResearchServiceErrorCode.INVALID_TASK_TRANSITION
                    and self._withdrawn_now(provider, submission_id)
                ):
                    # its owner withdrew it between this read and the start (`withdraw`): never a worker failure
                    return None
                raise
            finally:
                # G-LEAD-10 row 1: a build its own program failed uses the daily spot (never raises)
                self._file_recipe_spot(owner, task_id, provider)
                # Order 3: a build that ended on Carbon's infrastructure is queued again once, at its place
                self._requeue_failed_build(owner, task_id, provider)
            return 1
        resumable = getattr(provider, "resumable", None)
        if (
            task.state is DirectTaskStateV3.RUNNING
            and callable(resumable)
            and resumable(task_id)
        ):
            # a task a start left RUNNING (owner, 20 Nov 2026: a restart never cancels an in-flight build): resumed at
            # its place, its remote build adopted (`resume_task`); one that ends on Carbon's side re-runs as any build
            self.check_served_source()
            try:
                with _build_wall_guard(getattr(self, "owner_claims", None)):
                    provider.resume_task(task_id)
            finally:
                self._file_recipe_spot(owner, task_id, provider)
                self._requeue_failed_build(owner, task_id, provider)
            return 1
        return None

    def _apply_rebuild_requests(self):
        """The operator's build re-arm (`infra_requeue rebuild`, on Validator-2's receipt): each request line not yet
        applied is applied ONCE through `_requeue_failed_build` in operator mode (a FAILED_INFRA build, or one refused
        only for the CPU worker wall, re-run as its next generation even when it was itself the door's requeue). Fresh
        task id, fresh ops: no settled op is ever cleared. The outcome (the new task, or None) is logged beside the request.
        Never raises: the advance round goes on."""
        # one applier at a time (live 116, 18 Nov 2026: every concurrent advance round walked the list from a done-set read
        # before any other round wrote, so each request was tried up to ~23 times): a round that finds it held skips
        if not _REBUILD_APPLY.acquire(blocking=False):
            return
        try:
            self._apply_rebuild_requests_locked()
        finally:
            _REBUILD_APPLY.release()

    def _apply_rebuild_requests_locked(self):
        try:
            directory = Path(self.ledger.path).parent / "auto-grade" / "requeued"
            requests = _jsonl(directory / REBUILD_REQUESTS) + [
                {"task": line.get("task"), "ruling": STOP_CANCEL_RULING}
                for line in _jsonl(directory / STOP_CANCELLED)
            ]
            if not requests:
                return
            # once per task AND ruling: an operator's request under its own ruling is applied even after the door's
            # own stop-cancel re-run of the task was refused (live 116, 20 Nov 2026: rtsk_9d6de7ea, owed, unreachable)
            done = {
                (line.get("task"), line.get("ruling"))
                for line in _jsonl(directory / REBUILD_APPLIED)
            }
            from carbon.research import ResearchTaskId

            for line in requests:
                task, ruling = line.get("task"), line.get("ruling")
                if (
                    (task, ruling) in done
                    or type(task) is not str
                    or type(ruling) is not str
                ):
                    continue
                done.add((task, ruling))
                new_task, code = None, None
                try:
                    owner = self._active_owner(task)
                    if owner is None:
                        code = "owner_unavailable"
                    else:
                        new_task = self._requeue_failed_build(
                            owner,
                            ResearchTaskId(task),
                            self._provider(owner),
                            operator=ruling,
                        )
                        code = None if new_task else "not_rebuilt"
                except Exception as failure:  # noqa: BLE001 - one request only
                    code = type(failure).__name__
                with open(directory / REBUILD_APPLIED, "a", encoding="utf-8") as log:
                    log.write(
                        json.dumps(
                            {
                                "task": task,
                                "ruling": ruling,
                                "new_task": new_task,
                                "code": code,
                                "at_ns": time.time_ns(),
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
        except Exception:  # noqa: BLE001, S110 - never fails the round
            pass

    def _file_recipe_spot(self, owner, task_id, provider):
        """G-LEAD-10 row 1 (owner 20 Nov 2026, RECIPE CRASHED: spot USED, typed reason, no rebuild; V2 part (1) spec
        13:11Z): right after a build run ends at this door, file ONE daily-spot use (`ExamCap.file_build_spent`) when
        the build ended on the candidate's OWN structured failure, and only then (`recipe_spot_code`). Prospective (a
        build that ended before this code runs is never filed), idempotent, and it never raises: anything unreadable or
        unproven files nothing (the spot stays the miner's). Returns the filed code or None.
        """
        try:
            from carbon.research import DirectGetTaskRequestV3

            task = provider.get_research_result(
                DirectGetTaskRequestV3(self.discovery.info.challenge_key, task_id)
            ).task
            code = recipe_spot_code(provider, owner, task_id.value, task)
            if code is None:
                return None
            from carbon.challenge_validator.exam_cap import (
                ExamCap,
                submission_block,
            )

            block = submission_block(self.ledger, self.contract_digest, task_id.value)
            if block is None:
                return None
            filed = ExamCap(self.ledger).file_build_spent(
                hotkey=owner,
                challenge_id=self.challenge_id,
                challenge_version=self.challenge_version,
                submission_id=task_id.value,
                block=block,
                code=code,
            )
            if filed:
                from carbon.challenge_validator.koth_journal import note

                note("build_spot_used", task=task_id.value, code=code)
            return code
        except Exception:  # noqa: BLE001 - never stops a build round; nothing filed
            return None

    def _requeue_failed_build(self, owner, task_id, provider, *, operator=None):
        """Order 3 (Lead 17 Nov 2026, handoff s3 item 5): a build whose task ended on Carbon's side (FAILED_INFRA, or
        UNRESOLVED: owner via the Lead and V2, 18 Nov 2026, "our failures re-run automatically, miners never resubmit"; an
        UNRESOLVED build is Carbon's, invariant 7) is started again as its next generation (`_request` ``rerun`` + 1: the
        same task its miner's resubmit would make), at the failed task's ORIGINAL queue place and epoch
        (`AttemptLedger.requeue_failed_build`), and its grade neither spends nor is refused by the miner's round or day
        (`ExamCap.mark_requeued`, the operator requeue's bypass). Bounded by owner D16, as grades are: at most
        `BUILD_CODE_RETRIES` re-runs per failure code and `BUILD_CHAIN_RETRIES` in all within one task's chain (counted
        in `BUILD_RETRIES`); a spent cap writes ``build_retry_cap_spent`` to the owed-list feed (`BUILD_ALERTS`). A
        re-run of a re-run is allowed within the caps; never when the miner already resubmitted, never past
        `MAX_INFRA_RERUNS`. Never raises: anything unreadable leaves the task as today. Logged either way.
        """
        from carbon.challenge_validator.koth_journal import note

        # Grade-speed (18 Nov 2026): a task whose requeue was refused for good is never asked again in this process (27
        # tasks were re-read on every pass, each a lazy-owner touch)
        settled = self.__dict__.setdefault("_requeue_settled", set())
        # an operator's request (a V2 ruling, or the stop's own record) is applied once by its caller: never throttled
        if operator is None and task_id.value in settled:
            return None
        # and any task is asked at most once per `REQUEUE_ASK_SECONDS` (Lead: one attempt per id per N min)
        import time as _time

        asked = self.__dict__.setdefault("_requeue_asked", {})
        now = _time.monotonic()
        if (
            operator is None
            and now - asked.get(task_id.value, -REQUEUE_ASK_SECONDS)
            < REQUEUE_ASK_SECONDS
        ):
            return None
        asked[task_id.value] = now

        def refused(code):
            note("build_requeue_refused", task=task_id.value, code=code)
            if code not in _REQUEUE_RETRYABLE:
                settled.add(task_id.value)

        try:
            from carbon.research import DirectGetTaskRequestV3, DirectTaskStateV3

            task = provider.get_research_result(
                DirectGetTaskRequestV3(self.discovery.info.challenge_key, task_id)
            ).task
            stop_cancelled = (
                operator is not None
                and task.state is DirectTaskStateV3.CANCELLED
                and not _withdrawn_cancellation(provider, task_id.value)
            )
            if (
                task.state
                not in (
                    DirectTaskStateV3.FAILED_INFRA,
                    DirectTaskStateV3.UNRESOLVED,
                )
                and not stop_cancelled
                and not (
                    task.state is DirectTaskStateV3.REFUSED
                    and _cpu_wall_refusal(provider, owner, task_id.value)
                )
            ):
                # CARBON-CUT REQUEUE (V2, 18 Nov 2026): a build CANCELLED by the receiver's own stop (never a miner's
                # withdrawal) re-runs too, on an operator request or the stop's own record (`STOP_CANCELLED`)
                # 17 Nov (Lead; owner: "miners re-run automatically"): a build refused ONLY because its build-pipeline
                # inference hit the worker wall on the door's CPU worker is re-run like a FAILED_INFRA one
                return None
            if not hasattr(self.ledger, "requeue_failed_build"):
                return None
            retained = provider._requests.get(task_id.value)
            if retained is None:
                refused("no_request")
                return None
            recipe = self._retained_recipe(retained)
            requests = [
                self._request(
                    owner,
                    recipe,
                    evaluation_pack_digest=provider.evaluation_pack_digest,
                    rerun=rerun,
                )
                for rerun in range(MAX_INFRA_RERUNS + 1)
            ]
            rerun = next(
                (n for n, request in enumerate(requests) if request == retained), None
            )
            if rerun is None or rerun >= MAX_INFRA_RERUNS:
                refused("no_next_generation")
                return None
            request = requests[rerun + 1]
            new_task = provider._task_id(request).value
            # OWNER G-LEAD-10 (20 Nov 2026, "Go with the table"), replacing the 3x requeue + D16 cap for builds: a proven
            # Carbon-side failure is rebuilt ONCE, on a healthy box, unless its miner submitted since; an unknown one is
            # not (the miner resubmits when ready; its spot was never used); a recipe-side one is not. A receiver stop's
            # own cancellation keeps its earlier rule (CARBON-CUT REQUEUE).
            if stop_cancelled:
                failure_class = None
            elif task.state is DirectTaskStateV3.REFUSED:
                failure_class = "carbon_cpu_worker_wall"  # `_cpu_wall_refusal` above: the door's CPU worker
            else:
                failure_class = _failure_class(provider, task_id)
            code = failure_class or _build_failure_code(task)
            retries = Path(self.ledger.path).parent / "auto-grade" / "requeued"
            root, chain, same = _build_retry_counts(retries, task_id.value, code)
            # an operator's own rebuild request (an owed re-run under LO-1 (d)) is never refused by the automatic rule
            automatic = not stop_cancelled and operator is None
            by_class = _class_refusal(failure_class, chain) if automatic else None
            # the failure's own time (its terminal receipt); unknown: no skip (the rebuild runs)
            completed = getattr(
                getattr(task, "terminal_receipt", None), "completed_at_micros", None
            )
            chain_tasks = {
                line.get(key)
                for line in _jsonl(retries / BUILD_RETRIES)
                if line.get("chain_root") == root
                for key in ("from_task", "new_task")
            } | {task_id.value, root}
            if (
                by_class is None
                and automatic
                and type(completed) is int
                and completed > 0
                and hasattr(self.ledger, "submitted_since")
                and self.ledger.submitted_since(
                    self.contract_digest,
                    owner,
                    completed * 1000,
                    exclude=chain_tasks,
                )
            ):
                by_class = "miner_submitted_since"
            if by_class is not None:
                _append_line(
                    retries / BUILD_ALERTS,
                    {
                        "task": task_id.value,
                        "event": "build_not_rerun",
                        "reason": by_class,
                        "code": code,
                        "chain_root": root,
                        "chain_retries": chain,
                        "code_retries": same,
                        "at_ns": time.time_ns(),
                    },
                )
                refused(by_class)
                return None
            # an OWED re-run (an operator's request under a V2 ruling, never the stop's own cancellation) runs
            # outside the caps (V2-OWED-CAP-20261120: "one re-run ... uncharged, outside the cap")
            owed = operator is not None and operator != STOP_CANCEL_RULING
            if not owed and (
                chain >= BUILD_CHAIN_RETRIES or same >= BUILD_CODE_RETRIES
            ):
                _append_line(
                    retries / BUILD_ALERTS,
                    {
                        "task": task_id.value,
                        "event": "build_retry_cap_spent",
                        "reason": "owed_list",
                        "code": code,
                        "chain_root": root,
                        "chain_retries": chain,
                        "code_retries": same,
                        "at_ns": time.time_ns(),
                    },
                )
                note("build_requeue_refused", task=task_id.value, code="cap_spent")
                return None
            ask = {"from_task": task_id.value, "new_task": new_task, "hotkey": owner}
            # a re-run of the door's own re-run is allowed within the D16 caps above (V2, 18 Nov 2026)
            result = self.ledger.requeue_failed_build(
                self.contract_digest, apply=False, operator=True, **ask
            )
            if result != "requeuable":
                refused(result)
                return None
            from carbon.research import canonical_bytes

            # as a miner's resubmit does: its task intent, its catalog document, then the START. Only a started task gets
            # the place and the bypass: a start that fails leaves an intent only (as an interrupted resubmit does), and
            # the miner's own resubmit of the recipe still starts this same task
            self.ledger.record_recipe_task_intent(
                self.contract_digest,
                new_task,
                owner,
                "sha256:" + hashlib.sha256(canonical_bytes(request)).hexdigest(),
            )
            catalog = self.ledger.catalog_submission(
                self.contract_digest, task_id.value
            )
            if catalog is not None:
                self.ledger.record_catalog_submission(
                    self.contract_digest, new_task, catalog
                )
            # from the failed task's own retained source, never the live workspace (`start_research_task`)
            provider.start_research_task(
                request, measure_query=self._measure_query, rebuild_of=task_id.value
            )
            result = self.ledger.requeue_failed_build(
                self.contract_digest, operator=True, **ask
            )
            if result != "requeued":
                # the miner resubmitted it meanwhile: it runs as their resubmit, at the back, as today
                note("build_requeue_refused", task=task_id.value, code=result)
                return None
            from carbon.challenge_validator.exam_cap import ExamCap

            ExamCap(self.ledger).mark_requeued(new_task)
            _append_line(
                retries / BUILD_RETRIES,
                {
                    "from_task": task_id.value,
                    "new_task": new_task,
                    "chain_root": root,
                    "code": code,
                    "at_ns": time.time_ns(),
                    **({} if operator is None else {"ruling": operator}),
                    # a class rebuild runs on a healthy box (`rebuild_build_identities`)
                    **({} if stop_cancelled else {"healthy_box": True}),
                },
            )
            note(
                "build_requeued",
                task=task_id.value,
                new_task=new_task,
                **({} if operator is None else {"ruling": operator}),
            )
            return new_task
        except Exception as failure:  # noqa: BLE001 - never fails the build round
            note(
                "build_requeue_failed",
                task=getattr(task_id, "value", None),
                type=type(failure).__name__,
            )
            return None

    @staticmethod
    def _retained_recipe(retained):
        from carbon.development_session.construction_recipe import ConstructionRecipe

        return ConstructionRecipe.from_dict(retained.recipe)

    @staticmethod
    def _withdrawn_now(provider, submission_id):
        """Whether ``submission_id`` is CANCELLED by its owner's withdrawal in ``provider`` now (under its lock)."""
        from carbon.research import DirectTaskStateV3

        with provider._lock:
            view = provider._views.get(submission_id)
            return (
                view is not None
                and view.state is DirectTaskStateV3.CANCELLED
                and _withdrawn_cancellation(provider, submission_id)
            )

    def withdraw(self, hotkey, submission_id):
        """A miner withdraws its OWN queued, not-yet-building official submission (owner GO 15 Nov 2026 via the Lead).

        Returns `WITHDRAWN` (it was QUEUED and is now CANCELLED under the durable cancellation id `WITHDRAW_PREFIX` + its
        id), `ALREADY_WITHDRAWN` (the same withdrawal again: idempotent), `WITHDRAW_TOO_LATE` (building, cancel
        requested, built or ended in any other way: nothing is changed) or `WITHDRAW_UNKNOWN` (no such submission, or
        not this hotkey's: one answer for both, so nothing is said of another key's). The state check and the cancel
        are made under the provider's own lock, the lock its QUEUED -> RUNNING start takes, so a withdrawal and a start
        can never both happen: whichever takes the lock first wins, and the other sees the state it left.

        Nothing else is written here: no try is used and no allowance (a slot is reserved only when a grade starts,
        `exam_cap.ExamCap.reserve`). The door records the withdrawal and its terminal grade marker after this
        (`DirectRecipeIntake._withdraw`); the grade round repairs a missing marker (`AutoGrader._settle_withdrawn`).
        """
        from carbon.research import (
            DirectCancelTaskRequestV3,
            DirectTaskStateV3,
            ResearchTaskId,
        )

        if type(hotkey) is not str or type(submission_id) is not str:
            return WITHDRAW_UNKNOWN
        if self.ledger.owned_outcome(self.contract_digest, submission_id) != hotkey:
            return WITHDRAW_UNKNOWN
        try:
            owner = self.owner(submission_id)
        except Unavailable as unavailable:
            if unavailable.code == "direct_provider_binding_unavailable":
                return WITHDRAW_UNKNOWN  # no provider for that hotkey on this door
            raise
        if owner != hotkey:
            return WITHDRAW_UNKNOWN
        provider = self._provider(hotkey)
        with provider._lock:
            view = provider._views.get(submission_id)
            if view is None:
                return WITHDRAW_UNKNOWN
            if view.state is DirectTaskStateV3.CANCELLED and _withdrawn_cancellation(
                provider, submission_id
            ):
                return ALREADY_WITHDRAWN
            if view.state is not DirectTaskStateV3.QUEUED:
                return WITHDRAW_TOO_LATE
            ended = provider.cancel_research_task(
                DirectCancelTaskRequestV3(
                    self.discovery.info.challenge_key,
                    ResearchTaskId(submission_id),
                    WITHDRAW_PREFIX + submission_id,
                )
            ).task
            if ended.state is not DirectTaskStateV3.CANCELLED:
                raise RuntimeError("a queued task's withdrawal did not cancel it")
        return WITHDRAWN

    def withdrawn_by_miner(self, submission_id):
        """The owning hotkey when ``submission_id`` is CANCELLED by its owner's withdrawal (`withdraw`), else None: the grade
        round's repair of a withdrawal whose ledger row or marker was not written (`AutoGrader._settle_withdrawn`). A read
        of the owner's provider view only, through the door's own provider for that owner.
        """
        from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

        owner = self.ledger.owned_outcome(self.contract_digest, submission_id)
        if owner is None:
            return None
        provider = self.provider_for(owner)
        if (
            type(provider) is not DirectDevelopmentTasksV3
            or provider.owner != owner
            or provider.discovery is not self.discovery
        ):
            return None
        return owner if self._withdrawn_now(provider, submission_id) else None

    def score_record(self, submission_id):
        raise LookupError("score_pack_unbound")

    def sealed_roles(self):
        return frozenset()

    def _prepare_batch(self, role, *, kind, **options):
        raise Unavailable("development_fixture_has_no_exam")

    def reference_jobs(self, fingerprint):
        raise Unavailable("development_fixture_has_no_exam")

    def ingest_references(self, fingerprint, records):
        raise Unavailable("development_fixture_has_no_exam")

    def open_pool(self):
        raise Unavailable("development_fixture_has_no_exam")

    def status(self):
        return {
            "schema": "carbon.lean-recipe-adapter-status.v1",
            "contract_digest": self.contract_digest,
            "submissions": sum(
                self._active_owner(submission_id) is not None
                for submission_id in self.ledger.submitted_outcomes(
                    self.contract_digest
                )
            ),
            "score_pack": None,
            "qualification": False,
        }
