"""`GraphiteProvider`: Carbon's own research agent behind the campaign controller.

It implements the #475 provider contract (`..provider.ResearchAgentProvider`)
so the controller's grant, caps, cancellation checks, findings and ledger
apply to Graphite exactly as they would to any provider (plan §2, rule 1).

**What a run is.** One session of one role. `start` opens it: it resolves the
task's `instructions_digest` to a brief Carbon registered beforehand, checks
the role runs under the task's campaign role, takes the role's current rung
from the ladder, and writes the opening half of the session record. `run` is
the worker: it drives the existing research loop
(`research_loop.run_epoch`) with the role's prompt and closed tool manifest,
the role's toolbox as the loop's `sdk`, and the model access's transport. The
loop's own ledger (`research_ledger.CampaignLedger`) and `research_agent`
meter each call: reservation before dispatch, settlement from the provider's
reported charge, replay without resending, typed failures.

**Caps.** Each run's ledger is frozen with the grant's `worst_case_run_cost`
as its money ceiling (in nanodollars), the controller's reservation for the
run, so a run can never spend more than the controller reserved. An optional
operator cap on model calls narrows it further. No numerical work, final
replica or reference call is admitted in phase 1 (each is capped at zero).

**Cancellation.** `cancel` records the request; the worker stops at the
loop's next ledger checkpoint, which precedes every reservation, so no new
call is reserved or sent after it. A call already in flight finishes and is
journalled. Workers report terminated only when the worker has returned.

**Crash recovery.** Everything is on disk under a private root. A process
that dies mid-run leaves the session record and the loop's journal; `run` on
a fresh provider resumes from them. Completed calls replay from the journal
and are not sent again; a call whose outcome is unknown keeps its full
reservation and stops the run for reconciliation, never resent. On resume the
session record is re-verified against the role's prompt digest and tool
manifest, the model selection and the literature snapshot; any difference
refuses the run.

**Authority.** None. Results are data returned to the controller. Nothing
here grades, scores, rewards or reads confirmation material.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.model_provider import select, selection_from_record
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent import ProviderCallFailed
from carbon.development_session.research_ledger import VERSION, CampaignLedger
from carbon.development_session.research_loop import run_epoch

from ..controller import SimulatedCrash
from ..grant import SpendingGrant
from ..provider import (
    Artifact,
    Capabilities,
    IntegrationMode,
    ProviderUnavailable,
    RunHandle,
    RunState,
    RunStatus,
    TaskSpec,
    Usage,
    digest_text,
    identifier,
)
from . import tools as toolbox
from .ladder import Ladder
from .literature import FIXTURE_INDEX, LiteratureIndex
from .model import ENGY_ADAPTERS
from .roles import ROLES, RoleName

PROVIDER = "graphite"
SESSION_SCHEMA = "carbon.graphite.session-record.v1"
BRIEF_SCHEMA = "carbon.graphite.brief.v1"
OWNER = "graphite"
EPOCH = 1
CRASH_POINTS = ("after_open", "before_finish")
NANO_PER_USD = Decimal(10) ** 9
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_TERMINAL = ("succeeded", "failed", "cancelled")
#: Research-layer refusals that mean a run limit was reached, by message.
_LIMIT_MESSAGES = {
    "provider timeout cannot fit remaining campaign time": "elapsed_seconds",
    "campaign elapsed-time exhausted or clock regressed": "elapsed_seconds",
}


class RunCancelled(Exception):
    """The run's cancellation was observed at a ledger checkpoint."""


class RunCapReached(ValueError):
    """A run cap refused the next reservation."""

    def __init__(self, dimension):
        super().__init__("run cap reached: " + dimension)
        self.dimension = dimension


class SessionMismatch(ValueError):
    """A session record no longer matches the code or inputs that resume it."""


@dataclass(frozen=True)
class SessionBrief:
    """What one session of a role is given. Registered before launch; a task
    names it by digest (`TaskSpec.instructions_digest`)."""

    role: RoleName
    initial_observation: dict
    checkout_commit: str
    checkout_manifest_digest: str

    def __post_init__(self):
        if type(self.role) is not RoleName:
            raise TypeError("exact RoleName required")
        if type(self.initial_observation) is not dict:
            raise TypeError("the initial observation is a JSON object")
        canonical(self.initial_observation)  # JSON-serialisable, finite
        if type(self.checkout_commit) is not str or not _COMMIT.fullmatch(
            self.checkout_commit
        ):
            raise ValueError("checkout_commit is a 40-hex commit")
        digest_text(self.checkout_manifest_digest, "checkout_manifest_digest")
        if toolbox.protected(self.initial_observation):
            raise ValueError("refused: a brief names protected material")

    def document(self):
        role = ROLES[self.role]
        return {
            "schema": BRIEF_SCHEMA,
            "role": self.role.value,
            "role_prompt_digest": role.prompt_digest,
            "tool_manifest_digest": role.tool_manifest_digest,
            "initial_observation": self.initial_observation,
            "checkout": {
                "commit": self.checkout_commit,
                "manifest_digest": self.checkout_manifest_digest,
            },
        }

    @property
    def digest(self):
        return digest(canonical(self.document()))


class GraphiteLedger(CampaignLedger):
    """The research loop's ledger with two hooks at its existing checkpoint:
    cancellation and, in tests, a process death at the Nth checkpoint."""

    def __init__(self, root, *, clock, cancelled, crash):
        super().__init__(root, clock=clock)
        self._cancelled, self._crash = cancelled, crash

    def checkpoint(self):
        super().checkpoint()
        self._crash()
        if self._cancelled():
            raise RunCancelled()

    def _reserve(self, identity, **kwargs):
        try:
            return super()._reserve(identity, **kwargs)
        except ValueError as error:
            text = str(error)
            if text.startswith("miner budget: "):
                raise RunCapReached(text.removeprefix("miner budget: ")) from None
            if text in _LIMIT_MESSAGES:
                raise RunCapReached(_LIMIT_MESSAGES[text]) from None
            raise


def _verify(opened, role, selection_record, literature_digest, brief_digest, limits):
    """The session record still describes what would resume it: the role's
    prompt and manifest, the model selection, the literature snapshot, the
    brief, and the grant and caps the run is held to."""
    recorded = opened["role"]
    if (
        recorded["prompt_digest"] != role.prompt_digest
        or recorded["tool_manifest"] != list(role.tools)
        or recorded["tool_manifest_digest"] != role.tool_manifest_digest
        or recorded["boundary"] != role.boundary.value
    ):
        raise SessionMismatch("role_changed")
    if opened["model"] != selection_record:
        raise SessionMismatch("model_selection_changed")
    if opened["literature"]["snapshot_digest"] != literature_digest:
        raise SessionMismatch("literature_snapshot_changed")
    if opened["brief"]["digest"] != brief_digest:
        raise SessionMismatch("brief_changed")
    if {"grant": opened["grant"], "caps": opened["caps"]} != limits:
        raise SessionMismatch("grant_or_caps_changed")


def _check_role(role, spec):
    """A Graphite role runs only under its own campaign role."""
    if role.boundary.value != spec.role:
        raise ProviderUnavailable("role_boundary_mismatch")


def _replace(path, payload):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, path)


class GraphiteProvider:
    def __init__(
        self,
        *,
        root,
        grant,
        model,
        literature_index=FIXTURE_INDEX,
        miner_tools=None,
        adapter_id="engy-anthropic",
        max_calls_per_run=None,
        clock=time.time,
        crash_at=None,
        crash_at_checkpoint=None,
    ):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("graphite root must be private and absolute")
        if type(grant) is not SpendingGrant:
            raise ProviderUnavailable("spending_grant_required")
        if grant.provider != PROVIDER:
            raise ProviderUnavailable("grant_provider_mismatch")
        if grant.currency != "USD":
            # Charges are metered in USD nanodollars; another currency has no
            # conversion here, so nothing is admitted against it.
            raise ProviderUnavailable("grant_currency_must_be_usd")
        if not callable(getattr(model, "transport_for", None)):
            raise ProviderUnavailable("model_access_required")
        if model.live and getattr(model, "grant", None) != grant:
            raise ProviderUnavailable("live_model_grant_mismatch")
        if adapter_id not in ENGY_ADAPTERS:
            raise ProviderUnavailable("engy_adapter_required")
        if type(literature_index) is not LiteratureIndex:
            raise TypeError("exact LiteratureIndex required")
        if max_calls_per_run is not None and (
            type(max_calls_per_run) is not int or max_calls_per_run < 1
        ):
            raise ValueError("max_calls_per_run is a positive integer or None")
        if crash_at is not None and crash_at not in CRASH_POINTS:
            raise ValueError("unknown crash point")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        for name in ("briefs", "runs"):
            (root / name).mkdir(exist_ok=True, mode=0o700)
        self.root, self.grant, self.model = root, grant, model
        self.literature = literature_index
        self.miner_tools = miner_tools
        self.adapter_id = adapter_id
        self.max_calls_per_run = max_calls_per_run
        self.clock = clock
        self.crash_at = crash_at
        self.crash_at_checkpoint = crash_at_checkpoint
        self._checkpoints = 0
        self.ladder = Ladder(root / "ladder")
        self._active = set()

    # -- configuration ------------------------------------------------------------------
    def capabilities(self):
        return Capabilities(
            provider=PROVIDER,
            mode=IntegrationMode.TOOL_ADAPTER,
            verified=True,
            supports_idempotent_start=True,
            supports_cancel=True,
            reports_worker_termination=True,
            reports_usage=True,
            basis=(
                "Carbon's own in-process harness (GRAPHITE-01 phase 1): the existing "
                "research loop and ledger; usage from that ledger; "
                + (
                    "live model under a spending grant"
                    if self.model.live
                    else "scripted model, no live inference"
                )
            ),
        )

    def per_run_ceiling_nano(self):
        """The grant's worst-case run cost, the controller's reservation for
        one run, in whole nanodollars (rounded down)."""
        return int(
            (self.grant.worst_case_run_cost * NANO_PER_USD).to_integral_value(
                rounding=ROUND_FLOOR
            )
        )

    def caps(self):
        return {
            "epochs": 1,
            "provider_attempts": self.max_calls_per_run,
            "provider_nanodollars": self.per_run_ceiling_nano(),
            "research_trials": 0,
            "final_replicas": 0,
            "numerical_milliseconds": 0,
            "reference_trajectories": 0,
            "reference_invocations": 0,
            "retained_bytes": None,
        }

    def _grant_record(self):
        return {
            "grant_id": self.grant.grant_id,
            "currency": self.grant.currency,
            "per_run_ceiling_nanodollars": self.per_run_ceiling_nano(),
        }

    def register_brief(self, brief):
        if type(brief) is not SessionBrief:
            raise TypeError("exact SessionBrief required")
        document = canonical(brief.document())
        write_once(self.root / "briefs" / (brief.digest[7:] + ".json"), document)
        return brief.digest

    def _brief(self, brief_digest):
        path = self.root / "briefs" / (brief_digest.removeprefix("sha256:") + ".json")
        if not path.is_file() or path.is_symlink():
            return None
        body = path.read_bytes()
        if digest(body) != brief_digest:
            raise SessionMismatch("brief_changed")
        return json.loads(body)

    # -- paths and state -----------------------------------------------------------------
    @staticmethod
    def run_id_for(idempotency_key):
        return "graphite-" + digest(idempotency_key.encode())[7:23]

    def _dir(self, run_id):
        identifier(run_id, "provider_run_id")
        return self.root / "runs" / run_id

    def _opened(self, run_id):
        path = self._dir(run_id) / "session-open.json"
        if not path.is_file():
            raise ProviderUnavailable("unknown_run")
        return json.loads(path.read_bytes())

    def _state(self, run_id):
        path = self._dir(run_id) / "state.json"
        if not path.exists():
            self._opened(run_id)
            return {"state": "running", "cancel_requested": False, "failure": None}
        return json.loads(path.read_bytes())

    def _set_state(self, run_id, **changes):
        state = {**self._state(run_id), **changes}
        _replace(self._dir(run_id) / "state.json", canonical(state))
        return state

    def _emit(self, run_id, event_id, body):
        """Append one event once; replays never duplicate it."""
        path = self._dir(run_id) / "events.jsonl"
        existing = path.read_bytes().splitlines() if path.exists() else []
        if any(json.loads(line)["event_id"] == event_id for line in existing):
            return
        line = canonical({"event_id": event_id, "sequence": len(existing), **body})
        with path.open("ab") as stream:
            stream.write(line + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o600)

    def _crash(self, point):
        if self.crash_at == point:
            raise SimulatedCrash(point)

    def _checkpoint_crash(self):
        self._checkpoints += 1
        if self.crash_at_checkpoint == self._checkpoints:
            raise SimulatedCrash("checkpoint " + str(self._checkpoints))

    def _ledger(self, run_id):
        return GraphiteLedger(
            self._dir(run_id) / "ledger",
            clock=self.clock,
            cancelled=lambda: self._state(run_id)["cancel_requested"],
            crash=self._checkpoint_crash,
        )

    def _manifest(self, opened):
        return {
            "schema": VERSION,
            "ceilings": opened["caps"],
            "elapsed_seconds": opened["task"]["max_runtime_s"],
            "campaign_id": opened["run_id"],
            "implementation": "graphite-phase1-harness",
            "objective": "graphite-role:" + opened["role"]["name"],
            "sampling": "none",
            "control": "graphite-provider",
            "selection": "role-defined",
            "replica_policy": "none",
            "provider": opened["model"]["provider_id"],
            "owner": OWNER,
        }

    def _selection(self, model_id):
        return select(
            provider_id=self.adapter_id,
            model_id=model_id,
            credential={"kind": "file", "reference": self.model.credential_reference},
        )

    # -- the provider operations -----------------------------------------------------------
    def start(self, spec: TaskSpec, idempotency_key: str):
        if type(spec) is not TaskSpec:
            raise TypeError("exact TaskSpec required")
        identifier(idempotency_key, "idempotency_key")
        run_id = self.run_id_for(idempotency_key)
        directory = self._dir(run_id)
        if (directory / "session-open.json").is_file():
            opened = self._opened(run_id)
            if opened["idempotency_key"] != idempotency_key:
                raise ProviderUnavailable("run_id_collision")
            return self._handle(run_id)
        brief = self._brief(spec.instructions_digest)
        if brief is None:
            raise ProviderUnavailable("unknown_brief")
        role = ROLES[RoleName(brief["role"])]
        _check_role(role, spec)
        if (
            brief["role_prompt_digest"] != role.prompt_digest
            or brief["tool_manifest_digest"] != role.tool_manifest_digest
        ):
            # The brief was registered against another prompt or manifest.
            raise ProviderUnavailable("brief_role_changed")
        rung = self.ladder.rung(role.name)
        model_id = self.ladder.model(role.name)
        selection = self._selection(model_id)
        self.model.transport_for(selection)  # refuses before anything is opened
        opened = {
            "schema": SESSION_SCHEMA,
            "provider": PROVIDER,
            "run_id": run_id,
            "idempotency_key": idempotency_key,
            "task": dict(spec.__dict__),
            "role": {**role.record(), "rung": rung, "model": model_id},
            "model": selection.record(),
            "brief": {
                "digest": spec.instructions_digest,
                "initial_observation_digest": digest(
                    canonical(brief["initial_observation"])
                ),
            },
            "literature": {
                "snapshot_digest": self.literature.snapshot_digest,
                "label": self.literature.label,
            },
            "checkout": brief["checkout"],
            "grant": self._grant_record(),
            "caps": self.caps(),
            "live_inference": bool(self.model.live),
            "authority": {
                "evaluator": False,
                "official_material": False,
                "score": False,
                "reward": False,
            },
        }
        directory.mkdir(mode=0o700, exist_ok=True)
        write_once(directory / "session-open.json", canonical(opened))
        if not (directory / "state.json").exists():
            self._set_state(
                run_id, state="running", cancel_requested=False, failure=None
            )
        self._emit(
            run_id,
            "session-opened",
            {
                "kind": "session_opened",
                "session_open_digest": digest(canonical(opened)),
                "role": role.name.value,
                "model": model_id,
            },
        )
        self._crash("after_open")
        return self._handle(run_id)

    def _handle(self, run_id):
        return RunHandle(run_id, (run_id + "-worker",))

    def find(self, idempotency_key):
        identifier(idempotency_key, "idempotency_key")
        run_id = self.run_id_for(idempotency_key)
        if not (self._dir(run_id) / "session-open.json").is_file():
            return None
        return self._handle(run_id)

    def status(self, run_id):
        state = self._state(run_id)
        value = {
            "running": (
                RunState.CANCELLING if state["cancel_requested"] else RunState.RUNNING
            ),
            "succeeded": RunState.SUCCEEDED,
            "failed": RunState.FAILED,
            "cancelled": RunState.CANCELLED,
        }[state["state"]]
        return RunStatus(
            value, self._handle(run_id).worker_ids, run_id not in self._active
        )

    def events(self, run_id, after):
        path = self._dir(run_id) / "events.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_bytes().splitlines()[after:]]

    def artifacts(self, run_id):
        path = self._dir(run_id) / "graphite-session.json"
        if not path.is_file():
            return []
        return [Artifact("graphite-session.json", path.read_bytes())]

    def cancel(self, run_id):
        state = self._state(run_id)
        if state["state"] in _TERMINAL:
            return
        self._set_state(run_id, cancel_requested=True)
        self._emit(run_id, "cancel-requested", {"kind": "cancel_requested"})
        if run_id not in self._active:
            # No worker is executing: nothing to stop, so it is cancelled now.
            self._finish(run_id, "cancelled", None, None)

    def usage(self, run_id):
        settled, pending = self._spend(run_id)
        return Usage(
            True,
            Decimal(settled) / NANO_PER_USD,
            Decimal(pending) / NANO_PER_USD,
            self.grant.currency,
        )

    def _spend(self, run_id):
        """Settled and still-reserved nanodollars from the run's ledger."""
        self._opened(run_id)
        if not (self._dir(run_id) / "ledger" / "campaign.sqlite3").exists():
            return 0, 0
        settled = pending = 0
        for call in self._calls(run_id):
            if call["settlement"] is None:
                pending += call["reservation"].get("provider_nanodollars", 0)
            else:
                settled += call["settlement"].get("provider_nanodollars", 0)
        return settled, pending

    def _calls(self, run_id):
        ledger = CampaignLedger(self._dir(run_id) / "ledger", clock=self.clock)
        calls = []
        for op in ledger.status(owner=OWNER)["operations"]:
            if not op["reservation"].get("provider_attempts"):
                continue
            result = op["result"] or {}
            calls.append(
                {
                    "identity": op["id"],
                    "state": op["state"],
                    "reservation": op["reservation"],
                    "settlement": op["actual"],
                    "charge": result.get("charge"),
                    "usage": result.get("usage"),
                    "provider_model": result.get("provider_model"),
                    "provider_rejection": result.get("provider_rejection"),
                    "request_digest": result.get("request_digest"),
                    "response_digest": result.get("response_digest"),
                }
            )
        return calls

    # -- the worker --------------------------------------------------------------------------
    def run(self, run_id):
        """Execute (or resume) one session. Returns the final state."""
        state = self._state(run_id)
        if state["state"] in _TERMINAL:
            return state["state"]
        if state["cancel_requested"]:
            return self._finish(run_id, "cancelled", None, None)
        opened = self._opened(run_id)
        role = ROLES[RoleName(opened["role"]["name"])]
        try:
            brief = self._brief(opened["brief"]["digest"])
            if brief is None:
                raise SessionMismatch("brief_missing")
            selection = selection_from_record(
                opened["model"], credential_file=self.model.credential_reference
            )
            _verify(
                opened,
                role,
                selection.record(),
                self.literature.snapshot_digest,
                digest(canonical(brief)),
                {"grant": self._grant_record(), "caps": self.caps()},
            )
        except (SessionMismatch, ValueError) as error:
            code = (
                error.args[0]
                if type(error) is SessionMismatch
                else "model_selection_changed"
            )
            return self._finish(
                run_id,
                "failed",
                {"code": "session_record_mismatch", "detail": code},
                None,
            )
        ledger = self._ledger(run_id)
        ledger.freeze(self._manifest(opened))
        self._active.add(run_id)
        try:
            report = asyncio.run(self._epoch(run_id, ledger, role, brief, selection))
        except RunCancelled:
            return self._finish(run_id, "cancelled", None, None)
        except RunCapReached as error:
            return self._finish(
                run_id,
                "failed",
                {"code": "run_cap_reached", "dimension": error.dimension},
                None,
            )
        except ProviderCallFailed as error:
            # A rejection before generation is settled with no charge; any
            # other failure keeps its full reservation for reconciliation.
            unresolved = self._unresolved(run_id)
            return self._finish(
                run_id,
                "failed",
                {
                    "code": (
                        "reconciliation_required"
                        if unresolved
                        else "provider_call_failed"
                    ),
                    "outcome": error.outcome.value,
                },
                None,
            )
        except Exception as error:  # noqa: BLE001 - typed below, never echoed
            unresolved = self._unresolved(run_id)
            if (
                not unresolved
                and type(error) is ValueError
                and str(error) in _LIMIT_MESSAGES
            ):
                # The research layer refused the next call before reserving
                # it because the run's elapsed limit cannot hold it.
                return self._finish(
                    run_id,
                    "failed",
                    {
                        "code": "run_cap_reached",
                        "dimension": _LIMIT_MESSAGES[str(error)],
                    },
                    None,
                )
            return self._finish(
                run_id,
                "failed",
                {
                    "code": (
                        "reconciliation_required" if unresolved else "harness_error"
                    ),
                    "type": type(error).__name__,
                },
                None,
            )
        finally:
            self._active.discard(run_id)
        if report["status"] == "RECONCILIATION_REQUIRED":
            return self._finish(
                run_id, "failed", {"code": "reconciliation_required"}, report
            )
        return self._finish(run_id, "succeeded", None, report)

    async def _epoch(self, run_id, ledger, role, brief, selection):
        """One research epoch of the session: the role's toolbox as the loop's
        `sdk`, the role's prompt and closed tools. A later phase overrides
        this to attach what its role acts through (GRAPHITE-D18)."""
        sdk = toolbox.GraphiteToolbox(
            role=role,
            literature_index=self.literature,
            emit=lambda event_id, body: self._emit(run_id, event_id, body),
            miner_tools=self.miner_tools,
        )
        return await run_epoch(
            ledger,
            owner=OWNER,
            epoch=EPOCH,
            sdk=sdk,
            credential_file=None,
            initial_observation=brief["initial_observation"],
            transport=self.model.transport_for(selection),
            provider=selection,
            instructions=role.prompt,
            tools=role.tool_schemas(),
        )

    def _unresolved(self, run_id):
        """True when a reservation's outcome is unknown: it keeps its full
        amount and the run needs reconciliation."""
        return any(c["settlement"] is None for c in self._calls(run_id))

    def _finish(self, run_id, final, failure, report):
        self._crash("before_finish")
        directory = self._dir(run_id)
        record = self.session_record(run_id, final=final, failure=failure)
        record_digest = digest(canonical(record))
        for call in record["calls"]:
            self._emit(
                run_id,
                "call-" + call["identity"],
                {
                    "kind": "model_call",
                    "identity": call["identity"],
                    "state": call["state"],
                    "reservation": call["reservation"],
                    "settlement": call["settlement"],
                },
            )
        write_once(
            directory / "graphite-session.json",
            canonical(
                {
                    "schema": "carbon.graphite.session-export.v1",
                    "session_record": record,
                    "session_record_digest": record_digest,
                    "outcome": _outcome_view(report),
                    "authority_granted": False,
                }
            ),
        )
        self._emit(
            run_id,
            "session-closed",
            {
                "kind": "session_closed",
                "state": final,
                "failure": failure,
                "session_record_digest": record_digest,
            },
        )
        self._set_state(run_id, state=final, failure=failure)
        return final

    def session_record(self, run_id, *, final=None, failure=None):
        """The session record: the opening half plus every call's reservation
        and settlement and the outcome. Deterministic: canonical JSON with no
        wall-clock time and no local path."""
        opened = self._opened(run_id)
        ledger_exists = (self._dir(run_id) / "ledger" / "campaign.sqlite3").exists()
        state = self._state(run_id)
        outcome_path = self._dir(run_id) / "ledger" / f"epoch-{EPOCH}" / "outcome.json"
        return {
            **opened,
            "calls": self._calls(run_id) if ledger_exists else [],
            "outcome": {
                "state": final or state["state"],
                "failure": failure if final else state["failure"],
                "loop_outcome_digest": (
                    digest(outcome_path.read_bytes())
                    if outcome_path.is_file()
                    else None
                ),
            },
        }

    def session_record_digest(self, run_id):
        return digest(canonical(self.session_record(run_id)))


def _outcome_view(report):
    """The loop's outcome as returned data, without its accounting echo."""
    if report is None:
        return None
    return {
        key: value
        for key, value in report.items()
        if key not in ("accounting", "provider_turns", "caching")
    }
