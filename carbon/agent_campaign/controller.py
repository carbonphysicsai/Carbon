"""The durable campaign controller: Carbon supervises the external agent.

`carbon.miner_mcp.agent_connection` serves the protocol and deliberately does
not launch, supervise or stop an external agent. This controller does (handoff
§5). It is the only thing that dispatches work to a research-agent provider,
and it holds every limit outside the agent:

- **Intent before dispatch.** A run's idempotency key, reservation and spec are
  committed to the store before the provider is called.
- **Identities recorded.** The provider run id and worker ids are stored as
  soon as the provider returns them.
- **Ambiguity is reconciled, never retried blindly.** A timeout or a crash
  between intent and record leaves `DISPATCH_UNKNOWN`; only `reconcile` (which
  asks the provider by idempotency key) resolves it, and dispatch stays halted
  until it does. Nothing is ever restarted automatically.
- **Limits outside the agent.** Total spend (the grant's ceiling and each
  campaign's own owner-supplied ceiling), concurrency, runtime, run count and
  submissions. The permitted worst-case spend of a run is reserved before it
  launches; a launch that would let reservations plus settled spend plus the
  cleanup allowance exceed a ceiling is refused.
- **Unknown stops dispatch.** Unknown usage, unknown run state, unresolved
  dispatch and incomplete cleanup each halt new dispatch.
- **Cancellation is verified.** Cancel is recorded before the provider call;
  the run is `CANCELLED` only when the provider confirms every worker stopped,
  otherwise `CLEANUP_INCOMPLETE`, an actionable state that also halts dispatch.
  A closed chat session is not a stopped experiment.
- **Findings stop locking, not exploration** (OWNER-GRAPHITE-TEST-WAVE-03 §2).
  Emitted conditions (`carbon.battery.value.divergence`, canary exposure) are
  recorded as findings. No expansion on the LOCK path (`record_expansion`,
  Track A's `expansions`) may be recorded after one, mirroring
  `carbon.challenge_readiness.admission`. A development expansion
  (`record_development_expansion`) proceeds into its own ledger, and every
  result recorded while a finding is open (events, artifacts, terminal
  states and development expansions) is tagged with the open findings under
  `conditional-evidence.v1` (`carbon.challenge_readiness.conditional_evidence`).
  A finding is open until an operator records its repair (`record_repair`).
  It is never removed, and it keeps the LOCK path closed.
- **Everything the agent returns is data.** Events and artifacts are stored by
  digest and scanned for canaries; nothing in them is interpreted as a command.

The store lives under a private root (0700) that the agent's workspace never
contains. The attempt ledger is hash-chained: hashes show the ledger is
internally consistent; they do not authenticate an author or prove a run
occurred. Internal development only: no score, reward, qualification or chain
action follows from anything here.
"""

from __future__ import annotations

import datetime
import fcntl
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from enum import Enum
from pathlib import Path

from carbon.challenge_readiness import admission, conditional_evidence

from . import boundaries
from .grant import SpendingGrant
from .provider import (
    TERMINAL,
    ProviderError,
    ProviderTimeout,
    RunState,
    TaskSpec,
    digest_text,
    identifier,
    money,
)

#: v2: result entries (`RESULT_KINDS`) also carry `conditional_on` and
#: `conditional_policy` (conditional-evidence.v1); every other key is v1's.
ATTEMPT_SCHEMA = "carbon.agent-campaign.attempt.v2"
#: The ledger entries that are results of a run: what the agent returned and
#: how the run ended. Each is tagged with the findings open when it is recorded.
RESULT_KINDS = frozenset({"event", "artifact", "terminal"})
CRASH_POINTS = (
    "after_intent",
    "after_dispatch",
    "after_record",
    "after_cancel_request",
    "after_cancel_call",
    "after_settle",
)


class Phase(str, Enum):
    INTENT = "intent"
    DISPATCH_UNKNOWN = "dispatch_unknown"
    NOT_DISPATCHED = "not_dispatched"
    DISPATCHED = "dispatched"
    STATE_UNKNOWN = "state_unknown"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    CLEANUP_INCOMPLETE = "cleanup_incomplete"


#: Phases whose spend is not final and whose workers may be alive.
OPEN = frozenset(
    {
        Phase.INTENT,
        Phase.DISPATCH_UNKNOWN,
        Phase.DISPATCHED,
        Phase.STATE_UNKNOWN,
        Phase.CANCEL_REQUESTED,
        Phase.CLEANUP_INCOMPLETE,
    }
)
#: Phases that halt all new dispatch until resolved.
HALTING = frozenset(
    {
        Phase.INTENT,
        Phase.DISPATCH_UNKNOWN,
        Phase.STATE_UNKNOWN,
        Phase.CLEANUP_INCOMPLETE,
    }
)


class ControllerError(RuntimeError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class SimulatedCrash(BaseException):
    """Raised at a named lifecycle boundary in crash tests; a process death."""


def _now():
    return datetime.datetime.now(datetime.UTC)


def _stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class CampaignController:
    def __init__(
        self,
        *,
        root,
        provider,
        grant,
        operator,
        clock=_now,
        crash_at=None,
    ):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise ControllerError("controller_root_must_be_private_absolute")
        if type(grant) is not SpendingGrant:
            # No grant, no dispatch: a controller cannot exist without one.
            raise ControllerError("grant_required")
        capabilities = provider.capabilities()
        if capabilities.provider != grant.provider:
            raise ControllerError("grant_provider_mismatch")
        self.operator = identifier(operator, "operator")
        self.provider = provider
        self.capabilities = capabilities
        self.grant = grant
        self.clock = clock
        self.crash_at = crash_at
        if crash_at is not None and crash_at not in CRASH_POINTS:
            raise ValueError("unknown crash point")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self.root = root
        self.evidence = root / "evidence"
        self.evidence.mkdir(exist_ok=True, mode=0o700)
        self._lease = (root / "supervisor.lock").open("a+b")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lease.close()
            raise ControllerError("controller_already_active") from None
        self._database = root / "campaign.sqlite3"
        schema = sqlite3.connect(self._database)
        try:
            schema.executescript("""
                CREATE TABLE IF NOT EXISTS binding (id INTEGER PRIMARY KEY CHECK(id=1), grant_doc TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS campaigns (id TEXT PRIMARY KEY, role TEXT NOT NULL, workspace TEXT NOT NULL UNIQUE, credential TEXT NOT NULL UNIQUE, checkout TEXT NOT NULL, profile TEXT NOT NULL, ceiling TEXT NOT NULL, canaries TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reserved_identities (name TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS runs (key TEXT PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(id), spec TEXT NOT NULL, phase TEXT NOT NULL, run_id TEXT, workers TEXT, reserved TEXT NOT NULL, settled TEXT, usage_known INTEGER NOT NULL DEFAULT 1, started_at TEXT NOT NULL, events_seen INTEGER NOT NULL DEFAULT 0, artifacts_seen TEXT NOT NULL DEFAULT '[]');
                CREATE TABLE IF NOT EXISTS ledger (seq INTEGER PRIMARY KEY, body TEXT NOT NULL, hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS expansions (sequence INTEGER PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS findings (id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS development_expansions (sequence INTEGER PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS finding_states (seq INTEGER PRIMARY KEY, finding TEXT NOT NULL REFERENCES findings(id), state TEXT NOT NULL CHECK(state IN ('REPAIRED','RECURRED')), body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS halts (reason TEXT PRIMARY KEY, detail TEXT NOT NULL);
            """)
        finally:
            schema.close()
        with self._db() as db:
            row = db.execute("SELECT grant_doc FROM binding WHERE id=1").fetchone()
            document = _canonical(grant.document())
            if row is None:
                db.execute("INSERT INTO binding VALUES(1,?)", (document,))
            elif row[0] != document:
                raise ControllerError("grant_changed_under_existing_store")
        self._database.chmod(0o600)

    # -- plumbing --------------------------------------------------------------------
    @contextmanager
    def _db(self):
        db = sqlite3.connect(self._database, isolation_level=None)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def close(self):
        """Release the supervisor lease (also what a process death does)."""
        if not self._lease.closed:
            self._lease.close()

    def _crash(self, point):
        if self.crash_at == point:
            raise SimulatedCrash(point)

    def _append(self, db, **entry):
        row = db.execute("SELECT seq, hash FROM ledger ORDER BY seq DESC").fetchone()
        seq, previous = (0, "sha256:" + "0" * 64) if row is None else row
        body = {
            "schema": ATTEMPT_SCHEMA,
            "sequence": seq + 1,
            "recorded_at": _stamp(self.clock()),
            "previous": previous,
            "campaign_id": None,
            "run_key": None,
            "kind": None,
            "profile_digest": None,
            "artifact_digest": None,
            "execution_identity": None,
            "observed_result": None,
            "resource_use": None,
            "disposition": None,
            "evidence": [],
        }
        unknown = set(entry) - set(body)
        if unknown:
            raise ValueError("unknown ledger fields: " + ", ".join(sorted(unknown)))
        body.update(entry)
        if body["kind"] in RESULT_KINDS:
            body.update(conditional_evidence.tag(self._open_findings(db)))
        text = _canonical(body)
        digest = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        db.execute("INSERT INTO ledger VALUES(?,?,?)", (seq + 1, text, digest))

    def _store_evidence(self, body: bytes):
        digest = "sha256:" + hashlib.sha256(body).hexdigest()
        path = self.evidence / (digest.removeprefix("sha256:") + ".bin")
        if not path.exists():
            path.write_bytes(body)
            path.chmod(0o600)
        return {"path": str(path.relative_to(self.root)), "sha256": digest}

    # -- identities and campaigns --------------------------------------------------------
    def reserve_evaluation_identity(self, name):
        """Mark a workspace or credential as Carbon evaluation's; no campaign
        may ever use it."""
        identifier(name, "identity")
        with self._db() as db:
            used = db.execute(
                "SELECT 1 FROM campaigns WHERE workspace=? OR credential=?",
                (name, name),
            ).fetchone()
            if used:
                raise ControllerError("identity_already_used_by_a_campaign")
            db.execute("INSERT OR IGNORE INTO reserved_identities VALUES(?)", (name,))

    def register_campaign(
        self,
        campaign_id,
        *,
        role,
        workspace_id,
        credential_ref,
        checkout_digest,
        profile_digest,
        ceiling,
        canaries=(),
    ):
        """One campaign, one role, one workspace and one credential, never shared.

        `ceiling` is the owner's per-campaign monetary ceiling. It has no
        default: None (unset) refuses registration, so nothing dispatches."""
        identifier(campaign_id, "campaign_id")
        if type(role) is not boundaries.Role:
            raise TypeError("exact Role required")
        if role not in boundaries.AGENT_ROLES:
            raise ControllerError("evaluation_role_never_dispatched")
        identifier(workspace_id, "workspace_id")
        identifier(credential_ref, "credential_ref")
        digest_text(checkout_digest, "checkout_digest")
        digest_text(profile_digest, "profile_digest")
        if ceiling is None or ceiling == "HUMAN_INPUT":
            raise ControllerError("campaign_ceiling_unset")
        amount = money(ceiling)
        if amount <= 0 or amount + self.grant.cleanup_allowance > (
            self.grant.monetary_ceiling
        ):
            raise ControllerError("campaign_ceiling_outside_grant")
        with self._db() as db:
            for name in (workspace_id, credential_ref):
                if db.execute(
                    "SELECT 1 FROM reserved_identities WHERE name=?", (name,)
                ).fetchone():
                    raise ControllerError("evaluation_identity_refused")
            existing = db.execute(
                "SELECT id FROM campaigns WHERE id=? OR workspace=? OR credential=?",
                (campaign_id, workspace_id, credential_ref),
            ).fetchone()
            if existing:
                raise ControllerError("workspace_or_credential_shared")
            db.execute(
                "INSERT INTO campaigns VALUES(?,?,?,?,?,?,?,?)",
                (
                    campaign_id,
                    role.value,
                    workspace_id,
                    credential_ref,
                    checkout_digest,
                    profile_digest,
                    str(amount),
                    json.dumps(sorted(canaries)),
                ),
            )
            self._append(
                db,
                campaign_id=campaign_id,
                kind="campaign_registered",
                profile_digest=profile_digest,
                disposition="REGISTERED",
                observed_result={
                    "role": role.value,
                    "workspace_id": workspace_id,
                    "credential_ref": credential_ref,
                    "checkout_digest": checkout_digest,
                    "ceiling": str(amount),
                    "canaries": len(canaries),
                },
            )

    def _campaign(self, db, campaign_id):
        row = db.execute(
            "SELECT id, role, workspace, credential, checkout, profile, ceiling, canaries "
            "FROM campaigns WHERE id=?",
            (campaign_id,),
        ).fetchone()
        if row is None:
            raise ControllerError("unknown_campaign")
        keys = (
            "id",
            "role",
            "workspace",
            "credential",
            "checkout",
            "profile",
            "ceiling",
            "canaries",
        )
        campaign = dict(zip(keys, row))
        campaign["canaries"] = tuple(json.loads(campaign["canaries"]))
        return campaign

    def current_profile(self, db=None):
        """The permissions digest in force: the newest recorded expansion, or
        None when no expansion is recorded (each campaign's baseline holds)."""
        if db is None:
            with self._db() as connection:
                return self.current_profile(connection)
        row = db.execute(
            "SELECT body FROM expansions ORDER BY sequence DESC"
        ).fetchone()
        return None if row is None else json.loads(row[0])["permissions"]

    def development_profile(self, db=None):
        """The newest development expansion's permissions digest, or None.
        Development-only: it never changes `current_profile`."""
        if db is None:
            with self._db() as connection:
                return self.development_profile(connection)
        row = db.execute(
            "SELECT body FROM development_expansions ORDER BY sequence DESC"
        ).fetchone()
        return None if row is None else json.loads(row[0])["permissions"]

    # -- spending ------------------------------------------------------------------------
    @staticmethod
    def _committed(row):
        reserved = Decimal(row["reserved"])
        if row["settled"] is None:
            return reserved
        settled = Decimal(row["settled"])
        return settled if row["phase"] not in OPEN else max(settled, reserved)

    def _rows(self, db, where="", args=()):
        keys = (
            "key",
            "campaign",
            "spec",
            "phase",
            "run_id",
            "workers",
            "reserved",
            "settled",
            "usage_known",
            "started_at",
            "events_seen",
            "artifacts_seen",
        )
        return [
            dict(zip(keys, r))
            for r in db.execute(
                "SELECT "
                + ",".join(keys)
                + " FROM runs "
                + where
                + " ORDER BY started_at, key",
                args,
            ).fetchall()
        ]

    def budget(self):
        with self._db() as db:
            rows = self._rows(db)
            campaigns = {
                r[0]: Decimal(r[1])
                for r in db.execute("SELECT id, ceiling FROM campaigns").fetchall()
            }
        total = sum((self._committed(r) for r in rows), Decimal(0))
        per = {
            cid: sum(
                (self._committed(r) for r in rows if r["campaign"] == cid), Decimal(0)
            )
            for cid in campaigns
        }
        return {
            "currency": self.grant.currency,
            "grant_ceiling": str(self.grant.monetary_ceiling),
            "cleanup_allowance": str(self.grant.cleanup_allowance),
            "committed": str(total),
            "available": str(
                self.grant.monetary_ceiling - self.grant.cleanup_allowance - total
            ),
            "campaigns": {
                cid: {"ceiling": str(campaigns[cid]), "committed": str(per[cid])}
                for cid in sorted(campaigns)
            },
            "basis": (
                "committed = settled spend of closed runs plus, for open runs, the "
                "larger of the reservation and reported spend"
            ),
        }

    # -- halts -------------------------------------------------------------------------
    def halts(self):
        """Every reason dispatch is stopped now, with what would clear it."""
        with self._db() as db:
            return self._halts(db)

    def _halts(self, db):
        found = []
        for row in self._rows(db):
            phase = Phase(row["phase"])
            if phase in HALTING:
                found.append(f"run {row['key']}: {phase.value}")
            elif not row["usage_known"]:
                found.append(f"run {row['key']}: usage_unknown")
        for reason, detail in db.execute("SELECT reason, detail FROM halts"):
            found.append(f"{reason}: {detail}")
        return found

    def clear_halt(self, reason, *, operator, note):
        """An operator clears a persistent halt (for example after exposure
        is investigated). The finding that caused it is never removed."""
        if operator != self.operator:
            raise ControllerError("operator_required")
        if type(note) is not str or len(note.strip()) < 20:
            raise ControllerError("say why the halt is cleared")
        with self._db() as db:
            if not db.execute("DELETE FROM halts WHERE reason=?", (reason,)).rowcount:
                raise ControllerError("no_such_halt")
            self._append(
                db,
                kind="halt_cleared",
                disposition="CLEARED",
                observed_result={
                    "reason": reason,
                    "operator": operator,
                    "note": note.strip(),
                },
            )

    # -- the protections, one place each ----------------------------------------------
    @staticmethod
    def _check_session(spec, campaign):
        """A task reaches only its own campaign's role, workspace and credential."""
        if (
            spec.role != campaign["role"]
            or spec.workspace_id != campaign["workspace"]
            or spec.credential_ref != campaign["credential"]
        ):
            raise ControllerError("cross_session_access_refused")

    @staticmethod
    def _stopped(status):
        """Stopped means terminal and every worker confirmed stopped."""
        return status.state in TERMINAL and status.workers_terminated is True

    @staticmethod
    def _expansion_blocked(db):
        """Any finding, repaired or not, blocks every later LOCK-path
        expansion. Development expansions are tagged instead."""
        return bool(db.execute("SELECT COUNT(*) FROM findings").fetchone()[0])

    # -- launch ------------------------------------------------------------------------
    def launch(self, spec: TaskSpec, idempotency_key: str):
        """Persist intent, reserve worst-case spend, then dispatch once."""
        if type(spec) is not TaskSpec:
            raise TypeError("exact TaskSpec required")
        identifier(idempotency_key, "idempotency_key")
        if not self.capabilities.dispatchable:
            raise ControllerError("provider_not_dispatchable", self.capabilities.basis)
        moment = self.clock()
        with self._db() as db:
            existing = self._rows(db, "WHERE key=?", (idempotency_key,))
            if existing:
                # Idempotent: the same key never dispatches twice.
                return existing[0]["phase"]
            campaign = self._campaign(db, spec.campaign_id)
            self._check_session(spec, campaign)
            profile = self.current_profile(db) or campaign["profile"]
            # Exploration may also run under the newest development profile
            # (OWNER-GRAPHITE-TEST-WAVE-03 §2); only Carbon's own campaigns
            # are ever dispatched here.
            if spec.profile_digest not in (profile, self.development_profile(db)):
                raise ControllerError("profile_not_in_force")
            halts = self._halts(db)
            if halts:
                raise ControllerError("dispatch_halted", "; ".join(halts))
            if moment >= self.grant.expires_at:
                raise ControllerError("grant_expired")
            if spec.max_runtime_s > self.grant.max_runtime_s:
                raise ControllerError("runtime_above_grant")
            rows = self._rows(db)
            if len(rows) >= self.grant.permitted_runs:
                raise ControllerError("run_limit_reached")
            if (
                sum(Phase(r["phase"]) in OPEN for r in rows)
                >= self.grant.max_concurrency
            ):
                raise ControllerError("concurrency_limit_reached")
            reserve = self.grant.worst_case_run_cost
            total = sum((self._committed(r) for r in rows), Decimal(0))
            if (
                total + reserve + self.grant.cleanup_allowance
                > self.grant.monetary_ceiling
            ):
                raise ControllerError("grant_ceiling_reached")
            mine = sum(
                (self._committed(r) for r in rows if r["campaign"] == spec.campaign_id),
                Decimal(0),
            )
            if mine + reserve > Decimal(campaign["ceiling"]):
                raise ControllerError("campaign_ceiling_reached")
            db.execute(
                "INSERT INTO runs(key,campaign,spec,phase,reserved,started_at) VALUES(?,?,?,?,?,?)",
                (
                    idempotency_key,
                    spec.campaign_id,
                    _canonical(spec.__dict__),
                    Phase.INTENT.value,
                    str(reserve),
                    _stamp(moment),
                ),
            )
            self._append(
                db,
                campaign_id=spec.campaign_id,
                run_key=idempotency_key,
                kind="launch_intent",
                profile_digest=spec.profile_digest,
                resource_use={"reserved": str(reserve)},
                disposition="INTENT_RECORDED",
            )
        self._crash("after_intent")
        try:
            handle = self.provider.start(spec, idempotency_key)
        except ProviderTimeout:
            self._set(
                idempotency_key,
                Phase.DISPATCH_UNKNOWN,
                kind="dispatch_timeout",
                disposition="DISPATCH_UNKNOWN",
            )
            return Phase.DISPATCH_UNKNOWN.value
        except ProviderError as error:
            # Refused before taking effect only when the adapter says so;
            # any other failure is ambiguous.
            self._set(
                idempotency_key,
                Phase.DISPATCH_UNKNOWN,
                kind="dispatch_error",
                disposition="DISPATCH_UNKNOWN",
                observed_result={"error": type(error).__name__},
            )
            return Phase.DISPATCH_UNKNOWN.value
        self._crash("after_dispatch")
        self._record_handle(idempotency_key, handle, kind="dispatched")
        self._crash("after_record")
        return Phase.DISPATCHED.value

    def _set(self, key, phase, **entry):
        with self._db() as db:
            db.execute("UPDATE runs SET phase=? WHERE key=?", (phase.value, key))
            row = self._rows(db, "WHERE key=?", (key,))[0]
            self._append(db, campaign_id=row["campaign"], run_key=key, **entry)

    def _record_handle(self, key, handle, *, kind):
        with self._db() as db:
            row = self._rows(db, "WHERE key=?", (key,))[0]
            if row["run_id"] not in (None, handle.provider_run_id):
                raise ControllerError("provider_run_id_changed")
            db.execute(
                "UPDATE runs SET phase=?, run_id=?, workers=? WHERE key=?",
                (
                    Phase.DISPATCHED.value,
                    handle.provider_run_id,
                    json.dumps(list(handle.worker_ids)),
                    key,
                ),
            )
            self._append(
                db,
                campaign_id=row["campaign"],
                run_key=key,
                kind=kind,
                profile_digest=json.loads(row["spec"])["profile_digest"],
                execution_identity={
                    "provider": self.capabilities.provider,
                    "provider_run_id": handle.provider_run_id,
                    "worker_ids": list(handle.worker_ids),
                },
                disposition="DISPATCHED",
            )

    # -- reconciliation and polling ----------------------------------------------------
    def reconcile(self, key):
        """Resolve an ambiguous dispatch by asking the provider by key."""
        with self._db() as db:
            row = self._rows(db, "WHERE key=?", (key,))[0]
        if Phase(row["phase"]) not in (Phase.INTENT, Phase.DISPATCH_UNKNOWN):
            return row["phase"]
        try:
            handle = self.provider.find(key)
        except ProviderError:
            return row["phase"]
        if handle is None:
            with self._db() as db:
                db.execute(
                    "UPDATE runs SET phase=?, settled='0' WHERE key=?",
                    (Phase.NOT_DISPATCHED.value, key),
                )
                self._append(
                    db,
                    campaign_id=row["campaign"],
                    run_key=key,
                    kind="reconciled",
                    observed_result={"provider_has_run": False},
                    disposition="NOT_DISPATCHED",
                )
            return Phase.NOT_DISPATCHED.value
        self._record_handle(key, handle, kind="reconciled")
        return Phase.DISPATCHED.value

    def poll(self, key):
        """Read status, events, artifacts and usage for one run."""
        with self._db() as db:
            row = self._rows(db, "WHERE key=?", (key,))[0]
            campaign = self._campaign(db, row["campaign"])
        phase = Phase(row["phase"])
        if phase not in (Phase.DISPATCHED, Phase.STATE_UNKNOWN):
            return phase.value
        run_id = row["run_id"]
        try:
            status = self.provider.status(run_id)
        except ProviderError:
            self._set(
                key,
                Phase.STATE_UNKNOWN,
                kind="status_error",
                disposition="STATE_UNKNOWN",
            )
            return Phase.STATE_UNKNOWN.value
        self._ingest(row, campaign)
        if status.state is RunState.UNKNOWN:
            self._set(
                key,
                Phase.STATE_UNKNOWN,
                kind="status",
                observed_result={"state": "unknown"},
                disposition="STATE_UNKNOWN",
            )
            return Phase.STATE_UNKNOWN.value
        if status.state in TERMINAL:
            final = (
                Phase.COMPLETED
                if status.state is RunState.SUCCEEDED
                else (
                    Phase.FAILED if status.state is RunState.FAILED else Phase.CANCELLED
                )
            )
            if not self._stopped(status):
                final = Phase.CLEANUP_INCOMPLETE
            self._settle(key, final, status)
            return final.value
        started = datetime.datetime.strptime(
            row["started_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=datetime.UTC)
        limit = min(json.loads(row["spec"])["max_runtime_s"], self.grant.max_runtime_s)
        if (self.clock() - started).total_seconds() > limit:
            return self.cancel(key, reason="runtime_limit")
        if phase is Phase.STATE_UNKNOWN:
            self._set(
                key,
                Phase.DISPATCHED,
                kind="status",
                observed_result={"state": status.state.value},
                disposition="STATE_KNOWN_AGAIN",
            )
        self._usage(key, row)
        return Phase.DISPATCHED.value

    def _usage(self, key, row):
        try:
            usage = self.provider.usage(row["run_id"])
        except ProviderError:
            usage = None
        known = usage is not None and usage.known
        with self._db() as db:
            if known:
                db.execute(
                    "UPDATE runs SET usage_known=1, settled=? WHERE key=?",
                    (str(usage.settled + usage.pending), key),
                )
            else:
                db.execute("UPDATE runs SET usage_known=0 WHERE key=?", (key,))
            self._append(
                db,
                campaign_id=row["campaign"],
                run_key=key,
                kind="usage",
                resource_use=(
                    {"known": False}
                    if not known
                    else {
                        "known": True,
                        "settled": str(usage.settled),
                        "pending": str(usage.pending),
                        "units": usage.units,
                    }
                ),
                disposition="USAGE_KNOWN" if known else "USAGE_UNKNOWN",
            )
        return usage if known else None

    def _settle(self, key, final, status):
        with self._db() as db:
            row = self._rows(db, "WHERE key=?", (key,))[0]
        usage = self._usage(key, row)
        with self._db() as db:
            db.execute("UPDATE runs SET phase=? WHERE key=?", (final.value, key))
            if usage is not None:
                db.execute(
                    "UPDATE runs SET settled=? WHERE key=?",
                    (str(usage.settled + usage.pending), key),
                )
            self._append(
                db,
                campaign_id=row["campaign"],
                run_key=key,
                kind="terminal",
                execution_identity={
                    "provider_run_id": row["run_id"],
                    "worker_ids": list(status.worker_ids),
                    "workers_terminated": status.workers_terminated,
                },
                observed_result={"state": status.state.value},
                disposition=final.value.upper(),
            )
        self._crash("after_settle")

    def _ingest(self, row, campaign):
        """Store events and artifacts by digest; scan for canaries. Nothing in
        them is interpreted as an instruction."""
        run_id = row["run_id"]
        try:
            events = self.provider.events(run_id, row["events_seen"])
            artifacts = self.provider.artifacts(run_id)
        except ProviderError:
            return
        seen = set(json.loads(row["artifacts_seen"]))
        with self._db() as db:
            for event in events:
                body = _canonical(event).encode()
                ref = self._store_evidence(body)
                hits = boundaries.exposed(body, campaign["canaries"])
                self._append(
                    db,
                    campaign_id=row["campaign"],
                    run_key=row["key"],
                    kind="event",
                    evidence=[ref],
                    disposition="CANARY_EXPOSED" if hits else "RECORDED_AS_DATA",
                )
                if hits:
                    self._exposure(db, row, ref)
            submitted = db.execute(
                "SELECT COUNT(*) FROM ledger WHERE json_extract(body,'$.kind')='artifact' "
                "AND json_extract(body,'$.disposition')='SUBMITTED'"
            ).fetchone()[0]
            for artifact in artifacts:
                if artifact.sha256 in seen:
                    continue
                seen.add(artifact.sha256)
                ref = self._store_evidence(artifact.body)
                hits = boundaries.exposed(artifact.body, campaign["canaries"])
                if hits:
                    disposition = "CANARY_EXPOSED"
                elif submitted >= self.grant.max_submissions:
                    disposition = "REJECTED_SUBMISSION_LIMIT"
                else:
                    disposition = "SUBMITTED"
                    submitted += 1
                self._append(
                    db,
                    campaign_id=row["campaign"],
                    run_key=row["key"],
                    kind="artifact",
                    profile_digest=json.loads(row["spec"])["profile_digest"],
                    artifact_digest=artifact.sha256,
                    execution_identity={"provider_run_id": run_id},
                    evidence=[ref],
                    disposition=disposition,
                )
                if hits:
                    self._exposure(db, row, ref)
            db.execute(
                "UPDATE runs SET events_seen=?, artifacts_seen=? WHERE key=?",
                (
                    row["events_seen"] + len(events),
                    json.dumps(sorted(seen)),
                    row["key"],
                ),
            )

    def _exposure(self, db, row, ref):
        ordinal = db.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        self._finding(
            db,
            "canary-" + ref["sha256"].removeprefix("sha256:")[:16],
            "OTHER_SIGNAL",
            ref,
            ordinal,
        )
        db.execute(
            "INSERT OR REPLACE INTO halts VALUES(?,?)",
            (
                "protected_data_exposure",
                f"canary in run {row['key']} evidence {ref['sha256']}",
            ),
        )

    # -- cancellation ------------------------------------------------------------------
    def cancel(self, key, *, reason="operator"):
        """Record the request, ask the provider, then verify the workers."""
        with self._db() as db:
            row = self._rows(db, "WHERE key=?", (key,))[0]
            if Phase(row["phase"]) not in OPEN:
                return row["phase"]  # already closed; nothing to stop
            if row["run_id"] is None:
                raise ControllerError("reconcile_before_cancel")
            db.execute(
                "UPDATE runs SET phase=? WHERE key=?",
                (Phase.CANCEL_REQUESTED.value, key),
            )
            self._append(
                db,
                campaign_id=row["campaign"],
                run_key=key,
                kind="cancel_requested",
                observed_result={"reason": reason},
                disposition="CANCEL_REQUESTED",
            )
        self._crash("after_cancel_request")
        try:
            self.provider.cancel(row["run_id"])
        except ProviderError:
            return Phase.CANCEL_REQUESTED.value
        self._crash("after_cancel_call")
        return self.verify_cancel(key)

    def verify_cancel(self, key):
        with self._db() as db:
            row = self._rows(db, "WHERE key=?", (key,))[0]
        try:
            status = self.provider.status(row["run_id"])
        except ProviderError:
            return row["phase"]
        if self._stopped(status):
            self._settle(key, Phase.CANCELLED, status)
            return Phase.CANCELLED.value
        with self._db() as db:
            db.execute(
                "UPDATE runs SET phase=? WHERE key=?",
                (Phase.CLEANUP_INCOMPLETE.value, key),
            )
            self._append(
                db,
                campaign_id=row["campaign"],
                run_key=key,
                kind="cleanup_check",
                execution_identity={
                    "provider_run_id": row["run_id"],
                    "worker_ids": list(status.worker_ids),
                    "workers_terminated": status.workers_terminated,
                },
                observed_result={"state": status.state.value},
                disposition="CLEANUP_INCOMPLETE",
            )
        return Phase.CLEANUP_INCOMPLETE.value

    def cleanup_actions(self):
        """What an operator must do: every run whose workers are not confirmed
        stopped, with its identities."""
        with self._db() as db:
            rows = self._rows(db, "WHERE phase=?", (Phase.CLEANUP_INCOMPLETE.value,))
        return [
            {
                "run_key": r["key"],
                "provider": self.capabilities.provider,
                "provider_run_id": r["run_id"],
                "worker_ids": json.loads(r["workers"] or "[]"),
                "action": "confirm every worker is stopped, then verify_cancel",
            }
            for r in rows
        ]

    # -- recovery ----------------------------------------------------------------------
    def recover(self):
        """After a restart: resolve every open run from the provider's state.
        Never restarts a run."""
        with self._db() as db:
            rows = self._rows(db)
            self._append(db, kind="recovery_started", disposition="RECOVERING")
        out = {}
        for row in rows:
            phase = Phase(row["phase"])
            if phase in (Phase.INTENT, Phase.DISPATCH_UNKNOWN):
                out[row["key"]] = self.reconcile(row["key"])
            elif phase in (Phase.DISPATCHED, Phase.STATE_UNKNOWN):
                out[row["key"]] = self.poll(row["key"])
            elif phase is Phase.CANCEL_REQUESTED:
                out[row["key"]] = self.cancel(row["key"], reason="recovery")
            elif phase is Phase.CLEANUP_INCOMPLETE:
                out[row["key"]] = self.verify_cancel(row["key"])
        return out

    # -- findings and expansions -------------------------------------------------------
    def _finding(self, db, finding_id, condition, ref, ordinal):
        if condition not in admission.CONDITIONS:
            raise ControllerError("unknown_condition")
        if db.execute("SELECT 1 FROM findings WHERE id=?", (finding_id,)).fetchone():
            if self._repaired(db, finding_id):
                self._recur(db, finding_id, condition, ref)
            return
        after = db.execute("SELECT COUNT(*) FROM expansions").fetchone()[0]
        body = {
            "id": finding_id,
            "condition": condition,
            "after_expansion": after,
            "evidence": ref,
        }
        db.execute(
            "INSERT INTO findings VALUES(?,?,?)",
            (finding_id, ordinal, _canonical(body)),
        )
        self._append(
            db,
            kind="finding",
            observed_result={"id": finding_id, "condition": condition},
            evidence=[ref],
            disposition="EXPANSION_BLOCKED",
        )

    def _finding_body(self, db, finding_id):
        row = db.execute(
            "SELECT body FROM findings WHERE id=?", (finding_id,)
        ).fetchone()
        return None if row is None else json.loads(row[0])

    @staticmethod
    def _repaired(db, finding_id):
        """Whether the finding's latest state is a recorded repair."""
        row = db.execute(
            "SELECT state FROM finding_states WHERE finding=? ORDER BY seq DESC",
            (finding_id,),
        ).fetchone()
        return row is not None and row[0] == "REPAIRED"

    def _recur(self, db, finding_id, condition, ref):
        """A repaired finding recorded again is open again; the repair stays."""
        body = {
            "finding": conditional_evidence.reference(
                self._finding_body(db, finding_id)
            ),
            "evidence": ref,
            "recorded_at": _stamp(self.clock()),
        }
        db.execute(
            "INSERT INTO finding_states(finding, state, body) VALUES(?,?,?)",
            (finding_id, "RECURRED", _canonical(body)),
        )
        self._append(
            db,
            kind="finding_recurred",
            observed_result={"id": finding_id, "condition": condition},
            evidence=[ref],
            disposition="FINDING_REOPENED",
        )

    def _open_findings(self, db):
        return [
            conditional_evidence.reference(json.loads(body))
            for finding_id, body in db.execute(
                "SELECT id, body FROM findings ORDER BY ordinal"
            ).fetchall()
            if not self._repaired(db, finding_id)
        ]

    def open_findings(self):
        """Every open finding as `{id, digest}` (conditional-evidence.v1):
        recorded and not repaired since."""
        with self._db() as db:
            return conditional_evidence.tag(self._open_findings(db))["conditional_on"]

    def record_repair(self, finding_id, *, operator, note, evidence: bytes):
        """An operator records that a finding is repaired and its affected
        attacks re-run (OWNER-GRAPHITE-TEST-WAVE-03 §2), with the re-run's
        evidence. Later results are no longer conditional on it. The finding
        stays in the findings ledger and still blocks every LOCK-path
        expansion; one that is recorded again is open again."""
        if operator != self.operator:
            raise ControllerError("operator_required")
        if type(note) is not str or len(note.strip()) < 20:
            raise ControllerError("say what was repaired and which attacks were re-run")
        if type(evidence) is not bytes or not evidence:
            raise ControllerError("repair_evidence_required")
        with self._db() as db:
            finding = self._finding_body(db, finding_id)
            if finding is None:
                raise ControllerError("no_such_finding")
            if self._repaired(db, finding_id):
                raise ControllerError("finding_already_repaired")
            ref = self._store_evidence(evidence)
            body = {
                "finding": conditional_evidence.reference(finding),
                "operator": operator,
                "note": note.strip(),
                "rerun_evidence": ref,
                "recorded_at": _stamp(self.clock()),
                "policy": conditional_evidence.identity(),
            }
            db.execute(
                "INSERT INTO finding_states(finding, state, body) VALUES(?,?,?)",
                (finding_id, "REPAIRED", _canonical(body)),
            )
            self._append(
                db,
                kind="finding_repaired",
                observed_result=body,
                evidence=[ref],
                disposition="REPAIR_RECORDED",
            )
        return body

    def record_finding(self, finding_id, condition, evidence: bytes):
        identifier(finding_id, "finding id")
        with self._db() as db:
            ordinal = db.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            self._finding(
                db, finding_id, condition, self._store_evidence(evidence), ordinal
            )

    def consume_conditions(self, report_path):
        """Record every condition a divergence report emits as a finding,
        bound to the report's bytes. Returns the finding ids."""
        body = Path(report_path).read_bytes()
        report = json.loads(body)
        if report.get("schema") != "carbon.admission-conditions.v1":
            raise ControllerError("unsupported_conditions_report")
        ids = []
        with self._db() as db:
            ref = self._store_evidence(body)
            for index, condition in enumerate(report["conditions"]):
                finding_id = "{}-{}-{}".format(
                    ref["sha256"].removeprefix("sha256:")[:12],
                    index,
                    condition["condition"],
                )
                ordinal = db.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
                self._finding(db, finding_id, condition["condition"], ref, ordinal)
                ids.append(finding_id)
        return ids

    def _bound_version(self, challenge, permissions, operator):
        """The operator, the permissions digest and the challenge's newest
        recorded construction contract (#468), as the entry's `version`."""
        from carbon.reconstruction import expansion_record

        if operator != self.operator:
            raise ControllerError("operator_required")
        digest_text(permissions, "permissions")
        unrecorded = expansion_record.unrecorded()
        if challenge in unrecorded:
            raise ControllerError(
                "construction_contract_unrecorded", unrecorded[challenge]
            )
        history = expansion_record.records(challenge)
        if not history:
            raise ControllerError("construction_contract_unrecorded", challenge)
        newest = history[-1]
        return "{}/{:04d} {}".format(
            challenge, newest["sequence"], newest["contract_digest"]
        )

    def record_expansion(self, *, challenge, profile, widened, permissions, operator):
        """Append a widening of the permission profile on the LOCK path
        (Track A's `expansions`: what may be locked, opened to miners or feed
        a frozen run). Refused after any finding, and refused unless the
        challenge's live construction contract is recorded (#468), whose
        newest record the entry binds."""
        version = self._bound_version(challenge, permissions, operator)
        with self._db() as db:
            if self._expansion_blocked(db):
                raise ControllerError("admission_expansion_after_finding")
            sequence = db.execute("SELECT COUNT(*) FROM expansions").fetchone()[0] + 1
            entry = {
                "sequence": sequence,
                "recorded_at": _stamp(self.clock()),
                "profile": profile,
                "version": version,
                "widened": widened,
                "permissions": permissions,
            }
            existing = [
                json.loads(r[0])
                for r in db.execute("SELECT body FROM expansions ORDER BY sequence")
            ]
            admission._expansions([*existing, entry])
            db.execute(
                "INSERT INTO expansions VALUES(?,?)", (sequence, _canonical(entry))
            )
            self._append(
                db,
                kind="expansion",
                profile_digest=permissions,
                observed_result=entry,
                disposition="RECORDED",
            )
        return entry

    def record_development_expansion(
        self, *, challenge, profile, widened, permissions, operator
    ):
        """Append a widening for a development-only contract variant, which
        only Carbon's own campaigns run (OWNER-GRAPHITE-TEST-WAVE-03 §1-2).

        It proceeds while findings are open and is tagged with them
        (conditional-evidence.v1). It is recorded in the development ledger,
        never in Track A's `expansions`: it never counts toward or enters a
        LOCK, never changes `current_profile` and never reaches a miner."""
        version = self._bound_version(challenge, permissions, operator)
        with self._db() as db:
            existing = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT body FROM development_expansions ORDER BY sequence"
                )
            ]
            entry = {
                "sequence": len(existing) + 1,
                "recorded_at": _stamp(self.clock()),
                "kind": conditional_evidence.DEVELOPMENT_KIND,
                "profile": profile,
                "version": version,
                "widened": widened,
                "permissions": permissions,
                **conditional_evidence.tag(self._open_findings(db)),
            }
            conditional_evidence.validate_development_ledger([*existing, entry])
            db.execute(
                "INSERT INTO development_expansions VALUES(?,?)",
                (entry["sequence"], _canonical(entry)),
            )
            self._append(
                db,
                kind="development_expansion",
                profile_digest=permissions,
                observed_result=entry,
                disposition=(
                    "RECORDED_CONDITIONAL" if entry["conditional_on"] else "RECORDED"
                ),
            )
        return entry

    def development_ledger(self):
        """The development expansions, validated, with the findings open now
        and the policy identity. Never part of `admission_ledgers`."""
        with self._db() as db:
            expansions = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT body FROM development_expansions ORDER BY sequence"
                )
            ]
            open_now = self._open_findings(db)
        conditional_evidence.validate_development_ledger(expansions)
        return {
            "expansions": expansions,
            "expansions_digest": admission.ledger_digest(expansions),
            "open_findings": conditional_evidence.tag(open_now)["conditional_on"],
            "policy": conditional_evidence.identity(),
        }

    def admission_ledgers(self):
        """Track A's `expansions` and `findings`, validated exactly as
        `carbon.challenge_readiness.admission` validates them (evidence paths
        are relative to this controller's root). Development expansions are
        never here (`development_ledger`)."""
        with self._db() as db:
            expansions = [
                json.loads(r[0])
                for r in db.execute("SELECT body FROM expansions ORDER BY sequence")
            ]
            findings = [
                json.loads(r[0])
                for r in db.execute("SELECT body FROM findings ORDER BY ordinal")
            ]
        admission._expansions(expansions)
        admission._findings(findings, expansions, self.root)
        return {
            "expansions": expansions,
            "findings": findings,
            "expansions_digest": admission.ledger_digest(expansions),
            "findings_digest": admission.ledger_digest(findings),
        }

    # -- ledger --------------------------------------------------------------------------
    def ledger(self):
        with self._db() as db:
            rows = db.execute("SELECT body, hash FROM ledger ORDER BY seq").fetchall()
        return [json.loads(body) for body, _ in rows]

    def verify_ledger(self):
        """Recompute the hash chain. Consistency only: a hash does not
        authenticate who wrote an entry or prove a run happened."""
        with self._db() as db:
            rows = db.execute(
                "SELECT seq, body, hash FROM ledger ORDER BY seq"
            ).fetchall()
        previous = "sha256:" + "0" * 64
        for index, (seq, body, digest) in enumerate(rows, start=1):
            entry = json.loads(body)
            if (
                seq != index
                or entry["sequence"] != index
                or entry["previous"] != previous
                or "sha256:" + hashlib.sha256(body.encode()).hexdigest() != digest
            ):
                return {"consistent": False, "entries": len(rows), "first_bad": seq}
            previous = digest
        return {"consistent": True, "entries": len(rows), "first_bad": None}
