"""Fixed C-W1-D1 operator composition over retained source-owner journals."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from carbon.audit import (
    DevelopmentEvidenceLedger,
    DevelopmentVerificationKey,
    LedgerReceiptRef,
)
from carbon.chain import ChainContext
from carbon.chain.dispatch import DispatchJournal
from carbon.chain.sdk_weights import BittensorPublicationBackend
from carbon.execution import ExecutionStage
from carbon.miner_mcp import MinerMcpJournal
from carbon.orchestration import (
    DevelopmentOperationalAccount,
    OperationalDisposition,
    StageAccount,
    StageDisposition,
)
from carbon.transport.models import ReceiptRef
from carbon.transport.store import ReceiptJournal

from .model import (
    DevelopmentTestnetEvidence,
    DevelopmentTestnetFailure,
    DevelopmentTestnetProfile,
    DevelopmentTestnetWeightIntent,
    LocalRetentionEvidence,
)
from .publication import DevelopmentTestnetPublisher
from .service import DevelopmentTestnetIntentIssuer

SOURCE_SCHEMA = "carbon.development-testnet.source-handoff.v1"
MAX_SOURCE_BYTES = 128 * 1024
MAX_REPORT_BYTES = 2 * 1024 * 1024
MAX_EXPORT_MEMBERS = 1024


def _json(path: Path, maximum: int) -> dict[str, object]:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
    ):
        raise DevelopmentTestnetFailure("REGULAR_SOURCE_FILE_REQUIRED")
    try:
        if not 0 < path.stat().st_size <= maximum:
            raise ValueError

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError
                result[key] = value
            return result

        value = json.loads(path.read_text(encoding="ascii"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise DevelopmentTestnetFailure("INVALID_SOURCE_FILE") from None
    if type(value) is not dict:
        raise DevelopmentTestnetFailure("INVALID_SOURCE_FILE")
    return value


def _path(root: Path, value: object) -> Path:
    if type(value) is not str or not value:
        raise DevelopmentTestnetFailure("EXPLICIT_SOURCE_PATH_REQUIRED")
    candidate = Path(value)
    result = (candidate if candidate.is_absolute() else root / candidate).absolute()
    if result.is_symlink():
        raise DevelopmentTestnetFailure("SOURCE_PATH_SYMLINK_REJECTED")
    return result


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _stream_digest(path: Path, expected_bytes: int) -> str:
    digest = hashlib.sha256()
    observed = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                observed += len(chunk)
                if observed > expected_bytes:
                    raise DevelopmentTestnetFailure("LOCAL_EXPORT_MEMBER_MISMATCH")
                digest.update(chunk)
    except OSError:
        raise DevelopmentTestnetFailure("INVALID_LOCAL_EXPORT_MEMBER") from None
    if observed != expected_bytes:
        raise DevelopmentTestnetFailure("LOCAL_EXPORT_MEMBER_MISMATCH")
    return "sha256:" + digest.hexdigest()


def _verify_export(path: Path) -> tuple[LocalRetentionEvidence, frozenset[Path]]:
    raw = _json(path, MAX_REPORT_BYTES)
    if set(raw) != {"schema", "entries"} or raw["schema"] != (
        "carbon.development-testnet.local-export-manifest.v1"
    ):
        raise DevelopmentTestnetFailure("INVALID_LOCAL_EXPORT_MANIFEST")
    entries = raw["entries"]
    if type(entries) is not list or not 1 <= len(entries) <= MAX_EXPORT_MEMBERS:
        raise DevelopmentTestnetFailure("INVALID_LOCAL_EXPORT_MANIFEST")
    total = 0
    validated = []
    member_paths = set()
    root = path.parent
    for entry in entries:
        if type(entry) is not dict or set(entry) != {"path", "bytes", "digest"}:
            raise DevelopmentTestnetFailure("INVALID_LOCAL_EXPORT_MANIFEST")
        relative = entry["path"]
        if (
            type(relative) is not str
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or Path(relative).as_posix() != relative
            or type(entry["bytes"]) is not int
            or entry["bytes"] < 0
        ):
            raise DevelopmentTestnetFailure("INVALID_LOCAL_EXPORT_MANIFEST")
        member = root / relative
        if (
            member in member_paths
            or member.is_symlink()
            or not member.is_file()
            or member.resolve() != member.absolute()
        ):
            raise DevelopmentTestnetFailure("INVALID_LOCAL_EXPORT_MEMBER")
        member_paths.add(member)
        total += entry["bytes"]
        if total > 2 * 1024**3:
            raise DevelopmentTestnetFailure("LOCAL_EXPORT_LIMIT_EXCEEDED")
        if _stream_digest(member, entry["bytes"]) != entry["digest"]:
            raise DevelopmentTestnetFailure("LOCAL_EXPORT_MEMBER_MISMATCH")
        validated.append(entry)
    canonical_entries = json.dumps(
        validated,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return (
        LocalRetentionEvidence(
            evidence_set_digest=_sha256(canonical_entries),
            export_manifest_digest=_sha256(path.read_bytes()),
            retained_bytes=total,
        ),
        frozenset((root / entry["path"]).absolute() for entry in validated),
    )


def _account(value: object) -> DevelopmentOperationalAccount:
    if type(value) is not dict or set(value) != {
        "attempt",
        "authority",
        "disposition",
        "finished_at_micros",
        "missing_stages",
        "receipt",
        "request_digest",
        "schema",
        "stages",
        "started_at_micros",
    }:
        raise DevelopmentTestnetFailure("INVALID_SOURCE_ACCOUNT")
    attempt, receipt = value["attempt"], value["receipt"]
    if (
        type(attempt) is not dict
        or set(attempt) != {"attempt_number", "submission_id"}
        or type(receipt) is not dict
        or set(receipt) != {"digest", "id"}
        or type(value["stages"]) is not list
        or type(value["missing_stages"]) is not list
    ):
        raise DevelopmentTestnetFailure("INVALID_SOURCE_ACCOUNT")
    try:
        stages = tuple(
            StageAccount(
                ExecutionStage(item["stage"]),
                StageDisposition(item["disposition"]),
                item["artifact_ref"],
                item["evidence_digest"],
            )
            for item in value["stages"]
            if type(item) is dict
            and set(item) == {"artifact_ref", "disposition", "evidence_digest", "stage"}
        )
        if len(stages) != len(value["stages"]):
            raise ValueError
        result = DevelopmentOperationalAccount(
            request_digest=value["request_digest"],
            submission_id=attempt["submission_id"],
            attempt_number=attempt["attempt_number"],
            disposition=OperationalDisposition(value["disposition"]),
            stages=stages,
            missing_stages=tuple(
                ExecutionStage(item) for item in value["missing_stages"]
            ),
            started_at_micros=value["started_at_micros"],
            finished_at_micros=value["finished_at_micros"],
            receipt_id=receipt["id"],
            receipt_digest=receipt["digest"],
            schema=value["schema"],
            authority_marker=value["authority"]["marker"],
            official=value["authority"]["official"],
            protected_execution_eligible=value["authority"][
                "protected_execution_eligible"
            ],
            score_eligible=value["authority"]["score_eligible"],
            archive_acknowledged=value["authority"]["archive_acknowledged"],
            network_eligible=value["authority"]["network_eligible"],
            reward_eligible=value["authority"]["reward_eligible"],
        )
    except (KeyError, TypeError, ValueError):
        raise DevelopmentTestnetFailure("INVALID_SOURCE_ACCOUNT") from None
    if result.document() != value:
        raise DevelopmentTestnetFailure("NONCANONICAL_SOURCE_ACCOUNT")
    return result


@dataclass(frozen=True, slots=True)
class DevelopmentSourceHandoff:
    intent_identity: str
    publication_journal: Path
    transport_journal: Path
    transport_context: ChainContext
    evidence_ledger: Path
    export_manifest: Path
    account_report: Path
    verification_keys: tuple[DevelopmentVerificationKey, ...]
    evidence: DevelopmentTestnetEvidence


def _require_within(path: Path, root: Path, failure: str) -> None:
    try:
        if path.resolve() != path.absolute() or not path.resolve().is_relative_to(
            root.resolve()
        ):
            raise ValueError
    except (OSError, RuntimeError, ValueError):
        raise DevelopmentTestnetFailure(failure) from None


def load_source_handoff(
    path: Path,
    *,
    retention_root: Path | None = None,
    export_root: Path | None = None,
) -> DevelopmentSourceHandoff:
    raw = _json(path, MAX_SOURCE_BYTES)
    expected = {
        "schema",
        "intent_identity",
        "publication_journal",
        "transport_journal",
        "transport_context",
        "evidence_ledger",
        "verification_keys",
        "account_report",
        "ledger_reference",
        "authenticated_request_receipt",
        "local_retention",
        "export_manifest",
    }
    if set(raw) != expected or raw["schema"] != SOURCE_SCHEMA:
        raise DevelopmentTestnetFailure("EXACT_SOURCE_HANDOFF_REQUIRED")
    root = path.parent
    account_report = _path(root, raw["account_report"])
    export_manifest = _path(root, raw["export_manifest"])
    publication_journal = _path(root, raw["publication_journal"])
    transport_journal = _path(root, raw["transport_journal"])
    evidence_ledger = _path(root, raw["evidence_ledger"])
    if retention_root is not None:
        for candidate in (publication_journal, transport_journal, evidence_ledger):
            _require_within(
                candidate, retention_root, "SOURCE_OUTSIDE_BOUNDED_RETENTION_ROOT"
            )
    if export_root is not None:
        for candidate in (export_manifest, account_report):
            _require_within(
                candidate, export_root, "SOURCE_OUTSIDE_BOUNDED_EXPORT_ROOT"
            )
    report = _json(account_report, MAX_REPORT_BYTES)
    if set(report) != {"account", "ledger_reference", "signed_receipt"}:
        raise DevelopmentTestnetFailure("PRIVATE_C07_REPORT_REQUIRED")
    account = _account(report["account"])
    try:
        ledger_ref = LedgerReceiptRef(**raw["ledger_reference"])
        if raw["ledger_reference"] != report["ledger_reference"]:
            raise ValueError
        authenticated_ref = ReceiptRef(**raw["authenticated_request_receipt"])
        retention, exported_members = _verify_export(export_manifest)
        if account_report not in exported_members:
            raise ValueError
        if raw["local_retention"] != {
            "evidence_set_digest": retention.evidence_set_digest,
            "export_manifest_digest": retention.export_manifest_digest,
            "retained_bytes": retention.retained_bytes,
            "storage_scope": retention.storage_scope,
            "policy_id": retention.policy_id,
            "host_loss_recoverable": retention.host_loss_recoverable,
            "archive_acknowledgement": retention.archive_acknowledgement,
        }:
            raise ValueError
        context = ChainContext(**raw["transport_context"])
        keys = tuple(
            DevelopmentVerificationKey(
                key_id=item["key_id"],
                public_key=bytes.fromhex(item["public_key_hex"]),
                valid_from_micros=item["valid_from_micros"],
                valid_until_micros=item["valid_until_micros"],
                revoked_at_micros=item["revoked_at_micros"],
            )
            for item in raw["verification_keys"]
        )
        evidence = DevelopmentTestnetEvidence(
            account, ledger_ref, authenticated_ref, retention
        )
    except (KeyError, TypeError, ValueError):
        raise DevelopmentTestnetFailure("INVALID_SOURCE_HANDOFF") from None
    return DevelopmentSourceHandoff(
        raw["intent_identity"],
        publication_journal,
        transport_journal,
        context,
        evidence_ledger,
        export_manifest,
        account_report,
        keys,
        evidence,
    )


def write_source_handoff(
    path: Path,
    *,
    intent_identity: str,
    publication_journal: Path,
    transport_journal: ReceiptJournal,
    evidence_ledger: DevelopmentEvidenceLedger,
    verification_keys: tuple[DevelopmentVerificationKey, ...],
    account_report: Path,
    ledger_reference: LedgerReceiptRef,
    authenticated_request_receipt: ReceiptRef,
    export_manifest: Path,
) -> DevelopmentSourceHandoff:
    """Seal one controller-produced handoff; it contains no signing material."""

    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or path.is_symlink()
        or type(transport_journal) is not ReceiptJournal
        or type(evidence_ledger) is not DevelopmentEvidenceLedger
        or type(verification_keys) is not tuple
        or any(
            type(item) is not DevelopmentVerificationKey for item in verification_keys
        )
    ):
        raise DevelopmentTestnetFailure("INVALID_SOURCE_HANDOFF_OUTPUT")
    report = _json(account_report, MAX_REPORT_BYTES)
    account = _account(report.get("account"))
    retention, exported_members = _verify_export(export_manifest)
    if account_report not in exported_members or report.get(
        "ledger_reference"
    ) != asdict(ledger_reference):
        raise DevelopmentTestnetFailure("SOURCE_EXPORT_ASSOCIATION_MISMATCH")
    # Resolve every source owner before serializing a transport document.
    DevelopmentEvidenceLedger(evidence_ledger.path, verification_keys).resolve(
        ledger_reference, verified_at_micros=account.finished_at_micros
    )
    MinerMcpJournal(transport_journal).resolve_development_source(
        authenticated_request_receipt, account
    )
    value = {
        "schema": SOURCE_SCHEMA,
        "intent_identity": intent_identity,
        "publication_journal": str(publication_journal.absolute()),
        "transport_journal": str(transport_journal.path.absolute()),
        "transport_context": asdict(transport_journal.context),
        "evidence_ledger": str(evidence_ledger.path.absolute()),
        "verification_keys": [
            {
                "key_id": item.key_id,
                "public_key_hex": item.public_key.hex(),
                "valid_from_micros": item.valid_from_micros,
                "valid_until_micros": item.valid_until_micros,
                "revoked_at_micros": item.revoked_at_micros,
            }
            for item in verification_keys
        ],
        "account_report": str(account_report.absolute()),
        "ledger_reference": asdict(ledger_reference),
        "authenticated_request_receipt": asdict(authenticated_request_receipt),
        "export_manifest": str(export_manifest.absolute()),
        "local_retention": asdict(retention),
    }
    payload = (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise DevelopmentTestnetFailure("CONFLICTING_SOURCE_HANDOFF")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        except FileExistsError:
            raise DevelopmentTestnetFailure("CONFLICTING_SOURCE_HANDOFF") from None
    return load_source_handoff(path)


def composition(config, source: DevelopmentSourceHandoff, backend):
    """Reopen exact journals. This neither reads a wallet nor executes science."""

    profile = DevelopmentTestnetProfile(config.context, config.expected_runtime_spec)
    receipts = ReceiptJournal(source.publication_journal, config.context)
    evidence = DevelopmentEvidenceLedger(
        source.evidence_ledger, source.verification_keys
    )
    transport = ReceiptJournal(source.transport_journal, source.transport_context)
    issuer = DevelopmentTestnetIntentIssuer(
        receipts, evidence, MinerMcpJournal(transport), profile
    )
    return issuer, DevelopmentTestnetPublisher(
        issuer, backend, config.transaction_authorization
    )


def retained_intent(config, source: DevelopmentSourceHandoff):
    receipts = ReceiptJournal(source.publication_journal, config.context)
    with receipts.transaction() as database:
        exists = database.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='development_testnet_intent_v1'"
        ).fetchone()
        row = (
            None
            if exists is None
            else database.execute(
                "SELECT digest FROM development_testnet_intent_v1 WHERE identity=?",
                (source.intent_identity,),
            ).fetchone()
        )
    if row is None:
        return None, DispatchJournal(
            receipts,
            network="testnet",
            intent_type=DevelopmentTestnetWeightIntent,
        )
    ref = DevelopmentTestnetWeightIntent(source.intent_identity, row[0])
    return ref, DispatchJournal(
        receipts,
        network="testnet",
        intent_type=DevelopmentTestnetWeightIntent,
    )


def _require_context(config, source: DevelopmentSourceHandoff) -> None:
    if source.transport_context != config.context:
        raise DevelopmentTestnetFailure("AUTHENTICATED_REQUEST_CONTEXT_MISMATCH")


async def execute_run(config, source: DevelopmentSourceHandoff, wallet):
    _require_context(config, source)
    backend = BittensorPublicationBackend(
        config.context, config.publisher_hotkey, wallet, network="testnet"
    )
    try:
        issuer, publisher = composition(config, source, backend)
        signed, _ = issuer.evidence_ledger.resolve(
            source.evidence.ledger_reference,
            verified_at_micros=source.evidence.account.finished_at_micros,
        )
        if (
            signed.receipt.binding.worker_image_digest != config.worker_image_digest
            or signed.receipt.binding.resource_policy_digest
            != config.resource_policy_digest
        ):
            raise DevelopmentTestnetFailure("EXECUTION_PROFILE_SOURCE_MISMATCH")
        snapshot, _ = await backend.observe()
        ref = issuer.issue(source.intent_identity, source.evidence, snapshot=snapshot)
        return await publisher.publish(ref)
    finally:
        await backend.close()


async def execute_resume(config, source: DevelopmentSourceHandoff):
    _require_context(config, source)
    ref, _ = retained_intent(config, source)
    if ref is None:
        raise DevelopmentTestnetFailure("NO_DISPATCH_TO_RESUME")
    backend = BittensorPublicationBackend(
        config.context, config.publisher_hotkey, None, network="testnet"
    )
    try:
        _, publisher = composition(config, source, backend)
        return await publisher.reconcile(ref.digest)
    finally:
        await backend.close()


def execution_status(config, source: DevelopmentSourceHandoff):
    _require_context(config, source)
    ref, journal = retained_intent(config, source)
    row = None if ref is None else journal.get(ref.digest)
    return {
        "schema": "carbon.development-testnet.execution-status.v1",
        "intent_identity": source.intent_identity,
        "intent_digest": None if ref is None else ref.digest,
        "dispatch": row,
        "operator_action": (
            "RUN_AUTHORIZED_SCENARIO"
            if row is None
            else (
                "NONE_TERMINAL"
                if row["state"]
                in {
                    "ROW_VERIFIED",
                    "CHAIN_REJECTED",
                    "FAILED_BEFORE_SIGNING",
                    "EXPOSURE_CHANGED",
                }
                else "RESUME_RECONCILIATION"
            )
        ),
        "stored_weights_may_remain_effective": row is not None,
        "protected_or_official_eligible": False,
    }


__all__ = [
    "DevelopmentSourceHandoff",
    "execute_resume",
    "execute_run",
    "execution_status",
    "load_source_handoff",
    "write_source_handoff",
]
