"""Submission terms at the door (owner G-LEAD-50, 23 Nov 2026, OWNER_LINES block 47): from the next opens every
submission records the terms version, the sha256 of the terms text as published, and the miner's acceptance; a
submission without them is refused.

Per Challenge VERSION, never per door (v2 scope read, row 4781): `TERMS_BY_VERSION` names the versions that require
terms. The live Motor 1.8 door and every other version are untouched: their discovery carries no ``terms`` and their
``construction_submit`` keeps its strict two fields.

- `PINNED_SHA256` holds the sha256 of each terms version's PUBLISHED text, pinned only after v2 has checked the
  published bytes against the approved wording (None = not yet: a door of that version then refuses every submission,
  ``terms_unavailable``, 503: refuse-without, never accept-without).
- The text is the operator's file (receiver.json ``submission_terms_text``: the checkout's
  ``docs/terms/<version>.md``), read once at start. The door serves those exact bytes (text/markdown) only when their
  sha256 is the pinned one, and refuses every submission while they are missing or another text.
- The acceptance is the hotkey's own btauth signature over a ``construction_submit`` whose fields carry
  ``terms_version`` and ``terms_sha256``. The door keeps that signed request (its body and its ``x-bittensor-*``
  headers, so anyone can verify the signature again) append-only, one row per transport receipt, BEFORE admission: a
  submission whose acceptance cannot be recorded is not admitted.

The record is custody only: nothing here is public, scored or ranked, and it never enters a grade.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

#: Challenge version -> the terms version its submissions must accept (owner G-LEAD-50). None is named on this public
#: tree (owner G-LEAD-122); a version registered later names its terms in its exam registry row (``terms``: the version
#: and its published sha256).
TERMS_BY_VERSION = {}
#: Terms version -> sha256 (64 hex) of its text AS PUBLISHED, or None until published and checked by v2.
PINNED_SHA256 = {
    # docs/terms/carbon-submission-terms-v0.md as published (miner-ux 4825: section (a) minus section 9 and the counsel
    # line, 2154 B); v2 row 4828 verified it byte for byte against the owner-approved file 98de6640.
    "carbon-submission-terms-v0": "946244f64b9c8580010595822ad997eb22e7184dd4074dfca808868c30232faa",
}
#: The submit fields that carry the acceptance (inside the hotkey-signed body).
FIELDS = ("terms_version", "terms_sha256")
#: Where a terms door serves its text (one path per terms version).
PATH_PREFIX = "/carbon/v1/terms/"
#: The text's bound: the whole terms text is far below it, and the door reads it once at start.
MAX_TEXT_BYTES = 65536
#: The request headers kept with the signed body: the btauth/1 signature headers, nothing else (no address, no cookie).
AUTH_HEADER_PREFIX = "x-bittensor-"
RECORD_NAME = "submission_terms.sqlite3"

NOT_ACCEPTED = "terms_not_accepted"
MISMATCH = "terms_mismatch"
UNAVAILABLE = "terms_unavailable"
#: The terms version of a door whose registered terms cannot be read (never a published one).
UNREADABLE = "terms-unreadable"

_VERSION = re.compile(r"[a-z0-9][a-z0-9.-]{0,63}")
_SHA = re.compile(r"[0-9a-f]{64}")


class TermsUnavailable(Exception):
    """The door cannot take a terms-bound submission now (sha not pinned, text missing or not the pinned one, record
    not writable). Not the miner's fault, never counted."""

    code = UNAVAILABLE


def required_version(challenge_id, version):
    """The terms version a Challenge version's submissions must accept, or None (no terms: the door is unchanged)."""
    found = _registered(challenge_id, version)
    return None if found is None else found[0]


def _registered(challenge_id, version):
    """(terms version, pinned sha256) of a Challenge version: the tables above, else its exam registry row; None for a
    version with no row. A version that HAS a row accepts nothing without terms (owner G-LEAD-50): a malformed row, a row
    with no ``terms``, or one that pins another text for a terms version pinned above, is `TermsUnavailable`.
    """
    own = TERMS_BY_VERSION.get((challenge_id, version))
    if own is not None:
        return own, PINNED_SHA256[own]
    from carbon.challenge_registry import exam_registry

    try:
        row = exam_registry.require(challenge_id, version, "terms")
    except exam_registry.ExamRowRefused as refused:
        raise TermsUnavailable() from refused
    if row is None:
        if exam_registry.digest(challenge_id, version) is not None:
            raise TermsUnavailable()
        return None
    if PINNED_SHA256.get(row["version"], row["sha256"]) != row["sha256"]:
        raise TermsUnavailable()
    return row["version"], row["sha256"]


def path_of(terms_version):
    return PATH_PREFIX + terms_version


def _check_tables():
    for key, terms_version in TERMS_BY_VERSION.items():
        if not _VERSION.fullmatch(terms_version) or terms_version not in PINNED_SHA256:
            raise ValueError(f"submission terms table: {key}")
    for terms_version, sha in PINNED_SHA256.items():
        if not _VERSION.fullmatch(terms_version) or not (
            sha is None or (type(sha) is str and _SHA.fullmatch(sha))
        ):
            raise ValueError(f"submission terms pin: {terms_version}")


_check_tables()


@dataclass(frozen=True)
class Terms:
    """One door's terms: the version, its pinned sha256 (None = not published yet) and the text, when the operator's
    file is the pinned one."""

    version: str
    sha256: str | None
    text: bytes | None

    @property
    def ready(self):
        return self.sha256 is not None and self.text is not None

    def facts(self):
        """The discovery entry (`DirectRecipeIntake.public`): what a client shows and signs."""
        return {
            "version": self.version,
            "sha256": self.sha256,
            "path": path_of(self.version),
        }


def read_text(path, sha256):
    """The operator's terms text (its exact bytes) at ``path`` when they hash to ``sha256``, else None (missing,
    oversized, not UTF-8, or another text). Never raises: an unready text makes the door refuse terms-bound submissions, not crash.
    """
    if path is None or sha256 is None:
        return None
    try:
        file = Path(path)
        if not file.is_file() or file.stat().st_size > MAX_TEXT_BYTES:
            return None
        body = file.read_bytes()
        if hashlib.sha256(body).hexdigest() != sha256:
            return None
        body.decode("utf-8")
        return body
    except (OSError, UnicodeDecodeError):
        return None


def for_door(challenge_id, version, text_path):
    """This door's `Terms`, or None when its Challenge version requires none. Terms that cannot be read from the registry
    give a door that is not ready: it starts, and refuses every submission (400 `terms_not_accepted` / `terms_mismatch`,
    or 503 `terms_unavailable`)."""
    try:
        found = _registered(challenge_id, version)
    except TermsUnavailable:
        return Terms(UNREADABLE, None, None)
    if found is None:
        return None
    terms_version, sha = found
    return Terms(terms_version, sha, read_text(text_path, sha))


def check_fields(terms, fields):
    """The submit fields of a terms door: (None, the two recipe fields) when they carry the door's current terms, else
    (refusal code, None). ``terms`` None = no terms door: the strict two fields, as before (`submission_fields`).
    """
    recipe = {"strategy_json", "contract_digest"}
    if terms is None:
        return (None, fields) if set(fields) == recipe else ("submission_fields", None)
    if set(fields) == recipe:
        return NOT_ACCEPTED, None
    if set(fields) != recipe | set(FIELDS):
        return "submission_fields", None
    if (fields["terms_version"], fields["terms_sha256"]) != (
        terms.version,
        terms.sha256,
    ):
        return MISMATCH, None
    return None, {name: fields[name] for name in recipe}


def refusal(code, terms):
    """A terms refusal's answer body: the code and, for the miner's client, the door's current terms to show again."""
    body = {"refused": code}
    if terms is not None:
        body["terms"] = terms.facts()
    return body


def auth_headers(headers):
    """The btauth/1 signature headers of a request, names lower-cased, sorted (what a later signature check needs)."""
    items = headers.items() if hasattr(headers, "items") else ()
    return {
        k.lower(): v
        for k, v in sorted(items, key=lambda item: str(item[0]).lower())
        if type(k) is str
        and type(v) is str
        and k.lower().startswith(AUTH_HEADER_PREFIX)
    }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS acceptance (
    receipt_sequence INTEGER PRIMARY KEY,
    receipt_digest TEXT NOT NULL UNIQUE,
    hotkey TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    terms_version TEXT NOT NULL,
    terms_sha256 TEXT NOT NULL,
    finalized_block INTEGER,
    request_sha256 TEXT NOT NULL,
    request_body BLOB NOT NULL,
    auth_headers TEXT NOT NULL,
    recorded_utc TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS acceptance_no_update BEFORE UPDATE ON acceptance
BEGIN SELECT RAISE(ABORT, 'acceptance is append-only'); END;
CREATE TRIGGER IF NOT EXISTS acceptance_no_delete BEFORE DELETE ON acceptance
BEGIN SELECT RAISE(ABORT, 'acceptance is append-only'); END;
"""


class AcceptanceStore:
    """The door's append-only record of terms acceptances (custody only), one row per transport receipt."""

    def __init__(self, path):
        self.path = Path(path)

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA synchronous=FULL")
        connection.executescript(_SCHEMA)
        return connection

    def record(self, *, receipt, hotkey, challenge, terms, body, headers, now=None):
        """Keep one acceptance before its submission is admitted, or raise `TermsUnavailable`. The same receipt twice is
        one row (a retried admission of one signed request)."""
        when = now or datetime.datetime.now(datetime.UTC)
        row = (
            int(receipt["sequence"]),
            str(receipt["digest"]),
            hotkey,
            challenge.challenge_id,
            challenge.version,
            terms.version,
            terms.sha256,
            receipt.get("block"),
            hashlib.sha256(body).hexdigest(),
            sqlite3.Binary(body),
            json.dumps(auth_headers(headers), sort_keys=True, separators=(",", ":")),
            when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO acceptance VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    row,
                )
                found = connection.execute(
                    "SELECT receipt_digest, hotkey, terms_version, terms_sha256 FROM acceptance"
                    " WHERE receipt_sequence = ?",
                    (row[0],),
                ).fetchone()
        except (sqlite3.Error, OSError, ValueError, TypeError) as failure:
            raise TermsUnavailable() from failure
        if found != (row[1], row[2], row[5], row[6]):
            raise TermsUnavailable()

    def rows(self):
        """Every acceptance, oldest first (custody / audit reads only)."""
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            return [
                dict(r)
                for r in connection.execute(
                    "SELECT * FROM acceptance ORDER BY receipt_sequence"
                )
            ]


__all__ = [
    "AUTH_HEADER_PREFIX",
    "FIELDS",
    "MISMATCH",
    "NOT_ACCEPTED",
    "PATH_PREFIX",
    "PINNED_SHA256",
    "RECORD_NAME",
    "TERMS_BY_VERSION",
    "UNAVAILABLE",
    "UNREADABLE",
    "AcceptanceStore",
    "Terms",
    "TermsUnavailable",
    "auth_headers",
    "check_fields",
    "for_door",
    "path_of",
    "read_text",
    "refusal",
    "required_version",
]
