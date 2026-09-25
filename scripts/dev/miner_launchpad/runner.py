"""Loopback control adapter over Carbon's existing finite research runner.

Only the local operator - the miner, on their own machine - supplies
configuration and paths. Browser callers select an opaque profile. No
scientific loop, evaluator or consumption ledger lives here.

**Registration is the only admission gate (C-MLP-02-D11).** A launch reads the
chain for the miner's hotkey *before* anything durable is written, and admits
the campaign with the `RegisteredMiner` that read produced. There is no grant
anywhere on this path: the development grant is development machinery, and the
only form of it this module may hold is `RetainedGrant`, which proves ownership
of a campaign launched under one before the decision so it can still be cleaned
up, and structurally admits no new work.

A budget is the miner's to set, at launch, or not at all. Its absence blocks
nothing.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace

from carbon.development_session import research_guidance as guidance
from carbon.development_session.private_records import private_json
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_control import CampaignControl, DispatchStopped
from carbon.development_session.research_ledger import CampaignLedger
from scripts.dev.miner_launchpad.controller import Rejected, owner_lock

PROFILE_SCHEMA = "carbon.launchpad.runner-profile.v2"
RETIRED_PROFILE_SCHEMA = "carbon.launchpad.runner-profile.v1"

PATH_FIELDS = {
    "image_manifest",
    "analysis_image_manifest",
    "operator_config",
    "api_key_file",
    "miner_public",
    "miner_password_file",
    "quarantine_journal",
}
#: Paths a profile may add. `battery_validator` is the operator's battery
#: validator deployment (`carbon.battery.deployment`, the M3 daemon); without
#: it a battery submission is refused as evaluation_unavailable, never scored
#: another way.
OPTIONAL_PATH_FIELDS = {"battery_validator"}

PROFILE_FIELDS = {
    "schema",
    "profile_id",
    "principal",
    "enabled",
    "paths",
    "accepted_revision",
    "campaigns_root",
    "runtime",
}
OPTIONAL_PROFILE_FIELDS = {"research_guidance", "disabled_reason"}

# The runtime compositions this runner can actually assemble and dispatch.
#
# `implementation` and `images` are what every campaign runs on. The rest are
# optional research compositions the campaign runner knows how to build: an
# authored Julia analysis image, the scientific task selection, and GPU research
# on the miner lane. A key outside this set means the profile describes
# something this runner cannot assemble, which is refused before launch rather
# than discovered after the miner has started spending.
REQUIRED_RUNTIME_KEYS = frozenset({"implementation", "images"})
SUPPORTED_RUNTIME_KEYS = REQUIRED_RUNTIME_KEYS | {
    "authored_research",
    "scientific_tasks",
    "gpu_research",
}


def review_pin(cfg):
    """Opaque v3 review: the profile the miner reviewed, nothing else."""
    return "review-v3:" + digest(canonical(cfg))


def chain_registration(cfg):
    """The admission read: is the configured hotkey registered, right now.

    The same read the onboarding `status` answers from, through the operator's
    configured chain context. Returns a `RegisteredMiner` or raises the closed
    onboarding failure that says why not.
    """
    from carbon.chain.sdk import BittensorReader
    from carbon.development_session.chain_onboarding import registered_miner
    from carbon.development_testnet.operator import load_config

    config = load_config(Path(cfg["paths"]["operator_config"]))
    public = json.loads(Path(cfg["paths"]["miner_public"]).read_bytes())
    return asyncio.run(
        registered_miner(BittensorReader(), config.context, public["hotkey"])
    )


def runner_database(cfg):
    """Where both doors record this profile's campaigns: beside them, so a
    campaign launched from a browser and one launched from a miner's own MCP
    client are one list, read and controlled the same way."""
    return Path(cfg["campaigns_root"]) / "launchpad-campaigns.sqlite3"


def product_agent(root):
    """Who selects in the campaign at `root`, from its frozen manifest."""
    manifest = Path(root) / "campaign-manifest.json"
    if not manifest.exists():
        return None
    return json.loads(manifest.read_bytes()).get("agent", "autonomous")


def validated_profile(cfg):
    """A runner profile v2, closed, or the reason it is not one.

    Shared by both front doors - this runner and the MCP registered tier - so
    the two cannot disagree about what a miner's profile is.
    """
    if cfg.get("schema") == RETIRED_PROFILE_SCHEMA:
        raise Rejected("runner_profile_v1_retired", 409)
    if set(cfg) - OPTIONAL_PROFILE_FIELDS != PROFILE_FIELDS or (
        cfg["schema"] != PROFILE_SCHEMA
    ):
        raise ValueError("closed operator configuration required")
    guidance.configured(cfg)  # Validate before registration or dispatch.
    if type(cfg["enabled"]) is not bool or (
        "disabled_reason" in cfg
        and (cfg["disabled_reason"] != "OWNER_EXPERIMENT_PAUSE" or cfg["enabled"])
    ):
        raise ValueError("invalid disabled profile explanation")
    if (
        type(cfg["paths"]) is not dict
        or set(cfg["paths"]) - OPTIONAL_PATH_FIELDS != PATH_FIELDS
    ):
        raise ValueError("closed runner inputs required")
    if any(
        type(v) is not str or not Path(v).is_absolute()
        for v in [*cfg["paths"].values(), cfg["campaigns_root"]]
    ):
        raise ValueError("operator paths must be absolute")
    runtime = cfg["runtime"]
    if (
        type(runtime) is not dict
        or type(runtime.get("implementation")) is not dict
        or runtime["implementation"].get("revision") != cfg["accepted_revision"]
    ):
        raise ValueError("the runtime must name the accepted revision")
    return cfg


class RunnerAdapter:
    def __init__(
        self, database, *, configuration=None, principal=None, registration=None
    ):
        self.database = database
        self.configuration = configuration
        self.principal = (
            private_json(configuration)["principal"]
            if configuration is not None
            else principal
        )
        # Injectable so a test reads a device-free stub chain; the default is
        # the real read against the operator's configured context.
        self.registration = registration or chain_registration
        self.threads = {}
        self.lock = threading.RLock()
        with self.db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS launchpad_campaigns (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, request_digest TEXT NOT NULL, profile TEXT NOT NULL, principal TEXT NOT NULL, config_digest TEXT NOT NULL, campaign TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, root TEXT NOT NULL, admission BLOB NOT NULL, budget BLOB NOT NULL, research_guidance BLOB)"
            )
            # Campaigns launched under the retired development grant. Kept so
            # their evidence stays readable and their work can be cleaned up;
            # nothing new is ever written here.
            db.execute(
                "CREATE TABLE IF NOT EXISTS research_runs (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, profile TEXT NOT NULL, principal TEXT NOT NULL, config_digest TEXT NOT NULL, grant_digest TEXT NOT NULL, campaign TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, root TEXT NOT NULL, grant_record BLOB NOT NULL, grant_id TEXT UNIQUE NOT NULL)"
            )
            if "research_guidance" not in {
                r[1] for r in db.execute("PRAGMA table_info(research_runs)")
            }:
                db.execute(
                    "ALTER TABLE research_runs ADD COLUMN research_guidance BLOB"
                )
            roots = [
                Path(r[0])
                for table in ("launchpad_campaigns", "research_runs")
                for r in db.execute(
                    f"SELECT root FROM {table} WHERE principal=?",
                    (self.principal,),
                )
            ]
        for root in roots:
            if (root / "campaign.sqlite3").exists():
                try:
                    with owner_lock(root):
                        control = CampaignControl(CampaignLedger(root))
                        if control.status()["state"] not in {
                            "COMPLETED",
                            "STOPPED",
                            "PAUSED",
                        }:
                            control.settled(control.acquire(), cleanup_verified=False)
                except RuntimeError:
                    pass  # Another live owner still holds the exact campaign lock.

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _configuration(self):
        if self.configuration is None:
            raise ValueError("operator configuration absent")
        cfg = validated_profile(private_json(self.configuration))
        if cfg["principal"] != self.principal:
            raise ValueError("operator principal mismatch")
        return cfg

    def configured(self):
        cfg = self._configuration()
        if not cfg["enabled"]:
            raise Rejected("research_dispatch_disabled", 409)
        runtime = cfg["runtime"]
        if not set(runtime) <= SUPPORTED_RUNTIME_KEYS:
            # Closed rather than permissive: a runtime naming a composition this
            # runner cannot actually assemble is refused here instead of being
            # carried to a campaign that would fail after the miner had started.
            raise Rejected("research_runtime_interface_unavailable", 409)
        if not REQUIRED_RUNTIME_KEYS <= set(runtime):
            raise Rejected("research_runtime_interface_unavailable", 409)
        if "gpu_research" in runtime:
            from carbon.development_session.gpu_research import declared_gpu_runtime

            # Shape, here. The scope's binding to this campaign's own public
            # TRAIN material is recomputed inside the campaign once that
            # material exists; this only refuses a runtime the runner could
            # never assemble, before the launch is recorded.
            try:
                declared_gpu_runtime(runtime)
            except ValueError:
                raise Rejected("research_runtime_interface_unavailable", 409) from None
        return cfg

    def preflight(self):
        from scripts.dev.miner_launchpad.prelaunch import review

        try:
            cfg = self.configured()
            value = {
                "available": True,
                "profile": cfg["profile_id"],
                "mode": "LIVE_PRACTICE_RESEARCH",
                "challenge": "carbon.burgers-autoresearch-development.v1",
                "agent": "carbon-autoresearch",
                "reasoning": "gpt-5-mini-2025-08-07",
                "compute": (
                    "local-isolated-gpu"
                    if "gpu_research" in cfg["runtime"]
                    else "local-isolated-cpu"
                ),
                # Registration is read at launch, before anything is recorded.
                # A budget is the miner's to set at launch or not at all.
                "admission": "SUBNET_REGISTRATION_CHECKED_AT_LAUNCH",
                "budget": "SET_BY_MINER_AT_LAUNCH_OR_NONE",
                "status": "PROFILE_CONFIGURED_REGISTRATION_CHECK_AT_LAUNCH",
                "review_digest": review_pin(cfg),
            }
            task = guidance.configured(cfg)
            if task is not None:
                value.update(
                    research_guidance=task,
                    runtime_revision=cfg["accepted_revision"],
                )
            value["review"] = review(cfg)
            return value
        except Rejected as refused:
            if refused.code == "runner_profile_v1_retired":
                return {
                    "available": False,
                    "profile": None,
                    "status": "PROFILE_V1_RETIRED",
                    "reason": "This profile names a development grant. Launching needs only subnet registration now: replace grant_file and account_ref with campaigns_root and the runtime your campaign runs on (runner-profile v2).",
                }
            return self._unavailable()
        except Exception:  # noqa: BLE001 - private configuration errors stay private.
            return self._unavailable()

    def _unavailable(self):
        try:
            cfg = self._configuration()
            paused = cfg.get("disabled_reason") == "OWNER_EXPERIMENT_PAUSE"
            return {
                "available": False,
                "profile": cfg["profile_id"],
                "status": ("OWNER_EXPERIMENT_PAUSE" if paused else "DISPATCH_DISABLED"),
                "reason": (
                    "Owner experiment pause is active. New owner authorization is required before research can resume. Status, export, stop and reconciliation remain available."
                    if paused
                    else "Research dispatch is disabled in this profile, or its runtime is one this runner cannot assemble."
                ),
                "research_guidance": guidance.configured(cfg),
                "runtime_revision": cfg["accepted_revision"],
                "review": self._review(cfg),
            }
        except Exception:  # noqa: BLE001 - no private paths or errors disclosed.
            return {
                "available": False,
                "profile": None,
                "status": "DISPATCH_DISABLED",
                "reason": "A runner profile with your registered miner and the exact accepted runtime and images is required.",
            }

    @staticmethod
    def _review(cfg):
        from scripts.dev.miner_launchpad.prelaunch import review

        return review(cfg)

    def launch(self, value, key):
        """The browser's launch: a caller of the shared `launch` operation."""
        from scripts.dev.miner_launchpad.operations import perform

        if type(value) is not dict or "profile" not in value:
            raise Rejected("closed_research_launch_required")
        request = {"agent": "autonomous", **value, "idempotency_key": key}
        return perform(self, "launch", request)

    # -- The campaign host: what the operations table's gates and bodies ask of
    # -- whichever door is calling. Both doors construct this same class.

    @classmethod
    def for_profile(cls, configuration, *, legacy_database=None, registration=None):
        """The campaign host both doors construct for one runner profile.

        Its records live beside the profile's campaigns. `legacy_database` is a
        browser database from before the doors shared one: its campaign rows
        are copied across once, so nothing launched earlier is lost.
        """
        cfg = validated_profile(private_json(Path(configuration)))
        database = runner_database(cfg)
        database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        host = cls(database, configuration=configuration, registration=registration)
        if legacy_database is not None and Path(legacy_database).exists():
            host._adopt(Path(legacy_database))
        database.chmod(0o600)
        return host

    def _adopt(self, legacy):
        with self.db() as db:
            db.execute("ATTACH DATABASE ? AS legacy", (str(legacy),))
            try:
                tables = {
                    r[0]
                    for r in db.execute(
                        "SELECT name FROM legacy.sqlite_master WHERE type='table'"
                    )
                }
                for table in ("launchpad_campaigns", "research_runs"):
                    if table in tables:
                        columns = ",".join(
                            r[1]
                            for r in db.execute(f"PRAGMA legacy.table_info({table})")
                        )
                        db.execute(
                            f"INSERT OR IGNORE INTO main.{table} ({columns}) "
                            f"SELECT {columns} FROM legacy.{table}"
                        )
            finally:
                db.commit()
                db.execute("DETACH DATABASE legacy")

    def replayed(self, cfg, request):
        """Launch's read-only replay gate: validates the request, and returns
        the campaign a lost response created, reading no chain; or None."""
        from carbon.development_session.product_campaign import AGENTS, miner_budget

        key = request["idempotency_key"]
        if (
            type(key) is not str
            or not 16 <= len(key) <= 80
            or not all(c.isascii() and (c.isalnum() or c in "-_") for c in key)
        ):
            raise Rejected("invalid_idempotency_key")
        if request["agent"] not in AGENTS:
            raise Rejected("invalid_agent")
        try:
            miner_budget(request.get("budget"))
        except ValueError:
            raise Rejected("invalid_budget") from None
        if cfg["principal"] != self.principal:
            raise Rejected("research_profile_mismatch", 409)
        task = guidance.configured(cfg)
        if (task is not None or "review_digest" in request) and request.get(
            "review_digest"
        ) != review_pin(cfg):
            raise Rejected("research_review_changed", 409)
        run_id, digest_value, config_pin = self._launch_identity(cfg, request)
        with self.db() as db:
            previous = db.execute(
                "SELECT * FROM launchpad_campaigns WHERE request_key=? OR id=?",
                (key, run_id),
            ).fetchall()
        if not previous:
            return None
        # A lost response replays the campaign it created. It was admitted
        # when it was recorded; replaying it reads no chain and starts
        # nothing new.
        if len(previous) != 1 or any(
            previous[0][k] != v
            for k, v in {
                "id": run_id,
                "request_digest": digest_value,
                "principal": cfg["principal"],
                "config_digest": config_pin,
            }.items()
        ):
            raise Rejected("research_launch_replay_conflict", 409)
        return self.get(run_id)

    def _launch_identity(self, cfg, request):
        # The browser's request digest is of the launch fields it historically
        # sent, so a replay of a launch recorded before operations existed still
        # matches. The agent choice joins it only when it is not the default.
        fields = {
            k: v for k, v in request.items() if k not in {"idempotency_key", "agent"}
        }
        if request["agent"] != "autonomous":
            fields["agent"] = request["agent"]
        run_id = digest(canonical([cfg["principal"], request["idempotency_key"]]))[7:39]
        return run_id, digest(canonical(fields)), digest(canonical(cfg))

    @staticmethod
    def _challenge(request):
        """The launch's Challenge, resolved exactly, or None for the historical
        default. An unknown, reserved, deferred or wrong-version Challenge is
        refused by its code; nothing falls back to another Challenge."""
        if "challenge" not in request and "challenge_version" not in request:
            return None
        from carbon.challenge_registry import ResolutionError, resolve

        challenge = {
            "id": request.get("challenge"),
            "version": request.get("challenge_version"),
        }
        try:
            resolve(challenge["id"], challenge["version"], "cpu_research")
        except ResolutionError as refused:
            raise Rejected(refused.code, 409) from None
        return challenge

    def launch_admitted(self, admitted, request):
        """Record and dispatch an admitted launch."""
        from carbon.development_session.product_campaign import (
            ProductLaunch,
            miner_budget,
        )

        cfg, miner = admitted.profile, admitted.miner
        task = guidance.configured(cfg)
        budget = miner_budget(request.get("budget"))
        run_id, request_digest, config_pin = self._launch_identity(cfg, request)
        root = Path(cfg["campaigns_root"]) / run_id
        product = ProductLaunch(
            campaign_id="cmp-" + run_id,
            principal=cfg["principal"],
            miner=miner,
            runtime=cfg["runtime"],
            budget=budget,
            agent=request["agent"],
            challenge=self._challenge(request),
        )
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO launchpad_campaigns (id,request_key,request_digest,profile,principal,config_digest,campaign,state,created,root,admission,budget,research_guidance) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        request["idempotency_key"],
                        request_digest,
                        cfg["profile_id"],
                        cfg["principal"],
                        config_pin,
                        product.campaign_id,
                        "QUEUED",
                        time.time(),
                        str(root),
                        canonical(miner.record()),
                        canonical(budget),
                        canonical(task) if task is not None else None,
                    ),
                )
            except sqlite3.IntegrityError:
                raise Rejected("research_launch_replay_conflict", 409) from None
        self._start(run_id, cfg, root, product)
        return self.get(run_id)

    def owner(self):
        """Whose campaigns this host serves, for operations that read or
        withdraw: no enabled or runnable profile is required for those."""
        if type(self.principal) is not str or not self.principal:
            raise Rejected("research_profile_unavailable", 409)
        return {"principal": self.principal}

    def owned_campaign(self, identity):
        """The campaign gate: a campaign this principal owns, and its kind."""
        if type(identity) is not str:
            raise Rejected("research_run_unavailable", 404)
        row, kind, _ = self._bound(identity)
        return {**dict(row), "kind": kind}

    def options_admitted(self, admitted, request):
        """What a miner can choose at launch, and whether it can run now.

        The vocabulary is check-design's (supported, not_yet_rebuildable,
        needs_owner_decision, excluded) for what Carbon can rebuild, and
        configured / unavailable-with-reason for what this host has. Built
        from the capability registry and the profile, never from a static list,
        so no option is offered that cannot run.
        """
        from carbon.development_session.design_check import availability
        from carbon.development_session.product_campaign import BUDGET_KEYS
        from carbon.development_session.research_ledger import DIMENSIONS
        from carbon.reconstruction.capability_registry import REGISTRY, Dimension

        # The gate established whose profile this is; its content is read here.
        cfg = self.configured()
        paths = cfg.get("paths", {})
        runtime = cfg.get("runtime", {})
        key = paths.get("api_key_file")
        agent_ready = type(key) is str and Path(key).is_file()

        def host(present, reason):
            return (
                {"availability": "configured"}
                if present
                else {
                    "availability": "unavailable",
                    "reason": reason,
                }
            )

        return {
            "schema": "carbon.launchpad.launch-options.v1",
            "agents": [
                {"value": "none", "availability": "available"},
                {
                    "value": "autonomous",
                    **(
                        {"availability": "available"}
                        if agent_ready
                        else {
                            "availability": "unavailable",
                            "reason": "model_provider_key_not_configured",
                        }
                    ),
                },
            ],
            "families": [
                {
                    "id": c.capability_id,
                    "selector": c.selector,
                    "summary": c.summary,
                    **availability(c),
                }
                for c in REGISTRY
                if c.dimension is Dimension.MODEL_FAMILY
            ],
            "research_lanes": {
                "julia": host(
                    "authored_research" in runtime or "authored_julia_image" in cfg,
                    "no_julia_image_installed_for_this_profile",
                ),
                "gpu": host("gpu_research" in runtime, "no_gpu_runtime_declared"),
            },
            # The miner's own budget: every part optional, no bound to be
            # outside of. Read from the ledger's own vocabulary, so a launch
            # form built from it offers exactly what a launch accepts.
            "budget": {
                "availability": "available",
                "keys": sorted(BUDGET_KEYS),
                "ceilings": list(DIMENSIONS),
                "bounds": "none: a ceiling is any whole number >= 0, elapsed_seconds any whole number >= 1; blank is no cap",
            },
            "vocabulary": {
                "supported": "Carbon rebuilds it in DEVELOPMENT; not official qualification",
                "not_yet_rebuildable": "explore it in research; engineering has not registered it",
                "needs_owner_decision": "research-only until the owner decides; see its trigger",
                "excluded": "outside the declarative rule",
                "configured": "this host has it",
                "unavailable": "this host does not, for the reason given",
            },
        }

    def _design_refusal(self, strategy):
        """Check-design's verdict for a recipe about to be practiced or frozen:
        refused now, by name, rather than failing at submission."""
        from carbon.development_session.design_check import check_design

        try:
            verdict = check_design({"strategy": strategy})
        except ValueError:
            raise Rejected("design_malformed") from None
        if verdict["verdict"] != "submittable":
            raise Rejected("design_" + verdict["verdict"], 409)

    def observe_admitted(self, admitted, request):
        return self.get(admitted.campaign["id"])

    def halt_admitted(self, admitted, request):
        if request["action"] not in {"stop", "pause", "reconcile"}:
            raise Rejected("invalid_research_control")
        return self._control(admitted.campaign["id"], request["action"])

    def resume_admitted(self, admitted, request):
        return self._control(admitted.campaign["id"], "resume")

    def practice_admitted(self, admitted, request):
        """One practice trial of a registered recipe, run in the background:
        real training takes minutes, and observe shows the result."""
        import uuid

        from carbon.development_session.research_campaign import practice_recipe
        from scripts.dev.miner_launchpad.operations import strategy_value

        strategy = strategy_value(request)
        self._design_refusal(strategy)
        hypothesis = request["hypothesis"]
        expected = request.get("expected_effect", hypothesis)
        for text in (hypothesis, expected):
            if type(text) is not str or not 1 <= len(text) <= 2048:
                raise Rejected("bounded_hypothesis_required")
        identity = "miner-practice-" + uuid.uuid4().hex[:16]

        async def practice(prepared):
            return await practice_recipe(
                prepared,
                strategy=strategy,
                hypothesis=hypothesis,
                expected_effect=expected,
                identity=identity,
            )

        return self._background(admitted, practice, "PRACTICING")

    def freeze_candidate_admitted(self, admitted, request):
        """Freeze a practiced recipe. Its refusals - agent-selected campaign,
        no practice result, a candidate awaiting submission, final exams used -
        are read from the campaign's own records before anything starts, so a
        person gets the named reason at once; the freeze itself then runs in
        the background, because preparing the campaign can take a while."""
        from carbon.development_session.research_campaign import (
            freeze_candidate,
            freeze_refusal,
        )
        from scripts.dev.miner_launchpad.operations import strategy_value

        strategy = strategy_value(request)
        used = request.get("used_feedback", False)
        if type(used) is not bool:
            raise Rejected("used_feedback_boolean_required")
        reason = request["reason"]
        if type(reason) is not str or not 1 <= len(reason) <= 4096:
            raise Rejected("bounded_reason_required")
        self._design_refusal(strategy)
        refusal = freeze_refusal(Path(admitted.campaign["root"]), strategy)
        if refusal is not None:
            raise Rejected(refusal, 409)

        async def freeze(prepared):
            return await freeze_candidate(
                prepared, strategy=strategy, reason=reason, used_feedback=used
            )

        return self._background(admitted, freeze, "FREEZING")

    def submit_admitted(self, admitted, request):
        from carbon.development_session.research_campaign import submit_frozen

        # Checked before the thread starts, so a submit with nothing frozen is
        # refused to the caller rather than failing where no one sees it.
        self._require_frozen(admitted)
        return self._background(admitted, submit_frozen, "SUBMITTING")

    def _background(self, admitted, work, state):
        """Run a long miner operation on its own thread; observe reports it."""
        identity = admitted.campaign["id"]
        with self.lock:
            previous = self.threads.get(identity)
            if previous is not None and previous.is_alive():
                # A finished operation settles the campaign READY and then its
                # thread exits: give it a moment to, so a client that saw
                # READY is not told busy. A running one still answers busy.
                previous.join(timeout=2)
                if previous.is_alive():
                    raise Rejected("campaign_busy", 409)
            thread = threading.Thread(
                target=self._operation_thread, args=(admitted, work), daemon=True
            )
            self.threads[identity] = thread
            self._state(identity, state)
            thread.start()
        return self.get(identity)

    @staticmethod
    def _require_frozen(admitted):
        from carbon.development_session.research_campaign import FINAL_EPOCHS

        root = Path(admitted.campaign["root"])
        for epoch in FINAL_EPOCHS:
            folder = root / ("epoch-" + str(epoch))
            if (folder / "permitted-final-feedback.json").exists():
                continue
            if (folder / "selected-recipe.json").exists():
                return
            break
        raise Rejected("freeze_a_candidate_first", 409)

    def _operation_thread(self, admitted, work):
        try:
            self._operate(admitted, work)
        except Exception:  # noqa: BLE001 - never publish provider/key errors.
            self._state(admitted.campaign["id"], "INTERRUPTED")

    def _operate(self, admitted, work):
        """Run one miner operation on a prepared campaign, under its owner lock
        and a fresh control generation, and settle it afterwards.

        A refusal changes nothing, so the campaign settles READY again; only
        an unexpected failure leaves it for reconciliation.
        """
        from carbon.development_session.research_agent_policy import AUTONOMOUS
        from carbon.development_session.research_campaign import (
            OperationRefused,
            prepare,
        )

        row, cfg = admitted.campaign, admitted.profile
        root = Path(row["root"])
        task = guidance.verify(
            json.loads(row["research_guidance"])
            if row["research_guidance"] is not None
            else None
        )
        stack = ExitStack()
        try:
            stack.enter_context(owner_lock(root))
        except RuntimeError:
            raise Rejected("campaign_busy", 409) from None
        with stack:
            ledger = CampaignLedger(root)
            control = CampaignControl(ledger)
            generation = control.acquire()
            ledger.generation = generation
            args = SimpleNamespace(
                **{k: Path(v) for k, v in cfg["paths"].items()},
                root=root,
                accepted_revision=cfg["accepted_revision"],
                principal=cfg["principal"],
                agent_policy=AUTONOMOUS,
                product=None,
                research_guidance=task["text"] if task is not None else None,
                command="resume",
            )

            async def run():
                prepared = await prepare(args, ledger=ledger)
                if prepared is None:
                    raise OperationRefused("campaign_complete")
                try:
                    return await work(prepared)
                finally:
                    prepared.close()

            refused = None
            try:
                result = asyncio.run(run())
            except OperationRefused as exc:
                refused = exc.code
            except BaseException:
                control.settled(generation, cleanup_verified=self._cleanup(ledger))
                raise
            complete = (root / "campaign-complete.json").exists()
            control.settled(
                generation,
                completed=complete,
                ready=not complete,
                cleanup_verified=self._cleanup(ledger),
            )
            self._state(row["id"], "COMPLETED" if complete else "READY")
        if refused is not None:
            raise Rejected(refused, 409)
        return result

    def _start(self, run_id, cfg, root, product=None):
        with self.lock:
            if run_id in self.threads and self.threads[run_id].is_alive():
                return
            thread = threading.Thread(
                target=self._run, args=(run_id, cfg, root, product), daemon=True
            )
            self.threads[run_id] = thread
            thread.start()

    def _run(self, run_id, cfg, root, product):
        from carbon.development_session.research_agent_policy import AUTONOMOUS
        from carbon.development_session.research_campaign import execute

        generation = None
        try:
            # Recheck the real operator profile at the thread handoff. A
            # disabled profile must not slip through a queued HTTP request.
            if self.configuration is not None and self.configured() != cfg:
                raise ValueError("dispatch configuration changed")
            row, kind, _ = self._bound(run_id)
            if kind != "product":
                raise ValueError("a retired grant campaign is never dispatched")
            task = guidance.verify(
                json.loads(row["research_guidance"])
                if row["research_guidance"] is not None
                else None
            )
            if task != guidance.configured(cfg):
                raise ValueError("frozen research guidance differs")
            with owner_lock(root):
                ledger = CampaignLedger(root)
                control = CampaignControl(ledger)
                generation = control.acquire()
                ledger.generation = generation
                # Ambiguous work never resumes automatically, even under a new
                # generation. Completed observations remain replayable by runner.
                with ledger.db() as db:
                    pending = db.execute(
                        "SELECT 1 FROM operations WHERE state IN ('RESERVED','HELD') LIMIT 1"
                    ).fetchone()
                if pending:
                    raise DispatchStopped("unresolved operation")
                args = SimpleNamespace(
                    **{k: Path(v) for k, v in cfg["paths"].items()},
                    root=root,
                    accepted_revision=cfg["accepted_revision"],
                    principal=cfg["principal"],
                    agent_policy=AUTONOMOUS,
                    product=product,
                    research_guidance=task["text"] if task is not None else None,
                    command=(
                        "resume"
                        if (root / "campaign-manifest.json").exists()
                        else "run"
                    ),
                )
                try:
                    asyncio.run(execute(args, ledger=ledger))
                except Exception:  # noqa: BLE001 - never publish provider/key errors.
                    self._state(run_id, "INTERRUPTED")
                finally:
                    clean = self._cleanup(ledger)
                    completed = (root / "campaign-complete.json").exists()
                    # An agent-less campaign is prepared and waiting for its
                    # miner: ready, not interrupted.
                    ready = not completed and product_agent(root) == "none"
                    state = control.settled(
                        generation,
                        completed=completed,
                        ready=ready,
                        cleanup_verified=clean,
                    )
                    if state == "READY":
                        self._state(run_id, "READY")
        except Exception:  # noqa: BLE001
            self._state(run_id, "RECONCILIATION_REQUIRED")
            if generation is not None:
                control.settled(generation, cleanup_verified=False)

    def _state(self, run_id, state):
        with self.db() as db:
            for table in ("launchpad_campaigns", "research_runs"):
                db.execute(
                    f"UPDATE {table} SET state=? WHERE id=?",
                    (state, run_id),
                )

    @staticmethod
    def _cleanup(ledger):
        """Use domain cleanup journals; absence of a browser process proves nothing."""
        from carbon.development_session.research_carrier import reconcile_worker
        from carbon.execution import DurableWorkerLaunchStore
        from carbon.reconstruction.worker.docker_runtime import (
            DockerCLI,
            remove_exact_container,
        )
        from carbon.reconstruction.worker.operator import _stores

        clean = True
        # HELD is capacity, never a worker. Release through the same sequence
        # transaction; dispatched children still need their actual domain journal.
        with ledger.db() as db:
            sequences = db.execute(
                "SELECT parent,owner FROM operation_sequences"
            ).fetchall()
        for parent, owner in sequences:
            try:
                ledger.cancel_sequence_held(parent, owner=owner)
                ledger.settle_sequence(parent, owner=owner)
            except Exception:  # noqa: BLE001
                clean = False
        with ledger.db() as db:
            rows = db.execute(
                "SELECT id,owner,reservation FROM operations WHERE state='RESERVED'"
            ).fetchall()
        for identity, owner, reserved in rows:
            if json.loads(reserved).get("numerical_milliseconds"):
                try:
                    reconcile_worker(ledger, owner=owner, identity=identity)
                except Exception:  # noqa: BLE001
                    clean = False
        for path in _stores(ledger.root):
            store = DurableWorkerLaunchStore(path)
            for item in store.reconciliation_targets():
                try:
                    cli = DockerCLI()
                    remove_exact_container(
                        cli=cli,
                        container_name=item["container_name"],
                        launch_digest=item["launch_digest"],
                    )
                    if cli.run(
                        [
                            "ps",
                            "-aq",
                            "--filter",
                            "name=^" + item["container_name"] + "$",
                        ],
                        timeout=10,
                    ).stdout.strip():
                        raise ValueError("owned worker remains")
                    store.record_operator_cleanup(
                        execution_id=item["execution_id"],
                        launch_digest=item["launch_digest"],
                        cleaned=True,
                    )
                except Exception:  # noqa: BLE001
                    clean = False
        return clean

    def _bound(self, identity):
        """The campaign row, which kind it is, and its root.

        Product campaigns and retired-grant campaigns are separate records, so
        a retired one can never be mistaken for something to dispatch.
        """
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM launchpad_campaigns WHERE id=?", (identity,)
            ).fetchone()
            kind = "product"
            if row is None:
                row = db.execute(
                    "SELECT * FROM research_runs WHERE id=?", (identity,)
                ).fetchone()
                kind = "retired_grant"
        if row is None or row["principal"] != self.principal:
            raise Rejected("research_run_unavailable", 404)
        return row, kind, Path(row["root"])

    def _ledger(self, row, kind, root):
        """The campaign's ledger. A retired grant is held only for cleanup."""
        if kind == "product":
            return CampaignLedger(root)
        from carbon.development_session.research_admission import (
            retained_grant_ledger,
        )

        return retained_grant_ledger(
            root, json.loads(row["grant_record"]), row["grant_digest"]
        )

    def control(self, identity, action):
        """The browser's control route: a caller of halt or resume."""
        from scripts.dev.miner_launchpad.operations import perform

        if action == "resume":
            return perform(self, "resume", {"campaign": identity})
        return perform(self, "halt", {"campaign": identity, "action": action})

    def _control(self, identity, action):
        row, kind, root = self._bound(identity)
        if action == "resume" and kind != "product":
            # Resuming would dispatch new work under a grant, which no product
            # surface may do. Observe, pause, stop and reconcile still work.
            raise Rejected("retired_grant_campaign", 409)
        ledger = self._ledger(row, kind, root)
        control = CampaignControl(ledger)
        if action == "reconcile":
            with owner_lock(root):
                generation = control.acquire()
                ledger.generation = generation
                control.settled(generation, cleanup_verified=self._cleanup(ledger))
        else:
            if action == "resume":
                cfg = self.configured()
                if digest(canonical(cfg)) != row["config_digest"]:
                    raise ValueError("resume binding differs")
            control.request(action)
            if action == "stop":
                ledger.generation = control.status()["generation"]
                from carbon.development_session.research_carrier import request_cancel

                with ledger.db() as db:
                    sequences = db.execute(
                        "SELECT parent,owner FROM operation_sequences"
                    ).fetchall()
                    operations = db.execute(
                        "SELECT id,owner FROM operations WHERE state='RESERVED'"
                    ).fetchall()
                for parent, owner in sequences:
                    ledger.cancel_sequence_held(parent, owner=owner)
                for operation, owner in operations:
                    request_cancel(ledger, owner=owner, identity=operation)
            if action == "resume":
                # Resumes the frozen campaign; its manifest carries everything
                # the launch admitted, so no new admission is constructed.
                self._start(identity, cfg, root)
        return self.get(identity)

    def get(self, identity):
        from scripts.dev.miner_launchpad.projection import project

        row, _, root = self._bound(identity)
        return project(dict(row), root)

    def recent(self):
        with self.db() as db:
            ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM (SELECT id,created FROM launchpad_campaigns WHERE principal=? UNION ALL SELECT id,created FROM research_runs WHERE principal=?) ORDER BY created DESC LIMIT 100",
                    (self.principal, self.principal),
                )
            ]
        result = []
        for identity in ids:
            try:
                result.append(self.get(identity))
            except Rejected:
                result.append(
                    {
                        "id": identity,
                        "state": "READBACK_UNAVAILABLE",
                        "mode": "LIVE_PRACTICE_RESEARCH",
                    }
                )
        return result

    def close(self):
        for identity, thread in tuple(self.threads.items()):
            if thread.is_alive():
                try:
                    self.control(identity, "stop")
                except Exception:  # noqa: BLE001
                    self._state(identity, "RECONCILIATION_REQUIRED")
        for thread in tuple(self.threads.values()):
            thread.join(timeout=1)
