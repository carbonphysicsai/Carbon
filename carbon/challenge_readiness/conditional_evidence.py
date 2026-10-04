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
GRAPHITE-CONDITIONAL-EXPLORATION-01.

- `tag(open_findings)` gives the two keys a result carries:
  `conditional_on`, every open finding as `{id, digest}` sorted by id, where
  the digest is the sha256 of the finding body's canonical JSON; and
  `conditional_policy`, the policy identity. An empty `conditional_on` is an
  unconditional result under the policy.
- `require_unconditional(value, site=...)` refuses, with the typed code
  `conditional_evidence_cited_unconditionally`, any value that carries a
  non-empty `conditional_on` at any depth, so a tagged result nested in a
  cited document is caught too. `require_unconditional_path` does the same for
  a cited file or directory: JSON, JSON Lines, or other bytes that embed a
  non-empty `conditional_on` list.
- A tag never leaves its result. Once its findings are repaired, unconditional
  evidence is a result produced after the repair.
- `validate_development_ledger(entries)` validates the campaign controller's
  development ledger. It is kept apart from Track A's `expansions`, whose
  exact keys stay strict, so a development entry never enters a LOCK.

Stdlib only, because the contract lane has no numpy. These are structural
checks. They are not scientific or security acceptance.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

POLICY = "conditional-evidence.v1"

#: OWNER-GRAPHITE-TEST-WAVE-03 §2 as registered rules. The rule is a
#: hypothesis the Attacker may test; a change is a new version, and results
#: keep the identity they were tagged under.
CONDITIONAL_EVIDENCE_V1 = {
    "policy": POLICY,
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

#: The policies a tag may name, by identity.
POLICIES = {POLICY: CONDITIONAL_EVIDENCE_V1}

CITED = "conditional_evidence_cited_unconditionally"
MALFORMED = "conditional_evidence_tag_malformed"
UNKNOWN_POLICY = "conditional_evidence_policy_unknown"
TAG_KEYS = ("conditional_on", "conditional_policy")
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
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
#: A non-empty conditional_on list embedded in bytes that are not JSON.
_EMBEDDED = re.compile(rb'"conditional_on"\s*:\s*\[\s*[^\]\s]')
_FILE_LIMIT = 32 * 1024 * 1024


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


def tag(open_findings, policy=POLICY):
    """The keys a result carries: `conditional_on` and `conditional_policy`."""
    refs = sorted((dict(item) for item in open_findings), key=lambda r: str(r["id"]))
    check_references(refs)
    return {"conditional_on": refs, "conditional_policy": identity(policy)}


def conditional_on(value):
    """Every open-finding reference a value carries, at any depth."""
    found = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if "conditional_on" in item:
                found.extend(check_references(item["conditional_on"]))
            if "conditional_policy" in item:
                check_policy(item["conditional_policy"])
            stack.extend(item.values())
        elif isinstance(item, list | tuple):
            stack.extend(item)
    return found


def require_unconditional(value, *, site):
    """Refuse a value cited as established while it carries a non-empty
    `conditional_on` anywhere in it."""
    found = conditional_on(value)
    if found:
        ids = ", ".join(sorted({str(r["id"]) for r in found}))
        raise ConditionalEvidenceError(
            CITED, f"{site} cites a result conditional on open findings {ids}"
        )
    return value


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


def require_unconditional_bytes(body, *, site):
    documents = _documents(body)
    if documents is not None:
        require_unconditional(documents, site=site)
    elif _EMBEDDED.search(body):
        raise ConditionalEvidenceError(
            CITED, f"{site} embeds a result with a non-empty conditional_on"
        )


def require_unconditional_path(path, *, site):
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
        require_unconditional_bytes(item.read_bytes(), site=f"{site} ({item.name})")


def validate_development_ledger(entries):
    """The controller's development ledger: every development widening, in
    order, each with its tag. Never Track A's `expansions`."""
    if type(entries) is not list:
        raise ConditionalEvidenceError("development_ledger_list_required")
    previous = None
    for index, entry in enumerate(entries, start=1):
        if type(entry) is not dict or set(entry) != DEVELOPMENT_KEYS:
            raise ConditionalEvidenceError("development_expansion_exact_keys_required")
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
