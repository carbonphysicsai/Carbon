"""One-campaign authority for the non-qualifying B-E4 development pilot.

This is deliberately not a general approval or authentication framework.  It
binds one authenticated Carbon-owner act to one immutable DEVELOPMENT request,
one provider project identity, one durable journal, and one terminal campaign
result.  Qualification and every later campaign remain outside its authority.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Self

CARBON_OWNER_GITHUB_LOGIN = "jbequ5"
CARBON_OWNER_GITHUB_USER_ID = 99_085_788
DEVELOPMENT_OWNER_ROLES = (
    "RESEARCH",
    "EXACT_PROTOCOL",
    "SCIENCE",
    "STATISTICS",
    "SECURITY",
)
DEVELOPMENT_AUTHORIZATION_LIFETIME_SECONDS = 432_000
DEVELOPMENT_RETENTION_SELECTION = (
    "STANDARD_API_ABUSE_MONITORING_STORE_FALSE_NO_TRAINING_OR_DATA_SHARING_"
    "OPT_IN_DOCUMENTED_PROMPT_CACHE_RETENTION_ACCEPTED"
)

_AUTHORIZATION_DOMAIN = b"carbon.be4.development-authorization.v1\x00"
_BINDINGS_DOMAIN = b"carbon.be4.development-authorization-bindings.v1\x00"
_IDENTITY_DOMAIN = b"carbon.be4.development-provider-identity.v1\x00"
_LIVE_PRINCIPAL_TOKEN = object()
_LIVE_ADMISSION_TOKEN = object()
_FIXTURE_ADMISSION_TOKEN = object()


class DevelopmentAuthorizationError(RuntimeError):
    """The bounded development authorization cannot be issued or used."""


class DevelopmentAuthenticationError(DevelopmentAuthorizationError):
    """The current external identity is not the assigned Carbon owner."""


class DevelopmentApprovalUnavailable(DevelopmentAuthorizationError):
    """No current, matching, claimed development authorization exists."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise DevelopmentAuthorizationError(
            "authorization value is not canonical JSON"
        ) from error


def _digest(domain: bytes, value: object) -> str:
    return "sha256:" + hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def _is_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _utc_from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")


def provider_identity_digest(value: str, *, kind: str) -> str:
    """Bind a provider identity without retaining or displaying its raw value."""

    if type(value) is not str or not value or type(kind) is not str or not kind:
        raise TypeError("provider identity digest requires non-empty exact text")
    return _digest(_IDENTITY_DOMAIN, {"kind": kind, "value": value})


@dataclass(frozen=True, slots=True)
class DevelopmentAuthorizationBindings:
    request_digest: str
    campaign_manifest_digest: str
    proposal_digest: str
    implementation_digest: str
    artifact_manifest_digest: str
    owner_decisions_digest: str
    retention_contract_digest: str
    journal_binding: str
    project_id_digest: str
    organization_id_digest: str | None
    monetary_ceiling_usd: Decimal
    stage: str = "DEVELOPMENT"

    def __post_init__(self) -> None:
        digests = (
            self.request_digest,
            self.campaign_manifest_digest,
            self.proposal_digest,
            self.implementation_digest,
            self.artifact_manifest_digest,
            self.owner_decisions_digest,
            self.retention_contract_digest,
            self.journal_binding,
            self.project_id_digest,
        )
        if (
            type(self) is not DevelopmentAuthorizationBindings
            or any(not _is_digest(item) for item in digests)
            or (
                self.organization_id_digest is not None
                and not _is_digest(self.organization_id_digest)
            )
            or type(self.monetary_ceiling_usd) is not Decimal
            or self.monetary_ceiling_usd != Decimal("14.42")
            or self.stage != "DEVELOPMENT"
        ):
            raise TypeError("development authorization bindings are invalid")

    def to_json(self) -> dict[str, object]:
        return {
            "artifact_manifest_digest": self.artifact_manifest_digest,
            "campaign_manifest_digest": self.campaign_manifest_digest,
            "implementation_digest": self.implementation_digest,
            "journal_binding": self.journal_binding,
            "monetary_ceiling_usd": str(self.monetary_ceiling_usd),
            "organization_id_digest": self.organization_id_digest,
            "owner_decisions_digest": self.owner_decisions_digest,
            "project_id_digest": self.project_id_digest,
            "proposal_digest": self.proposal_digest,
            "request_digest": self.request_digest,
            "retention_contract_digest": self.retention_contract_digest,
            "stage": self.stage,
        }

    @classmethod
    def from_json(cls, value: object) -> DevelopmentAuthorizationBindings:
        if type(value) is not dict or set(value) != {
            "artifact_manifest_digest",
            "campaign_manifest_digest",
            "implementation_digest",
            "journal_binding",
            "monetary_ceiling_usd",
            "organization_id_digest",
            "owner_decisions_digest",
            "project_id_digest",
            "proposal_digest",
            "request_digest",
            "retention_contract_digest",
            "stage",
        }:
            raise DevelopmentAuthorizationError(
                "stored authorization bindings are invalid"
            )
        try:
            return cls(
                value["request_digest"],
                value["campaign_manifest_digest"],
                value["proposal_digest"],
                value["implementation_digest"],
                value["artifact_manifest_digest"],
                value["owner_decisions_digest"],
                value["retention_contract_digest"],
                value["journal_binding"],
                value["project_id_digest"],
                value["organization_id_digest"],
                Decimal(value["monetary_ceiling_usd"]),
                value["stage"],
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as error:
            raise DevelopmentAuthorizationError(
                "stored authorization bindings are invalid"
            ) from error

    @property
    def content_digest(self) -> str:
        return _digest(_BINDINGS_DOMAIN, self.to_json())


@dataclass(frozen=True, slots=True)
class _AuthenticatedCarbonOwner:
    login: str
    user_id: int
    authenticated_at_utc: str
    authentication_method: str
    _token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not _AuthenticatedCarbonOwner
            or self._token is not _LIVE_PRINCIPAL_TOKEN
            or self.login != CARBON_OWNER_GITHUB_LOGIN
            or self.user_id != CARBON_OWNER_GITHUB_USER_ID
            or type(self.authenticated_at_utc) is not str
            or not self.authenticated_at_utc
            or self.authentication_method != "AUTHENTICATED_GITHUB_REST_VIEWER"
        ):
            raise DevelopmentAuthenticationError(
                "authenticated principal is not the assigned Carbon owner"
            )


class GitHubCliCarbonOwnerAuthenticator:
    """Authenticate the current principal through GitHub's `/user` endpoint."""

    __slots__ = ()

    def authenticate(self) -> _AuthenticatedCarbonOwner:
        if type(self) is not GitHubCliCarbonOwnerAuthenticator:
            raise DevelopmentAuthenticationError(
                "production owner authentication cannot be substituted"
            )
        try:
            process = subprocess.run(
                [
                    "gh",
                    "api",
                    "--header",
                    "Accept: application/vnd.github+json",
                    "--header",
                    "X-GitHub-Api-Version: 2022-11-28",
                    "/user",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise DevelopmentAuthenticationError(
                "GitHub owner authentication is unavailable"
            ) from error
        if process.returncode != 0:
            raise DevelopmentAuthenticationError(
                "GitHub owner authentication did not succeed"
            )
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError as error:
            raise DevelopmentAuthenticationError(
                "GitHub owner authentication returned invalid JSON"
            ) from error
        if (
            type(payload) is not dict
            or payload.get("login") != CARBON_OWNER_GITHUB_LOGIN
            or payload.get("id") != CARBON_OWNER_GITHUB_USER_ID
            or payload.get("type") != "User"
        ):
            raise DevelopmentAuthenticationError(
                "current GitHub principal is not jbequ5 / 99085788"
            )
        return _AuthenticatedCarbonOwner(
            CARBON_OWNER_GITHUB_LOGIN,
            CARBON_OWNER_GITHUB_USER_ID,
            _utc_from_timestamp(time.time()),
            "AUTHENTICATED_GITHUB_REST_VIEWER",
            _LIVE_PRINCIPAL_TOKEN,
        )


@dataclass(frozen=True, slots=True)
class _RealExecutionAdmission:
    authorization_id: str
    bindings: DevelopmentAuthorizationBindings
    journal_binding: str
    _store: DevelopmentAuthorizationStore = field(repr=False, compare=False)
    _token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not _RealExecutionAdmission
            or self._token is not _LIVE_ADMISSION_TOKEN
            or type(self.authorization_id) is not str
            or not self.authorization_id.startswith("be4-development-")
            or type(self.bindings) is not DevelopmentAuthorizationBindings
            or not _is_digest(self.journal_binding)
            or type(self._store) is not DevelopmentAuthorizationStore
        ):
            raise DevelopmentApprovalUnavailable(
                "real development execution admission is invalid"
            )

    def assert_current(
        self, *, project_id_digest: str, organization_id_digest: str | None
    ) -> None:
        self._store.assert_current(
            self,
            project_id_digest=project_id_digest,
            organization_id_digest=organization_id_digest,
        )


@dataclass(frozen=True, slots=True)
class ControlledExecutionAdmission:
    """Loopback-only admission used by offline HTTP integration tests."""

    authorization_id: str
    bindings: DevelopmentAuthorizationBindings
    journal_binding: str
    _store: ControlledDevelopmentAuthorizationStore = field(repr=False, compare=False)
    _token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not ControlledExecutionAdmission
            or self._token is not _FIXTURE_ADMISSION_TOKEN
            or not self.authorization_id.startswith("fixture-be4-development-")
            or type(self.bindings) is not DevelopmentAuthorizationBindings
            or not _is_digest(self.journal_binding)
            or type(self._store) is not ControlledDevelopmentAuthorizationStore
        ):
            raise DevelopmentApprovalUnavailable(
                "controlled development admission is invalid"
            )

    def assert_current(
        self, *, project_id_digest: str, organization_id_digest: str | None
    ) -> None:
        self._store.assert_current(
            self,
            project_id_digest=project_id_digest,
            organization_id_digest=organization_id_digest,
        )


class _AuthorizationStore:
    __slots__ = ("_connection", "path")

    environment: str
    authorization_prefix: str

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise TypeError("authorization store requires an exact path")
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=30, isolation_level=None)
        path.chmod(0o600)
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS authorization (
                authorization_id TEXT PRIMARY KEY,
                environment TEXT NOT NULL,
                request_digest TEXT NOT NULL UNIQUE,
                bindings_digest TEXT NOT NULL UNIQUE,
                bindings_json TEXT NOT NULL,
                approval_act_digest TEXT NOT NULL,
                approval_act_json TEXT NOT NULL,
                issuer_login TEXT NOT NULL,
                issuer_user_id INTEGER NOT NULL,
                issued_at_unix REAL NOT NULL,
                expires_at_unix REAL NOT NULL,
                state TEXT NOT NULL,
                journal_binding TEXT,
                terminal_report_digest TEXT,
                updated_at_utc TEXT NOT NULL
            );
            """)
        self.path = path
        self._connection = connection

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _issue(
        self,
        bindings: DevelopmentAuthorizationBindings,
        *,
        issuer_login: str,
        issuer_user_id: int,
        authenticated_at_utc: str,
    ) -> str:
        if type(bindings) is not DevelopmentAuthorizationBindings:
            raise TypeError("authorization issuance requires exact bindings")
        existing = self._connection.execute(
            "SELECT authorization_id, environment, bindings_digest, state "
            "FROM authorization WHERE request_digest = ?",
            (bindings.request_digest,),
        ).fetchone()
        if existing is not None:
            if (
                existing[1] != self.environment
                or existing[2] != bindings.content_digest
            ):
                raise DevelopmentAuthorizationError(
                    "execution request already has different authorization bindings"
                )
            if existing[3] in ("ISSUED", "CLAIMED"):
                return str(existing[0])
            raise DevelopmentAuthorizationError(
                "execution request authorization was already terminal"
            )
        issued_at = time.time()
        expires_at = issued_at + DEVELOPMENT_AUTHORIZATION_LIFETIME_SECONDS
        authorization_id = self.authorization_prefix + secrets.token_hex(16)
        approval_act = {
            "action": "APPROVE_AND_AUTHORIZE_EXACTLY_ONE_DEVELOPMENT_CAMPAIGN",
            "authenticated_at_utc": authenticated_at_utc,
            "bindings": bindings.to_json(),
            "independent_multidisciplinary_ratification_claimed": False,
            "issuer": {
                "github_login": issuer_login,
                "github_user_id": issuer_user_id,
            },
            "owner_roles": list(DEVELOPMENT_OWNER_ROLES),
            "principal_count": 1,
            "retention_selection": DEVELOPMENT_RETENTION_SELECTION,
            "scope": "ONE_NONQUALIFYING_DEVELOPMENT_CAMPAIGN_ONLY",
        }
        act_digest = _digest(_AUTHORIZATION_DOMAIN, approval_act)
        now = _utc_from_timestamp(issued_at)
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                "INSERT INTO authorization VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ISSUED', ?, NULL, ?)",
                (
                    authorization_id,
                    self.environment,
                    bindings.request_digest,
                    bindings.content_digest,
                    _canonical_bytes(bindings.to_json()).decode("ascii"),
                    act_digest,
                    _canonical_bytes(approval_act).decode("ascii"),
                    issuer_login,
                    issuer_user_id,
                    issued_at,
                    expires_at,
                    bindings.journal_binding,
                    now,
                ),
            )
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise DevelopmentAuthorizationError(
                "a concurrent issuer already created this campaign authorization"
            ) from error
        return authorization_id

    def _claim_row(
        self,
        authorization_id: str,
        bindings: DevelopmentAuthorizationBindings,
        journal_binding: str,
    ) -> None:
        if (
            type(authorization_id) is not str
            or not authorization_id.startswith(self.authorization_prefix)
            or type(bindings) is not DevelopmentAuthorizationBindings
            or not _is_digest(journal_binding)
            or journal_binding != bindings.journal_binding
        ):
            raise DevelopmentApprovalUnavailable("authorization claim is invalid")
        now = time.time()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT environment, bindings_digest, expires_at_unix, state, "
                "journal_binding FROM authorization WHERE authorization_id = ?",
                (authorization_id,),
            ).fetchone()
            if (
                row is None
                or row[0] != self.environment
                or row[1] != bindings.content_digest
                or float(row[2]) <= now
                or row[3] not in ("ISSUED", "CLAIMED")
                or row[4] != journal_binding
            ):
                raise DevelopmentApprovalUnavailable(
                    "authorization is absent, expired, terminal, or differently bound"
                )
            if row[3] == "ISSUED":
                changed = self._connection.execute(
                    "UPDATE authorization SET state = 'CLAIMED', updated_at_utc = ? "
                    "WHERE authorization_id = ? AND state = 'ISSUED'",
                    (
                        _utc_from_timestamp(now),
                        authorization_id,
                    ),
                ).rowcount
                if changed != 1:
                    raise DevelopmentApprovalUnavailable(
                        "authorization claim lost its one-use race"
                    )
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def _assert_current(
        self,
        *,
        authorization_id: str,
        bindings: DevelopmentAuthorizationBindings,
        journal_binding: str,
        project_id_digest: str,
        organization_id_digest: str | None,
    ) -> None:
        row = self._connection.execute(
            "SELECT environment, bindings_digest, expires_at_unix, state, "
            "journal_binding FROM authorization WHERE authorization_id = ?",
            (authorization_id,),
        ).fetchone()
        if (
            row is None
            or row[0] != self.environment
            or row[1] != bindings.content_digest
            or float(row[2]) <= time.time()
            or row[3] != "CLAIMED"
            or row[4] != journal_binding
            or project_id_digest != bindings.project_id_digest
            or organization_id_digest != bindings.organization_id_digest
        ):
            raise DevelopmentApprovalUnavailable(
                "development authorization is not current for this operation"
            )

    def public_record(self, authorization_id: str) -> dict[str, object]:
        row = self._connection.execute(
            "SELECT environment, request_digest, bindings_digest, bindings_json, "
            "approval_act_digest, issuer_login, issuer_user_id, issued_at_unix, "
            "expires_at_unix, state, journal_binding, terminal_report_digest "
            "FROM authorization WHERE authorization_id = ?",
            (authorization_id,),
        ).fetchone()
        if row is None:
            raise DevelopmentApprovalUnavailable("authorization record is absent")
        try:
            bindings = DevelopmentAuthorizationBindings.from_json(json.loads(row[3]))
        except (json.JSONDecodeError, DevelopmentAuthorizationError) as error:
            raise DevelopmentApprovalUnavailable(
                "stored authorization bindings cannot be verified"
            ) from error
        if (
            bindings.content_digest != row[2]
            or bindings.request_digest != row[1]
            or bindings.journal_binding != row[10]
        ):
            raise DevelopmentApprovalUnavailable(
                "stored authorization bindings do not match their durable identity"
            )
        return {
            "approval_act_digest": row[4],
            "authorization_id": authorization_id,
            "bindings": bindings.to_json(),
            "bindings_digest": row[2],
            "environment": row[0],
            "expires_at_utc": _utc_from_timestamp(float(row[8])),
            "independent_multidisciplinary_ratification_claimed": False,
            "issued_at_utc": _utc_from_timestamp(float(row[7])),
            "issuer_github_login": row[5],
            "issuer_github_user_id": int(row[6]),
            "journal_binding": row[10],
            "monetary_ceiling_usd": str(bindings.monetary_ceiling_usd),
            "organization_id_digest": bindings.organization_id_digest,
            "principal_count": 1,
            "project_id_digest": bindings.project_id_digest,
            "request_digest": row[1],
            "stage": bindings.stage,
            "state": row[9],
            "terminal_report_digest": row[11],
        }

    def _finalize(
        self, authorization_id: str, *, report_digest: str, state: str
    ) -> None:
        if not _is_digest(report_digest) or state not in (
            "CONSUMED",
            "STOPPED_UNRECONCILED",
        ):
            raise TypeError("authorization finalization is invalid")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT state, terminal_report_digest FROM authorization "
                "WHERE authorization_id = ?",
                (authorization_id,),
            ).fetchone()
            if row is None:
                raise DevelopmentApprovalUnavailable("authorization record is absent")
            if row[0] == state and row[1] == report_digest:
                self._connection.execute("COMMIT")
                return
            if row[0] != "CLAIMED":
                raise DevelopmentApprovalUnavailable(
                    "only a claimed authorization can become terminal"
                )
            self._connection.execute(
                "UPDATE authorization SET state = ?, terminal_report_digest = ?, "
                "updated_at_utc = ? WHERE authorization_id = ?",
                (
                    state,
                    report_digest,
                    _utc_from_timestamp(time.time()),
                    authorization_id,
                ),
            )
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise


class DevelopmentAuthorizationStore(_AuthorizationStore):
    """Live store; only a freshly authenticated assigned owner may issue."""

    environment = "LIVE_OPENAI_RESPONSES"
    authorization_prefix = "be4-development-"

    def issue(
        self,
        bindings: DevelopmentAuthorizationBindings,
        *,
        approve_exact_request_digest: str,
    ) -> str:
        if approve_exact_request_digest != bindings.request_digest:
            raise DevelopmentAuthorizationError(
                "explicit approval act does not match the execution request"
            )
        owner = GitHubCliCarbonOwnerAuthenticator().authenticate()
        return self._issue(
            bindings,
            issuer_login=owner.login,
            issuer_user_id=owner.user_id,
            authenticated_at_utc=owner.authenticated_at_utc,
        )

    def claim(
        self,
        authorization_id: str,
        *,
        bindings: DevelopmentAuthorizationBindings,
        journal_binding: str,
    ) -> _RealExecutionAdmission:
        self._claim_row(authorization_id, bindings, journal_binding)
        return _RealExecutionAdmission(
            authorization_id,
            bindings,
            journal_binding,
            self,
            _LIVE_ADMISSION_TOKEN,
        )

    def existing_authorization_id(
        self, bindings: DevelopmentAuthorizationBindings
    ) -> str:
        row = self._connection.execute(
            "SELECT authorization_id, bindings_digest FROM authorization "
            "WHERE request_digest = ?",
            (bindings.request_digest,),
        ).fetchone()
        if row is None or row[1] != bindings.content_digest:
            raise DevelopmentApprovalUnavailable(
                "no matching issued development authorization exists"
            )
        return str(row[0])

    def assert_current(
        self,
        admission: _RealExecutionAdmission,
        *,
        project_id_digest: str,
        organization_id_digest: str | None,
    ) -> None:
        if type(admission) is not _RealExecutionAdmission:
            raise DevelopmentApprovalUnavailable("live admission type is invalid")
        self._assert_current(
            authorization_id=admission.authorization_id,
            bindings=admission.bindings,
            journal_binding=admission.journal_binding,
            project_id_digest=project_id_digest,
            organization_id_digest=organization_id_digest,
        )

    def finalize(
        self,
        admission: _RealExecutionAdmission,
        *,
        report_digest: str,
        unresolved: bool,
    ) -> None:
        if type(admission) is not _RealExecutionAdmission:
            raise TypeError("live finalization requires an exact admission")
        self._finalize(
            admission.authorization_id,
            report_digest=report_digest,
            state="STOPPED_UNRECONCILED" if unresolved else "CONSUMED",
        )

    def revoke(self, bindings: DevelopmentAuthorizationBindings) -> None:
        GitHubCliCarbonOwnerAuthenticator().authenticate()
        now = _utc_from_timestamp(time.time())
        with self._connection:
            changed = self._connection.execute(
                "UPDATE authorization SET state = 'REVOKED', updated_at_utc = ? "
                "WHERE request_digest = ? AND bindings_digest = ? "
                "AND state IN ('ISSUED', 'CLAIMED')",
                (now, bindings.request_digest, bindings.content_digest),
            ).rowcount
        if changed != 1:
            raise DevelopmentApprovalUnavailable(
                "no current matching authorization can be revoked"
            )

    def revoke_request_digest(self, request_digest: str) -> None:
        """Revoke the one request even if its journal or provider config is lost."""

        if not _is_digest(request_digest):
            raise TypeError("revocation requires an exact execution request digest")
        GitHubCliCarbonOwnerAuthenticator().authenticate()
        now = _utc_from_timestamp(time.time())
        with self._connection:
            changed = self._connection.execute(
                "UPDATE authorization SET state = 'REVOKED', updated_at_utc = ? "
                "WHERE request_digest = ? AND environment = ? "
                "AND state IN ('ISSUED', 'CLAIMED')",
                (now, request_digest, self.environment),
            ).rowcount
        if changed != 1:
            raise DevelopmentApprovalUnavailable(
                "no current matching authorization can be revoked"
            )


class ControlledDevelopmentAuthorizationStore(_AuthorizationStore):
    """Structurally separate authority for loopback-only transport tests."""

    environment = "CONTROLLED_LOOPBACK_FIXTURE_ONLY"
    authorization_prefix = "fixture-be4-development-"

    def issue_fixture(self, bindings: DevelopmentAuthorizationBindings) -> str:
        return self._issue(
            bindings,
            issuer_login="FIXTURE_TEST_PRINCIPAL",
            issuer_user_id=0,
            authenticated_at_utc="2026-09-09T00:00:00Z",
        )

    def claim_fixture(
        self,
        authorization_id: str,
        *,
        bindings: DevelopmentAuthorizationBindings,
        journal_binding: str,
    ) -> ControlledExecutionAdmission:
        self._claim_row(authorization_id, bindings, journal_binding)
        return ControlledExecutionAdmission(
            authorization_id,
            bindings,
            journal_binding,
            self,
            _FIXTURE_ADMISSION_TOKEN,
        )

    def assert_current(
        self,
        admission: ControlledExecutionAdmission,
        *,
        project_id_digest: str,
        organization_id_digest: str | None,
    ) -> None:
        if type(admission) is not ControlledExecutionAdmission:
            raise DevelopmentApprovalUnavailable("controlled admission type is invalid")
        self._assert_current(
            authorization_id=admission.authorization_id,
            bindings=admission.bindings,
            journal_binding=admission.journal_binding,
            project_id_digest=project_id_digest,
            organization_id_digest=organization_id_digest,
        )

    def finalize_fixture(
        self,
        admission: ControlledExecutionAdmission,
        *,
        report_digest: str,
        unresolved: bool = False,
    ) -> None:
        if type(admission) is not ControlledExecutionAdmission:
            raise TypeError("fixture finalization requires an exact admission")
        self._finalize(
            admission.authorization_id,
            report_digest=report_digest,
            state="STOPPED_UNRECONCILED" if unresolved else "CONSUMED",
        )

    def revoke_fixture(self, authorization_id: str) -> None:
        """Revoke only a controlled fixture authorization."""

        with self._connection:
            changed = self._connection.execute(
                "UPDATE authorization SET state = 'REVOKED', updated_at_utc = ? "
                "WHERE authorization_id = ? AND environment = ? "
                "AND state IN ('ISSUED', 'CLAIMED')",
                (
                    _utc_from_timestamp(time.time()),
                    authorization_id,
                    self.environment,
                ),
            ).rowcount
        if changed != 1:
            raise DevelopmentApprovalUnavailable(
                "controlled authorization cannot be revoked"
            )

    def expire_fixture(self, authorization_id: str) -> None:
        """Move only a controlled fixture expiry into the past."""

        with self._connection:
            changed = self._connection.execute(
                "UPDATE authorization SET expires_at_unix = ? "
                "WHERE authorization_id = ? AND environment = ?",
                (time.time() - 1.0, authorization_id, self.environment),
            ).rowcount
        if changed != 1:
            raise DevelopmentApprovalUnavailable(
                "controlled authorization cannot be expired"
            )


__all__ = (
    "CARBON_OWNER_GITHUB_LOGIN",
    "CARBON_OWNER_GITHUB_USER_ID",
    "DEVELOPMENT_AUTHORIZATION_LIFETIME_SECONDS",
    "DEVELOPMENT_OWNER_ROLES",
    "DEVELOPMENT_RETENTION_SELECTION",
    "ControlledDevelopmentAuthorizationStore",
    "ControlledExecutionAdmission",
    "DevelopmentApprovalUnavailable",
    "DevelopmentAuthenticationError",
    "DevelopmentAuthorizationBindings",
    "DevelopmentAuthorizationError",
    "DevelopmentAuthorizationStore",
    "GitHubCliCarbonOwnerAuthenticator",
    "provider_identity_digest",
)
