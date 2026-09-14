"""Atomic logical-capacity admission for the C-EA1 private-alpha profile."""

from __future__ import annotations

from dataclasses import dataclass

from .alpha_profile import (
    ALPHA_LOGICAL_QUOTA_BYTES,
    ALPHA_MAX_ACTIVE_EVALUATIONS,
)
from .model import ArchiveCode, ArchiveFailure, content_digest, validate_token
from .storage import PostgresCatalogue

ALPHA_CAPACITY_SCHEMA = "carbon.evidence-archive.alpha-capacity.v1"

ALPHA_CAPACITY_MIGRATION_001 = """
CREATE TABLE IF NOT EXISTS cea1_alpha_capacity_meta (
  singleton smallint PRIMARY KEY CHECK (singleton = 1),
  schema_version text NOT NULL,
  migration_checksum text NOT NULL
);
CREATE TABLE IF NOT EXISTS cea1_alpha_capacity_reservation (
  reservation_id text PRIMARY KEY,
  tenant_id text NOT NULL,
  evaluation_id text NOT NULL UNIQUE,
  declared_bytes bigint NOT NULL CHECK (declared_bytes > 0),
  state text NOT NULL CHECK (state IN ('PENDING', 'RETAINED', 'RELEASED')),
  binding_digest text NOT NULL
);
CREATE INDEX IF NOT EXISTS cea1_alpha_capacity_tenant_state
  ON cea1_alpha_capacity_reservation(tenant_id, state);
CREATE TABLE IF NOT EXISTS cea1_alpha_capacity_event (
  sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  reservation_id text NOT NULL REFERENCES cea1_alpha_capacity_reservation(reservation_id),
  state text NOT NULL CHECK (state IN ('PENDING', 'RETAINED', 'RELEASED')),
  event_digest text NOT NULL
);
""".strip()
ALPHA_CAPACITY_MIGRATION_001_CHECKSUM = content_digest(
    "carbon.evidence-archive.alpha-capacity-migration.v1",
    ALPHA_CAPACITY_MIGRATION_001.encode("utf-8"),
)


@dataclass(frozen=True, slots=True)
class AlphaCapacityReservation:
    reservation_id: str
    tenant_id: str
    evaluation_id: str
    declared_bytes: int
    state: str
    active_evaluations: int
    pending_bytes: int
    retained_bytes: int

    def __post_init__(self) -> None:
        if (
            type(self.reservation_id) is not str
            or not self.reservation_id.startswith("sha256:")
            or len(self.reservation_id) != 71
            or validate_token(self.tenant_id) != self.tenant_id
            or validate_token(self.evaluation_id) != self.evaluation_id
            or type(self.declared_bytes) is not int
            or self.declared_bytes < 1
            or self.state not in {"PENDING", "RETAINED", "RELEASED"}
            or any(
                type(value) is not int or value < 0
                for value in (
                    self.active_evaluations,
                    self.pending_bytes,
                    self.retained_bytes,
                )
            )
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)


def derive_alpha_reservation_id(
    *, tenant_id: str, evaluation_id: str, declared_bytes: int
) -> str:
    tenant_id = validate_token(tenant_id)
    evaluation_id = validate_token(evaluation_id)
    if (
        type(declared_bytes) is not int
        or not 1 <= declared_bytes <= ALPHA_LOGICAL_QUOTA_BYTES
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    return content_digest(
        "carbon.evidence-archive.alpha-reservation.v1",
        f"{tenant_id}\n{evaluation_id}\n{declared_bytes}\n".encode("ascii"),
    )


class PostgresAlphaCapacityLedger:
    """Count retained and pending bytes under one PostgreSQL transaction."""

    def __init__(self, catalogue: PostgresCatalogue, *, tenant_id: str) -> None:
        if type(catalogue) is not PostgresCatalogue:
            raise ArchiveFailure(ArchiveCode.DENIED)
        self.catalogue = catalogue
        self.tenant_id = validate_token(tenant_id)

    def migrate(self) -> None:
        with self.catalogue.transaction() as connection:
            connection.execute(ALPHA_CAPACITY_MIGRATION_001)
            connection.execute(
                "INSERT INTO cea1_alpha_capacity_meta VALUES (1,%s,%s) "
                "ON CONFLICT (singleton) DO NOTHING",
                (ALPHA_CAPACITY_SCHEMA, ALPHA_CAPACITY_MIGRATION_001_CHECKSUM),
            )
        self.verify_schema()

    def verify_schema(self) -> None:
        with self.catalogue.transaction() as connection:
            row = connection.execute(
                "SELECT schema_version,migration_checksum "
                "FROM cea1_alpha_capacity_meta WHERE singleton=1"
            ).fetchone()
            relation = connection.execute(
                "SELECT to_regclass('public.cea1_alpha_capacity_reservation')"
            ).fetchone()
            event_relation = connection.execute(
                "SELECT to_regclass('public.cea1_alpha_capacity_event')"
            ).fetchone()
        if (
            row
            != (
                ALPHA_CAPACITY_SCHEMA,
                ALPHA_CAPACITY_MIGRATION_001_CHECKSUM,
            )
            or relation != ("cea1_alpha_capacity_reservation",)
            or event_relation != ("cea1_alpha_capacity_event",)
        ):
            raise ArchiveFailure(ArchiveCode.STORE)

    @staticmethod
    def _counts(connection, tenant_id: str) -> tuple[int, int, int]:
        row = connection.execute(
            "SELECT "
            "count(*) FILTER (WHERE state='PENDING'),"
            "coalesce(sum(declared_bytes) FILTER (WHERE state='PENDING'),0),"
            "coalesce(sum(declared_bytes) FILTER (WHERE state='RETAINED'),0) "
            "FROM cea1_alpha_capacity_reservation WHERE tenant_id=%s",
            (tenant_id,),
        ).fetchone()
        return tuple(int(value) for value in row)

    def reserve(
        self, *, evaluation_id: str, declared_bytes: int
    ) -> AlphaCapacityReservation:
        evaluation_id = validate_token(evaluation_id)
        reservation_id = derive_alpha_reservation_id(
            tenant_id=self.tenant_id,
            evaluation_id=evaluation_id,
            declared_bytes=declared_bytes,
        )
        binding_digest = content_digest(
            "carbon.evidence-archive.alpha-capacity-binding.v1",
            f"{self.tenant_id}\n{evaluation_id}\n{declared_bytes}\n".encode("ascii"),
        )
        with self.catalogue.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(43454132)")
            old = connection.execute(
                "SELECT reservation_id,declared_bytes,state,binding_digest "
                "FROM cea1_alpha_capacity_reservation WHERE evaluation_id=%s",
                (evaluation_id,),
            ).fetchone()
            if old is not None:
                if old != (
                    reservation_id,
                    declared_bytes,
                    "PENDING",
                    binding_digest,
                ):
                    raise ArchiveFailure(ArchiveCode.CONFLICT)
            else:
                active, pending, retained = self._counts(connection, self.tenant_id)
                if (
                    active + 1 > ALPHA_MAX_ACTIVE_EVALUATIONS
                    or pending + retained + declared_bytes > ALPHA_LOGICAL_QUOTA_BYTES
                ):
                    raise ArchiveFailure(ArchiveCode.CAPACITY)
                connection.execute(
                    "INSERT INTO cea1_alpha_capacity_reservation "
                    "VALUES (%s,%s,%s,%s,'PENDING',%s)",
                    (
                        reservation_id,
                        self.tenant_id,
                        evaluation_id,
                        declared_bytes,
                        binding_digest,
                    ),
                )
                connection.execute(
                    "INSERT INTO cea1_alpha_capacity_event "
                    "(reservation_id,state,event_digest) VALUES (%s,'PENDING',%s)",
                    (
                        reservation_id,
                        content_digest(
                            "carbon.evidence-archive.alpha-capacity-event.v1",
                            f"{reservation_id}\nPENDING\n{binding_digest}\n".encode(
                                "ascii"
                            ),
                        ),
                    ),
                )
            active, pending, retained = self._counts(connection, self.tenant_id)
        return AlphaCapacityReservation(
            reservation_id,
            self.tenant_id,
            evaluation_id,
            declared_bytes,
            "PENDING",
            active,
            pending,
            retained,
        )

    def retain(self, reservation_id: str) -> AlphaCapacityReservation:
        return self._transition(reservation_id, "RETAINED")

    def release_unacknowledged(self, reservation_id: str) -> AlphaCapacityReservation:
        return self._transition(reservation_id, "RELEASED")

    def _transition(self, reservation_id: str, target: str) -> AlphaCapacityReservation:
        if target not in {"RETAINED", "RELEASED"}:
            raise ArchiveFailure(ArchiveCode.INVALID)
        if type(reservation_id) is not str or len(reservation_id) != 71:
            raise ArchiveFailure(ArchiveCode.INVALID)
        with self.catalogue.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(43454132)")
            row = connection.execute(
                "SELECT tenant_id,evaluation_id,declared_bytes,state "
                "FROM cea1_alpha_capacity_reservation WHERE reservation_id=%s",
                (reservation_id,),
            ).fetchone()
            if row is None or row[0] != self.tenant_id:
                raise ArchiveFailure(ArchiveCode.STATE)
            tenant_id, evaluation_id, declared_bytes, state = row
            if state == "PENDING":
                connection.execute(
                    "UPDATE cea1_alpha_capacity_reservation SET state=%s "
                    "WHERE reservation_id=%s AND state='PENDING'",
                    (target, reservation_id),
                )
                state = target
                connection.execute(
                    "INSERT INTO cea1_alpha_capacity_event "
                    "(reservation_id,state,event_digest) VALUES (%s,%s,%s)",
                    (
                        reservation_id,
                        target,
                        content_digest(
                            "carbon.evidence-archive.alpha-capacity-event.v1",
                            f"{reservation_id}\n{target}\n".encode("ascii"),
                        ),
                    ),
                )
            elif state != target:
                raise ArchiveFailure(ArchiveCode.CONFLICT)
            active, pending, retained = self._counts(connection, self.tenant_id)
        return AlphaCapacityReservation(
            reservation_id,
            tenant_id,
            evaluation_id,
            int(declared_bytes),
            state,
            active,
            pending,
            retained,
        )

    def snapshot(self) -> tuple[int, int, int]:
        with self.catalogue.transaction() as connection:
            return self._counts(connection, self.tenant_id)
