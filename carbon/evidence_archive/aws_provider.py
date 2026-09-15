"""AWS provider adapters for the unprovisioned C-EA1 private-alpha package.

The module contains no default credentials, account, region, or network action.
Clients are injected so the same closed behavior can be tested against local
non-secret fakes before an operator supplies an authorized AWS session.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .model import ArchiveCode, ArchiveFailure, content_digest, validate_token
from .storage import KeyMaterial, validate_object_key

AWS_PROVIDER_SCHEMA = "carbon.evidence-archive.aws-provider.v2"
AWS_PROVIDER_PROFILE_ID_V1 = "carbon.alpha-evidence-archive.aws.private.v1"
AWS_PROVIDER_PROFILE_ID = "carbon.alpha-evidence-archive.aws.private.v2"
AWS_MAX_OBJECT_BYTES = 128 * 1024 * 1024
AWS_MAX_LISTED_OBJECTS = 8192

_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
_ACCOUNT = re.compile(r"[0-9]{12}")
_KMS_ARN = re.compile(r"arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[0-9a-fA-F-]{36}")
_RDS_HOST = re.compile(r"[a-z0-9][a-z0-9.-]{1,251}[a-z0-9]")


def _bounded_text(value: object, *, maximum: int = 256) -> str:
    if type(value) is not str:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return validate_token(value, maximum=maximum)


def _bounded_ascii(value: object, *, maximum: int = 256) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= maximum
        or not value.isascii()
        or any(character.isspace() or ord(character) < 33 for character in value)
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    return value


def _bounded_provider_id(value: object, *, maximum_bytes: int = 1024) -> str:
    if (
        type(value) is not str
        or not value
        or any(
            character.isspace() or not character.isprintable() for character in value
        )
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise ArchiveFailure(ArchiveCode.INVALID) from None
    if len(encoded) > maximum_bytes:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return value


def _error_code(error: BaseException) -> str | None:
    response = getattr(error, "response", None)
    if type(response) is not dict:
        return None
    detail = response.get("Error")
    if type(detail) is not dict or type(detail.get("Code")) is not str:
        return None
    return detail["Code"]


def _retention_epoch(response: object) -> int:
    retention = response.get("Retention") if type(response) is dict else None
    value = retention.get("RetainUntilDate") if type(retention) is dict else None
    mode = retention.get("Mode") if type(retention) is dict else None
    if mode != "COMPLIANCE" or not isinstance(value, datetime):
        raise ArchiveFailure(ArchiveCode.INTEGRITY)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp())


def _legal_hold(response: object) -> bool:
    hold = response.get("LegalHold") if type(response) is dict else None
    status = hold.get("Status") if type(hold) is dict else None
    if status not in {"ON", "OFF"}:
        raise ArchiveFailure(ArchiveCode.INTEGRITY)
    return status == "ON"


@dataclass(frozen=True, slots=True)
class AwsArchiveConfiguration:
    region: str
    bucket: str
    expected_bucket_owner: str
    storage_kms_key_arn: str
    envelope_kms_key_arn: str
    tenant_id: str
    prefix: str = "carbon-alpha-v1"
    max_object_bytes: int = AWS_MAX_OBJECT_BYTES
    max_listed_objects: int = AWS_MAX_LISTED_OBJECTS

    def __post_init__(self) -> None:
        region = _bounded_text(self.region, maximum=32)
        bucket = _bounded_text(self.bucket, maximum=63)
        owner = _bounded_text(self.expected_bucket_owner, maximum=12)
        storage_kms = _bounded_ascii(self.storage_kms_key_arn, maximum=256)
        envelope_kms = _bounded_ascii(self.envelope_kms_key_arn, maximum=256)
        tenant = validate_token(self.tenant_id)
        prefix = validate_token(self.prefix, maximum=64)
        if (
            _BUCKET.fullmatch(bucket) is None
            or ".." in bucket
            or _ACCOUNT.fullmatch(owner) is None
            or _KMS_ARN.fullmatch(storage_kms) is None
            or _KMS_ARN.fullmatch(envelope_kms) is None
            or storage_kms == envelope_kms
            or any(
                kms.split(":")[3] != region or kms.split(":")[4] != owner
                for kms in (storage_kms, envelope_kms)
            )
            or type(self.max_object_bytes) is not int
            or not 1 <= self.max_object_bytes <= AWS_MAX_OBJECT_BYTES
            or type(self.max_listed_objects) is not int
            or not 1 <= self.max_listed_objects <= AWS_MAX_LISTED_OBJECTS
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)
        object.__setattr__(self, "region", region)
        object.__setattr__(self, "bucket", bucket)
        object.__setattr__(self, "expected_bucket_owner", owner)
        object.__setattr__(self, "storage_kms_key_arn", storage_kms)
        object.__setattr__(self, "envelope_kms_key_arn", envelope_kms)
        object.__setattr__(self, "tenant_id", tenant)
        object.__setattr__(self, "prefix", prefix)

    @property
    def identity(self) -> str:
        document = (
            f"{AWS_PROVIDER_SCHEMA}\n{self.region}\n{self.bucket}\n"
            f"{self.expected_bucket_owner}\n{self.storage_kms_key_arn}\n"
            f"{self.envelope_kms_key_arn}\n"
            f"{self.tenant_id}\n{self.prefix}\n{self.max_object_bytes}\n"
            f"{self.max_listed_objects}\n"
        ).encode("ascii")
        return content_digest(AWS_PROVIDER_SCHEMA, document)


@dataclass(frozen=True, slots=True)
class AwsRdsIamConfiguration:
    region: str
    hostname: str
    port: int
    database: str
    username: str

    def __post_init__(self) -> None:
        region = _bounded_text(self.region, maximum=32)
        hostname = _bounded_text(self.hostname, maximum=253)
        database = validate_token(self.database, maximum=63)
        username = validate_token(self.username, maximum=63)
        if (
            _RDS_HOST.fullmatch(hostname) is None
            or type(self.port) is not int
            or not 1 <= self.port <= 65535
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)
        object.__setattr__(self, "region", region)
        object.__setattr__(self, "hostname", hostname)
        object.__setattr__(self, "database", database)
        object.__setattr__(self, "username", username)


class AwsRdsIamConnectionFactory:
    """Open TLS PostgreSQL connections using fresh, non-persisted IAM tokens."""

    def __init__(self, rds_client: Any, configuration: AwsRdsIamConfiguration) -> None:
        self.rds_client = rds_client
        self.configuration = configuration

    def __call__(self) -> Any:
        try:
            token = self.rds_client.generate_db_auth_token(
                DBHostname=self.configuration.hostname,
                Port=self.configuration.port,
                DBUsername=self.configuration.username,
                Region=self.configuration.region,
            )
            if type(token) is not str or not token:
                raise ValueError
            import psycopg

            return psycopg.connect(
                host=self.configuration.hostname,
                port=self.configuration.port,
                dbname=self.configuration.database,
                user=self.configuration.username,
                password=token,
                sslmode="verify-full",
                connect_timeout=5,
            )
        except Exception:  # noqa: BLE001 - token/provider details stay private.
            raise ArchiveFailure(ArchiveCode.STORE) from None


@dataclass(frozen=True, slots=True, repr=False)
class AwsDataKeyLease:
    key: KeyMaterial
    encrypted_key: bytes
    kms_key_arn: str
    encryption_context: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if (
            type(self.key) is not KeyMaterial
            or type(self.encrypted_key) is not bytes
            or not self.encrypted_key
            or len(self.encrypted_key) > 8192
            or _KMS_ARN.fullmatch(self.kms_key_arn) is None
            or type(self.encryption_context) is not tuple
            or not self.encryption_context
            or any(
                type(item) is not tuple
                or len(item) != 2
                or type(item[0]) is not str
                or type(item[1]) is not str
                for item in self.encryption_context
            )
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    @property
    def wrapped_key_digest(self) -> str:
        return content_digest(
            "carbon.evidence-archive.aws-wrapped-key.v1", self.encrypted_key
        )


@dataclass(frozen=True, slots=True)
class AwsObjectWriteReceipt:
    object_key: str
    version_id: str
    checksum_sha256: str
    created: bool

    def __post_init__(self) -> None:
        if (
            type(self.object_key) is not str
            or not self.object_key
            or _bounded_provider_id(self.version_id) != self.version_id
            or type(self.checksum_sha256) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", self.checksum_sha256) is None
            or type(self.created) is not bool
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)


@dataclass(frozen=True, slots=True)
class AwsRetentionReceipt:
    object_key: str
    version_id: str
    retain_until_epoch_seconds: int
    obligation_hold: bool

    def __post_init__(self) -> None:
        if (
            type(self.object_key) is not str
            or not self.object_key
            or _bounded_provider_id(self.version_id) != self.version_id
            or type(self.retain_until_epoch_seconds) is not int
            or self.retain_until_epoch_seconds < 0
            or type(self.obligation_hold) is not bool
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)


def _kms_context(*, tenant_id: str, archive_entry_id: str) -> dict[str, str]:
    return {
        "carbon:profile": AWS_PROVIDER_PROFILE_ID,
        "carbon:tenant": validate_token(tenant_id),
        "carbon:entry": _bounded_text(archive_entry_id, maximum=80),
    }


class AwsKmsDataKeyService:
    """Generate and recover per-entry AES-256 keys under one exact KMS key."""

    def __init__(self, client: Any, configuration: AwsArchiveConfiguration) -> None:
        self.client = client
        self.configuration = configuration

    def generate(self, *, archive_entry_id: str) -> AwsDataKeyLease:
        context = _kms_context(
            tenant_id=self.configuration.tenant_id,
            archive_entry_id=archive_entry_id,
        )
        try:
            response = self.client.generate_data_key(
                KeyId=self.configuration.envelope_kms_key_arn,
                KeySpec="AES_256",
                EncryptionContext=context,
            )
        except Exception:  # noqa: BLE001 - provider details remain private.
            raise ArchiveFailure(ArchiveCode.KEY_UNAVAILABLE) from None
        plaintext = response.get("Plaintext") if type(response) is dict else None
        wrapped = response.get("CiphertextBlob") if type(response) is dict else None
        key_id = response.get("KeyId") if type(response) is dict else None
        if (
            type(plaintext) is not bytes
            or len(plaintext) != 32
            or type(wrapped) is not bytes
            or not wrapped
            or key_id != self.configuration.envelope_kms_key_arn
        ):
            raise ArchiveFailure(ArchiveCode.INTEGRITY)
        key_ref = "aws-kms-" + hashlib.sha256(wrapped).hexdigest()
        return AwsDataKeyLease(
            KeyMaterial(key_ref, plaintext),
            wrapped,
            key_id,
            tuple(sorted(context.items())),
        )

    def recover(self, *, archive_entry_id: str, encrypted_key: bytes) -> KeyMaterial:
        if type(encrypted_key) is not bytes or not 1 <= len(encrypted_key) <= 8192:
            raise ArchiveFailure(ArchiveCode.INVALID)
        context = _kms_context(
            tenant_id=self.configuration.tenant_id,
            archive_entry_id=archive_entry_id,
        )
        try:
            response = self.client.decrypt(
                CiphertextBlob=encrypted_key,
                EncryptionContext=context,
                KeyId=self.configuration.envelope_kms_key_arn,
            )
        except Exception:  # noqa: BLE001
            raise ArchiveFailure(ArchiveCode.KEY_UNAVAILABLE) from None
        plaintext = response.get("Plaintext") if type(response) is dict else None
        key_id = response.get("KeyId") if type(response) is dict else None
        if (
            type(plaintext) is not bytes
            or len(plaintext) != 32
            or key_id != self.configuration.envelope_kms_key_arn
        ):
            raise ArchiveFailure(ArchiveCode.INTEGRITY)
        return KeyMaterial(
            "aws-kms-" + hashlib.sha256(encrypted_key).hexdigest(), plaintext
        )


class S3ImmutableObjectStore:
    """Bounded, tenant-scoped S3 implementation of the archive object protocol."""

    def __init__(self, client: Any, configuration: AwsArchiveConfiguration) -> None:
        self.client = client
        self.configuration = configuration
        self.tenant_id = configuration.tenant_id

    def _provider_key(self, object_key: str) -> str:
        validate_object_key(object_key, self.tenant_id)
        return f"{self.configuration.prefix}/{object_key}"

    def _read(self, response: object) -> bytes:
        if type(response) is not dict:
            raise ArchiveFailure(ArchiveCode.INTEGRITY)
        length = response.get("ContentLength")
        body = response.get("Body")
        if (
            type(length) is not int
            or not 1 <= length <= self.configuration.max_object_bytes
            or not hasattr(body, "read")
        ):
            raise ArchiveFailure(ArchiveCode.CAPACITY)
        try:
            payload = body.read(self.configuration.max_object_bytes + 1)
        except Exception:  # noqa: BLE001
            raise ArchiveFailure(ArchiveCode.STORE) from None
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()
        if type(payload) is not bytes or len(payload) != length:
            raise ArchiveFailure(ArchiveCode.INTEGRITY)
        return payload

    def get(self, object_key: str) -> bytes:
        try:
            response = self.client.get_object(
                Bucket=self.configuration.bucket,
                Key=self._provider_key(object_key),
                ExpectedBucketOwner=self.configuration.expected_bucket_owner,
            )
        except Exception:  # noqa: BLE001
            raise ArchiveFailure(ArchiveCode.STORE) from None
        return self._read(response)

    def get_version(self, object_key: str, version_id: str) -> bytes:
        version_id = _bounded_provider_id(version_id)
        try:
            response = self.client.get_object(
                Bucket=self.configuration.bucket,
                Key=self._provider_key(object_key),
                VersionId=version_id,
                ExpectedBucketOwner=self.configuration.expected_bucket_owner,
            )
        except Exception:  # noqa: BLE001
            raise ArchiveFailure(ArchiveCode.STORE) from None
        return self._read(response)

    def put_immutable(self, object_key: str, body: bytes) -> bool:
        return self.put_immutable_with_receipt(object_key, body).created

    def put_immutable_with_receipt(
        self, object_key: str, body: bytes
    ) -> AwsObjectWriteReceipt:
        if (
            type(body) is not bytes
            or not 1 <= len(body) <= self.configuration.max_object_bytes
        ):
            raise ArchiveFailure(ArchiveCode.CAPACITY)
        key = self._provider_key(object_key)
        checksum = base64.b64encode(hashlib.sha256(body).digest()).decode("ascii")
        try:
            response = self.client.put_object(
                Bucket=self.configuration.bucket,
                Key=key,
                Body=body,
                ContentLength=len(body),
                ChecksumSHA256=checksum,
                ExpectedBucketOwner=self.configuration.expected_bucket_owner,
                IfNoneMatch="*",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=self.configuration.storage_kms_key_arn,
                BucketKeyEnabled=True,
            )
            version_id = response.get("VersionId") if type(response) is dict else None
            observed_checksum = (
                response.get("ChecksumSHA256") if type(response) is dict else None
            )
            if (
                type(version_id) is not str
                or not version_id
                or observed_checksum != checksum
            ):
                raise ArchiveFailure(ArchiveCode.INTEGRITY)
            return AwsObjectWriteReceipt(
                object_key,
                version_id,
                "sha256:" + hashlib.sha256(body).hexdigest(),
                True,
            )
        except Exception as error:
            if type(error) is ArchiveFailure:
                raise
            if _error_code(error) not in {"PreconditionFailed", "412"}:
                raise ArchiveFailure(ArchiveCode.STORE) from None
        existing = self.get(object_key)
        if existing != body:
            raise ArchiveFailure(ArchiveCode.CONFLICT)
        try:
            response = self.client.head_object(
                Bucket=self.configuration.bucket,
                Key=key,
                ChecksumMode="ENABLED",
                ExpectedBucketOwner=self.configuration.expected_bucket_owner,
            )
        except Exception:  # noqa: BLE001
            raise ArchiveFailure(ArchiveCode.STORE) from None
        version_id = response.get("VersionId") if type(response) is dict else None
        observed_checksum = (
            response.get("ChecksumSHA256") if type(response) is dict else None
        )
        if (
            type(version_id) is not str
            or not version_id
            or observed_checksum != checksum
        ):
            raise ArchiveFailure(ArchiveCode.INTEGRITY)
        return AwsObjectWriteReceipt(
            object_key,
            version_id,
            "sha256:" + hashlib.sha256(body).hexdigest(),
            False,
        )

    def apply_version_retention(
        self,
        object_key: str,
        version_id: str,
        *,
        retain_until_epoch_seconds: int,
        obligation_hold: bool,
    ) -> AwsRetentionReceipt:
        """Extend one exact object version and bind any open-obligation hold.

        Compliance retention is never shortened.  An obligation hold is enabled
        before retention changes and is released only after the required
        last-use deadline has been verified on the exact version.
        """

        key = self._provider_key(object_key)
        version_id = _bounded_provider_id(version_id)
        if (
            type(retain_until_epoch_seconds) is not int
            or retain_until_epoch_seconds < 0
            or type(obligation_hold) is not bool
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)
        try:
            observed_retention = self.client.get_object_retention(
                Bucket=self.configuration.bucket,
                Key=key,
                VersionId=version_id,
                ExpectedBucketOwner=self.configuration.expected_bucket_owner,
            )
            observed_hold = self.client.get_object_legal_hold(
                Bucket=self.configuration.bucket,
                Key=key,
                VersionId=version_id,
                ExpectedBucketOwner=self.configuration.expected_bucket_owner,
            )
        except Exception:  # noqa: BLE001
            raise ArchiveFailure(ArchiveCode.STORE) from None
        current = _retention_epoch(observed_retention)
        current_hold = _legal_hold(observed_hold)
        target = max(current, retain_until_epoch_seconds)
        try:
            if obligation_hold and not current_hold:
                self.client.put_object_legal_hold(
                    Bucket=self.configuration.bucket,
                    Key=key,
                    VersionId=version_id,
                    LegalHold={"Status": "ON"},
                    ExpectedBucketOwner=self.configuration.expected_bucket_owner,
                )
            if target > current:
                self.client.put_object_retention(
                    Bucket=self.configuration.bucket,
                    Key=key,
                    VersionId=version_id,
                    Retention={
                        "Mode": "COMPLIANCE",
                        "RetainUntilDate": datetime.fromtimestamp(target, UTC),
                    },
                    ExpectedBucketOwner=self.configuration.expected_bucket_owner,
                )
            verified_retention = self.client.get_object_retention(
                Bucket=self.configuration.bucket,
                Key=key,
                VersionId=version_id,
                ExpectedBucketOwner=self.configuration.expected_bucket_owner,
            )
            if _retention_epoch(verified_retention) < target:
                raise ArchiveFailure(ArchiveCode.INTEGRITY)
            if not obligation_hold and current_hold:
                self.client.put_object_legal_hold(
                    Bucket=self.configuration.bucket,
                    Key=key,
                    VersionId=version_id,
                    LegalHold={"Status": "OFF"},
                    ExpectedBucketOwner=self.configuration.expected_bucket_owner,
                )
            verified_hold = self.client.get_object_legal_hold(
                Bucket=self.configuration.bucket,
                Key=key,
                VersionId=version_id,
                ExpectedBucketOwner=self.configuration.expected_bucket_owner,
            )
        except ArchiveFailure:
            raise
        except Exception:  # noqa: BLE001
            raise ArchiveFailure(ArchiveCode.STORE) from None
        if _legal_hold(verified_hold) is not obligation_hold:
            raise ArchiveFailure(ArchiveCode.INTEGRITY)
        return AwsRetentionReceipt(object_key, version_id, target, obligation_hold)

    def list_keys(self, tenant_id: str) -> tuple[str, ...]:
        if validate_token(tenant_id) != self.tenant_id:
            raise ArchiveFailure(ArchiveCode.DENIED)
        prefix = f"{self.configuration.prefix}/v1/{self.tenant_id}/"
        continuation: str | None = None
        values: list[str] = []
        while True:
            request: dict[str, object] = {
                "Bucket": self.configuration.bucket,
                "Prefix": prefix,
                "MaxKeys": min(1000, self.configuration.max_listed_objects + 1),
                "ExpectedBucketOwner": self.configuration.expected_bucket_owner,
            }
            if continuation is not None:
                request["ContinuationToken"] = continuation
            try:
                response = self.client.list_objects_v2(**request)
            except Exception:  # noqa: BLE001
                raise ArchiveFailure(ArchiveCode.STORE) from None
            if (
                type(response) is not dict
                or type(response.get("Contents", [])) is not list
            ):
                raise ArchiveFailure(ArchiveCode.INTEGRITY)
            for item in response.get("Contents", []):
                if type(item) is not dict or type(item.get("Key")) is not str:
                    raise ArchiveFailure(ArchiveCode.INTEGRITY)
                provider_key = item["Key"]
                if not provider_key.startswith(f"{self.configuration.prefix}/"):
                    raise ArchiveFailure(ArchiveCode.INTEGRITY)
                value = provider_key[len(self.configuration.prefix) + 1 :]
                values.append(validate_object_key(value, self.tenant_id))
                if len(values) > self.configuration.max_listed_objects:
                    raise ArchiveFailure(ArchiveCode.CAPACITY)
            if response.get("IsTruncated") is not True:
                break
            continuation = response.get("NextContinuationToken")
            if type(continuation) is not str or not continuation:
                raise ArchiveFailure(ArchiveCode.INTEGRITY)
        return tuple(sorted(values))

    def quarantine(self, object_key: str) -> str:
        provider_key = self._provider_key(object_key)
        quarantine_ref = content_digest(
            "carbon.evidence-archive.aws-quarantine.v1", provider_key.encode("ascii")
        )
        try:
            self.client.put_object_tagging(
                Bucket=self.configuration.bucket,
                Key=provider_key,
                ExpectedBucketOwner=self.configuration.expected_bucket_owner,
                Tagging={
                    "TagSet": [
                        {"Key": "carbon-quarantine", "Value": "true"},
                        {"Key": "carbon-quarantine-ref", "Value": quarantine_ref[7:]},
                    ]
                },
            )
        except Exception:  # noqa: BLE001
            raise ArchiveFailure(ArchiveCode.STORE) from None
        return quarantine_ref


def create_aws_clients(*, region: str) -> tuple[Any, Any, Any]:
    """Construct credential-chain clients only when an operator calls it."""

    region = _bounded_text(region, maximum=32)
    try:
        import boto3

        session = boto3.Session(region_name=region)
        return session.client("s3"), session.client("kms"), session.client("rds")
    except Exception:  # noqa: BLE001
        raise ArchiveFailure(ArchiveCode.STORE) from None
