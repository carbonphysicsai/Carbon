"""One long-lived supervisor owns a runner's campaign threads (LP-PROD-C).

A campaign's work - the launch that prepares it, Carbon's agent loop, a
miner's practice, freeze or submit - runs on a thread for minutes or hours.
Before this module that thread lived in whichever process received the
request, including a short-lived MCP stdio process: when the miner's client
exited, the thread died with it, a launch was left QUEUED with no frozen
manifest, and closing a client sent every live campaign an irreversible stop.

Now one process per runner database and principal supervises:

- **The Control Center**, while it runs, is the supervisor (`SUPERVISOR`).
  It starts its own requests on its own threads and drains everything other
  clients queue.
- **Otherwise a detached supervisor** (`DETACHED`) does: a client that queues
  work and finds no supervisor alive starts
  ``python -m scripts.dev.miner_launchpad.supervisor --configuration PROFILE``
  in a new session, so it outlives the client. It exits once nothing is
  queued and none of its threads is alive.
- **Clients** (`CLIENT`: every MCP door) never own a campaign thread. They
  run the operations table's gates, record what was admitted in the queue
  below, wake or start the supervisor, and observe.

Exactly one supervisor holds the lock for a runner database and principal at
a time: an OS lock (`controller.owner_lock`) in a directory beside the
database, released by the OS when its process exits. Only the holder starts
queued work, and only the holder recovers campaigns a dead process left
behind, because only then is every earlier holder known to be gone.

**A Control Center that starts while a detached supervisor holds the lock
takes over** (the handover): it holds a second OS lock, its presence, for as
long as it runs. A detached supervisor that sees it starts nothing more,
pauses Carbon's agent in each campaign it runs (`paused_for_handover`), lets
the miner's operations finish, then releases the lock and exits; the Control
Center takes the lock and resumes what was paused for it. Until then the
Control Center queues its own work like a client, and if it closes first,
what it admitted is withdrawn or paused, as closing it would pause what it
supervised.

The queue (`launchpad_dispatch`, in the runner's own database) holds what a
client admitted, not authority: the supervisor re-reads the runner profile,
refuses an item admitted under a different profile, and re-reads the chain for
a launch it rebuilds (`RunnerAdapter._recorded_launch`). A claimed item is
never started twice. One whose supervisor died is marked interrupted and never
replayed: the campaign's ledger, not the queue, says what may have been
dispatched. (A launch that died before it was prepared, with nothing
outstanding, is carried out again once, as a new item: nothing could have been
dispatched for it. See `RunnerAdapter._redispatch_stranded`.)

`INLINE` is the historical single-process behaviour, kept for fixtures and
tests that drive a host directly: it starts its own threads and recovers at
construction, but never re-dispatches.

Refusals that happen on a supervisor thread, where no caller can see them,
are kept as the campaign's `last_refusal`: a closed code, the next action
from `NEXT_ACTIONS`, and when (`refusal`). No exception text, provider
response or path is ever kept. A refusal returned to its caller stays the
caller's `{error}`; the same table, served as the refusal catalog
(`catalog`, `GET /api/v1/refusals`), says what to do next for any code.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import signal
import sys
import threading
import time
from pathlib import Path

INLINE, SUPERVISOR, DETACHED, CLIENT = "inline", "supervisor", "detached", "client"
ROLES = (INLINE, SUPERVISOR, DETACHED, CLIENT)
#: How often a supervisor looks for queued work when nothing wakes it.
POLL_SECONDS = 0.5
#: How long a detached supervisor stays with nothing queued and no live
#: thread before it exits.
IDLE_EXIT_SECONDS = 10.0
#: How long a starting (or re-arming) supervisor keeps trying for the lock.
#: A client's liveness probe holds it for microseconds; a supervisor holds it
#: for its whole life, so a few seconds tells the two apart.
ACQUIRE_SECONDS = 3.0
#: How long closing a supervisor waits for its paused threads to settle.
CLOSE_JOIN_SECONDS = 5.0

#: Queue item states. A QUEUED item is admitted and not started; RUNNING was
#: claimed by one supervisor; DONE never runs again.
QUEUED, RUNNING, DONE = "QUEUED", "RUNNING", "DONE"
#: The `last_refusal` a detached supervisor records on a campaign whose agent
#: it paused so a starting Control Center could take it over. Only a Control
#: Center resumes it; any other supervisor keeps the pause (D4).
HANDED_OVER = "paused_for_handover"
#: What a queue item carries out: the campaign's run (a launch or resume), or
#: one of a miner's operations.
OPERATIONS = ("run", "practice", "freeze_candidate", "submit")

#: Ledger control states in which some process was working when it last
#: wrote. Seen by a supervisor holding the campaign's free ownership lock,
#: they are stale: that process is gone.
IN_FLIGHT = frozenset(
    {
        "QUEUED",
        "RECONCILING",
        "RUNNING",
        "PAUSE_REQUESTED",
        "RESUME_REQUESTED",
        "STOPPING",
    }
)
TERMINAL = frozenset({"COMPLETED", "STOPPED"})

_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}|[A-Z][A-Z0-9_]{0,63}")

#: The next step for each refusal or interruption code a supervisor records.
#: Closed: a code not listed gets `FALLBACK_ACTION`, and the code itself is
#: still shown, so a new code from another slice (the validator intake's, for
#: one) reaches the miner before this table names it.
NEXT_ACTIONS = {
    # The campaign's own lock and state.
    "campaign_busy": (
        "Another session holds this campaign: an attached agent, the "
        "Control Center's tools, or an operation still running. Detach it "
        "(carbon_detach_campaign) or close the tools, then try again."
    ),
    "campaign_stopped": "This campaign is stopped. Launch a new one to continue.",
    "campaign_paused": "This campaign is paused. Resume it, then try again.",
    "campaign_complete": "This campaign is complete. Launch a new one to continue.",
    "reconciliation_required": (
        "Work may have been dispatched and its outcome is unknown. Reconcile "
        "the campaign (halt with action=reconcile) before anything else runs."
    ),
    "unresolved_operation": (
        "An earlier operation's outcome is unknown. Reconcile the campaign "
        "(halt with action=reconcile); nothing is resent blindly."
    ),
    # Interruptions this module records.
    "operation_interrupted": (
        "The operation stopped before it finished, most likely because the "
        "process running it exited. Observe the campaign, then try again; "
        "reconcile first if it asks for reconciliation."
    ),
    "campaign_interrupted": (
        "The campaign stopped before it finished. Resume it; reconcile first "
        "if it asks for reconciliation."
    ),
    "paused_when_supervisor_closed": (
        "The Control Center (or the supervisor running this campaign) closed, "
        "so the campaign was paused, not stopped. Resume it to continue."
    ),
    "paused_for_handover": (
        "Paused for a moment so the Control Center could take this campaign "
        "over from the background supervisor running it; the Control Center "
        "resumes it on its own once it has it. If it stays paused, resume it."
    ),
    "withdrawn_when_supervisor_closed": (
        "The Control Center closed before this request started, so it was "
        "withdrawn and nothing ran. Send it again."
    ),
    # Launch and profile.
    "launch_choices_unrecorded": (
        "This launch was recorded before its choices were kept, so it cannot "
        "be restarted exactly. Stop it and launch again."
    ),
    "launch_record_differs": (
        "This launch's record no longer matches what was admitted. Stop it "
        "and launch again."
    ),
    "profile_differs_from_request": (
        "The runner profile changed after this request was admitted, or the "
        "Control Center and your agent use different profiles. Use one "
        "profile, then send the request again."
    ),
    "dispatch_configuration_changed": (
        "The runner profile changed after this request was admitted. Review "
        "it, then resume or send the request again."
    ),
    "profile_changed_since_launch": (
        "Something this campaign was frozen with has changed in your runner "
        "profile since launch (the accepted revision, its images, the hotkey "
        "or the research guidance), so it cannot continue under this profile. "
        "Launch a new campaign; this one stays readable and can be stopped."
    ),
    "carbon_updated_rerun_installer": (
        "Carbon in this checkout is not the revision your runner profile "
        "accepted: it was updated, or its worker image was rebuilt. Re-run the "
        "installer so your profile accepts this checkout and its images, then "
        "launch. Campaigns frozen under the earlier revision stay readable."
    ),
    "campaign_readback_unavailable": (
        "This campaign's records could not be read back consistently. Nothing "
        "was changed. Export its record if you need it, and launch a new "
        "campaign to continue."
    ),
    "campaign_read_failed": (
        "This campaign could not be read just now. Nothing was changed. Reload "
        "the page; if it persists, restart the Control Center."
    ),
    "operation_not_completed": (
        "The request did not complete. Observe the campaign: its state and "
        "last refusal say what happened. Then try again."
    ),
    "readback_unavailable": (
        "This could not be read back. Nothing was changed. Reload the page; if "
        "it persists, restart the Control Center."
    ),
    "research_profile_unavailable": (
        "Your runner profile cannot be read. Check it under Set up your "
        "environment, then try again."
    ),
    "research_dispatch_disabled": (
        "Research dispatch is disabled in this runner profile. Enable it, "
        "then resume."
    ),
    "research_runtime_interface_unavailable": (
        "This runner profile names a runtime the runner cannot assemble. "
        "Set up your environment again, then resume."
    ),
    "challenge_retired": "This Challenge is retired. Launch a campaign on another.",
    # Registration and the miner's signer (operations._registered, SignerCode).
    "registration_required": (
        "Your hotkey is not registered on the subnet. Register it in your own "
        "wallet tooling, confirm, then resume."
    ),
    "registration_unreadable": (
        "The chain could not be read. Try again shortly; nothing was started."
    ),
    "registration_wrong_network": (
        "Your profile points at another network. Set up your environment "
        "again for Carbon's subnet, then resume."
    ),
    "signer_not_running": (
        "Start carbon-miner-signer for your hotkey, then try again. Nothing "
        "was signed."
    ),
    "signer_refused": "Your signer declined the request. Check it, then try again.",
    "signer_wrong_hotkey": (
        "Your signer holds a different hotkey than the registered miner. "
        "Start it with the registered hotkey, then try again."
    ),
    "signer_timeout": "Your signer did not answer in time. Check it, then try again.",
    # The model provider key, from the runner profile.
    "model_provider_credential_not_configured": (
        "No key file is configured for this campaign's model provider. Add "
        "it under Set up your environment, then resume."
    ),
    "model_provider_credential_unusable": (
        "The model provider key file cannot be used (owner-only regular file "
        "required). Fix it under Set up your environment, then resume."
    ),
    # A miner's own journey (research_campaign).
    "the_agent_selects_in_this_campaign": (
        "Carbon's agent selects in this campaign; freeze and submit are its. "
        "Launch with agent=none to select yourself."
    ),
    "campaign_not_prepared": (
        "The campaign is still being prepared. Observe it until it is READY, "
        "then try again."
    ),
    "practice_result_required": (
        "Practice this recipe first; only a practiced recipe can be frozen "
        "and submitted."
    ),
    "candidate_awaits_submission": (
        "A frozen candidate is waiting. Submit it before freezing another."
    ),
    "freeze_a_candidate_first": "Freeze a practiced recipe, then submit.",
    "final_exams_used": (
        "Both final exams of this campaign are used. Launch a new campaign "
        "to continue."
    ),
    # The validator's answer to a DEVELOPMENT submission (carbon.battery).
    "evaluation_queued": (
        "The validator queued your submission. Observe later; the frozen "
        "candidate is kept, and submitting again replays the same admission."
    ),
    "evaluation_unavailable": (
        "No validator deployment or intake is configured for this Challenge "
        "in your runner profile. Add one under Set up your environment; the "
        "frozen candidate is kept, so submit again once it is."
    ),
    "evaluation_failed_infra": (
        "The validator's infrastructure failed. That is not a scientific "
        "result. The frozen candidate is kept; submit again later."
    ),
    "intake_unreachable": (
        "The validator intake could not be reached. The frozen candidate is "
        "kept; submit again later."
    ),
    # Attaching to a campaign (`standard_cli.attached`): which check failed.
    "runner_profile_unusable": (
        "Your runner profile could not be read, or it does not validate. "
        "Check the --configuration path, or write it again under Set up your "
        "environment."
    ),
    "campaign_not_found": (
        "No campaign of this profile has that id. List your campaigns "
        "(carbon_observe, or the Control Center) and name one by its "
        "32-character id."
    ),
    "campaign_manifest_differs": (
        "This campaign's frozen record was not launched under this profile, "
        "or differs from its own ledger. Nothing was changed. Attach with the "
        "profile that launched it."
    ),
    "campaign_revision_differs": (
        "This campaign was frozen under another Carbon revision than your "
        "profile accepts. Attach from the checkout and profile it was launched "
        "with, or launch a new campaign."
    ),
    "runtime_unavailable": (
        "This host cannot run the campaign's accepted worker images right "
        "now: Docker is not running, or an image is missing. Start Docker, or "
        "re-run the installer, then try again."
    ),
    "campaign_runtime_differs": (
        "This campaign was frozen with a runtime this host no longer "
        "composes. Launch a new campaign; this one stays readable."
    ),
    "remote_setup_unavailable": (
        "Your remote GPU setup does not match this campaign, or cannot be "
        "used. Check it under Set up your environment, Compute, then try again."
    ),
    "session_unavailable": (
        "This campaign has no prepared authenticated session yet. Resume the "
        "campaign once so it is prepared, then attach."
    ),
    "campaign_owner_changed": (
        "Your signer authenticates as another miner than the one this "
        "campaign was launched under. Attach with the hotkey and signer that "
        "launched it, or launch a new campaign; this one stays readable."
    ),
    "registration_check_failed": (
        "Your hotkey's registration could not be confirmed on the subnet. "
        "Check it is registered (carbon_onboarding status) and the chain is "
        "reachable, then try again."
    ),
    "miner_differs_from_campaign": (
        "The hotkey in your runner profile is not the one this campaign was "
        "launched with. Use that hotkey's profile, or launch a new campaign."
    ),
    "task_left_running": (
        "A research task was left RUNNING by an earlier session. Attach with "
        "--cleanup-only (carbon-mcp --configuration PROFILE --campaign ID "
        "--cleanup-only) to observe and cancel it, then reconcile the "
        "campaign (halt with action=reconcile)."
    ),
    "carbon_mcp_failed": (
        "Carbon MCP stopped unexpectedly. Start it again; if it keeps failing, "
        "open the Control Center to check your setup."
    ),
    "carbon_mcp_interrupted": "Interrupted. Start Carbon MCP again when you are ready.",
}
FALLBACK_ACTION = (
    "Read the code: it names what was refused. Correct what it names and try "
    "again; observe shows the campaign's state."
)


def exception_code(exc):
    """A typed failure's closed code (its `code`, or that code's `value`), or
    None. Never the message: a `Rejected`, an `OperationRefused`, a
    `SignerFailure` and the attach refusals carry one; a bare ValueError does
    not."""
    code = getattr(exc, "code", None)
    code = getattr(code, "value", code)
    return code if type(code) is str and _CODE.fullmatch(code) else None


#: The refusal catalog's schema (`catalog`).
CATALOG_SCHEMA = "carbon.launchpad.refusal-catalog.v1"


def catalog():
    """The closed table, as a door serves it (`GET /api/v1/refusals`), so a
    page renders the next action for any code it meets - a synchronous
    refusal's `{error}`, or a campaign's `last_refusal` - from this one
    source. A code the table does not name takes `fallback`."""
    return {
        "schema": CATALOG_SCHEMA,
        "next_actions": dict(NEXT_ACTIONS),
        "fallback": FALLBACK_ACTION,
    }


def refusal(code, *, operation=None, kind="refused", at=None):
    """A `last_refusal` entry: closed code, next action, when, and which
    operation. An unrecognisable code is kept as `operation_refused` rather
    than echoed, so nothing free-form reaches the record."""
    if type(code) is not str or not _CODE.fullmatch(code):
        code = "operation_refused" if kind == "refused" else "campaign_interrupted"
    return {
        "code": code,
        "next_action": NEXT_ACTIONS.get(code, FALLBACK_ACTION),
        "at": round(time.time() if at is None else at, 3),
        "operation": operation if operation in OPERATIONS else None,
        "kind": kind if kind in ("refused", "interrupted", "paused") else "refused",
    }


def read_refusal(stored):
    """A stored `last_refusal`, rechecked, or None. A record that does not
    parse into the closed shape is withheld rather than shown."""
    if stored is None:
        return None
    try:
        value = json.loads(stored)
        if type(value) is not dict or type(value.get("code")) is not str:
            return None
        entry = refusal(
            value["code"],
            operation=value.get("operation"),
            kind=value.get("kind", "refused"),
            at=float(value["at"]),
        )
    except (ValueError, TypeError, KeyError):
        return None
    return entry if entry["code"] == value["code"] else None


def recovery_actions(state, in_flight=None, *, resumable=True):
    """What gets a campaign moving again from `state`, as operations a door
    can call: `[{"action", "operation"}]`, empty when nothing is needed.

    `resumable` is False for a campaign nothing resumes - one launched under
    the retired grant, or on a retired Challenge - whose resume is always
    refused: it is offered only what can succeed (stop, reconcile)."""
    resume = [{"action": "resume", "operation": "resume"}] if resumable else []
    stop = {"action": "stop", "operation": "halt"}
    if state == "RECONCILIATION_REQUIRED":
        return [{"action": "reconcile", "operation": "halt"}, stop]
    if state in ("INTERRUPTED", "PAUSED", "PAUSE_REQUESTED"):
        return [*resume, stop]
    if state == "QUEUED" and in_flight is None:
        # Admitted and nothing carrying it out: resume dispatches it again.
        return [*resume, stop]
    return []


# ---- The queue, in the runner's own database.


def ensure_schema(db):
    """The queue table and the campaign columns this module reads. Additive:
    an older database gains them in place and loses nothing."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS launchpad_dispatch (seq INTEGER PRIMARY KEY AUTOINCREMENT, principal TEXT NOT NULL, campaign TEXT NOT NULL, operation TEXT NOT NULL, params BLOB NOT NULL, config_digest TEXT NOT NULL, state TEXT NOT NULL, outcome TEXT, supervisor TEXT, created REAL NOT NULL, claimed REAL, finished REAL)"
    )
    columns = {r[1] for r in db.execute("PRAGMA table_info(launchpad_campaigns)")}
    # What a launch chose, so a supervisor in another process (or after a
    # restart) can carry it out exactly; and the campaign's last refusal.
    for column in ("launch_request", "last_refusal"):
        if column not in columns:
            db.execute(f"ALTER TABLE launchpad_campaigns ADD COLUMN {column} BLOB")


def enqueue(
    db, *, principal, campaign, operation, params, config_digest, state, supervisor=None
):
    """Record one admitted dispatch; returns its sequence number. A QUEUED
    item waits for a supervisor; a RUNNING one was started at once by
    `supervisor`, the process that records it."""
    if operation not in OPERATIONS or state not in (QUEUED, RUNNING):
        raise ValueError("closed dispatch required")
    if (state == RUNNING) != (supervisor is not None):
        raise ValueError("a running dispatch names its supervisor")
    return db.execute(
        "INSERT INTO launchpad_dispatch (principal,campaign,operation,params,config_digest,state,supervisor,created,claimed) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            principal,
            campaign,
            operation,
            json.dumps(params, sort_keys=True, separators=(",", ":")),
            config_digest,
            state,
            supervisor,
            time.time(),
            time.time() if state == RUNNING else None,
        ),
    ).lastrowid


def claim(db, *, principal, supervisor):
    """Claim every queued item of `principal`, oldest first, for
    `supervisor`. Each item is claimed exactly once."""
    db.execute("BEGIN IMMEDIATE")
    rows = db.execute(
        "SELECT * FROM launchpad_dispatch WHERE principal=? AND state=? ORDER BY seq",
        (principal, QUEUED),
    ).fetchall()
    for row in rows:
        db.execute(
            "UPDATE launchpad_dispatch SET state=?,supervisor=?,claimed=? WHERE seq=? AND state=?",
            (RUNNING, supervisor, time.time(), row["seq"], QUEUED),
        )
    return [dict(r) for r in rows]


def finish(db, seq, outcome):
    db.execute(
        "UPDATE launchpad_dispatch SET state=?,outcome=?,finished=? WHERE seq=? AND state!=?",
        (DONE, outcome, time.time(), seq, DONE),
    )


def withdraw(db, seq):
    """Withdraw a QUEUED item no supervisor has claimed. True when withdrawn;
    False when one claimed it first (it is then that supervisor's)."""
    return (
        db.execute(
            "UPDATE launchpad_dispatch SET state=?,outcome=?,finished=? WHERE seq=? AND state=?",
            (DONE, "withdrawn", time.time(), seq, QUEUED),
        ).rowcount
        == 1
    )


def interrupted_runs(db, *, principal, campaign):
    """How many of the campaign's runs a dead supervisor left unfinished."""
    return db.execute(
        "SELECT COUNT(*) FROM launchpad_dispatch WHERE principal=? AND campaign=? AND operation='run' AND outcome='interrupted'",
        (principal, campaign),
    ).fetchone()[0]


def active(db, *, principal, campaign):
    """The newest item admitted for `campaign` and not yet done, or None."""
    row = db.execute(
        "SELECT * FROM launchpad_dispatch WHERE principal=? AND campaign=? AND state!=? ORDER BY seq DESC LIMIT 1",
        (principal, campaign, DONE),
    ).fetchone()
    return dict(row) if row is not None else None


def queued(db, *, principal):
    return (
        db.execute(
            "SELECT 1 FROM launchpad_dispatch WHERE principal=? AND state=? LIMIT 1",
            (principal, QUEUED),
        ).fetchone()
        is not None
    )


def orphaned(db, *, principal, supervisor):
    """RUNNING items another supervisor claimed. Seen by the lock holder,
    their supervisor is gone: they are interrupted, never replayed."""
    rows = db.execute(
        "SELECT * FROM launchpad_dispatch WHERE principal=? AND state=? AND (supervisor IS NULL OR supervisor!=?)",
        (principal, RUNNING, supervisor),
    ).fetchall()
    for row in rows:
        finish(db, row["seq"], "interrupted")
    return [dict(r) for r in rows]


# ---- The lock: one supervisor per runner database and principal.


def lock_directory(database, principal):
    """Where the supervisor lock for `principal`'s campaigns in `database`
    lives: beside the database, one directory per principal."""
    from carbon.development_session.profile import canonical, digest

    return Path(database).parent / (
        ".supervisor-" + digest(canonical([str(principal)]))[7:23]
    )


def presence_directory(database, principal):
    """Where a running Control Center's presence lock lives: beside the
    supervisor lock. Held for the Control Center's whole life, so a detached
    supervisor knows to hand over to it."""
    return lock_directory(database, principal) / "control-center"


class SupervisorLock:
    """The supervisor's OS lock, held for as long as this process supervises."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.stack = None

    @property
    def held(self):
        return self.stack is not None

    def try_acquire(self, wait=0.0):
        """Take the lock, trying for up to `wait` seconds. True when held."""
        from scripts.dev.miner_launchpad.controller import owner_lock

        if self.stack is not None:
            return True
        deadline = time.monotonic() + wait
        while True:
            stack = contextlib.ExitStack()
            try:
                stack.enter_context(owner_lock(self.directory))
            except RuntimeError:
                stack.close()
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)
                continue
            self.stack = stack
            return True

    def release(self):
        stack, self.stack = self.stack, None
        if stack is not None:
            stack.close()


def supervisor_alive(directory):
    """Whether some process holds the supervisor lock now. Probes by taking
    it for an instant; a supervisor that meets the probe retries."""
    from scripts.dev.miner_launchpad.controller import owner_lock

    try:
        with owner_lock(Path(directory)):
            return False
    except RuntimeError:
        return True


def repository_root():
    return Path(__file__).resolve().parents[3]


def spawn_detached(configuration):
    """Start a detached supervisor for the runner profile at `configuration`.

    A new session, so it outlives the client that started it; its own
    standard streams, so a client's stdio protocol is never written to. What
    it does is recorded in the campaigns themselves (their ledger, journal,
    interruptions and `last_refusal`), never in an output stream.
    """
    import subprocess

    root = repository_root()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root), *filter(None, [environment.get("PYTHONPATH")])]
    )
    options = {}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        options["start_new_session"] = True
    # A fixed module of this checkout and the profile path; no shell.
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scripts.dev.miner_launchpad.supervisor",
            "--configuration",
            str(Path(configuration)),
        ],
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        **options,
    )


class Supervisor:
    """The loop in whichever process supervises a host's campaigns.

    `tick` is one pass: take the lock if it is free (recovering what a dead
    supervisor left, once per acquisition), then start every queued item.
    The Control Center runs `start` (a daemon thread, until closed); a
    detached supervisor runs `run_until_idle`.

    The handover: a Control Center's `tick` also holds its presence lock; a
    detached supervisor's `tick` that finds it held starts nothing more and
    hands over (`RunnerAdapter.hand_over`), releasing the lock once nothing of
    its own is working. The Control Center's next `tick` takes the lock,
    recovers, and resumes what was paused for it (`RunnerAdapter.take_over`).
    """

    def __init__(
        self,
        host,
        *,
        poll=POLL_SECONDS,
        idle_exit=IDLE_EXIT_SECONDS,
        acquire_wait=ACQUIRE_SECONDS,
    ):
        self.host = host
        self.lock = SupervisorLock(lock_directory(host.database, host.principal))
        self.presence_directory = presence_directory(host.database, host.principal)
        #: The Control Center's presence (SUPERVISOR only), held while it runs.
        self.presence = (
            SupervisorLock(self.presence_directory) if host.role == SUPERVISOR else None
        )
        self.poll, self.idle_exit, self.acquire_wait = poll, idle_exit, acquire_wait
        self.wakeup = threading.Event()
        self.stopping = threading.Event()
        self.thread = None
        self.tick_lock = threading.Lock()
        #: DETACHED: a Control Center is running and this supervisor is
        #: handing over to it; `handed_over` once it released the lock to it.
        self.handing_over = False
        self.handed_over = False

    @property
    def held(self):
        return self.lock.held

    def control_center_running(self):
        """Whether a Control Center for this runner holds its presence lock.
        Probed by taking it for an instant; a Control Center that meets the
        probe takes it on its next pass."""
        return supervisor_alive(self.presence_directory)

    def acquire(self, wait=0.0):
        """Hold the lock; on taking it, recover what an earlier holder left.

        A detached supervisor that takes it with no Control Center running
        leaves what was paused to hand over to one paused, and says why
        (D4)."""
        if self.lock.held:
            return True
        if not self.lock.try_acquire(wait):
            return False
        # A failed recovery never takes the lock down; the campaign it could
        # not settle is settled by the next one, or by its miner.
        with contextlib.suppress(Exception):
            self.host.recover(redispatch=True)
        if self.presence is None:
            with contextlib.suppress(Exception):
                if not self.control_center_running():
                    self.host.release_handover_pauses()
        return True

    def tick(self, wait=0.0):
        """Start every queued item, if this process holds (or takes) the lock.

        A detached supervisor that finds a Control Center running starts
        nothing: it hands over, and answers False. A Control Center holding
        the lock resumes, on each pass, what was paused to hand over to it
        once the process that paused it is gone (`RunnerAdapter.take_over`)."""
        with self.tick_lock:
            if self.presence is not None:
                with contextlib.suppress(Exception):
                    self.presence.try_acquire()
            elif self.host.role == DETACHED:
                if self.control_center_running():
                    if self.lock.held:
                        self.handing_over = True
                        if self.host.hand_over():
                            self.lock.release()
                            self.handed_over = True
                    return False
                if self.handing_over:
                    # The Control Center closed before it took over: what was
                    # paused for it stays paused, as closing it pauses (D4).
                    self.handing_over = False
                    with contextlib.suppress(Exception):
                        self.host.release_handover_pauses()
            if not self.acquire(wait):
                return False
            if self.presence is not None:
                with contextlib.suppress(Exception):
                    self.host.take_over()
            with self.host.db() as db:
                items = claim(
                    db, principal=self.host.principal, supervisor=self.host.token
                )
            for item in items:
                self.host.start_item(item)
            return True

    def wake(self):
        self.wakeup.set()

    def start(self):
        """Supervise on a daemon thread until `stop` (the Control Center)."""
        if self.thread is not None:
            return

        def loop():
            while not self.stopping.is_set():
                # A bad pass never ends supervision.
                with contextlib.suppress(Exception):
                    self.tick()
                self.wakeup.wait(self.poll)
                self.wakeup.clear()

        self.thread = threading.Thread(
            target=loop, name="carbon-campaign-supervisor", daemon=True
        )
        self.thread.start()

    def idle(self):
        """No queued item and no campaign thread here still working.

        A run parked at its campaign's checkpoint while the campaign is
        paused (`RunnerAdapter.busy_threads`) does not count: it waits for a
        resume that a new run carries out anywhere, so exiting loses nothing.
        Before this, one paused autonomous campaign kept a detached
        supervisor alive for as long as it stayed paused."""
        with self.host.db() as db:
            waiting = queued(db, principal=self.host.principal)
        return not waiting and not self.host.busy_threads()

    def run_until_idle(self, clock=time.monotonic):
        """A detached supervisor's life: take the lock, work, and exit once
        idle for `idle_exit` seconds, or once it has handed over to a
        Control Center. Returns False when it never held the lock (another
        supervisor, or a running Control Center, carries the work out)."""
        if not self.tick(self.acquire_wait):
            return self.handed_over
        idle_since = None
        while not self.stopping.is_set():
            with contextlib.suppress(Exception):
                self.tick()
            if self.handed_over:
                return True
            if self.handing_over or not self.idle():
                idle_since = None
            else:
                idle_since = clock() if idle_since is None else idle_since
                if clock() - idle_since >= self.idle_exit and self._retire():
                    return True
            self.wakeup.wait(self.poll)
            self.wakeup.clear()
        return True

    def _retire(self):
        """Release the lock, then look once more: work queued in between is
        taken back (or left to whoever took the lock, or to a Control Center
        now running). True when retired."""
        self.lock.release()
        with contextlib.suppress(Exception):
            if (
                not self.idle()
                and not self.control_center_running()
                and self.acquire(self.acquire_wait)
            ):
                return False
        return True

    def stop(self):
        self.stopping.set()
        self.wake()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=5)

    def release(self):
        """Release the lock, then the presence: a detached supervisor that
        sees the presence go hands nothing over any more."""
        self.lock.release()
        if self.presence is not None:
            self.presence.release()


def main(argv=None):
    """`python -m scripts.dev.miner_launchpad.supervisor --configuration P`:
    supervise the campaigns of the runner profile P until idle."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument(
        "--idle-exit-seconds",
        type=float,
        default=IDLE_EXIT_SECONDS,
        help="How long to stay with nothing to do before exiting (0.1-3600).",
    )
    args = parser.parse_args(argv)
    if not 0.1 <= args.idle_exit_seconds <= 3600:
        parser.error("--idle-exit-seconds is between 0.1 and 3600")
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    try:
        host = RunnerAdapter.for_profile(args.configuration, role=DETACHED)
    except Exception:  # noqa: BLE001 - an unusable profile supervises nothing
        return 2
    host.supervisor.idle_exit = args.idle_exit_seconds
    stopping = host.supervisor.stopping

    def stop(*_):
        stopping.set()
        host.supervisor.wake()

    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        if hasattr(signal, name):
            with contextlib.suppress(ValueError, OSError):
                signal.signal(getattr(signal, name), stop)
    try:
        host.supervisor.run_until_idle()
    finally:
        host.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
