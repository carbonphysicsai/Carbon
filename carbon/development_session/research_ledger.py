"""Durable campaign accounting; unknown consumption keeps its reservation.

Trusted controller only. Never mounted into a miner worker. Integer units avoid
floating point underspend; timestamps are operational, not scientific evidence.

**Carbon does not cap a miner's own resources.** A miner may set a budget, and
if they do it binds exactly where they set it, because a budget that does not
bind is worse than none - it tells them they are protected when they are not.
A miner who sets no budget has no budget, and that is a supported state rather
than a default ceiling or an error.

So "no cap" is `NO_BUDGET`, a first-class state and deliberately not a very
large number. A large number would read as a limit to the next person and would
be wrong, and it would silently answer a comparison that should never have been
asked. `NO_BUDGET` is not an integer and supports no ordering, so a code path
that forgets to skip the check raises rather than quietly admitting work.

Two things here are not miner spending control and stay:

- `SERVICE_LIMITS` bound Carbon's own shared reference service. They are
  infrastructure capacity, never a cap on the miner's resources, and they are
  reported under their own name so the two cannot be confused.
- The development grant envelope in `research_admission`, which exists so a
  founder can cap Carbon's spend on Carbon's accounts in a bounded experiment.
  It is test machinery and is unreachable from any product surface.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .profile import canonical, digest

VERSION = "carbon.autoresearch.campaign.v1"

#: A product campaign: launched by a miner through a product surface, admitted
#: by subnet registration alone (C-MLP-02-D11), and controlled - pause, stop,
#: owner binding - exactly as a development grant campaign is, but with no
#: grant, no expiry and no limit the miner did not set.
PRODUCT = "carbon.launchpad.campaign.v1"

#: The admission a product manifest records. Registration is an access fact,
#: never scientific evidence.
PRODUCT_ADMISSION = "SUBNET_REGISTRATION"


class Unbounded:
    """No cap. A state, not a number.

    Supports no ordering and no arithmetic on purpose. `used + want > NO_BUDGET`
    is a `TypeError`, not `False`, so a branch that forgets to skip the headroom
    check fails loudly at the point of the mistake instead of admitting work
    against a limit that was never meant to exist.
    """

    __slots__ = ()

    def __repr__(self):
        return "NO_BUDGET"

    def __bool__(self):
        # Refused rather than answered: neither True nor False is honest about
        # "no cap", and every caller should be branching on identity instead.
        raise TypeError("NO_BUDGET is not a truth value; test `is NO_BUDGET`")


NO_BUDGET = Unbounded()

#: Everything the ledger accounts for. Accounting is not a spending control:
#: a miner can always see what they have spent, capped or not.
DIMENSIONS = (
    "epochs",
    "research_trials",
    "final_replicas",
    "provider_attempts",
    "provider_nanodollars",
    "numerical_milliseconds",
    "reference_trajectories",
    "reference_invocations",
    "retained_bytes",
)

#: Carbon's shared reference service, which runs on Carbon's infrastructure and
#: not on the miner's account. `retained_bytes` is deliberately not here:
#: `check_storage` measures the campaign root on the executing host - the
#: miner's own machine or their rented box - and no retained byte is accounted
#: against Carbon's side anywhere, so the storage is theirs and Carbon sets no
#: cap on it. These are service capacity limits and are named
#: as such wherever they are reported. They are not a miner budget and must
#: never be presented as a cap on the miner's own resources.
SERVICE_LIMITS = {
    "reference_trajectories": 512,
    "reference_invocations": 2048,
}

#: Offered, never imposed. Holding back part of a final phase is useful when a
#: miner wants to be sure the run can finish, but deciding that for them would
#: be Carbon allocating their money. Applied only to dimensions the miner
#: actually capped, and only when they asked for a reserve.
SUGGESTED_FINAL_RESERVE = {
    "final_replicas": 12,
    "provider_attempts": 8,
    "provider_nanodollars": 8 * 20480000,
    "numerical_milliseconds": 12 * 720000,
    "reference_trajectories": 48,
    "reference_invocations": 144,
    "retained_bytes": 2 * 1024**3,
}

#: The development grant envelope. Carbon's owner capping Carbon's spend on
#: Carbon's accounts for a bounded experiment - the provider cap is one dollar
#: and the wall clock is eight hours. These are development fixtures and bound
#: no miner; `research_admission` is the only module that may read them.
DEVELOPMENT_CEILINGS = {
    "epochs": 2,
    "research_trials": 16,
    "final_replicas": 12,
    "provider_attempts": 96,
    "provider_nanodollars": 1000000000,
    "numerical_milliseconds": 21600000,
    "reference_trajectories": 512,
    "reference_invocations": 2048,
    "retained_bytes": 10 * 1024**3,
}
DEVELOPMENT_ELAPSED_SECONDS = 8 * 3600


def _caps(manifest):
    """The miner's budget, as a mapping of dimension to cap or NO_BUDGET.

    `null` on the wire becomes `NO_BUDGET` in memory, and a dimension the miner
    never mentioned is uncapped. Both spellings mean the same thing and neither
    is a number, so nothing downstream can compare against them by accident.
    """
    ceilings = manifest.get("ceilings")
    if ceilings is None:
        return {}
    return {
        key: (NO_BUDGET if value is None else value) for key, value in ceilings.items()
    }


def _elapsed(manifest):
    """The miner's wall-clock budget, or NO_BUDGET if they set none."""
    value = manifest.get("elapsed_seconds")
    return NO_BUDGET if value is None else value


def _final_reserve(manifest):
    """Hold back a final phase only where the miner asked for it.

    Reserving is useful when someone wants to be sure a run can finish, and it
    is theirs to decline: deciding it for them would be Carbon allocating their
    money. A manifest that says nothing gets no reserve.
    """
    if manifest.get("final_reserve") is True:
        return SUGGESTED_FINAL_RESERVE
    if manifest["schema"] not in (VERSION, PRODUCT):
        # The development grant path keeps the reserve it was built with.
        return SUGGESTED_FINAL_RESERVE
    return {}


def _check_budget(manifest):
    """Validate a miner-authored budget without imposing one.

    There is no lower bound and no upper bound. A cap is whatever number the
    miner chose, and the absence of a cap is not an error - so this rejects
    incoherent input (a negative cap, an unknown dimension) and nothing else.
    """
    ceilings = manifest.get("ceilings")
    if ceilings is None:
        pass
    elif type(ceilings) is not dict or set(ceilings) - set(DIMENSIONS):
        raise ValueError("budget names an unknown resource")
    else:
        for key, value in ceilings.items():
            if value is None:
                continue
            if type(value) is not int or value < 0:
                raise ValueError("budget must be a nonnegative whole number: " + key)
    elapsed = manifest.get("elapsed_seconds")
    if elapsed is not None and (type(elapsed) is not int or elapsed < 1):
        raise ValueError("elapsed budget must be a positive whole number")
    if manifest.get("final_reserve") not in (None, True, False):
        raise ValueError("final_reserve is the miner's choice, true or false")


def _check_product(manifest):
    """A product manifest records how it was admitted, and nothing else admits it.

    Closed on the admission record so a manifest cannot claim registration in a
    shape nothing produced. The record is what `RegisteredMiner.record()`
    returns; the per-call registration read happens on the connection.
    """
    admission = manifest.get("admission")
    if (
        type(admission) is not dict
        or admission.get("admission") != PRODUCT_ADMISSION
        or set(admission)
        != {
            "admission",
            "network",
            "netuid",
            "hotkey",
            "uid",
            "registered_at_block",
            "observed_block",
            "snapshot_id",
        }
    ):
        raise ValueError("product campaign must record its registration admission")
    for key in ("principal", "runtime", "owner", "campaign_id"):
        if not manifest.get(key):
            raise ValueError("incomplete product campaign manifest")
    if "grant" in manifest:
        raise ValueError("a product campaign never carries a development grant")


def _vector(value):
    if type(value) is not dict or set(value) - set(DIMENSIONS):
        raise ValueError("unknown resource dimension")
    if any(type(v) is not int or v < 0 for v in value.values()):
        raise ValueError("nonnegative integer accounting required")
    return dict(value)


class CampaignLedger:
    def __init__(self, root: Path, *, clock=time.time, admission=None, generation=None):
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("private absolute campaign root required")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self.root, self.clock = root, clock
        self.admission, self.generation = admission, generation
        self.path = root / "campaign.sqlite3"
        if self.path.is_symlink():
            raise ValueError("symlink ledger rejected")
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS campaign (id INTEGER PRIMARY KEY CHECK(id=1), manifest BLOB NOT NULL, digest TEXT NOT NULL, started REAL);
                CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, owner TEXT NOT NULL, phase TEXT NOT NULL, request_digest TEXT NOT NULL, state TEXT NOT NULL, reservation BLOB NOT NULL, actual BLOB, result BLOB, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS notes (sequence INTEGER PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, body BLOB NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS operation_sequences (parent TEXT PRIMARY KEY, owner TEXT NOT NULL, document BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS operation_sequence_claims (child TEXT PRIMARY KEY, generation INTEGER NOT NULL, claimed REAL NOT NULL);
            """)
            existing = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
            if existing:
                self._check_admission_mode(json.loads(existing[0]))
        self.path.chmod(0o600)

    def _check_admission_mode(self, manifest):
        from .research_admission import MANIFEST

        if self.admission is not None and manifest.get("schema") != MANIFEST:
            raise ValueError("legacy campaign cannot consume a Launchpad grant")

    @staticmethod
    def controlled(manifest) -> bool:
        """Owner-bound and fenced by campaign control: pause, stop, generation.

        Both a development grant campaign and a product campaign are. The
        development CLI's own campaign (VERSION) is not - it has no control
        surface and runs to completion under the operator's hand.
        """
        from .research_admission import MANIFEST

        return manifest.get("schema") in (MANIFEST, PRODUCT)

    def authority(self, manifest) -> dict:
        """What admits this controlled campaign to dispatch, re-read now.

        A development grant campaign is admitted by its grant, re-verified on
        every call, and carries the grant's expiry. A product campaign is
        admitted by the registration its manifest records; it has no expiry,
        and the only limits on it are the ones its miner set. Registration
        itself is re-read per call by the connection, not here: this is the
        campaign's own authority, and a product campaign's is its manifest.
        """
        from .research_admission import MANIFEST

        schema = manifest.get("schema")
        if schema == MANIFEST:
            return {"kind": "DEVELOPMENT_GRANT", **self._grant(manifest)}
        if schema == PRODUCT:
            _check_product(manifest)
            if self.admission is not None:
                raise ValueError(
                    "a product campaign never consumes a development grant"
                )
            return {"kind": PRODUCT_ADMISSION, "expires_unix": None}
        raise ValueError("controlled campaign authority required")

    def retained_owner(self, owner, *, db=None):
        """Prove retained ownership for cleanup, admitting no further work.

        Expiry or revocation ends the right to spend, never the duty to clean
        up what was already started. For a grant campaign this is the grant's
        own proof; for a product campaign it is the frozen manifest's owner and
        the live control generation.
        """
        from .research_admission import MANIFEST, verify_cleanup_owner

        if db is None:
            with self.db() as connection:
                return self.retained_owner(owner, db=connection)
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
        if row is None:
            raise ValueError("frozen campaign required for cleanup")
        manifest = json.loads(row[0])
        if manifest.get("schema") == MANIFEST:
            return verify_cleanup_owner(self, owner, db=db)
        control = db.execute(
            "SELECT generation FROM launchpad_control WHERE id=1"
        ).fetchone()
        if (
            manifest.get("schema") != PRODUCT
            or manifest.get("owner") != owner
            or self.admission is not None
            or self.root.resolve() != self.root
            or self.generation is None
            or control is None
            or control[0] != self.generation
        ):
            raise ValueError("retained campaign ownership changed")
        _check_product(manifest)
        return manifest

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def check_storage(self, additional=0):
        if type(additional) is not int or additional < 0:
            raise ValueError("nonnegative storage admission required")
        paths = list(self.root.rglob("*"))
        if any(path.is_symlink() for path in paths):
            raise ValueError("campaign symlink rejected")
        size = sum(path.stat().st_size for path in paths if path.is_file())
        # Leave one MiB for SQLite pages and cancellation/status metadata.
        with self.db() as db:
            row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
        # The default matters: a budget that never mentions storage has no
        # storage cap, and `.get` without it would hand a None to the
        # comparison below.
        caps = _caps(json.loads(row[0])) if row else {}
        cap = caps.get("retained_bytes", NO_BUDGET)
        if cap is not NO_BUDGET and size + additional + 1024**2 > cap:
            raise ValueError("miner budget: retained_bytes")
        return size

    def freeze(self, manifest):
        from .research_admission import MANIFEST

        if type(manifest) is not dict or manifest.get("schema") not in {
            VERSION,
            MANIFEST,
            PRODUCT,
        }:
            raise ValueError("versioned campaign manifest required")
        self._check_admission_mode(manifest)
        if manifest["schema"] == MANIFEST:
            self._grant(manifest)
        else:
            _check_budget(manifest)
        if manifest["schema"] == PRODUCT:
            if self.admission is not None:
                raise ValueError(
                    "a product campaign never consumes a development grant"
                )
            _check_product(manifest)
        for key in (
            "campaign_id",
            "implementation",
            "objective",
            "sampling",
            "control",
            "selection",
            "replica_policy",
            "provider",
            "owner",
        ):
            if not manifest.get(key):
                raise ValueError("incomplete prospective campaign manifest")
        payload = canonical(manifest)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
            if old:
                if old[0] != payload:
                    raise ValueError("campaign freeze conflict")
            else:
                db.execute(
                    "INSERT INTO campaign VALUES(1,?,?,NULL)",
                    (payload, digest(payload)),
                )
        return digest(payload)

    def _grant(self, manifest):
        if self.admission is None:
            raise ValueError("trusted Launchpad admission required")
        doc = self.admission.verify(
            root=self.root,
            principal=manifest["principal"],
            runtime=manifest["runtime"],
            now=self.clock(),
        )
        if (
            manifest.get("grant") != self.admission.binding()
            or manifest["campaign_id"] != doc["campaign_id"]
            or manifest["authority"] != doc["authority"]
            or manifest["ceilings"] != doc["ceilings"]
            or manifest["elapsed_seconds"] != doc["elapsed_seconds"]
        ):
            raise ValueError("campaign differs from grant")
        return doc

    def checkpoint(self):
        with self.db() as db:
            row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
        if row:
            self._check_admission_mode(json.loads(row[0]))
        if row and self.controlled(json.loads(row[0])):
            from .research_control import CampaignControl

            self.authority(json.loads(row[0]))
            CampaignControl(self).checkpoint(self.generation)

    def _usage(self, db):
        used = dict.fromkeys(DIMENSIONS, 0)
        for reserved, actual in db.execute("SELECT reservation,actual FROM operations"):
            # A reconciled final actual vector replaces, never adds to, reservation.
            for key, value in json.loads(
                actual if actual is not None else reserved
            ).items():
                used[key] += value
        return used

    def reserve(self, identity, *, owner, phase, request, resources):
        from .research_control import DispatchPaused

        while True:
            self.checkpoint()
            try:
                return self._reserve(
                    identity,
                    owner=owner,
                    phase=phase,
                    request=request,
                    resources=resources,
                )
            except DispatchPaused:
                continue

    def _reserve(self, identity, *, owner, phase, request, resources):
        if phase not in {"research", "final", "selection", "report"}:
            raise ValueError("invalid campaign phase")
        for value in (identity, owner):
            if (
                type(value) is not str
                or not 1 <= len(value) <= 128
                or not value.isascii()
            ):
                raise ValueError("bounded identity required")
        resources = _vector(resources)
        fingerprint = digest(canonical(request))
        now = self.clock()
        if not math.isfinite(now):
            raise ValueError("invalid clock")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            frozen = db.execute(
                "SELECT manifest,started FROM campaign WHERE id=1"
            ).fetchone()
            if frozen is None:
                raise ValueError("freeze before dispatch")
            manifest = json.loads(frozen[0])
            self._check_admission_mode(manifest)
            caps, elapsed = _caps(manifest), _elapsed(manifest)
            expiry = None
            controlled = self.controlled(manifest)
            if controlled:
                from .research_control import CampaignControl

                grant = self.authority(manifest)
                if owner != manifest["owner"]:
                    raise ValueError("authenticated campaign owner differs")
                # Same transaction as the dispatch reservation: a concurrent
                # pause/stop is ordered before or after this admission.
                CampaignControl.assert_dispatch(db, self.generation)
                expiry = grant["expires_unix"]
            old = db.execute(
                "SELECT owner,phase,request_digest,state,reservation,result FROM operations WHERE id=?",
                (identity,),
            ).fetchone()
            if old:
                if old[:3] != (owner, phase, fingerprint) or old[4] != canonical(
                    resources
                ):
                    raise ValueError("operation replay conflict")
                return {
                    "dispatch": False,
                    "state": old[3],
                    "result": json.loads(old[5]) if old[5] else None,
                }
            started = frozen[1]
            if started is None:
                started = now
            if elapsed is NO_BUDGET:
                # An uncapped campaign has no wall clock of its own; a
                # development grant's expiry, where one exists, still applies.
                deadline = expiry
            else:
                deadline = (
                    min(started + elapsed, expiry) if expiry else started + elapsed
                )
            if now < started or (deadline is not None and now >= deadline):
                raise ValueError("campaign elapsed-time exhausted or clock regressed")
            if controlled and resources.get("provider_attempts", 0):
                if deadline is not None and now + 120 > deadline:
                    raise ValueError("provider timeout cannot fit remaining grant")
                pending = db.execute(
                    "SELECT reservation FROM operations WHERE state='RESERVED'"
                ).fetchall()
                if any(
                    json.loads(row[0]).get("provider_attempts", 0) for row in pending
                ):
                    raise ValueError(
                        "unknown provider metering; reconcile before dispatch"
                    )
            if resources.get("numerical_milliseconds", 0) > 720000:
                raise ValueError(
                    "per-worker productive plus validation/cleanup ceiling"
                )
            if resources.get("numerical_milliseconds", 0) > 0:
                # No deadline is a supported state: a miner who set no elapsed
                # budget has no wall clock for a worker to fit inside.
                if (
                    deadline is not None
                    and now + resources["numerical_milliseconds"] / 1000 > deadline
                ):
                    raise ValueError("worker cannot fit remaining elapsed time")
                active = db.execute(
                    "SELECT reservation FROM operations WHERE state='RESERVED'"
                ).fetchall()
                if any(
                    json.loads(row[0]).get("numerical_milliseconds", 0) > 0
                    for row in active
                ):
                    raise ValueError("one numerical worker; reconcile active operation")
            used = self._usage(db)
            reserve = _final_reserve(manifest)
            for key in DIMENSIONS:
                want = resources.get(key, 0)
                # Carbon's own shared reference service. Always applied, because
                # it protects Carbon's infrastructure rather than the miner's
                # money, and reported under its own name so the two are never
                # confused for one another.
                service = SERVICE_LIMITS.get(key)
                if service is not None and used[key] + want > service:
                    raise ValueError("carbon service capacity: " + key)
                cap = caps.get(key, NO_BUDGET)
                if cap is NO_BUDGET:
                    # No budget is a supported state, so the check is skipped
                    # rather than satisfied against a stand-in number.
                    continue
                headroom = reserve.get(key, 0) if phase == "research" else 0
                if controlled and key == "final_replicas":
                    # Preserve unspent final slots; consumed slots are already in
                    # used. Numerical and monetary reserves remain conservative.
                    headroom = max(0, headroom - used[key])
                if used[key] + want + headroom > cap:
                    raise ValueError("miner budget: " + key)
            db.execute("UPDATE campaign SET started=? WHERE id=1", (started,))
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    owner,
                    phase,
                    fingerprint,
                    "RESERVED",
                    canonical(resources),
                    None,
                    None,
                    now,
                ),
            )
        return {"dispatch": True, "state": "RESERVED", "result": None}

    def reserve_sequence(self, parent, *, owner, scope, children):
        from .research_sequences import reserve_sequence

        return reserve_sequence(
            self, parent, owner=owner, scope=scope, children=children
        )

    def claim_sequence_child(self, parent, *, owner, ordinal):
        from .research_sequences import claim_sequence_child

        return claim_sequence_child(self, parent, owner=owner, ordinal=ordinal)

    def cancel_sequence_held(self, parent, *, owner):
        from .research_sequences import cancel_sequence_held

        return cancel_sequence_held(self, parent, owner=owner)

    def sequence_status(self, parent, *, owner):
        from .research_sequences import sequence_status

        return sequence_status(self, parent, owner=owner)

    def settle_sequence(self, parent, *, owner):
        from .research_sequences import settle_sequence

        return settle_sequence(self, parent, owner=owner)

    def finish(self, identity, *, owner, state, actual, result):
        if state not in {"SUCCEEDED", "FAILED_INFRA", "CANCELLED"}:
            raise ValueError("terminal state required")
        actual = _vector(actual)
        body = canonical(result)
        if len(body) > 1024**2:
            raise ValueError("bounded result required")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM operation_sequences WHERE parent=?", (identity,)
            ).fetchone():
                raise ValueError("sequence parent requires child-derived settlement")
            old = db.execute(
                "SELECT owner,state,reservation,actual,result FROM operations WHERE id=?",
                (identity,),
            ).fetchone()
            if old is None or old[0] != owner:
                raise ValueError("operation unavailable")
            if old[1] != "RESERVED":
                if (old[1], old[3], old[4]) == (state, canonical(actual), body):
                    return
                raise ValueError("terminal conflict")
            reserved = json.loads(old[2])
            if set(actual) != set(reserved):
                raise ValueError(
                    "reconcile every reserved dimension; unknown is not zero"
                )
            if any(actual[k] > reserved[k] for k in actual):
                raise ValueError(
                    "reservation exceeded; retain unresolved charge and stop"
                )
            # Attempts/trials count even if execution failed or was cancelled.
            for key in (
                "provider_attempts",
                "research_trials",
                "final_replicas",
                "epochs",
            ):
                if actual.get(key, 0) != reserved.get(key, 0):
                    raise ValueError("attempt counters cannot be refunded")
            db.execute(
                "UPDATE operations SET state=?,actual=?,result=? WHERE id=?",
                (state, canonical(actual), body, identity),
            )

    def note(self, *, owner, kind, body):
        if kind not in {
            "hypothesis",
            "decision",
            "capability_request",
            "operational_error",
            "security_incident",
            "notebook",
        }:
            raise ValueError("unknown note kind")
        payload = canonical(body)
        self.check_storage(2 * len(payload) + 65536)
        if (
            type(owner) is not str
            or len(owner) > 128
            or not owner
            or len(payload) > 65536
        ):
            raise ValueError("bounded note required")
        with self.db() as db:
            db.execute(
                "INSERT INTO notes(owner,kind,body,created) VALUES(?,?,?,?)",
                (owner, kind, payload, self.clock()),
            )

    def status(self, *, owner):
        with self.db() as db:
            campaign = db.execute(
                "SELECT digest,started,manifest FROM campaign WHERE id=1"
            ).fetchone()
            operations = [
                {
                    "id": row[0],
                    "phase": row[1],
                    "state": row[2],
                    "reservation": json.loads(row[3]),
                    "actual": json.loads(row[4]) if row[4] else None,
                    "result": json.loads(row[5]) if row[5] else None,
                }
                for row in db.execute(
                    "SELECT id,phase,state,reservation,actual,result FROM operations WHERE owner=? ORDER BY created,id",
                    (owner,),
                )
            ]
            notes = [
                {"sequence": row[0], "kind": row[1], "body": json.loads(row[2])}
                for row in db.execute(
                    "SELECT sequence,kind,body FROM notes WHERE owner=? ORDER BY sequence",
                    (owner,),
                )
            ]
            return {
                "campaign_digest": campaign[0] if campaign else None,
                "started_unix": campaign[1] if campaign else None,
                # The miner's own budget, reported as they set it. `None` means
                # they set none, which is a state rather than a missing value.
                "budget": (
                    json.loads(campaign[2]).get("ceilings") if campaign else None
                ),
                "elapsed_limit_seconds": (
                    json.loads(campaign[2]).get("elapsed_seconds") if campaign else None
                ),
                # Carbon's infrastructure capacity, named separately so it can
                # never read as a cap on the miner's own resources.
                "carbon_service_limits": dict(SERVICE_LIMITS),
                "used": self._usage(db),
                "operations": operations,
                "notes": notes,
            }
