"""C-01-owned durable launch association for the C-03 worker."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from carbon.execution.model import QueueClaim
from carbon.reconstruction.worker.model import (
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
    WorkerLaunchState,
    WorkerTiming,
    exact_digest,
    exact_token,
    tagged_sha256,
)

_SCHEMA = "carbon.c01.c03-worker-launch.v1"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, slots=True)
class WorkerLaunchBinding:
    claim: QueueClaim
    replicate_id: str
    replicate_digest: str
    plan_digest: str
    reconstruction_profile_digest: str
    training_data_digest: str
    randomness_digest: str
    stage_digest: str
    worker_profile: DevelopmentWorkerProfile
    image: WorkerImageIdentity
    timing: WorkerTiming
    host_id: str
    container_name: str

    def __post_init__(self) -> None:
        if type(self.claim) is not QueueClaim:
            raise WorkerFailure(WorkerCode.INVALID)
        for name in ("replicate_id", "host_id", "container_name"):
            exact_token(getattr(self, name))
        for name in (
            "replicate_digest",
            "plan_digest",
            "reconstruction_profile_digest",
            "training_data_digest",
            "randomness_digest",
            "stage_digest",
        ):
            exact_digest(getattr(self, name))
        if (
            type(self.worker_profile) is not DevelopmentWorkerProfile
            or type(self.image) is not WorkerImageIdentity
            or type(self.timing) is not WorkerTiming
        ):
            raise WorkerFailure(WorkerCode.INVALID)

    @property
    def execution_id(self) -> str:
        return f"{self.claim.ref.submission_id.value}:{self.claim.ref.attempt_number}"

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "execution_id": self.execution_id,
            "claim_id": self.claim.claim_id,
            "worker_id": self.claim.worker_id,
            "replicate_id": self.replicate_id,
            "replicate_digest": self.replicate_digest,
            "plan_digest": self.plan_digest,
            "reconstruction_profile_digest": self.reconstruction_profile_digest,
            "training_data_digest": self.training_data_digest,
            "randomness_digest": self.randomness_digest,
            "stage_digest": self.stage_digest,
            "worker_profile_digest": self.worker_profile.digest,
            "worker_profile": self.worker_profile.body,
            "image": asdict(self.image),
            "timing": asdict(self.timing),
            "host_id": self.host_id,
            "container_name": self.container_name,
        }

    @property
    def launch_digest(self) -> str:
        return tagged_sha256(_canonical(self.payload).encode("utf-8"))


@dataclass(frozen=True, slots=True)
class WorkerLaunchRecord:
    binding: WorkerLaunchBinding
    launch_digest: str
    state: WorkerLaunchState
    container_id: str | None
    effective_controls_digest: str | None
    output_snapshot_digest: str | None
    terminal_code: str | None


_TRANSITIONS = {
    WorkerLaunchState.INTENT_RECORDED: {
        WorkerLaunchState.CREATING,
        WorkerLaunchState.FAILED_INFRA,
        WorkerLaunchState.RECONCILIATION_REQUIRED,
    },
    WorkerLaunchState.CREATING: {
        WorkerLaunchState.CREATED,
        WorkerLaunchState.FAILED_INFRA,
        WorkerLaunchState.RECONCILIATION_REQUIRED,
    },
    WorkerLaunchState.CREATED: {
        WorkerLaunchState.CONTROLS_VERIFIED,
        WorkerLaunchState.CANCELLED,
        WorkerLaunchState.FAILED_INFRA,
        WorkerLaunchState.RECONCILIATION_REQUIRED,
    },
    WorkerLaunchState.CONTROLS_VERIFIED: {
        WorkerLaunchState.RUNNING,
        WorkerLaunchState.CANCELLED,
        WorkerLaunchState.FAILED_INFRA,
        WorkerLaunchState.RECONCILIATION_REQUIRED,
    },
    WorkerLaunchState.RUNNING: {
        WorkerLaunchState.OUTPUT_SNAPSHOTTED,
        WorkerLaunchState.CANCELLED,
        WorkerLaunchState.FAILED_INFRA,
        WorkerLaunchState.RECONCILIATION_REQUIRED,
    },
    WorkerLaunchState.OUTPUT_SNAPSHOTTED: {
        WorkerLaunchState.TERMINATED,
        WorkerLaunchState.CANCELLED,
        WorkerLaunchState.RECONCILIATION_REQUIRED,
    },
    WorkerLaunchState.TERMINATED: {
        WorkerLaunchState.ASSOCIATED,
        WorkerLaunchState.FAILED_INFRA,
        WorkerLaunchState.RECONCILIATION_REQUIRED,
    },
    WorkerLaunchState.RECONCILIATION_REQUIRED: {
        WorkerLaunchState.CANCELLED,
        WorkerLaunchState.TERMINATED,
        WorkerLaunchState.FAILED_INFRA,
        WorkerLaunchState.QUARANTINED,
    },
    WorkerLaunchState.ASSOCIATED: set(),
    WorkerLaunchState.CANCELLED: set(),
    WorkerLaunchState.FAILED_INFRA: set(),
    WorkerLaunchState.QUARANTINED: set(),
}


class DurableWorkerLaunchStore:
    """Append-visible launch state; exact duplicate intents converge."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(self.path) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA synchronous=FULL")
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS c03_launch_v1 (
                        execution_id TEXT PRIMARY KEY,
                        launch_digest TEXT NOT NULL UNIQUE,
                        binding_json TEXT NOT NULL,
                        state TEXT NOT NULL,
                        container_id TEXT,
                        effective_controls_digest TEXT,
                        output_snapshot_digest TEXT,
                        terminal_code TEXT
                    );
                    CREATE TABLE IF NOT EXISTS c03_launch_event_v1 (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        execution_id TEXT NOT NULL,
                        state TEXT NOT NULL,
                        detail_json TEXT NOT NULL
                    );
                    """
                )
            self.path.chmod(0o600)
        except sqlite3.Error:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None

    def record_intent(self, binding: WorkerLaunchBinding) -> WorkerLaunchRecord:
        if type(binding) is not WorkerLaunchBinding:
            raise WorkerFailure(WorkerCode.INVALID)
        encoded = _canonical(binding.payload)
        try:
            with sqlite3.connect(self.path, isolation_level=None, timeout=5) as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT launch_digest,binding_json,state,container_id,"
                    "effective_controls_digest,output_snapshot_digest,terminal_code "
                    "FROM c03_launch_v1 WHERE execution_id=?",
                    (binding.execution_id,),
                ).fetchone()
                if row is None:
                    db.execute(
                        "INSERT INTO c03_launch_v1 VALUES (?,?,?,?,NULL,NULL,NULL,NULL)",
                        (
                            binding.execution_id,
                            binding.launch_digest,
                            encoded,
                            WorkerLaunchState.INTENT_RECORDED.value,
                        ),
                    )
                    db.execute(
                        "INSERT INTO c03_launch_event_v1(execution_id,state,detail_json) VALUES (?,?,?)",
                        (
                            binding.execution_id,
                            WorkerLaunchState.INTENT_RECORDED.value,
                            _canonical({"launch_digest": binding.launch_digest}),
                        ),
                    )
                    row = (
                        binding.launch_digest,
                        encoded,
                        WorkerLaunchState.INTENT_RECORDED.value,
                        None,
                        None,
                        None,
                        None,
                    )
                elif row[0] != binding.launch_digest or row[1] != encoded:
                    raise WorkerFailure(WorkerCode.CONFLICT)
                db.execute("COMMIT")
        except WorkerFailure:
            raise
        except sqlite3.Error:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        return WorkerLaunchRecord(
            binding,
            row[0],
            WorkerLaunchState(row[2]),
            row[3],
            row[4],
            row[5],
            row[6],
        )

    def transition(
        self,
        binding: WorkerLaunchBinding,
        state: WorkerLaunchState,
        *,
        container_id: str | None = None,
        effective_controls_digest: str | None = None,
        output_snapshot_digest: str | None = None,
        terminal_code: str | None = None,
    ) -> WorkerLaunchRecord:
        if (
            type(binding) is not WorkerLaunchBinding
            or type(state) is not WorkerLaunchState
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        if container_id is not None:
            exact_token(container_id, maximum=128)
        for value in (effective_controls_digest, output_snapshot_digest):
            if value is not None:
                exact_digest(value)
        if terminal_code is not None:
            exact_token(terminal_code)
        try:
            with sqlite3.connect(self.path, isolation_level=None, timeout=5) as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT launch_digest,state,container_id,effective_controls_digest,"
                    "output_snapshot_digest,terminal_code FROM c03_launch_v1 WHERE execution_id=?",
                    (binding.execution_id,),
                ).fetchone()
                if row is None or row[0] != binding.launch_digest:
                    raise WorkerFailure(WorkerCode.CONFLICT)
                current = WorkerLaunchState(row[1])
                values = (
                    container_id if container_id is not None else row[2],
                    effective_controls_digest
                    if effective_controls_digest is not None
                    else row[3],
                    output_snapshot_digest
                    if output_snapshot_digest is not None
                    else row[4],
                    terminal_code if terminal_code is not None else row[5],
                )
                if current is state:
                    if values != row[2:]:
                        raise WorkerFailure(WorkerCode.CONFLICT)
                elif state not in _TRANSITIONS[current]:
                    raise WorkerFailure(WorkerCode.CONFLICT)
                else:
                    db.execute(
                        "UPDATE c03_launch_v1 SET state=?,container_id=?,"
                        "effective_controls_digest=?,output_snapshot_digest=?,terminal_code=? "
                        "WHERE execution_id=? AND state=?",
                        (state.value, *values, binding.execution_id, current.value),
                    )
                    db.execute(
                        "INSERT INTO c03_launch_event_v1(execution_id,state,detail_json) VALUES (?,?,?)",
                        (
                            binding.execution_id,
                            state.value,
                            _canonical(
                                {
                                    "container_id": values[0],
                                    "effective_controls_digest": values[1],
                                    "output_snapshot_digest": values[2],
                                    "terminal_code": values[3],
                                }
                            ),
                        ),
                    )
                db.execute("COMMIT")
        except WorkerFailure:
            raise
        except (sqlite3.Error, ValueError):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        return WorkerLaunchRecord(binding, binding.launch_digest, state, *values)

    def claim_create(self, binding: WorkerLaunchBinding) -> bool:
        """Grant one caller the create effect; concurrent callers do no work."""
        if type(binding) is not WorkerLaunchBinding:
            raise WorkerFailure(WorkerCode.INVALID)
        try:
            with sqlite3.connect(self.path, isolation_level=None, timeout=5) as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT launch_digest,state FROM c03_launch_v1 WHERE execution_id=?",
                    (binding.execution_id,),
                ).fetchone()
                if row is None or row[0] != binding.launch_digest:
                    raise WorkerFailure(WorkerCode.CONFLICT)
                if WorkerLaunchState(row[1]) is not WorkerLaunchState.INTENT_RECORDED:
                    db.execute("COMMIT")
                    return False
                changed = db.execute(
                    "UPDATE c03_launch_v1 SET state=? WHERE execution_id=? AND state=?",
                    (
                        WorkerLaunchState.CREATING.value,
                        binding.execution_id,
                        WorkerLaunchState.INTENT_RECORDED.value,
                    ),
                ).rowcount
                if changed != 1:
                    raise WorkerFailure(WorkerCode.CONFLICT)
                db.execute(
                    "INSERT INTO c03_launch_event_v1(execution_id,state,detail_json) VALUES (?,?,?)",
                    (binding.execution_id, WorkerLaunchState.CREATING.value, "{}"),
                )
                db.execute("COMMIT")
                return True
        except WorkerFailure:
            raise
        except (sqlite3.Error, ValueError):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None

    def raw_status(self, execution_id: str) -> dict[str, object] | None:
        exact_token(execution_id)
        try:
            with sqlite3.connect(self.path) as db:
                row = db.execute(
                    "SELECT launch_digest,state,container_id,effective_controls_digest,"
                    "output_snapshot_digest,terminal_code FROM c03_launch_v1 WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
        except sqlite3.Error:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        if row is None:
            return None
        return {
            "execution_id": execution_id,
            "launch_digest": row[0],
            "state": row[1],
            "container_id": row[2],
            "effective_controls_digest": row[3],
            "output_snapshot_digest": row[4],
            "terminal_code": row[5],
        }

    def binding_payload(self, execution_id: str) -> dict[str, object] | None:
        """Read the exact retained intent for restart/replay comparison."""
        exact_token(execution_id)
        try:
            with sqlite3.connect(self.path) as db:
                row = db.execute(
                    "SELECT binding_json FROM c03_launch_v1 WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
            if row is None:
                return None
            value = json.loads(row[0])
            if type(value) is not dict or value.get("execution_id") != execution_id:
                raise ValueError
            return value
        except (sqlite3.Error, ValueError, TypeError, json.JSONDecodeError):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None

    def reconciliation_targets(self) -> tuple[dict[str, str], ...]:
        """Return only exact names/digests needed for scoped operator cleanup."""
        terminal = {
            WorkerLaunchState.ASSOCIATED.value,
            WorkerLaunchState.CANCELLED.value,
            WorkerLaunchState.FAILED_INFRA.value,
            WorkerLaunchState.QUARANTINED.value,
        }
        try:
            with sqlite3.connect(self.path) as db:
                rows = db.execute(
                    "SELECT execution_id,launch_digest,binding_json,state "
                    "FROM c03_launch_v1 ORDER BY execution_id"
                ).fetchall()
            result = []
            for execution_id, launch_digest, encoded, state in rows:
                if state in terminal:
                    continue
                value = json.loads(encoded)
                if (
                    value.get("execution_id") != execution_id
                    or value.get("container_name") is None
                ):
                    raise ValueError
                result.append(
                    {
                        "execution_id": exact_token(execution_id),
                        "launch_digest": exact_digest(launch_digest),
                        "container_name": exact_token(value["container_name"]),
                        "state": WorkerLaunchState(state).value,
                    }
                )
            return tuple(result)
        except (sqlite3.Error, ValueError, TypeError, json.JSONDecodeError):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None

    def all_statuses(self) -> tuple[dict[str, object], ...]:
        """Return sanitized status for every retained launch, including terminals."""
        try:
            with sqlite3.connect(self.path) as db:
                rows = db.execute(
                    "SELECT execution_id,launch_digest,state,container_id,"
                    "effective_controls_digest,output_snapshot_digest,terminal_code "
                    "FROM c03_launch_v1 ORDER BY execution_id"
                ).fetchall()
            return tuple(
                {
                    "execution_id": exact_token(row[0]),
                    "launch_digest": exact_digest(row[1]),
                    "state": WorkerLaunchState(row[2]).value,
                    "container_id": row[3],
                    "effective_controls_digest": row[4],
                    "output_snapshot_digest": row[5],
                    "terminal_code": row[6],
                }
                for row in rows
            )
        except (sqlite3.Error, ValueError, TypeError):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None

    def record_operator_cleanup(
        self, *, execution_id: str, launch_digest: str, cleaned: bool
    ) -> WorkerLaunchState:
        """Close one exact uncertain launch or quarantine its slot."""
        exact_token(execution_id)
        exact_digest(launch_digest)
        if type(cleaned) is not bool:
            raise WorkerFailure(WorkerCode.INVALID)
        target = (
            WorkerLaunchState.CANCELLED if cleaned else WorkerLaunchState.QUARANTINED
        )
        try:
            with sqlite3.connect(self.path, isolation_level=None, timeout=5) as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT launch_digest,state FROM c03_launch_v1 WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                if row is None or row[0] != launch_digest:
                    raise WorkerFailure(WorkerCode.CONFLICT)
                current = WorkerLaunchState(row[1])
                if current in {
                    WorkerLaunchState.ASSOCIATED,
                    WorkerLaunchState.CANCELLED,
                    WorkerLaunchState.FAILED_INFRA,
                }:
                    db.execute("COMMIT")
                    return current
                db.execute(
                    "UPDATE c03_launch_v1 SET state=?,terminal_code=? WHERE execution_id=?",
                    (
                        target.value,
                        (
                            "reconstruction.worker.operator.cleaned"
                            if cleaned
                            else WorkerCode.CLEANUP.value
                        ),
                        execution_id,
                    ),
                )
                db.execute(
                    "INSERT INTO c03_launch_event_v1(execution_id,state,detail_json) VALUES (?,?,?)",
                    (
                        execution_id,
                        target.value,
                        _canonical({"operator_cleanup_confirmed": cleaned}),
                    ),
                )
                db.execute("COMMIT")
                return target
        except WorkerFailure:
            raise
        except (sqlite3.Error, ValueError):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None


__all__ = [
    "DurableWorkerLaunchStore",
    "WorkerLaunchBinding",
    "WorkerLaunchRecord",
]
