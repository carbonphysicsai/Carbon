"""Durable attachments to existing DEVELOPMENT receipts, never an evaluator.

Only the trusted local operator supplies source handoff paths. The HTTP surface
uses opaque IDs and C-07's existing public projection. No private report is served.
Attaching evidence does not launch a campaign or grant resource authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path

SCHEMA = "carbon.launchpad.development-readback.v1"
MAX_SOURCE_BYTES = 128 * 1024


class SourceUnavailable(ValueError):
    def __init__(self):
        super().__init__("development_source_unavailable")


def source_pin(path: Path) -> str:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or path.resolve() != path.absolute()
        or not path.is_file()
    ):
        raise SourceUnavailable()
    with path.open("rb") as stream:
        payload = stream.read(MAX_SOURCE_BYTES + 1)
    if not 0 < len(payload) <= MAX_SOURCE_BYTES:
        raise SourceUnavailable()
    return hashlib.sha256(payload).hexdigest()


def resolve_public_source(path: Path, expected_pin: str) -> dict:
    """Revalidate signature, source association and current lifecycle each read."""
    from carbon.audit import DevelopmentEvidenceLedger
    from carbon.development_comparison.sources import validate_active_association
    from carbon.development_testnet.execution import load_source_handoff
    from carbon.miner_mcp import MinerMcpJournal
    from carbon.orchestration import public_projection
    from carbon.transport.store import ReceiptJournal

    if source_pin(path) != expected_pin:
        raise SourceUnavailable()
    source = load_source_handoff(
        path, retention_root=path.parent, export_root=path.parent
    )
    # A read must not initialize a missing journal as a replacement source.
    for journal in (source.evidence_ledger, source.transport_journal):
        if not journal.is_file() or journal.is_symlink():
            raise SourceUnavailable()
    account = source.evidence.account
    signed, lifecycle = DevelopmentEvidenceLedger(
        source.evidence_ledger, source.verification_keys
    ).resolve(
        source.evidence.ledger_reference, verified_at_micros=account.finished_at_micros
    )
    auth = MinerMcpJournal(
        ReceiptJournal(source.transport_journal, source.transport_context)
    ).resolve_development_source(source.evidence.authenticated_request_receipt, account)
    validate_active_association(signed.receipt, account, auth, lifecycle)
    if source_pin(path) != expected_pin:
        raise SourceUnavailable()
    return public_projection(account)


class DevelopmentSources:
    """Private controller attachment registry; no caller-supplied scientific data."""

    def __init__(self, database: Path):
        self.database = database
        with sqlite3.connect(database) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS development_sources "
                "(id TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL, pin TEXT NOT NULL)"
            )

    def attach(self, path: Path) -> str:
        """Operator-only registration; preserve the pin on retries and restarts."""
        pin = source_pin(path)
        resolve_public_source(path, pin)
        with sqlite3.connect(self.database) as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT id,pin FROM development_sources WHERE path=?", (str(path),)
            ).fetchone()
            if old:
                if old[1] != pin:
                    raise SourceUnavailable()
                return old[0]
            if (
                db.execute("SELECT COUNT(*) FROM development_sources").fetchone()[0]
                >= 100
            ):
                raise SourceUnavailable()
            identity = uuid.uuid4().hex
            db.execute(
                "INSERT INTO development_sources VALUES(?,?,?)",
                (identity, str(path), pin),
            )
        return identity

    def get(self, identity: str) -> dict:
        with sqlite3.connect(self.database) as db:
            row = db.execute(
                "SELECT path,pin FROM development_sources WHERE id=?", (identity,)
            ).fetchone()
        if row is None:
            raise SourceUnavailable()
        result = {
            "schema": SCHEMA,
            "id": identity,
            "mode": "DEVELOPMENT_EVALUATION",
            "origin": "OPERATOR_ATTACHED_EXISTING_SOURCE",
            "campaign_launched_by_launchpad": False,
            "status": "READBACK_UNAVAILABLE",
            "receipt": None,
        }
        try:
            result["receipt"] = resolve_public_source(Path(row[0]), row[1])
            result["status"] = "VERIFIED_SOURCE"
        except Exception:  # noqa: BLE001 - normalize private domain/path failures.
            result["receipt"] = None
            result["status"] = "READBACK_UNAVAILABLE"
        return result

    def recent(self) -> list[dict]:
        with sqlite3.connect(self.database) as db:
            identities = db.execute(
                "SELECT id FROM development_sources ORDER BY rowid DESC"
            ).fetchall()
        return [self.get(row[0]) for row in identities]

    def export(self, identity: str) -> bytes:
        value = self.get(identity)
        if value["status"] != "VERIFIED_SOURCE":
            raise SourceUnavailable()
        return json.dumps(value, allow_nan=False, sort_keys=True, indent=2).encode()
