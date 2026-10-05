"""Conditional evidence: a result produced while a finding is open says so.

OWNER-GRAPHITE-TEST-WAVE-03 §2 (owner, 2026-10-04): for internal testing, a
finding stops locking, not exploration. A finding still escalates, still
blocks `LOCK` and anything that opens a level to miners, and still blocks any
frozen admission run that would cite the affected state. Exploration on
development-only variants continues, and every result produced while a
finding is open is tagged with the open findings' ids and digests. A tagged
result cannot be cited as unconditional evidence until those findings are
repaired and the affected attacks re-run.

The tagging rule encodes an assumption the Attacker should be able to test,
so it is a registered, versioned policy (`POLICIES`), in the pattern of
`carbon.battery.exam.RULES` and Graphite's `FrozenRule` identity, and every
tag names the policy's identity. Engineering choices are recorded in
GRAPHITE-CONDITIONAL-EXPLORATION-01 and its 2026-10-05 amendment, which made
`conditional-evidence.v2` the current policy (`v1` stays registered, so a
result keeps the identity it was tagged under).

- `tag(open_findings, attested_repairs=())` gives the keys a result carries:
  `conditional_on`, every open finding as `{id, digest}` sorted by id, where
  the digest is the sha256 of the finding body's canonical JSON;
  `conditional_policy`, the policy identity; and, only when a finding was
  released by an operator's attestation (`repair-attestation.v1`),
  `repaired_by_attestation`, those repairs' ids. An empty `conditional_on` is
  an unconditional result under the policy.
- Only a claim that relies on a result is checked (`RELIANCE`: PASS,
  ACCEPTED, TESTED, FROZEN, LOCK). A FAIL, INCONCLUSIVE or NOT_RUN check, and
  a finding's own evidence, may cite a conditional result: the report that
  found a finding is conditional on it and is still the evidence of the FAIL.
- `require_unconditional(value, site=..., lock=False)` refuses, with the typed
  code `conditional_evidence_cited_unconditionally`, any value that carries a
  non-empty `conditional_on` at any depth, so a tagged result nested in a
  cited document is caught too. With `lock=True` (a LOCK, a FROZEN level that
  opens to miners, a frozen run) it also refuses `repaired_by_attestation`
  (`conditional_evidence_attested_repair_at_lock`): an attestation never
  unblocks those paths.
- `require_unconditional_bytes` / `_path` do the same for cited bytes: JSON,
  JSON Lines, a gzip, bzip2, xz or zip copy (read through), and otherwise text
  that embeds the key as JSON or as a YAML-style key. They also consult every
  `ConditionalLedger` they are given (a controller's attempt ledger): any
  cited bytes whose digest the ledger recorded on a result while a finding
  was open are conditional, whatever the bytes say.
- A tag never leaves its result. Once its findings are repaired, unconditional
  evidence is a result produced after the repair.
- `validate_development_ledger(entries)` validates the campaign controller's
  development ledger. It is kept apart from Track A's `expansions`, whose
  exact keys stay strict, so a development entry never enters a LOCK.

Stdlib only, because the contract lane has no numpy. These are structural
checks. They are not scientific or security acceptance.
"""

from __future__ import annotations

import bz2
import gzip
import hashlib
import io
import json
import lzma
import re
import sqlite3
import zipfile
import zlib
from pathlib import Path

POLICY_V1 = "conditional-evidence.v1"
POLICY = "conditional-evidence.v2"
REPAIR_POLICY = "repair-attestation.v1"

#: OWNER-GRAPHITE-TEST-WAVE-03 §2 as registered rules. The rule is a
#: hypothesis the Attacker may test; a change is a new version, and results
#: keep the identity they were tagged under. v1 is kept, unchanged, so a
#: result tagged under it still names a registered identity.
CONDITIONAL_EVIDENCE_V1 = {
    "policy": POLICY_V1,
    "status": "PROVISIONAL_INTERNAL_DEVELOPMENT",
    "authority": (
        "OWNER-GRAPHITE-TEST-WAVE-03 §2; engineering choices "
        "GRAPHITE-CONDITIONAL-EXPLORATION-01"
    ),
    "open": (
        "A finding recorded on Carbon's campaign controller is open from when it "
        "is recorded until an operator records its repair with the evidence of "
        "the re-run affected attacks. A repaired finding that is recorded again "
        "is open again. A finding is never removed."
    ),
    "tag": (
        "Every result recorded while any finding is open carries conditional_on, "
        "the open findings as {id, digest} sorted by id (digest: sha256 of the "
        "finding body's canonical JSON), and conditional_policy, this policy's "
        "identity. The results are: the controller's event, artifact and terminal "
        "entries and its development expansions; climb reports; attack family "
        "reports; Graphite phase 3 session results; and phase 4 coverage reports "
        "and iteration-log entries."
    ),
    "lock_path": (
        "An expansion that could lock, open a level to miners or feed a frozen "
        "run is refused after any finding, repaired or not "
        "(admission_expansion_after_finding)."
    ),
    "development_path": (
        "A development expansion proceeds while findings are open and is "
        "recorded, tagged, in the controller's separate development ledger. It "
        "never enters Track A's expansions, a LOCK or the profile miners get."
    ),
    "citation": (
        "A value that carries a non-empty conditional_on at any depth is never "
        "cited as unconditional evidence. The citing sites are ladder TESTED and "
        "FROZEN evidence, an ACCEPTED level proposal, admission report evidence "
        "and its LOCK, and a pipeline record's frozen run."
    ),
    "release": (
        "A tag stays on its result. After a repair, unconditional evidence is a "
        "result produced after the repair."
    ),
}

#: The Test Lead's v1 conditions for a repair (review of
#: carbonphysicsai/Carbon#577), as registered rules. Like the tagging rule it
#: is a hypothesis: a change is a new version.
REPAIR_ATTESTATION_V1 = {
    "policy": REPAIR_POLICY,
    "status": "PROVISIONAL_INTERNAL_DEVELOPMENT",
    "authority": (
        "Test Lead review of carbonphysicsai/Carbon#577 (v1 conditions); "
        "engineering choices GRAPHITE-CONDITIONAL-EXPLORATION-01, amended "
        "2026-10-05"
    ),
    "requires": (
        "An operator records a repair with the re-run's evidence identities: "
        "rerun, the re-run attempt ids or report digests (at least one); "
        "code_ref, the 40-hex commit the re-run ran at; operator, the "
        "controller's operator; a note; and the re-run's evidence bytes. An "
        "empty field is refused. The code cannot verify that the re-run "
        "happened or contains the fix: the record is the operator's attestation."
    ),
    "releases": (
        "A finding whose latest state is a repair stops tagging later results. "
        "A result recorded while any finding's latest state is an attested "
        "repair carries repaired_by_attestation, those repairs' ids."
    ),
    "never_unblocks": (
        "A repaired finding never unblocks a LOCK, opening a level to miners or "
        "a frozen run: it stays in the findings ledger and still refuses every "
        "LOCK-path expansion, and a result carrying repaired_by_attestation is "
        "refused at a LOCK, at FROZEN level evidence and at a frozen run. Those "
        "still need the existing review and lock path."
    ),
    "v2_target": (
        "Verify the re-run from the ledger instead of attesting it: for each "
        "family the finding affects, an attempt recorded after the repair time, "
        "at a code ref that contains the fix."
    ),
}
REPAIR_POLICIES = {REPAIR_POLICY: REPAIR_ATTESTATION_V1}

#: The Test Lead's review of carbonphysicsai/Carbon#577, items 1-4, as v2.
CONDITIONAL_EVIDENCE_V2 = {
    "policy": POLICY,
    "status": "PROVISIONAL_INTERNAL_DEVELOPMENT",
    "authority": (
        "OWNER-GRAPHITE-TEST-WAVE-03 §2; engineering choices "
        "GRAPHITE-CONDITIONAL-EXPLORATION-01, amended 2026-10-05 after the Test "
        "Lead's review of carbonphysicsai/Carbon#577"
    ),
    "supersedes": POLICY_V1,
    "open": CONDITIONAL_EVIDENCE_V1["open"],
    "tag": (
        "Every result recorded while any finding is open carries conditional_on, "
        "the open findings as {id, digest} sorted by id (digest: sha256 of the "
        "finding body's canonical JSON), and conditional_policy, this policy's "
        "identity; while any finding's latest state is an attested repair it "
        "also carries repaired_by_attestation, the sorted repair ids. The "
        "results are: the controller's event, artifact and terminal entries and "
        "its development expansions; climb reports; attack family reports; "
        "Graphite phase 3 session results and next-level proposals; and phase 4 "
        "coverage reports, family reports and iteration-log entries."
    ),
    "ordering": (
        "A finding is recorded on the controller before a result it could "
        "affect is written: phase 3 records each finding when it is found and "
        "syncs the session's findings before ingesting its events and "
        "artifacts; the controller records a canary finding before the entry "
        "that exposed it; phase 4 re-tags its family report after recording the "
        "findings the report raises."
    ),
    "lock_path": CONDITIONAL_EVIDENCE_V1["lock_path"],
    "development_path": CONDITIONAL_EVIDENCE_V1["development_path"],
    "citation": (
        "Only a claim that relies on a result is checked: ladder TESTED and "
        "FROZEN evidence, an ACCEPTED level proposal, the evidence of a PASS "
        "admission check, the LOCK, and a pipeline record's frozen run. Such a "
        "claim never cites a value that carries a non-empty conditional_on at "
        "any depth. A FAIL, INCONCLUSIVE or NOT_RUN check and a finding's own "
        "evidence may cite a conditional result."
    ),
    "ledger": (
        "Cited bytes are conditional when they carry a non-empty conditional_on "
        "(JSON, JSON Lines, a YAML-style key, embedded JSON, or any of these "
        "inside a gzip, bzip2, xz or zip copy), or when a controller ledger the "
        "check is given recorded their digest on a result while a finding was "
        "open, whatever the bytes say. The controller's stored evidence bytes "
        "cannot carry a tag without changing their digest: its ledger row is "
        "their tag of record."
    ),
    "repair": (
        "A finding is released for tagging only by a repair recorded under "
        "repair_attestation. A LOCK, FROZEN level evidence and a frozen run "
        "refuse a result that carries repaired_by_attestation."
    ),
    "repair_attestation": {
        "policy": REPAIR_POLICY,
        "digest": "sha256:"
        + hashlib.sha256(
            json.dumps(
                REPAIR_ATTESTATION_V1, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest(),
    },
    "release": CONDITIONAL_EVIDENCE_V1["release"],
}

#: The policies a tag may name, by identity.
POLICIES = {POLICY_V1: CONDITIONAL_EVIDENCE_V1, POLICY: CONDITIONAL_EVIDENCE_V2}

CITED = "conditional_evidence_cited_unconditionally"
ATTESTED_AT_LOCK = "conditional_evidence_attested_repair_at_lock"
MALFORMED = "conditional_evidence_tag_malformed"
UNKNOWN_POLICY = "conditional_evidence_policy_unknown"
TAG_KEYS = ("conditional_on", "conditional_policy")
#: Present on a v2 tag only while a finding is released by an attestation.
ATTESTED = "repaired_by_attestation"
#: The claims that rely on a result: only these are checked. A FAIL,
#: INCONCLUSIVE or NOT_RUN check never is (GRAPHITE-CONDITIONAL-EXPLORATION-01
#: amendment, item 1).
RELIANCE = frozenset({"PASS", "ACCEPTED", "TESTED", "FROZEN", "LOCK"})
DEVELOPMENT_KIND = "development"
DEVELOPMENT_KEYS = frozenset(
    {
        "sequence",
        "recorded_at",
        "kind",
        "profile",
        "version",
        "widened",
        "permissions",
        *TAG_KEYS,
    }
)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REPAIR_ID = re.compile(r"repair-[0-9a-f]{16}\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_FILE_LIMIT = 32 * 1024 * 1024
#: How deep compressed copies are read through (a gzip of a zip of ...).
_NESTING = 3


class ConditionalEvidenceError(ValueError):
    """A tag is malformed, or a tagged result is cited as unconditional."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _sha256(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _text(value):
    return type(value) is str and value.strip() != ""


def identity(policy=POLICY):
    """The identity a tagged result records: the policy's name, status,
    authority and the digest of its rules."""
    rules = POLICIES.get(policy)
    if rules is None:
        raise ConditionalEvidenceError(UNKNOWN_POLICY, str(policy))
    return {
        "policy": policy,
        "status": rules["status"],
        "authority": rules["authority"],
        "digest": _sha256(canonical(rules)),
    }


def repair_identity(policy=REPAIR_POLICY):
    """The identity a repair record names: the repair-attestation policy's
    name, status, authority and the digest of its rules."""
    rules = REPAIR_POLICIES.get(policy)
    if rules is None:
        raise ConditionalEvidenceError(UNKNOWN_POLICY, str(policy))
    return {
        "policy": policy,
        "status": rules["status"],
        "authority": rules["authority"],
        "digest": _sha256(canonical(rules)),
    }


def relies(claim):
    """Whether `claim` relies on the result it cites (`RELIANCE`)."""
    return claim in RELIANCE


def finding_digest(body):
    """The canonical digest of one finding body."""
    if type(body) is not dict or not _text(body.get("id")):
        raise ConditionalEvidenceError(MALFORMED, "a finding body names its id")
    return _sha256(canonical(body))


def reference(body):
    """One open finding as a tag names it: `{id, digest}`."""
    return {"id": body["id"], "digest": finding_digest(body)}


def check_references(items):
    """`conditional_on`: a list of `{id, digest}`, sorted by id, no repeats."""
    if type(items) is not list:
        raise ConditionalEvidenceError(MALFORMED, "conditional_on is a list")
    ids = []
    for item in items:
        if (
            type(item) is not dict
            or set(item) != {"id", "digest"}
            or not _text(item["id"])
            or type(item["digest"]) is not str
            or not _DIGEST.fullmatch(item["digest"])
        ):
            raise ConditionalEvidenceError(
                MALFORMED, "each open finding is {id, digest}"
            )
        ids.append(item["id"])
    if ids != sorted(set(ids)):
        raise ConditionalEvidenceError(MALFORMED, "open findings sorted by id, once")
    return items


def check_policy(value):
    """A tag names a registered policy's exact identity."""
    name = value.get("policy") if type(value) is dict else None
    if name not in POLICIES or value != identity(name):
        raise ConditionalEvidenceError(UNKNOWN_POLICY, repr(name))
    return value


def check_repairs(items):
    """`repaired_by_attestation`: a non-empty list of repair ids, sorted, once."""
    if (
        type(items) is not list
        or not items
        or any(type(i) is not str or not _REPAIR_ID.fullmatch(i) for i in items)
        or items != sorted(set(items))
    ):
        raise ConditionalEvidenceError(
            MALFORMED, "repaired_by_attestation is sorted repair ids, once each"
        )
    return items


def tag(open_findings, policy=POLICY, *, attested_repairs=()):
    """The keys a result carries: `conditional_on`, `conditional_policy` and,
    under v2 while a finding is released by an attestation,
    `repaired_by_attestation` (the repairs' ids)."""
    refs = sorted((dict(item) for item in open_findings), key=lambda r: str(r["id"]))
    check_references(refs)
    out = {"conditional_on": refs, "conditional_policy": identity(policy)}
    repairs = sorted(set(attested_repairs))
    if repairs:
        if policy == POLICY_V1:
            raise ConditionalEvidenceError(
                MALFORMED, f"{POLICY_V1} has no repaired_by_attestation"
            )
        out[ATTESTED] = check_repairs(repairs)
    return out


def _walk(value):
    """Every open-finding reference and attested repair id a value carries, at
    any depth, each tag checked on the way."""
    found, repairs = [], []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if "conditional_on" in item:
                found.extend(check_references(item["conditional_on"]))
            if "conditional_policy" in item:
                check_policy(item["conditional_policy"])
            if ATTESTED in item:
                repairs.extend(check_repairs(item[ATTESTED]))
            stack.extend(item.values())
        elif isinstance(item, list | tuple):
            stack.extend(item)
    return found, repairs


def conditional_on(value):
    """Every open-finding reference a value carries, at any depth."""
    return _walk(value)[0]


def attested_repairs(value):
    """Every attested repair id a value carries, at any depth."""
    return _walk(value)[1]


def require_unconditional(value, *, site, lock=False):
    """Refuse a value cited as established while it carries a non-empty
    `conditional_on` anywhere in it; with `lock` (a LOCK, a FROZEN level, a
    frozen run), also while it carries `repaired_by_attestation`."""
    found = conditional_on(value)
    if found:
        ids = ", ".join(sorted({str(r["id"]) for r in found}))
        raise ConditionalEvidenceError(
            CITED, f"{site} cites a result conditional on open findings {ids}"
        )
    if lock:
        repairs = attested_repairs(value)
        if repairs:
            raise ConditionalEvidenceError(
                ATTESTED_AT_LOCK,
                f"{site} cites a result released only by attested repairs "
                f"{', '.join(sorted(set(repairs)))} ({REPAIR_POLICY})",
            )
    return value


class ConditionalLedger:
    """The digests a campaign controller's attempt ledger recorded on results
    while findings were open, or while a finding was released only by an
    attested repair, with those findings and repairs.

    The controller stores what an agent returns by digest, and those bytes
    cannot carry a tag without changing their digest: the ledger row is their
    tag of record. A digest recorded once unconditionally and once while a
    finding was open is conditional (the union is kept)."""

    def __init__(self):
        self._entries = {}

    def __len__(self):
        return len(self._entries)

    def add(self, digest, refs=(), repairs=()):
        if type(digest) is not str or not _DIGEST.fullmatch(digest):
            raise ConditionalEvidenceError(MALFORMED, "a ledger digest is sha256")
        found, attested = self._entries.setdefault(digest, ({}, set()))
        for ref in check_references(sorted(refs, key=lambda r: str(r["id"]))):
            found[ref["id"]] = dict(ref)
        attested.update(check_repairs(sorted(set(repairs))) if repairs else ())

    @classmethod
    def from_entries(cls, entries):
        """From a controller's attempt-ledger entries: every evidence digest
        and artifact digest of an entry that carries a non-empty
        `conditional_on` or `repaired_by_attestation`."""
        ledger = cls()
        for entry in entries:
            if type(entry) is not dict:
                continue
            refs = entry.get("conditional_on") or []
            repairs = entry.get(ATTESTED) or []
            if not refs and not repairs:
                continue
            digests = [
                ref.get("sha256")
                for ref in entry.get("evidence") or []
                if type(ref) is dict
            ]
            digests.append(entry.get("artifact_digest"))
            for digest in digests:
                if type(digest) is str and _DIGEST.fullmatch(digest):
                    ledger.add(digest, refs, repairs)
        return ledger

    @classmethod
    def load(cls, path):
        """A controller store's attempt ledger, opened read-only: the
        controller root or its `campaign.sqlite3`."""
        path = Path(path)
        if path.is_dir():
            path = path / "campaign.sqlite3"
        if not path.is_file():
            raise ConditionalEvidenceError("conditional_ledger_unavailable", str(path))
        try:
            db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                rows = db.execute("SELECT body FROM ledger ORDER BY seq").fetchall()
            finally:
                db.close()
        except sqlite3.Error as error:
            raise ConditionalEvidenceError(
                "conditional_ledger_unavailable", f"{path}: {error}"
            ) from None
        return cls.from_entries(json.loads(body) for (body,) in rows)

    def lookup(self, digest):
        """`(conditional_on, repaired_by_attestation)` recorded for `digest`;
        both empty when the ledger never recorded it on such a result."""
        found, attested = self._entries.get(digest, ({}, set()))
        return [found[key] for key in sorted(found)], sorted(attested)


def _ledger_check(body, site, lock, ledgers):
    digest = _sha256(body)
    for ledger in ledgers:
        if type(ledger) is not ConditionalLedger:
            raise TypeError("ledgers are ConditionalLedger")
        found, repairs = ledger.lookup(digest)
        if found:
            ids = ", ".join(r["id"] for r in found)
            raise ConditionalEvidenceError(
                CITED,
                f"{site} cites bytes ({digest}) a controller ledger recorded "
                f"while findings {ids} were open",
            )
        if lock and repairs:
            raise ConditionalEvidenceError(
                ATTESTED_AT_LOCK,
                f"{site} cites bytes ({digest}) a controller ledger recorded "
                f"under attested repairs {', '.join(repairs)}",
            )


def _documents(body):
    """The JSON documents in `body`: one JSON value, JSON Lines, or None."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        return [json.loads(text)]
    except ValueError:
        pass
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        return [json.loads(line) for line in lines]
    except ValueError:
        return None


#: Inline values that say a key is empty.
_EMPTY = {b"[]", b"[ ]", b"null", b"~", b"''", b'""', b"none", b"None"}


def _embedded(body, key):
    """Whether text that is not JSON embeds a non-empty `key`: as JSON (or a
    Python-style dict) inline, or as a YAML- or TOML-style key whose value is
    not empty. Ambiguous text is read as embedding it (fail closed)."""
    name = re.escape(key.encode())
    inline = rb"""["']""" + name + rb"""["']\s*[:=]\s*\[\s*[^\]\s]"""
    if re.search(inline, body):
        return True
    keyed = re.compile(
        rb"""^([ \t]*)(?:-[ \t]+)?["']?""" + name + rb"""["']?[ \t]*[:=][ \t]*(.*)$"""
    )
    lines = body.splitlines()
    for index, line in enumerate(lines):
        match = keyed.match(line)
        if match is None:
            continue
        rest = match.group(2).split(b" #")[0].strip().rstrip(b",").strip()
        if rest in _EMPTY:
            continue
        if rest in (b"", b"["):
            following = next((x for x in lines[index + 1 :] if x.strip()), b"")
            stripped = following.strip()
            if rest == b"[" and stripped.startswith(b"]"):
                continue
            indent = len(following) - len(following.lstrip())
            if (
                rest == b""
                and not stripped.startswith(b"-")
                and indent <= len(match.group(1))
            ):
                continue
        return True
    return False


_MAGIC = (
    (re.compile(rb"\x1f\x8b"), "gzip"),
    (re.compile(rb"BZh[1-9]1AY&SY"), "bzip2"),
    (re.compile(rb"\xfd7zXZ\x00"), "xz"),
    (re.compile(rb"PK\x03\x04"), "zip"),
)


def _read_bounded(stream, site):
    data = stream.read(_FILE_LIMIT + 1)
    if len(data) > _FILE_LIMIT:
        raise ConditionalEvidenceError(CITED, f"{site} expands too large to check")
    return data


def _expanded(body, site):
    """The `(name, bytes)` a compressed copy holds, or None when `body` is not
    a gzip, bzip2, xz or zip file. A copy that cannot be read is refused."""
    kind = next((kind for magic, kind in _MAGIC if magic.match(body)), None)
    if kind is None:
        return None
    try:
        if kind == "zip":
            out, total = [], 0
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    with archive.open(info) as member:
                        data = _read_bounded(member, site)
                    total += len(data)
                    if total > _FILE_LIMIT:
                        raise ConditionalEvidenceError(
                            CITED, f"{site} expands too large to check"
                        )
                    out.append((info.filename, data))
            return out
        opener = {
            "gzip": lambda raw: gzip.GzipFile(fileobj=raw),
            "bzip2": bz2.BZ2File,
            "xz": lzma.LZMAFile,
        }[kind]
        with opener(io.BytesIO(body)) as stream:
            return [(kind, _read_bounded(stream, site))]
    except (OSError, EOFError, zlib.error, lzma.LZMAError, zipfile.BadZipFile):
        raise ConditionalEvidenceError(
            CITED, f"{site} cites a {kind} file that cannot be read to check it"
        ) from None


def require_unconditional_bytes(body, *, site, lock=False, ledgers=(), _depth=0):
    """Cited bytes (see the module docstring): refused when a ledger recorded
    their digest on a conditional result, or when they, or the bytes of a
    compressed copy, carry a non-empty `conditional_on` (with `lock`, also
    `repaired_by_attestation`)."""
    _ledger_check(body, site, lock, ledgers)
    expanded = _expanded(body, site)
    if expanded is not None:
        if _depth >= _NESTING:
            raise ConditionalEvidenceError(
                CITED, f"{site} nests compressed copies too deep to check"
            )
        for name, inner in expanded:
            require_unconditional_bytes(
                inner,
                site=f"{site} [{name}]",
                lock=lock,
                ledgers=ledgers,
                _depth=_depth + 1,
            )
        return
    documents = _documents(body)
    if documents is not None:
        require_unconditional(documents, site=site, lock=lock)
    elif _embedded(body, "conditional_on"):
        raise ConditionalEvidenceError(
            CITED, f"{site} embeds a result with a non-empty conditional_on"
        )
    elif lock and _embedded(body, ATTESTED):
        raise ConditionalEvidenceError(
            ATTESTED_AT_LOCK, f"{site} embeds a result released by attested repairs"
        )


def require_unconditional_path(path, *, site, lock=False, ledgers=()):
    """A cited file, or every file under a cited directory."""
    path = Path(path)
    files = (
        sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    )
    for item in files:
        if item.stat().st_size > _FILE_LIMIT:
            raise ConditionalEvidenceError(
                CITED, f"{site}: {item.name} is too large to check"
            )
        require_unconditional_bytes(
            item.read_bytes(), site=f"{site} ({item.name})", lock=lock, ledgers=ledgers
        )


def validate_development_ledger(entries):
    """The controller's development ledger: every development widening, in
    order, each with its tag. Never Track A's `expansions`."""
    if type(entries) is not list:
        raise ConditionalEvidenceError("development_ledger_list_required")
    previous = None
    for index, entry in enumerate(entries, start=1):
        if type(entry) is not dict or set(entry) - {ATTESTED} != DEVELOPMENT_KEYS:
            raise ConditionalEvidenceError("development_expansion_exact_keys_required")
        if ATTESTED in entry:
            check_repairs(entry[ATTESTED])
        if entry["kind"] != DEVELOPMENT_KIND:
            raise ConditionalEvidenceError("development_expansion_kind_required")
        if type(entry["sequence"]) is not int or entry["sequence"] != index:
            raise ConditionalEvidenceError("development_expansion_sequence_gap")
        when = entry["recorded_at"]
        if type(when) is not str or not _TIME.fullmatch(when):
            raise ConditionalEvidenceError("development_expansion_time_required")
        if previous is not None and when < previous:
            raise ConditionalEvidenceError("development_expansion_out_of_order")
        previous = when
        for key in ("profile", "version", "widened"):
            if not _text(entry[key]):
                raise ConditionalEvidenceError("development_expansion_text_required")
        if type(entry["permissions"]) is not str or not _DIGEST.fullmatch(
            entry["permissions"]
        ):
            raise ConditionalEvidenceError("development_expansion_unpinned")
        check_references(entry["conditional_on"])
        check_policy(entry["conditional_policy"])
    return entries
