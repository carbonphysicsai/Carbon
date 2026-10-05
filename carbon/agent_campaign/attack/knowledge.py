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
in the order they were added, once each. The journal is hash-chained: each
entry carries its sequence number and the sha256 of the entry line before it
(`prev`), and every read checks the sequence and the chain, so a dropped,
reordered, inserted or edited entry is refused (`attack_record_corrupt`),
never read past. `snapshot()` freezes the journal as
a document whose sha256 is the store's digest, and `pin(digest)` returns a
`ReadOnlyView` of exactly the records that snapshot holds. A frozen
admission run pins that digest in its suite version (`ReadOnlyView.suite_pin`);
specimens added later belong to the next suite version; replaying a frozen run
under any other digest is refused (`ReadOnlyView.replay`, invariant 10).

What the store learns from, and what it refuses:

- Only Carbon's own attack-oracle rows (`ORACLE`) and public material
  (`PUBLIC`). A finding is only ever an oracle row on a construction Carbon
  rebuilt; anything else is refused typed.
- Every record is checked with the store's protected rule (`protected`:
  Graphite's protected markers and the deny fragments that name sealed or
  confirmation material), its registered sealed identities
  (`SEALED_IDENTITIES`: public fingerprints, commitments, role names and
  condition ids, matched after Unicode, homoglyph, case and separator
  normalisation; short condition ids only study-qualified or in a record of
  their study)
  and its own sealed-material markers
  when it is written **and again when it is read**; a record that fails on
  read is withheld by the live store, never served, and a pinned view that
  holds such a record refuses to serve anything (`attack_snapshot_withheld`)
  rather than a subset. The store's root may not live in a
  sealed, confirmation, secret or canary location, and nothing here opens a
  path outside that root: it never reads sealed or confirmation material.
- A development finding that names a protected, sealed or held-out case is
  not dropped: it is recorded as an `OTHER_SIGNAL` finding (an exposure)
  with that content withheld and only its digest kept (`exposure_finding`).
- Findings use only the CONDITIONS vocabulary
  (`challenge_readiness.admission.CONDITIONS`).
- Held-out controls are never stored, and the engine never reads them: the
  store refuses a held-out control on write, and `training_view(adapter)` is
  the one way the engine reaches an adapter, an allow-list that refuses the
  held-out split and exposes nothing else that could reach it. Wrongful rejection on held-out controls is the report's
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
import unicodedata
from pathlib import Path

# `literature` first: `tools` imports it, and it calls back into `tools` while
# it loads, so importing `tools` first fails on the half-built module.
from carbon.agent_campaign.graphite import literature  # noqa: F401
from carbon.agent_campaign.graphite import tools as _tools
from carbon.challenge_pipeline import suite as _suite
from carbon.challenge_readiness.admission import CHECKS, CONDITIONS, LEDGER_TRACK
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

SCHEMA_PREFIX = "carbon.graphite.attack-knowledge"
RECORD_SCHEMA = SCHEMA_PREFIX + ".record.v1"
#: v2: each entry carries `prev`, the sha256 of the entry line before it
#: (None for the first), checked with `seq` on every read.
JOURNAL_SCHEMA = SCHEMA_PREFIX + ".journal.v2"
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

#: An attempt's outcome as the oracle reported it. FAILED_INFRA is an
#: infrastructure failure, kept apart from a crash (invariant 7).
OUTCOMES = (
    "HELD",
    "REFUSED",
    "BREACHED",
    "TIMEOUT",
    "CRASH",
    "FAILED_INFRA",
    "UNREBUILDABLE",
    "NOT_RUN",
)
#: Outcomes that show the boundary held. A REFUSED attack (a removed
#: permission coming back refused) is a hold.
HOLDS = ("HELD", "REFUSED")
#: Outcomes that are never a hold and never a breach: a timeout or an
#: infrastructure failure is never a pass, and neither is anything Carbon
#: could not rebuild or did not run.
INCONCLUSIVE_OUTCOMES = ("TIMEOUT", "CRASH", "FAILED_INFRA", "UNREBUILDABLE", "NOT_RUN")
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
#: An oracle verdict (`attack.adapter.OracleResult.verdict`) as a regression
#: state. Every verdict not listed (FAILED_INFRA, TIMEOUT, CRASHED, NOT_RUN,
#: or anything unknown) is INCONCLUSIVE.
VERDICT_STATES = {"HELD": "HELD", "REFUSED": "HELD", "BREACHED": "BREACHED"}

#: The eight shared Track A checks every adapter supplies.
TRACK_A_CHECKS = frozenset(CHECKS[LEDGER_TRACK])

TRAINED, HELD_OUT = "trained", "held_out"
#: The only control split the engine may read (`training_view`).
TRAINING_SPLIT = TRAINED

#: Sealed material, by its registered PUBLIC identity: only identities
#: already committed in the repository (commitments, fingerprints, role names
#: and condition ids), never sealed contents, which nothing here reads. Each
#: entry names the public record it is copied from. Matched after Unicode
#: (NFKC), homoglyph (`HOMOGLYPHS`), case (casefold) and separator
#: normalisation: a digest by its hex (whole, or a prefix of at least
#: `DIGEST_PREFIX_MIN` hex characters as its own token), a phrase as a
#: whole-token sequence, and a scoped phrase as a whole-token sequence after
#: one of its scope phrases, or alone in a value that names a scope phrase.
SEALED_IDENTITIES = (
    {
        "id": "ev5-confirmation-fingerprint",
        "kind": "digest",
        "value": "sha256:0add08ed7a3c6568a0779b0becb123578eedee6ca8e4f9f014588ed4ba934f3e",
        "source": ".agent/decisions/2026-10-03-OWNER-EV5-FREEZE-01.md",
    },
    {
        "id": "ev5-confirmation-journal-sequence",
        "kind": "phrase",
        "value": ("journal sequence 14", "journal seq 14"),
        "source": ".agent/decisions/2026-10-03-OWNER-EV5-FREEZE-01.md",
    },
    {
        "id": "ev5-confirmation-role",
        "kind": "phrase",
        "value": ("ev5-confirmation",),
        "source": "carbon/challenge_validator/interface.py RESERVED_SEED_ROLES",
    },
    {
        "id": "motor-private-pool-commitment",
        "kind": "digest",
        "value": "sha256:5ec0222502eb608c52d1162f4be6c7347deed7b6d4f03777ec4ea31b6d619559",
        "source": "docs/development/evidence/motor-pools-v1/pools.json",
    },
    {
        "id": "graphite-confirmation-role",
        "kind": "phrase",
        "value": ("graphite-confirmation-v1",),
        "source": ".agent/decisions/2026-10-04-OWNER-GRAPHITE-TEST-WAVE-01.md item 7",
    },
    {
        # Short ids that ordinary text can carry ("boundary 01"), so they are
        # scoped: the study-qualified id ("<study>/rep-01", or the Challenge
        # token before it) matches anywhere; the bare id only in a record
        # that names the study or the Challenge (a cooling-context record).
        "id": "cooling-final-condition-ids",
        "kind": "scoped_phrase",
        "value": (
            "rep-01",
            "rep-02",
            "rep-03",
            "rep-04",
            "boundary-01",
            "boundary-02",
        ),
        # freeze.json `study_id` and `decision_contract.challenge`.
        "scope": ("ai-accelerator-cooling-synthetic-v1", "chip-cold-plate"),
        "source": "docs/development/evidence/cold-plate-decision-fixture-v2/"
        "construction/freeze.json case_roles.final_decision_evaluation",
    },
)
#: The shortest hex prefix of a registered digest that counts as naming it
#: (git's short form).
DIGEST_PREFIX_MIN = 7
#: The checkout deny rule's fragments (`boundaries.DENY_FRAGMENTS`) that name
#: sealed or confirmation material. `ev4`/`ev5` match at a token start, so
#: `dev5` does not; the rest as substrings of the normalised text. The other
#: deny fragments (`.env`, `secret`, `credential`) and prefixes (`tests/`,
#: `carbon/agent_campaign/`, `.agent/`, `docs/development/evidence/`) name
#: attack *targets*, not material: the store holds attack inputs and
#: digests, never results, so a real breach that names one keeps its own
#: condition and its regression specimen, stored operator-side.
PROTECTED_TOKEN_STARTS = ("ev4", "ev5")
PROTECTED_FRAGMENTS = ("confirmation", "canary")

#: Sealed and confirmation material beyond the protected rule's markers
#: (EV5's sealed batch, a private pool, a Challenge's final conditions).
#: Matched after normalisation; the store may over-refuse, never
#: under-refuse.
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
SNAPSHOT_WITHHELD = "attack_snapshot_withheld"
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
    """Every string in a JSON value, including JSON carried inside strings."""
    if type(value) is str:
        yield value
        if value[:1] in ("{", "["):
            try:
                inner = json.loads(value)
            except (ValueError, RecursionError):
                return
            yield from _strings(inner)
    elif type(value) is dict:
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif type(value) in (list, tuple):
        for item in value:
            yield from _strings(item)


_TOKEN = re.compile(r"[^\W_]+")

#: Common Cyrillic and Greek look-alikes of Latin letters, folded to the
#: Latin letter before matching, so `ev5` or `held out` spelled with a
#: Cyrillic or Greek letter still names what it spells. The store may
#: over-refuse, never under-refuse.
HOMOGLYPHS = str.maketrans(
    {
        chr(code): latin
        for code, latin in (
            # Cyrillic, upper and lower case
            *((0x0410, "a"), (0x0430, "a"), (0x0412, "b"), (0x0432, "b")),
            *((0x0415, "e"), (0x0435, "e"), (0x0401, "e"), (0x0451, "e")),
            *((0x041A, "k"), (0x043A, "k"), (0x041C, "m"), (0x043C, "m")),
            *((0x041D, "h"), (0x043D, "h"), (0x041E, "o"), (0x043E, "o")),
            *((0x0420, "p"), (0x0440, "p"), (0x0421, "c"), (0x0441, "c")),
            *((0x0422, "t"), (0x0442, "t"), (0x0423, "y"), (0x0443, "y")),
            *((0x0425, "x"), (0x0445, "x"), (0x0406, "i"), (0x0456, "i")),
            *((0x0407, "i"), (0x0457, "i"), (0x0408, "j"), (0x0458, "j")),
            *((0x0405, "s"), (0x0455, "s"), (0x0500, "d"), (0x0501, "d")),
            *((0x04AE, "y"), (0x04AF, "y"), (0x04BA, "h"), (0x04BB, "h")),
            *((0x04C0, "l"), (0x04CF, "l"), (0x051A, "q"), (0x051B, "q")),
            *((0x051C, "w"), (0x051D, "w")),
            # Greek, upper and lower case
            *((0x0391, "a"), (0x03B1, "a"), (0x0392, "b"), (0x03B2, "b")),
            *((0x0395, "e"), (0x03B5, "e"), (0x0396, "z"), (0x0397, "h")),
            *((0x0399, "i"), (0x03B9, "i"), (0x039A, "k"), (0x03BA, "k")),
            *((0x039C, "m"), (0x039D, "n"), (0x03BD, "v"), (0x039F, "o")),
            *((0x03BF, "o"), (0x03A1, "p"), (0x03C1, "p"), (0x03A4, "t")),
            *((0x03C4, "t"), (0x03A5, "y"), (0x03C5, "u"), (0x03A7, "x")),
            *((0x03C7, "x"), (0x03F9, "c"), (0x03F2, "c"), (0x03F3, "j")),
        )
    }
)


def normalise(text):
    """`text` for matching: NFKC, invisible format characters dropped,
    Cyrillic and Greek look-alikes folded to Latin (`HOMOGLYPHS`),
    casefolded, every run of separators one space. Returns `(spaced,
    compact)`: the tokens joined by single spaces, and joined by nothing."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    tokens = _TOKEN.findall(text.translate(HOMOGLYPHS).casefold())
    return " ".join(tokens), "".join(tokens)


def _marker_hit(marker, spaced, compact):
    """A marker names the text: as a substring of its spaced form, or, for a
    marker of several tokens, of its compact form too (`privatepool`)."""
    m_spaced, m_compact = normalise(marker)
    if not m_spaced:
        return False
    if m_spaced in spaced:
        return True
    return " " in m_spaced and m_compact in compact


def _named(value, markers):
    for text in _strings(value):
        spaced, compact = normalise(text)
        if any(_marker_hit(marker, spaced, compact) for marker in markers):
            return True
    return False


_HEX = re.compile(r"[0-9a-f]+\Z")


def _phrase_in(phrase, padded):
    """A phrase names the text as a whole-token sequence (`padded` is the
    text's spaced form with a space at each end)."""
    return " " + normalise(phrase)[0] + " " in padded


def _scope_named(entry, texts):
    """Whether any of the normalised `texts` names one of a scoped entry's
    scope phrases: as whole tokens, or, for a phrase of several tokens, run
    together (`chipcoldplate`)."""
    for scope in entry["scope"]:
        s_spaced, s_compact = normalise(scope)
        for spaced, compact in texts:
            if " " + s_spaced + " " in " " + spaced + " ":
                return True
            if " " in s_spaced and s_compact in compact:
                return True
    return False


def _identity_hit(spaced, compact, scoped=frozenset()):
    """The registered sealed identity the text names, or None. `scoped` holds
    the ids of scoped entries whose scope the value names, so their bare
    phrases match too."""
    padded = " " + spaced + " "
    tokens = spaced.split()
    for entry in SEALED_IDENTITIES:
        if entry["kind"] == "digest":
            hexed = entry["value"].removeprefix("sha256:")
            if hexed in compact or any(
                len(token) >= DIGEST_PREFIX_MIN
                and _HEX.match(token)
                and hexed.startswith(token)
                for token in tokens
            ):
                return entry["id"]
        elif entry["kind"] == "scoped_phrase":
            for phrase in entry["value"]:
                if entry["id"] in scoped and _phrase_in(phrase, padded):
                    return entry["id"]
                if any(
                    _phrase_in(scope + " " + phrase, padded) for scope in entry["scope"]
                ):
                    return entry["id"]
        else:
            for phrase in entry["value"]:
                if _phrase_in(phrase, padded):
                    return entry["id"]
    return None


def sealed_identity(value):
    """The id of the registered sealed identity any string in `value` names
    (`SEALED_IDENTITIES`), or None. A scoped entry's bare phrase counts only
    when some string of the same value names its scope."""
    texts = [normalise(text) for text in _strings(value)]
    scoped = frozenset(
        entry["id"]
        for entry in SEALED_IDENTITIES
        if entry["kind"] == "scoped_phrase" and _scope_named(entry, texts)
    )
    for spaced, compact in texts:
        found = _identity_hit(spaced, compact, scoped)
        if found is not None:
            return found
    return None


def protected(value):
    """The store's protected rule: Graphite's protected markers
    (`graphite.tools.PROTECTED_MARKERS`, read at call time), and the
    checkout deny fragments that name sealed or confirmation material
    (`PROTECTED_TOKEN_STARTS`, `PROTECTED_FRAGMENTS`), after normalisation.
    Narrower than `graphite.tools.protected`, which also refuses the attack
    targets `.env`, `secret`, `credential` and repository paths: those are
    a request filter for a live session, not material the store may lose a
    finding over."""
    markers = (*_tools.PROTECTED_MARKERS, *PROTECTED_FRAGMENTS)
    for text in _strings(value):
        spaced, compact = normalise(text)
        if any(_marker_hit(marker, spaced, compact) for marker in markers):
            return True
        padded = " " + spaced
        if any(" " + start in padded for start in PROTECTED_TOKEN_STARTS):
            return True
    return False


def sealed(value):
    """True when any string in `value` names sealed or confirmation material:
    a registered sealed identity, the store's protected rule, or the store's
    own sealed markers."""
    return (
        protected(value)
        or sealed_identity(value) is not None
        or _named(value, SEALED_MARKERS)
    )


def held_out(value):
    """True when any string in `value` names held-out control material."""
    return _named(value, HELD_OUT_MARKERS)


def _content(record):
    """The record less its `check`, which is one of the eight fixed Track A
    check names (one of them, `fresh_attack_confirmation`, names the
    confirmation study it would run; it is vocabulary, not material)."""
    return {key: value for key, value in record.items() if key != "check"}


def _material(value):
    """True when `value` names protected, sealed or held-out material."""
    return sealed(value) or held_out(value)


def exposure_finding(record):
    """The `OTHER_SIGNAL` finding recorded for a development finding that
    names protected, sealed or held-out material: the material is withheld
    and only its digest kept; each identifying field that itself names it is
    dropped. The specimen is kept when neither it nor the family names the
    material, so the exposure still has a regression specimen to re-run."""
    kept = {}
    for key in ("family", "boundary", "strategy", "attempt_id"):
        value = record.get(key)
        kept[key] = None if value is None or _material(value) else value
    specimen, control = record.get("specimen"), record.get("control")
    if specimen is not None and (_material(specimen) or kept["family"] is None):
        specimen = None
    if control is not None and _material(control):
        control = None
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
        "specimen": specimen,
        "control": control,
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


def _payload(value, name, *, object_only=True):
    """`value` as canonical JSON data. An attempt is a JSON object; a
    specimen is any JSON value (an attack input may be a list or a scalar; a
    tuple is stored as a list)."""
    if value is None or (object_only and type(value) is not dict):
        raise _invalid(name + " is a JSON object" if object_only else name + " is set")
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


def _journal(path):
    """The journal's entries in order, each with the digest of its line,
    after checking the chain: schema, `seq` 1, 2, ... with no gap, `prev` the
    digest of the line before (None for the first), every line canonical and
    every record digest listed once. A torn final line (a crash mid-append)
    was never an entry and is ignored. Anything else is refused
    `attack_record_corrupt`."""
    if not path.exists():
        return []
    body = path.read_bytes()
    complete = body[: body.rfind(b"\n") + 1]
    out, seen, prev = [], set(), None
    for number, line in enumerate(complete.split(b"\n")[:-1], start=1):
        try:
            entry = json.loads(line)
        except ValueError:
            entry = None
        if (
            type(entry) is not dict
            or canonical(entry) != line
            or set(entry) != {"schema", "seq", "kind", "digest", "prev"}
            or entry["schema"] != JOURNAL_SCHEMA
            or type(entry["seq"]) is not int
            or entry["seq"] != number
            or entry["prev"] != prev
            or entry["kind"] not in KINDS
            or type(entry["digest"]) is not str
            or not _DIGEST.fullmatch(entry["digest"])
            or entry["digest"] in seen
        ):
            raise KnowledgeError(RECORD_CORRUPT, f"journal chain broken at {number}")
        seen.add(entry["digest"])
        prev = digest(line)
        out.append((entry, prev))
    return out


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


class SpecimenAttempt:
    """A regression specimen as an adapter's oracle takes an attempt: the
    shape of `attack.adapter.AttackInput` (`name`, `value`). `name` is the
    finding's attempt identity; `value` is the stored specimen (JSON data),
    which the adapter's family boundary receives as the attempt's input."""

    __slots__ = ("name", "value")

    def __init__(self, name, value):
        self.name, self.value = name, value

    def __eq__(self, other):
        return type(other) is SpecimenAttempt and (self.name, self.value) == (
            other.name,
            other.value,
        )

    __hash__ = None

    def __repr__(self):
        return f"SpecimenAttempt(name={self.name!r}, value={self.value!r})"


def _field(result, name):
    if type(result) is dict:
        return result.get(name)
    return getattr(result, name, None)


def _oracle_state(result, family):
    """A regression state from an adapter's oracle result
    (`attack.adapter.OracleResult`, or a dict of the same fields): its
    `verdict` through `VERDICT_STATES`. Every other verdict (FAILED_INFRA,
    TIMEOUT, CRASHED, NOT_RUN), a missing verdict, or a result for another
    family is INCONCLUSIVE: never a hold."""
    answered = _field(result, "family")
    if answered is not None and answered != family:
        return "INCONCLUSIVE"
    verdict = _field(result, "verdict")
    if type(verdict) is not str:
        return "INCONCLUSIVE"
    return VERDICT_STATES.get(verdict, "INCONCLUSIVE")


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
                "attempt_id": record["attempt_id"],
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
    """The records one snapshot froze: what a frozen admission run used.

    It serves all of them or none: if any frozen record is no longer
    admissible on read (the protected, sealed or held-out rules grew since
    the freeze), every read, the pin itself and `replay` are refused
    `attack_snapshot_withheld`. A frozen run is never silently served a
    subset of what it used (invariant 10). The live store keeps withholding.
    """

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
        # And every frozen record must still be admissible: all or nothing.
        self._served()

    def _entries(self):
        return self._frozen

    def _served(self):
        served, withheld = super()._served()
        if withheld:
            raise KnowledgeError(
                SNAPSHOT_WITHHELD,
                f"{len(withheld)} frozen record(s) of {self.digest} are no longer"
                " admissible; a frozen run is never served a subset",
            )
        return served, withheld

    def replay(self, value):
        """This view, for a replay under `value`; refused unless `value` is
        the digest the run pinned (invariant 10: no silent re-reading), and
        refused if any frozen record is no longer admissible."""
        if value != self.digest:
            raise KnowledgeError(
                REPLAY_REFUSED, f"pinned {self.digest}, asked {str(value)[:80]}"
            )
        self._served()
        return self

    def replay_recorded(self, record):
        """This view, for a replay under the digest an independent record
        pinned: a frozen run's suite record (`challenge_pipeline.suite.run`
        `attack_knowledge_digest`) or a session's pin file. Refused when the
        record names no digest, or another one than this view's."""
        value = record.get("attack_knowledge_digest") if type(record) is dict else None
        if type(value) is not str:
            raise KnowledgeError(REPLAY_REFUSED, "the record pins no store digest")
        return self.replay(value)

    def suite_pin(self):
        """What a frozen admission run records in its suite version."""
        return {"schema": SUITE_PIN_SCHEMA, "attack_knowledge_digest": self.digest}

    def _read_only(self, *_args, **_kwargs):
        raise KnowledgeError(READ_ONLY, "a pinned view is never written")

    add_attempt = add_near_miss = add_finding = add_regression = _read_only
    replay_specimens = snapshot = _read_only


if SUITE_PIN_SCHEMA != _suite.ATTACK_KNOWLEDGE_PIN_SCHEMA:  # pragma: no cover
    raise ImportError("the suite and the store disagree on the pin schema")


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
        return [
            (entry["kind"], entry["digest"]) for entry, _line in _journal(self.journal)
        ]

    def _lock(self):
        return _locked(self.root / "store.lock")

    def _put(self, record):
        body = canonical(record)
        value = digest(body)
        with self._lock():
            path = self.root / "objects" / (_hex(value) + ".json")
            write_once(path, body)
            entries = _journal(self.journal)
            if not any(entry["digest"] == value for entry, _line in entries):
                _append(
                    self.journal,
                    canonical(
                        {
                            "schema": JOURNAL_SCHEMA,
                            "seq": len(entries) + 1,
                            "kind": record["kind"],
                            "digest": value,
                            "prev": entries[-1][1] if entries else None,
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
        protected, sealed or held-out material is recorded as an OTHER_SIGNAL
        exposure with that material withheld (`exposure_finding`); a held-out
        `control` field is still refused, as on every record."""
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
            specimen=_payload(specimen, "specimen", object_only=False),
            control=control,
            evidence=sorted(set(evidence)),
        )
        if _material(_content(record)):
            # An exposure, never dropped; refused typed only if what it must
            # keep (its Challenge) still names the material.
            record = exposure_finding(record)
            _refuse_material(record)
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
        through its oracle (`adapter.oracle(family, SpecimenAttempt(name,
        value))`, the `AttackInput` shape), recording each result from the
        oracle's `verdict`. An oracle that raises is INCONCLUSIVE (a crash is
        never a hold). Returns `[{finding, state}]`."""
        view = training_view(adapter)
        rows = []
        for specimen in self.regression_due(
            view.challenge_id, view.level, view.contract_digest
        ):
            detail = None
            family = specimen["family"]
            try:
                state = _oracle_state(
                    view.oracle(
                        family,
                        SpecimenAttempt(
                            specimen["attempt_id"] or specimen["finding"],
                            specimen["specimen"],
                        ),
                    ),
                    family,
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
        """Freeze the records the store serves now, in journal order; the
        store's digest. The same records give the same digest. A record the
        protected, sealed or held-out rules withhold is not frozen."""
        with self._lock():
            document = {
                "schema": SNAPSHOT_SCHEMA,
                "records": [
                    {"kind": record["kind"], "digest": record["record_digest"]}
                    for record in self._served()[0]
                ],
            }
            body = canonical(document)
            value = digest(body)
            write_once(self.root / "snapshots" / (_hex(value) + ".json"), body)
        return value

    def pin(self, value):
        """A read-only view of exactly what snapshot `value` froze."""
        return ReadOnlyView(self.root, value)


#: What the engine may read of an adapter: these values ...
TRAINING_VALUES = ("challenge_id", "level", "contract_digest")
#: ... these calls, forwarded ...
TRAINING_CALLS = ("families", "oracle", "rebuild", "level_families")
#: ... and `controls(TRAINING_SPLIT)`. Nothing else is reachable.


def _split(control):
    return (
        control.get("split")
        if type(control) is dict
        else getattr(control, "split", None)
    )


class _TrainingAdapter:
    """An adapter as the engine may see it: an allow-list. Only
    `TRAINING_VALUES`, `TRAINING_CALLS` and `controls(TRAINING_SPLIT)` exist;
    there is no instance dictionary and no attribute that holds the adapter,
    so neither the held-out split nor a control collection (such as a
    declared adapter's `control_set`) can be reached by attribute access.
    This guards Carbon's own engine against reading held-out controls by
    mistake; it is not a sandbox for hostile code."""

    __slots__ = (*TRAINING_VALUES, *TRAINING_CALLS, "controls")

    def __setattr__(self, name, value):
        raise AttributeError("a training view is read only")

    def __delattr__(self, name):
        raise AttributeError("a training view is read only")


def _forward(call):
    def forwarded(*args, **kwargs):
        return call(*args, **kwargs)

    return forwarded


def _trained_only(adapter):
    def controls(split):
        if split != TRAINING_SPLIT:
            raise KnowledgeError(
                HELD_OUT_REFUSED, "the engine never reads held-out controls"
            )
        found = tuple(adapter.controls(split))
        if any(_split(control) not in (None, TRAINED) for control in found):
            raise KnowledgeError(
                HELD_OUT_REFUSED, "the adapter answered with another split"
            )
        return found

    return controls


def training_view(adapter):
    """The adapter as the engine may read it (an allow-list):
    `controls('held_out')` is refused and nothing else that could reach the
    held-out split exists. The held-out split is read only by the report."""
    if type(adapter) is _TrainingAdapter:
        return adapter
    view = object.__new__(_TrainingAdapter)
    for name in TRAINING_VALUES:
        object.__setattr__(view, name, getattr(adapter, name))
    for name in TRAINING_CALLS:
        call = getattr(adapter, name, None)
        if call is not None:
            object.__setattr__(view, name, _forward(call))
    object.__setattr__(view, "controls", _trained_only(adapter))
    return view


def trained_controls(adapter):
    """The adapter's trained controls: the only controls the engine reads."""
    return training_view(adapter).controls(TRAINING_SPLIT)
