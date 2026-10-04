"""Durable pre-dispatch accounting for a bounded cold-plate CFD campaign."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

CAMPAIGN_SCHEMA = "carbon.cold-plate.reference-campaign.v1"
PLAN_SCHEMA = "carbon.cold-plate.decision-reference-plan.v2"
SNAPSHOT_SCHEMA = "carbon.cold-plate.reference-campaign-snapshot.v1"


class CampaignLedgerError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _policy(plan):
    if type(plan) is not dict or plan.get("schema") != PLAN_SCHEMA:
        raise CampaignLedgerError("registered_plan_required")
    campaign = plan.get("campaign")
    if type(campaign) is not dict or campaign.get("schema") != CAMPAIGN_SCHEMA:
        raise CampaignLedgerError("registered_campaign_required")
    required = {
        "schema",
        "campaign_id",
        "study_id",
        "construction_identity_digest",
        "execution_backend",
        "solver_image",
        "ledger_relative_path",
        "initial_execution_limit",
        "retry_execution_limit",
        "total_execution_limit",
        "max_retries_per_case",
        "retry_eligible_statuses",
        "resource_policy",
    }
    if set(campaign) != required:
        raise CampaignLedgerError("campaign_policy_fields")
    if (
        type(campaign["campaign_id"]) is not str
        or type(campaign["construction_identity_digest"]) is not str
        or campaign["execution_backend"] != "DOCKER"
        or type(campaign["solver_image"]) is not str
        or "@sha256:" not in campaign["solver_image"]
        or len(campaign["solver_image"].rsplit("@sha256:", 1)[1]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in campaign["solver_image"].rsplit("@sha256:", 1)[1]
        )
        or type(campaign["ledger_relative_path"]) is not str
        or not campaign["ledger_relative_path"].startswith(".carbon-artifacts/")
        or Path(campaign["ledger_relative_path"]).is_absolute()
        or ".." in Path(campaign["ledger_relative_path"]).parts
        or campaign["max_retries_per_case"] != 1
        or type(campaign["retry_eligible_statuses"]) is not list
        or not campaign["retry_eligible_statuses"]
    ):
        raise CampaignLedgerError("campaign_policy_identity")
    for name in (
        "initial_execution_limit",
        "retry_execution_limit",
        "total_execution_limit",
    ):
        if type(campaign[name]) is not int or campaign[name] <= 0:
            raise CampaignLedgerError("campaign_positive_limit", name)
    if (
        campaign["initial_execution_limit"] + campaign["retry_execution_limit"]
        != campaign["total_execution_limit"]
    ):
        raise CampaignLedgerError("campaign_limit_arithmetic")
    identity = {
        key: value
        for key, value in campaign.items()
        if key not in {"schema", "campaign_id"}
    }
    expected_id = (
        "sha256:" + hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()
    )
    if campaign["campaign_id"] != expected_id:
        raise CampaignLedgerError("campaign_id_mismatch")
    if (
        plan.get("construction_identity_digest")
        != campaign["construction_identity_digest"]
        or type(plan.get("batch")) is not str
        or not plan["batch"]
    ):
        raise CampaignLedgerError("campaign_plan_identity")
    return campaign


class CampaignLedger:
    """SQLite ledger that reserves every attempted solver execution first."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as database:
            database.executescript("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    policy_json TEXT NOT NULL,
                    construction_identity_digest TEXT NOT NULL,
                    created_unix REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS batches (
                    campaign_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    batch TEXT NOT NULL,
                    output_path TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_unix REAL NOT NULL,
                    finished_unix REAL,
                    PRIMARY KEY (campaign_id, attempt),
                    UNIQUE (campaign_id, batch),
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
                );
                CREATE TABLE IF NOT EXISTS executions (
                    campaign_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    output_path TEXT NOT NULL,
                    state TEXT NOT NULL,
                    status TEXT,
                    reserved_unix REAL NOT NULL,
                    finished_unix REAL,
                    PRIMARY KEY (campaign_id, case_id, attempt),
                    FOREIGN KEY (campaign_id, attempt)
                        REFERENCES batches(campaign_id, attempt)
                );
                """)

    def _connect(self):
        database = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA busy_timeout = 30000")
        database.execute("PRAGMA foreign_keys = ON")
        return database

    def reserve(self, plan, output):
        """Atomically reserve a complete registered batch before dispatch."""

        campaign = _policy(plan)
        attempt = plan.get("attempt")
        if attempt not in (1, 2):
            raise CampaignLedgerError("campaign_attempt")
        cases = plan.get("cases")
        if type(cases) is not list:
            raise CampaignLedgerError("campaign_cases")
        case_ids = [case.get("case_id") for case in cases if type(case) is dict]
        if (
            len(case_ids) != len(cases)
            or any(type(case_id) is not str or not case_id for case_id in case_ids)
            or len(case_ids) != len(set(case_ids))
        ):
            raise CampaignLedgerError("campaign_case_ids")
        if attempt == 1 and len(cases) != campaign["initial_execution_limit"]:
            raise CampaignLedgerError("initial_campaign_must_reserve_full_set")
        if attempt == 2 and (
            not cases or len(cases) > campaign["retry_execution_limit"]
        ):
            raise CampaignLedgerError("retry_campaign_limit")
        output_path = str(Path(output).resolve())
        policy_json = _canonical(campaign)
        now = time.time()
        with self._connect() as database:
            try:
                database.execute("BEGIN IMMEDIATE")
                existing = database.execute(
                    "SELECT policy_json FROM campaigns WHERE campaign_id = ?",
                    (campaign["campaign_id"],),
                ).fetchone()
                if existing is None:
                    database.execute(
                        "INSERT INTO campaigns VALUES (?, ?, ?, ?)",
                        (
                            campaign["campaign_id"],
                            policy_json,
                            campaign["construction_identity_digest"],
                            now,
                        ),
                    )
                elif existing["policy_json"] != policy_json:
                    raise CampaignLedgerError("campaign_policy_changed")

                previous_batch = database.execute(
                    "SELECT output_path FROM batches "
                    "WHERE campaign_id = ? AND attempt = ?",
                    (campaign["campaign_id"], attempt),
                ).fetchone()
                if previous_batch is not None:
                    if previous_batch["output_path"] != output_path:
                        raise CampaignLedgerError(
                            "campaign_attempt_bound_to_other_output",
                            previous_batch["output_path"],
                        )
                    raise CampaignLedgerError("campaign_attempt_already_reserved")

                total = database.execute(
                    "SELECT COUNT(*) AS n FROM executions WHERE campaign_id = ?",
                    (campaign["campaign_id"],),
                ).fetchone()["n"]
                if total + len(cases) > campaign["total_execution_limit"]:
                    raise CampaignLedgerError("campaign_total_execution_limit")

                if attempt == 2:
                    initial = database.execute(
                        "SELECT state FROM batches WHERE campaign_id = ? AND attempt = 1",
                        (campaign["campaign_id"],),
                    ).fetchone()
                    if initial is None or initial["state"] != "FINISHED":
                        raise CampaignLedgerError("initial_campaign_not_finished")
                    eligible = set(campaign["retry_eligible_statuses"])
                    for case_id in case_ids:
                        first = database.execute(
                            "SELECT state, status FROM executions "
                            "WHERE campaign_id = ? AND case_id = ? AND attempt = 1",
                            (campaign["campaign_id"], case_id),
                        ).fetchone()
                        if (
                            first is None
                            or first["state"] != "FINISHED"
                            or first["status"] not in eligible
                        ):
                            raise CampaignLedgerError(
                                "case_not_retry_eligible", case_id
                            )

                database.execute(
                    "INSERT INTO batches "
                    "(campaign_id, attempt, batch, output_path, state, started_unix) "
                    "VALUES (?, ?, ?, ?, 'RESERVED', ?)",
                    (
                        campaign["campaign_id"],
                        attempt,
                        plan.get("batch"),
                        output_path,
                        now,
                    ),
                )
                database.executemany(
                    "INSERT INTO executions "
                    "(campaign_id, case_id, attempt, output_path, state, reserved_unix) "
                    "VALUES (?, ?, ?, ?, 'RESERVED', ?)",
                    [
                        (
                            campaign["campaign_id"],
                            case_id,
                            attempt,
                            output_path,
                            now,
                        )
                        for case_id in case_ids
                    ],
                )
                database.commit()
            except Exception:
                database.rollback()
                raise
        return campaign["campaign_id"]

    def finish_execution(self, campaign_id, case_id, attempt, status):
        if type(status) is not str or not status:
            raise CampaignLedgerError("execution_status")
        with self._connect() as database:
            database.execute("BEGIN IMMEDIATE")
            changed = database.execute(
                "UPDATE executions SET state = 'FINISHED', status = ?, "
                "finished_unix = ? WHERE campaign_id = ? AND case_id = ? "
                "AND attempt = ? AND state = 'RESERVED'",
                (status, time.time(), campaign_id, case_id, attempt),
            ).rowcount
            if changed != 1:
                database.rollback()
                raise CampaignLedgerError("execution_not_reserved", case_id)
            database.commit()

    def finish_batch(self, campaign_id, attempt):
        with self._connect() as database:
            database.execute("BEGIN IMMEDIATE")
            unfinished = database.execute(
                "SELECT COUNT(*) AS n FROM executions WHERE campaign_id = ? "
                "AND attempt = ? AND state != 'FINISHED'",
                (campaign_id, attempt),
            ).fetchone()["n"]
            if unfinished:
                database.rollback()
                raise CampaignLedgerError("campaign_batch_has_unfinished_executions")
            changed = database.execute(
                "UPDATE batches SET state = 'FINISHED', finished_unix = ? "
                "WHERE campaign_id = ? AND attempt = ? AND state = 'RESERVED'",
                (time.time(), campaign_id, attempt),
            ).rowcount
            if changed != 1:
                database.rollback()
                raise CampaignLedgerError("campaign_batch_not_reserved")
            database.commit()

    def snapshot(self, campaign_id):
        with self._connect() as database:
            campaign = database.execute(
                "SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
            if campaign is None:
                raise CampaignLedgerError("campaign_not_registered")
            batches = database.execute(
                "SELECT attempt, batch, output_path, state, started_unix, "
                "finished_unix FROM batches WHERE campaign_id = ? ORDER BY attempt",
                (campaign_id,),
            ).fetchall()
            executions = database.execute(
                "SELECT case_id, attempt, output_path, state, status, "
                "reserved_unix, finished_unix FROM executions "
                "WHERE campaign_id = ? ORDER BY attempt, case_id",
                (campaign_id,),
            ).fetchall()
        policy = json.loads(campaign["policy_json"])
        rows = [dict(row) for row in executions]
        return {
            "schema": SNAPSHOT_SCHEMA,
            "campaign_id": campaign_id,
            "construction_identity_digest": campaign["construction_identity_digest"],
            "policy": policy,
            "batches": [dict(row) for row in batches],
            "executions": rows,
            "accounting": {
                "attempted_executions": len(rows),
                "initial_attempts": sum(row["attempt"] == 1 for row in rows),
                "retry_attempts": sum(row["attempt"] == 2 for row in rows),
                "finished_executions": sum(row["state"] == "FINISHED" for row in rows),
            },
        }
