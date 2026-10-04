"""The attack-knowledge store: what Carbon's own attack runs have taught it.

OWNER-GRAPHITE-ATTACKER-01 (owner, 2026-10-04) §2 and §3. The general attack
engine improves as it goes by keeping, in one durable store per Carbon
host:

- **attempts** (every attack the oracle judged, with its outcome),
  **near-misses** and **verified findings**, each by Challenge, construction
  level, Track A check, family and boundary;
- **which strategy found what** (`priors(...)["by_strategy"]`);
- **per-Challenge and cross-Challenge priors** (`priors(challenge_id)` and
  `priors(None)`);
- **one regression specimen per verified finding**, re-run through the
  adapter's oracle whenever an adapter or contract version is new
  (`regression_due`, `replay_specimens`).

The store is content-addressed and append-only. Every record is a canonical
JSON object stored write-once under its sha256; a journal lists the records
in the order they were added, once each. `snapshot()` freezes the journal as
a document whose sha256 is the store's digest, and `pin(digest)` returns a
`ReadOnlyView` of exactly the records that snapshot holds. A frozen
admission run pins that digest in its suite version (`ReadOnlyView.suite_pin`);
specimens added later belong to the next suite version; replaying a frozen run
under any other digest is refused (`ReadOnlyView.replay`, invariant 10).

What the store learns from, and what it refuses:

- Only Carbon's own attack-oracle rows (`ORACLE`) and public material
  (`PUBLIC`). A finding is only ever an oracle row on a construction Carbon
  rebuilt; anything else is refused typed.
- Every record is checked with Graphite's protected-material rule
  (`graphite.tools.protected`) and the store's own sealed-material markers
  when it is written **and again when it is read**; a record that fails on
  read is withheld, never served. The store's root may not live in a
  sealed, confirmation, secret or canary location, and nothing here opens a
  path outside that root: it never reads sealed or confirmation material.
- A development finding that names a protected case is not dropped: it is
  recorded as an `OTHER_SIGNAL` finding (an exposure) with the protected
  content withheld and only its digest kept (`exposure_finding`).
- Findings use only the CONDITIONS vocabulary
  (`challenge_readiness.admission.CONDITIONS`).
- Held-out controls are never stored, and the engine never reads them: the
  store refuses a held-out control on write, and `training_view(adapter)` is
  the one way the engine reaches an adapter's controls, which refuses the
  held-out split. Wrongful rejection on held-out controls is the report's
  measurement (`attack.report`), never a training signal.
- A timeout, crash, unrebuildable construction or NOT_RUN family is never a
  hold: priors count it as inconclusive.

Neither the miner edition, the shared pack, the method cards, the Library,
the Launchpad nor the MCP door can reach this module
(`tests/invariants/test_attack_store_unreachable.py`). DEVELOPMENT only: no
weights, no chain writes, no score, threshold or gate is set here.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import re
from pathlib import Path

# `literature` first: `tools` imports it, and it calls back into `tools` while
# it loads, so importing `tools` first fails on the half-built module.
from carbon.agent_campaign.graphite import literature  # noqa: F401
from carbon.agent_campaign.graphite.tools import protected
from carbon.challenge_readiness.admission import CHECKS, CONDITIONS, LEDGER_TRACK
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

SCHEMA_PREFIX = "carbon.graphite.attack-knowledge"
RECORD_SCHEMA = SCHEMA_PREFIX + ".record.v1"
JOURNAL_SCHEMA = SCHEMA_PREFIX + ".journal.v1"
SNAPSHOT_SCHEMA = SCHEMA_PREFIX + ".snapshot.v1"
PRIORS_SCHEMA = SCHEMA_PREFIX + ".priors.v1"
SUITE_PIN_SCHEMA = SCHEMA_PREFIX + ".suite-pin.v1"
#: The directory name a host's store lives under (`<carbon root>/<this>`).
STORE_DIRNAME = "graphite-attack-knowledge"

ATTEMPT, NEAR_MISS, FINDING, REGRESSION = (
    "attempt",
    "near_miss",
    "finding",
    "regression",
)
KINDS = (ATTEMPT, NEAR_MISS, FINDING, REGRESSION)

#: Carbon's own attack oracle: the only source a finding may come from.
ORACLE = "carbon_attack_oracle"
#: Public material (published attack patterns, public Challenge documents).
PUBLIC = "public_material"
SOURCES = (ORACLE, PUBLIC)

#: An attempt's outcome as the oracle reported it.
OUTCOMES = (
    "HELD",
    "REFUSED",
    "BREACHED",
    "TIMEOUT",
    "CRASH",
    "UNREBUILDABLE",
    "NOT_RUN",
)
#: Outcomes that show the boundary held. A REFUSED attack (a removed
#: permission coming back refused) is a hold.
HOLDS = ("HELD", "REFUSED")
#: Outcomes that are never a hold and never a breach: a timeout is never a
#: pass, and neither is anything Carbon could not rebuild or did not run.
INCONCLUSIVE_OUTCOMES = ("TIMEOUT", "CRASH", "UNREBUILDABLE", "NOT_RUN")
#: What an oracle may raise when its run fails (a timeout is an `OSError`).
#: Each is recorded INCONCLUSIVE on a re-run; anything else propagates.
ORACLE_FAILURES = (
    ArithmeticError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
#: A regression specimen's state under a new adapter or contract version.
REGRESSION_STATES = ("HELD", "BREACHED", "INCONCLUSIVE")

#: The eight shared Track A checks every adapter supplies.
TRACK_A_CHECKS = frozenset(CHECKS[LEDGER_TRACK])

TRAINED, HELD_OUT = "trained", "held_out"
#: The only control split the engine may read (`training_view`).
TRAINING_SPLIT = TRAINED

#: Sealed and confirmation material beyond the protected rule's markers
#: (EV5's sealed batch, a private pool, a Challenge's final conditions).
#: Lower-case substrings; the store may over-refuse, never under-refuse.
SEALED_MARKERS = (
    "sealed",
    "private_pool",
    "private-pool",
    "private pool",
    "final_condition",
    "final-condition",
    "final condition",
)
#: Held-out control material, never stored for training.
HELD_OUT_MARKERS = ("held_out", "held-out", "held out", "heldout")
#: Path fragments a store root may not contain (any component, lower case).
ROOT_DENIED = (
    "ev4",
    "ev5",
    "confirmation",
    "seal",
    "secret",
    "credential",
    "canary",
    *HELD_OUT_MARKERS,
)

MAX_PAYLOAD_BYTES = 64 * 1024
MAX_TEXT = 500
MAX_EVIDENCE = 32
MAX_LEVEL = 64

STORE_ROOT_INVALID = "attack_store_root_invalid"
RECORD_INVALID = "attack_record_invalid"
RECORD_CORRUPT = "attack_record_corrupt"
PROTECTED_REFUSED = "protected_material_refused"
SEALED_REFUSED = "sealed_material_refused"
HELD_OUT_REFUSED = "held_out_control_refused"
SOURCE_REFUSED = "attack_source_refused"
CONDITION_REFUSED = "condition_not_in_vocabulary"
UNREBUILT_REFUSED = "unrebuilt_construction_not_scored"
SNAPSHOT_NOT_FOUND = "attack_snapshot_not_found"
SNAPSHOT_CORRUPT = "attack_snapshot_corrupt"
REPLAY_REFUSED = "replay_under_another_digest"
READ_ONLY = "attack_view_read_only"

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CHALLENGE = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
_FAMILY = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class KnowledgeError(ValueError):
    """A typed refusal from the attack-knowledge store; nothing was changed."""

    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code, self.detail = code, detail


# -- the content rules ------------------------------------------------------------


def _strings(value):
    if type(value) is str:
        yield value
    elif type(value) is dict:
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif type(value) in (list, tuple):
        for item in value:
            yield from _strings(item)


def _named(value, markers):
    return any(marker in text.lower() for text in _strings(value) for marker in markers)


def sealed(value):
    """True when any string in `value` names sealed or confirmation material
    (the protected rule's markers, or the store's own)."""
    return protected(value) or _named(value, SEALED_MARKERS)


def held_out(value):
    """True when any string in `value` names held-out control material."""
    return _named(value, HELD_OUT_MARKERS)


def _content(record):
    """The record less its `check`, which is one of the eight fixed Track A
    check names (one of them, `fresh_attack_confirmation`, names the
    confirmation study it would run; it is vocabulary, not material)."""
    return {key: value for key, value in record.items() if key != "check"}


def exposure_finding(record):
    """The `OTHER_SIGNAL` finding recorded for a development finding that
    names protected or sealed material: the material is withheld and only its
    digest kept; each identifying field that itself names it is dropped."""
    kept = {}
    for key in ("family", "boundary", "strategy", "attempt_id"):
        value = record.get(key)
        kept[key] = None if value is None or sealed(value) or held_out(value) else value
    return {
        "schema": RECORD_SCHEMA,
        "kind": FINDING,
        "challenge_id": record["challenge_id"],
        "level": record["level"],
        "contract_digest": record["contract_digest"],
        "check": record["check"],
        **kept,
        "source": ORACLE,
        "condition": "OTHER_SIGNAL",
        "reported_condition": record["condition"],
        "protected_case_named": True,
        "withheld_digest": digest(canonical(_content(record))),
        "specimen": None,
        "control": None,
        "evidence": list(record["evidence"]),
    }


def _admissible(record):
    """Why a stored record may not be served now, or None."""
    content = _content(record)
    if held_out(content):
        return HELD_OUT_REFUSED
    if sealed(content):
        return SEALED_REFUSED if not protected(content) else PROTECTED_REFUSED
    return None


# -- validation -----------------------------------------------------------------


def _invalid(detail):
    return KnowledgeError(RECORD_INVALID, detail)


def _text(value, name, *, pattern=None, optional=False):
    if value is None and optional:
        return None
    if type(value) is not str or not value:
        raise _invalid(name + " is a non-empty string")
    if pattern is not None and not pattern.fullmatch(value):
        raise _invalid(name + " is malformed")
    if len(value) > MAX_TEXT or _CONTROL_CHARS.search(value):
        raise _invalid(name + " is short printable text")
    return value


def _payload(value, name):
    if type(value) is not dict:
        raise _invalid(name + " is a JSON object")
    try:
        body = canonical(value)
    except (TypeError, ValueError):
        raise _invalid(name + " is finite JSON data") from None
    if len(body) > MAX_PAYLOAD_BYTES:
        raise _invalid(name + " is at most 64 KiB")
    return json.loads(body)


def _control(value):
    """None, or `{split, control_id}` for a control the oracle judged. Only a
    trained control is ever stored."""
    if value is None:
        return None
    if type(value) is not dict or set(value) != {"split", "control_id"}:
        raise _invalid("control is {split, control_id}")
    if value["split"] == HELD_OUT:
        raise KnowledgeError(HELD_OUT_REFUSED, "held-out controls are never stored")
    if value["split"] != TRAINED:
        raise _invalid("control split is trained")
    return {
        "split": TRAINED,
        "control_id": _text(value["control_id"], "control_id", pattern=_LABEL),
    }


def _common(
    kind,
    *,
    challenge_id,
    level,
    contract_digest,
    check,
    family,
    boundary,
    strategy,
    attempt_id,
    source,
):
    if type(level) is not int or not 0 <= level <= MAX_LEVEL:
        raise _invalid("level is a construction level")
    if check not in TRACK_A_CHECKS:
        raise _invalid("check is one of the eight Track A checks")
    if source not in SOURCES:
        raise KnowledgeError(
            SOURCE_REFUSED, "the store learns from " + ", ".join(SOURCES)
        )
    return {
        "schema": RECORD_SCHEMA,
        "kind": kind,
        "challenge_id": _text(challenge_id, "challenge_id", pattern=_CHALLENGE),
        "level": level,
        "contract_digest": _text(contract_digest, "contract_digest", pattern=_DIGEST),
        "check": check,
        "family": _text(family, "family", pattern=_FAMILY),
        "boundary": _text(boundary, "boundary"),
        "strategy": _text(strategy, "strategy", pattern=_LABEL),
        "attempt_id": _text(attempt_id, "attempt_id", pattern=_LABEL),
        "source": source,
    }


def _refuse_material(record):
    """Refuse a record that names held-out, sealed or protected material."""
    reason = _admissible(record)
    if reason is not None:
        raise KnowledgeError(reason, record["kind"])


# -- files ----------------------------------------------------------------------


def _flock(descriptor):
    try:
        import fcntl
    except ImportError:  # pragma: no cover - Carbon's hosts run Linux
        import msvcrt

        msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
        return
    fcntl.flock(descriptor, fcntl.LOCK_EX)


@contextlib.contextmanager
def _locked(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | _NOFOLLOW, 0o600)
    try:
        _flock(descriptor)
        yield
    finally:
        os.close(descriptor)


def _append(path, payload):
    """Append one complete line, durably. A torn final line (a crash
    mid-append) is cut off first; it was never a journal entry."""
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | _NOFOLLOW, 0o600)
    try:
        size = os.fstat(descriptor).st_size
        if size:
            body = os.pread(descriptor, size, 0)
            keep = body.rfind(b"\n") + 1
            if keep != size:
                os.ftruncate(descriptor, keep)
        line = memoryview(payload + b"\n")
        while line:
            line = line[os.write(descriptor, line) :]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _lines(path):
    if not path.exists():
        return []
    body = path.read_bytes()
    complete = body[: body.rfind(b"\n") + 1]
    return [json.loads(line) for line in complete.splitlines() if line]


def _hex(value):
    if type(value) is not str or not _DIGEST.fullmatch(value):
        raise KnowledgeError(SNAPSHOT_NOT_FOUND, "a digest is sha256")
    return value[len("sha256:") :]


def _checked_root(root):
    root = Path(root)
    if not root.is_absolute() or root.is_symlink():
        raise KnowledgeError(STORE_ROOT_INVALID, "an absolute, non-symlink root")
    for part in root.parts:
        lowered = part.lower()
        if any(fragment in lowered for fragment in ROOT_DENIED):
            raise KnowledgeError(
                STORE_ROOT_INVALID, "the root may not live in sealed material"
            )
    return root


# -- reading ----------------------------------------------------------------------


def _stats():
    return {
        "attempts": 0,
        "held": 0,
        "breached": 0,
        "inconclusive": 0,
        "near_misses": 0,
        "findings": 0,
    }


def _count(stats, record):
    kind = record["kind"]
    if kind == ATTEMPT:
        stats["attempts"] += 1
        outcome = record["outcome"]
        if outcome in HOLDS:
            stats["held"] += 1
        elif outcome == "BREACHED":
            stats["breached"] += 1
        else:
            stats["inconclusive"] += 1
    elif kind == NEAR_MISS:
        stats["near_misses"] += 1
    elif kind == FINDING:
        stats["findings"] += 1


def _oracle_state(result):
    """A regression state from an adapter's oracle result: an object or dict
    with `state` (an outcome) or a Boolean `breached`. Anything else, and
    every timeout, crash or unrebuildable result, is INCONCLUSIVE."""
    state = getattr(result, "state", None)
    if state is None and type(result) is dict:
        state = result.get("state")
    if state is None:
        breached = getattr(result, "breached", None)
        if breached is None and type(result) is dict:
            breached = result.get("breached")
        if type(breached) is bool:
            return "BREACHED" if breached else "HELD"
        return "INCONCLUSIVE"
    if state in HOLDS:
        return "HELD"
    return "BREACHED" if state == "BREACHED" else "INCONCLUSIVE"


class _Reader:
    """Reads over an ordered list of `(kind, digest)` entries."""

    def __init__(self, root):
        self.root = root
        self._cache = {}

    def _entries(self):  # pragma: no cover - each reader supplies its entries
        raise NotImplementedError

    def _object(self, value):
        found = self._cache.get(value)
        if found is None:
            path = self.root / "objects" / (_hex(value) + ".json")
            if not path.is_file() or path.is_symlink():
                raise KnowledgeError(RECORD_CORRUPT, "missing record " + value)
            body = path.read_bytes()
            if digest(body) != value:
                raise KnowledgeError(RECORD_CORRUPT, "record does not match " + value)
            found = json.loads(body)
            if found.get("schema") != RECORD_SCHEMA:
                raise KnowledgeError(RECORD_CORRUPT, "not an attack record")
            self._cache[value] = found
        return found

    def _served(self):
        """`(served, withheld)`: every record still admissible on read, with
        its digest, in journal order; and the digests of the rest."""
        served, withheld = [], []
        for kind, value in self._entries():
            record = self._object(value)
            if record["kind"] != kind:
                raise KnowledgeError(RECORD_CORRUPT, "journal kind mismatch")
            if _admissible(record) is not None:
                withheld.append(value)
                continue
            served.append({"record_digest": value, **json.loads(canonical(record))})
        return served, withheld

    def withheld(self):
        """Digests of records the protected or sealed rule withholds on read."""
        return self._served()[1]

    def records(self, kind=None, *, challenge_id=None, level=None):
        if kind is not None and kind not in KINDS:
            raise _invalid("kind is one of " + ", ".join(KINDS))
        return [
            record
            for record in self._served()[0]
            if (kind is None or record["kind"] == kind)
            and (challenge_id is None or record["challenge_id"] == challenge_id)
            and (level is None or record["level"] == level)
        ]

    def attempts(self, challenge_id=None, level=None):
        return self.records(ATTEMPT, challenge_id=challenge_id, level=level)

    def near_misses(self, challenge_id=None, level=None):
        return self.records(NEAR_MISS, challenge_id=challenge_id, level=level)

    def findings(self, challenge_id=None, level=None):
        return self.records(FINDING, challenge_id=challenge_id, level=level)

    def regressions(self, challenge_id=None, level=None):
        return self.records(REGRESSION, challenge_id=challenge_id, level=level)

    def specimens(self, challenge_id, level):
        """The regression specimens for one Challenge and construction level:
        one per verified finding that has one, in the order found."""
        return [
            {
                "finding": record["record_digest"],
                "challenge_id": record["challenge_id"],
                "level": record["level"],
                "contract_digest": record["contract_digest"],
                "check": record["check"],
                "family": record["family"],
                "boundary": record["boundary"],
                "strategy": record["strategy"],
                "condition": record["condition"],
                "specimen": record["specimen"],
            }
            for record in self.findings(challenge_id, level)
            if record["specimen"] is not None
        ]

    def regression_due(self, challenge_id, level, contract_digest):
        """The specimens not yet re-run under `contract_digest`, a version
        other than the one each was found under."""
        done = {
            record["finding"]
            for record in self.regressions(challenge_id, level)
            if record["contract_digest"] == contract_digest
        }
        return [
            specimen
            for specimen in self.specimens(challenge_id, level)
            if specimen["contract_digest"] != contract_digest
            and specimen["finding"] not in done
        ]

    def priors(self, challenge_id=None):
        """What the attack runs have taught, by check, family, boundary and
        strategy: for one Challenge, or across every Challenge (None).
        Families are keyed by name within a Challenge and by
        `<challenge>/<family>` across Challenges. Counts only: no score."""
        if challenge_id is not None:
            _text(challenge_id, "challenge_id", pattern=_CHALLENGE)
        by_check = {check: _stats() for check in sorted(TRACK_A_CHECKS)}
        by_family, by_strategy, challenges = {}, {}, set()
        for record in self._served()[0]:
            if record["kind"] == REGRESSION:
                continue
            if challenge_id is not None and record["challenge_id"] != challenge_id:
                continue
            challenges.add(record["challenge_id"])
            _count(by_check[record["check"]], record)
            if record["family"] is not None:
                key = record["family"]
                if challenge_id is None:
                    key = record["challenge_id"] + "/" + key
                family = by_family.setdefault(
                    key,
                    {
                        **_stats(),
                        "check": record["check"],
                        "levels": [],
                        "boundaries": {},
                    },
                )
                _count(family, record)
                if record["level"] not in family["levels"]:
                    family["levels"] = sorted([*family["levels"], record["level"]])
                if record["boundary"] is not None:
                    _count(
                        family["boundaries"].setdefault(record["boundary"], _stats()),
                        record,
                    )
            if record["strategy"] is not None:
                strategy = by_strategy.setdefault(
                    record["strategy"], {**_stats(), "found": []}
                )
                _count(strategy, record)
                if record["kind"] == FINDING:
                    strategy["found"].append(
                        {
                            "finding": record["record_digest"],
                            "challenge_id": record["challenge_id"],
                            "family": record["family"],
                            "condition": record["condition"],
                        }
                    )
        return json.loads(
            canonical(
                {
                    "schema": PRIORS_SCHEMA,
                    "scope": challenge_id,
                    "challenges": sorted(challenges),
                    "by_check": by_check,
                    "by_family": by_family,
                    "by_strategy": by_strategy,
                }
            )
        )


class ReadOnlyView(_Reader):
    """The records one snapshot froze: what a frozen admission run used."""

    def __init__(self, root, value):
        super().__init__(root)
        path = root / "snapshots" / (_hex(value) + ".json")
        if not path.is_file() or path.is_symlink():
            raise KnowledgeError(SNAPSHOT_NOT_FOUND, value)
        body = path.read_bytes()
        if digest(body) != value:
            raise KnowledgeError(SNAPSHOT_CORRUPT, "snapshot does not match " + value)
        document = json.loads(body)
        if document.get("schema") != SNAPSHOT_SCHEMA:
            raise KnowledgeError(SNAPSHOT_CORRUPT, "not an attack-knowledge snapshot")
        self.digest = value
        self._frozen = tuple(
            (entry["kind"], entry["digest"]) for entry in document["records"]
        )
        # Every frozen record must still be present and match its digest.
        for kind, record in self._frozen:
            if self._object(record)["kind"] != kind:
                raise KnowledgeError(SNAPSHOT_CORRUPT, "snapshot kind mismatch")

    def _entries(self):
        return self._frozen

    def replay(self, value):
        """This view, for a replay under `value`; refused unless `value` is
        the digest the run pinned (invariant 10: no silent re-reading)."""
        if value != self.digest:
            raise KnowledgeError(
                REPLAY_REFUSED, f"pinned {self.digest}, asked {str(value)[:80]}"
            )
        return self

    def suite_pin(self):
        """What a frozen admission run records in its suite version."""
        return {"schema": SUITE_PIN_SCHEMA, "attack_knowledge_digest": self.digest}

    def _read_only(self, *_args, **_kwargs):
        raise KnowledgeError(READ_ONLY, "a pinned view is never written")

    add_attempt = add_near_miss = add_finding = add_regression = _read_only
    replay_specimens = snapshot = _read_only


class AttackStore(_Reader):
    """The durable, content-addressed, append-only attack-knowledge store."""

    def __init__(self, root):
        root = _checked_root(root)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if hasattr(os, "getuid") and root.stat().st_uid != os.getuid():
            raise KnowledgeError(STORE_ROOT_INVALID, "the root is not this user's")
        root.chmod(0o700)
        for name in ("objects", "snapshots"):
            (root / name).mkdir(exist_ok=True, mode=0o700)
        super().__init__(root)
        self.journal = root / "journal.jsonl"

    def _entries(self):
        return [(entry["kind"], entry["digest"]) for entry in _lines(self.journal)]

    def _lock(self):
        return _locked(self.root / "store.lock")

    def _put(self, record):
        body = canonical(record)
        value = digest(body)
        with self._lock():
            path = self.root / "objects" / (_hex(value) + ".json")
            write_once(path, body)
            entries = _lines(self.journal)
            if not any(entry["digest"] == value for entry in entries):
                _append(
                    self.journal,
                    canonical(
                        {
                            "schema": JOURNAL_SCHEMA,
                            "seq": len(entries) + 1,
                            "kind": record["kind"],
                            "digest": value,
                        }
                    ),
                )
        return value

    # -- writes ---------------------------------------------------------------------
    def add_attempt(
        self,
        *,
        challenge_id,
        level,
        contract_digest,
        check,
        family,
        boundary,
        strategy,
        attempt_id,
        attempt,
        outcome,
        source=ORACLE,
        control=None,
    ):
        """Record one attack the oracle judged; its record digest. The same
        attempt recorded twice is stored once."""
        control = _control(control)
        record = _common(
            ATTEMPT,
            challenge_id=challenge_id,
            level=level,
            contract_digest=contract_digest,
            check=check,
            family=family,
            boundary=boundary,
            strategy=strategy,
            attempt_id=attempt_id,
            source=source,
        )
        if outcome not in OUTCOMES:
            raise _invalid("outcome is one of " + ", ".join(OUTCOMES))
        record.update(
            attempt=_payload(attempt, "attempt"), outcome=outcome, control=control
        )
        _refuse_material(record)
        return self._put(record)

    def add_near_miss(
        self,
        *,
        challenge_id,
        level,
        contract_digest,
        check,
        family,
        boundary,
        strategy,
        attempt_id,
        attempt,
        note,
        margin=None,
        source=ORACLE,
    ):
        """Record an attack that came close to a boundary without crossing
        it; `margin` is the oracle's own distance, when it reports one."""
        record = _common(
            NEAR_MISS,
            challenge_id=challenge_id,
            level=level,
            contract_digest=contract_digest,
            check=check,
            family=family,
            boundary=boundary,
            strategy=strategy,
            attempt_id=attempt_id,
            source=source,
        )
        if margin is not None and (
            type(margin) not in (int, float) or not math.isfinite(margin)
        ):
            raise _invalid("margin is a finite number")
        record.update(
            attempt=_payload(attempt, "attempt"),
            note=_text(note, "note"),
            margin=margin,
        )
        _refuse_material(record)
        return self._put(record)

    def add_finding(
        self,
        *,
        challenge_id,
        level,
        contract_digest,
        check,
        family,
        boundary,
        strategy,
        attempt_id,
        condition,
        specimen,
        evidence,
        rebuilt,
        source=ORACLE,
        control=None,
    ):
        """Record a verified finding and its regression specimen; its record
        digest. A finding is an oracle row on a construction Carbon rebuilt
        (`rebuilt` is True), in the CONDITIONS vocabulary. One that names
        protected or sealed material is recorded as an OTHER_SIGNAL exposure
        with that material withheld (`exposure_finding`)."""
        control = _control(control)
        record = _common(
            FINDING,
            challenge_id=challenge_id,
            level=level,
            contract_digest=contract_digest,
            check=check,
            family=family,
            boundary=boundary,
            strategy=strategy,
            attempt_id=attempt_id,
            source=source,
        )
        if source != ORACLE:
            raise KnowledgeError(SOURCE_REFUSED, "a finding is an attack-oracle row")
        if rebuilt is not True:
            raise KnowledgeError(
                UNREBUILT_REFUSED, "Carbon scores only what it rebuilt"
            )
        if condition not in CONDITIONS:
            raise KnowledgeError(CONDITION_REFUSED, str(condition)[:80])
        if (
            type(evidence) is not list
            or not 1 <= len(evidence) <= MAX_EVIDENCE
            or any(
                type(item) is not str or not _DIGEST.fullmatch(item)
                for item in evidence
            )
        ):
            raise _invalid("evidence is a list of sha256 digests")
        record.update(
            condition=condition,
            specimen=_payload(specimen, "specimen"),
            control=control,
            evidence=sorted(set(evidence)),
        )
        if held_out(_content(record)):
            raise KnowledgeError(HELD_OUT_REFUSED, FINDING)
        if sealed(_content(record)):
            record = exposure_finding(record)
        return self._put(record)

    def add_regression(self, *, finding, contract_digest, state, detail=None):
        """Record a specimen's re-run under a new adapter or contract
        version. TIMEOUT, CRASH and the like are INCONCLUSIVE, never HELD."""
        _text(finding, "finding", pattern=_DIGEST)
        if (FINDING, finding) not in self._entries():
            raise _invalid("a regression re-runs a recorded finding")
        source = self._object(finding)
        if source["specimen"] is None or _admissible(source) is not None:
            raise _invalid("a regression re-runs a finding's served specimen")
        if state not in REGRESSION_STATES:
            raise _invalid("state is one of " + ", ".join(REGRESSION_STATES))
        record = {
            "schema": RECORD_SCHEMA,
            "kind": REGRESSION,
            "challenge_id": source["challenge_id"],
            "level": source["level"],
            "contract_digest": _text(
                contract_digest, "contract_digest", pattern=_DIGEST
            ),
            "check": source["check"],
            "family": source["family"],
            "boundary": source["boundary"],
            "strategy": None,
            "attempt_id": None,
            "source": ORACLE,
            "finding": finding,
            "state": state,
            "detail": _text(detail, "detail", optional=True),
        }
        _refuse_material(record)
        return self._put(record)

    def replay_specimens(self, adapter):
        """Re-run every due specimen for the adapter's Challenge and level
        through its oracle (`adapter.oracle(family, specimen)`), recording
        each result. An oracle that raises is INCONCLUSIVE (a crash is never
        a hold). Returns `[{finding, state}]`."""
        view = training_view(adapter)
        rows = []
        for specimen in self.regression_due(
            view.challenge_id, view.level, view.contract_digest
        ):
            detail = None
            try:
                state = _oracle_state(
                    view.oracle(specimen["family"], specimen["specimen"])
                )
            except ORACLE_FAILURES as error:  # a crash is never a hold
                state = "INCONCLUSIVE"
                detail = "oracle raised " + type(error).__name__
            self.add_regression(
                finding=specimen["finding"],
                contract_digest=view.contract_digest,
                state=state,
                detail=detail,
            )
            rows.append({"finding": specimen["finding"], "state": state})
        return rows

    # -- snapshots -------------------------------------------------------------------
    def snapshot(self):
        """Freeze the journal; the store's digest. The same records give the
        same digest."""
        with self._lock():
            document = {
                "schema": SNAPSHOT_SCHEMA,
                "records": [
                    {"kind": kind, "digest": value} for kind, value in self._entries()
                ],
            }
            body = canonical(document)
            value = digest(body)
            write_once(self.root / "snapshots" / (_hex(value) + ".json"), body)
        return value

    def pin(self, value):
        """A read-only view of exactly what snapshot `value` froze."""
        return ReadOnlyView(self.root, value)


class _TrainingAdapter:
    """An adapter as the engine may see it: every attribute but the held-out
    controls."""

    def __init__(self, adapter):
        object.__setattr__(self, "_adapter", adapter)

    def __getattr__(self, name):
        return getattr(self._adapter, name)

    def __setattr__(self, name, value):
        raise AttributeError("a training view is read only")

    def controls(self, split):
        if split != TRAINING_SPLIT:
            raise KnowledgeError(
                HELD_OUT_REFUSED, "the engine never reads held-out controls"
            )
        return self._adapter.controls(split)


def training_view(adapter):
    """The adapter as the engine may read it: `controls('held_out')` is
    refused. The held-out split is read only by the report."""
    return adapter if type(adapter) is _TrainingAdapter else _TrainingAdapter(adapter)


def trained_controls(adapter):
    """The adapter's trained controls: the only controls the engine reads."""
    return training_view(adapter).controls(TRAINING_SPLIT)
