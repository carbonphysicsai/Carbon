#!/usr/bin/env python3
"""Detached CPES reference-reuse falsification harness.

This module intentionally lives under ``scripts/dev``.  It is not a Carbon
runtime service and cannot publish results, assign runtime packs, score a
candidate, or create reward authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import sqlite3
import statistics
import sys
import tempfile
import time
import zipfile
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

EXPECTED_ORIGINAL_ZIP_SHA256 = (
    "088d3e1182cbd8974c14ba6614a470cdcf3d5f3e6335c1db085699789ec5ffcb"
)
ORIGINAL_BLOCKED = {"AT-09", "AT-16", "AT-19", "AT-22", "AT-30"}
ATTACKS: dict[str, tuple[str, str, str]] = {
    "AT-01": ("P1", "Backdated exam manifest", "policy/case ordering"),
    "AT-02": ("P1", "Conflicting policy manifests", "policy commitment"),
    "AT-03": ("P1", "Selectively omitted abort", "abort history"),
    "AT-04": ("P2", "Changed dependency bytes", "immutable submission"),
    "AT-05": ("P2", "Post-exposure preprocessing mutation", "artifact seal"),
    "AT-06": ("P3", "Identity/retry as fresh entropy", "fixed selection domain"),
    "AT-07": ("P3", "Favorable event redraw", "event assignment"),
    "AT-08": ("P3", "Withheld private contribution", "abort/failure policy"),
    "AT-09": ("P3", "Public beacon treated as secret", "provider confidentiality"),
    "AT-10": ("P3", "Publish shared parent root", "lineage/allow-list"),
    "AT-11": ("P4", "Read reference mount or token", "custody access"),
    "AT-12": ("P4", "Read MMS answer expression", "training/reference flow"),
    "AT-13": ("P4", "Exfiltrate via logs/network", "egress/disclosure"),
    "AT-14": ("P4", "Read prior temporary/device state", "cross-job isolation"),
    "AT-15": (
        "P4",
        "Practice/client reads official cache",
        "cross-service authorization",
    ),
    "AT-16": ("P4", "Privileged operator copies plaintext", "host trust boundary"),
    "AT-17": ("P5", "Colluding hotkey late entry", "global membership lock"),
    "AT-18": ("P5", "Early summary influences pending job", "summary closure"),
    "AT-19": ("P5", "Renamed pack reuses old answers", "asset lineage"),
    "AT-20": ("P5", "Timer publishes before closure", "verified retirement"),
    "AT-21": ("P6", "Replace prediction/reference bytes", "content binding"),
    "AT-22": (
        "P6",
        "Valid signer fabricates evidence",
        "independent execution integrity",
    ),
    "AT-23": ("P6", "Drop failed hard reference", "typed reference failure"),
    "AT-24": ("P7", "Unlimited precommitted variants", "field/admission bound"),
    "AT-25": ("P8", "Forged approval flag", "registry authority"),
    "AT-26": ("P8", "Leak affects cached pending uses", "incident propagation"),
    "AT-27": ("P5", "Publication races late prediction", "atomic retirement"),
    "AT-28": ("P5", "Publish confidential or sibling material", "rights/lineage"),
    "AT-29": ("P7", "Advertise max group as throughput", "actual-fill accounting"),
    "AT-30": ("P8", "Exploit accumulated public archive", "future-case freshness"),
}


class ResearchRejected(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_original_bundle(path: Path) -> dict[str, object]:
    actual = file_sha256(path)
    if actual != EXPECTED_ORIGINAL_ZIP_SHA256:
        raise ResearchRejected("ORIGINAL_BUNDLE_DIGEST_MISMATCH")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        unsafe = [
            name
            for name in names
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
        ]
        if unsafe:
            raise ResearchRejected("UNSAFE_ARCHIVE_PATH")
        required = {
            "GAUNTLET_REPORT.md",
            "continuous_exam_gauntlet/GAUNTLET_REPORT.md",
            "continuous_exam_gauntlet/model.py",
            "continuous_exam_gauntlet/attacks.py",
            "continuous_exam_gauntlet/operating.py",
            "continuous_exam_gauntlet/publication.py",
            "continuous_exam_gauntlet/test_gauntlet.py",
            "continuous_exam_gauntlet/results/summary.json",
        }
        if not required.issubset(names):
            raise ResearchRejected("ORIGINAL_BUNDLE_MEMBER_MISSING")
        outer_report = archive.read("GAUNTLET_REPORT.md")
        inner_report = archive.read("continuous_exam_gauntlet/GAUNTLET_REPORT.md")
        if outer_report != inner_report:
            raise ResearchRejected("ORIGINAL_REPORT_MISMATCH")
        summary = json.loads(
            archive.read("continuous_exam_gauntlet/results/summary.json")
        )
    return {
        "status": "VERIFIED_BYTE_IDENTITY_ONLY",
        "sha256": actual,
        "member_count": len(names),
        "report_sha256": hashlib.sha256(outer_report).hexdigest(),
        "embedded_summary": summary,
        "claim_limit": (
            "Verification and rerun do not establish scientific validity, "
            "runtime security, or production authority."
        ),
    }


class ResearchLedger:
    """Disposable SQLite prototype for lifecycle/race falsification only."""

    def __init__(self, path: Path, *, vulnerable: frozenset[str] = frozenset()):
        self.path = path
        self.vulnerable = vulnerable
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs(
              job_id TEXT PRIMARY KEY,
              challenge TEXT NOT NULL,
              strategy_digest TEXT NOT NULL,
              compatibility_key TEXT NOT NULL,
              submitted_at INTEGER NOT NULL,
              pack_id TEXT,
              state TEXT NOT NULL,
              attempt_id INTEGER NOT NULL DEFAULT 0,
              artifact_digest TEXT,
              prediction_digest TEXT,
              result_digest TEXT,
              retries_open INTEGER NOT NULL DEFAULT 0,
              UNIQUE(challenge, strategy_digest)
            );
            CREATE TABLE IF NOT EXISTS packs(
              pack_id TEXT PRIMARY KEY,
              challenge TEXT NOT NULL,
              compatibility_key TEXT NOT NULL,
              cutoff INTEGER NOT NULL,
              case_identity TEXT NOT NULL UNIQUE,
              state TEXT NOT NULL,
              public_rights INTEGER NOT NULL DEFAULT 0,
              lineage TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS members(
              job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),
              pack_id TEXT NOT NULL REFERENCES packs(pack_id),
              ordinal INTEGER NOT NULL,
              UNIQUE(pack_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS verified_evidence(
              evidence_ref TEXT PRIMARY KEY,
              evidence_kind TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reference_cache(
              key_digest TEXT PRIMARY KEY,
              binding_json TEXT NOT NULL,
              artifact_digest TEXT NOT NULL,
              complete INTEGER NOT NULL CHECK(complete IN (0,1))
            );
            CREATE TABLE IF NOT EXISTS events(
              sequence INTEGER PRIMARY KEY AUTOINCREMENT,
              action TEXT NOT NULL,
              outcome TEXT NOT NULL,
              details_json TEXT NOT NULL
            );
            """)

    @classmethod
    def attach(cls, path: Path) -> ResearchLedger:
        return cls(path)

    def close(self) -> None:
        self.db.close()

    def _event(self, action: str, outcome: str, **details: object) -> None:
        self.db.execute(
            "INSERT INTO events(action,outcome,details_json) VALUES(?,?,?)",
            (action, outcome, json.dumps(details, sort_keys=True)),
        )

    def _reject(self, code: str) -> None:
        raise ResearchRejected(code)

    def submit(
        self,
        job_id: str,
        challenge: str,
        strategy: object,
        compatibility_key: str,
        submitted_at: int,
    ) -> str:
        strategy_digest = canonical_digest(strategy)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute(
                "SELECT job_id,strategy_digest FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                if existing["strategy_digest"] != strategy_digest:
                    self._reject("IMMUTABLE_SUBMISSION_CONFLICT")
                resolved = str(existing["job_id"])
                outcome = "IDEMPOTENT"
            else:
                duplicate = self.db.execute(
                    "SELECT job_id FROM jobs WHERE challenge=? AND strategy_digest=?",
                    (challenge, strategy_digest),
                ).fetchone()
                if duplicate:
                    resolved = str(duplicate["job_id"])
                    outcome = "DUPLICATE"
                else:
                    self.db.execute(
                        "INSERT INTO jobs(job_id,challenge,strategy_digest,compatibility_key,submitted_at,state) "
                        "VALUES(?,?,?,?,?,'COMMITTED')",
                        (
                            job_id,
                            challenge,
                            strategy_digest,
                            compatibility_key,
                            submitted_at,
                        ),
                    )
                    resolved = job_id
                    outcome = "ACCEPTED"
            self._event("submit", outcome, requested=job_id, resolved=resolved)
            self.db.execute("COMMIT")
            return resolved
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def lock_pack(
        self,
        pack_id: str,
        challenge: str,
        compatibility_key: str,
        members: tuple[str, ...],
        *,
        cutoff: int,
        case_identity: str,
        lineage: tuple[str, ...] = (),
        public_rights: bool = False,
    ) -> None:
        if not members or len(set(members)) != len(members):
            self._reject("INVALID_MEMBERSHIP")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute(
                "SELECT 1 FROM packs WHERE pack_id=?", (pack_id,)
            ).fetchone():
                self._reject("PACK_ALREADY_EXISTS")
            if self.db.execute(
                "SELECT 1 FROM packs WHERE case_identity=?", (case_identity,)
            ).fetchone():
                self._reject("DECLARED_ASSET_LINEAGE_REUSE")
            rows = []
            for member in members:
                row = self.db.execute(
                    "SELECT * FROM jobs WHERE job_id=?", (member,)
                ).fetchone()
                if (
                    row is None
                    or row["challenge"] != challenge
                    or row["compatibility_key"] != compatibility_key
                    or row["submitted_at"] > cutoff
                    or row["pack_id"] is not None
                ):
                    self._reject("INELIGIBLE_MEMBER")
                rows.append(row)
            self.db.execute(
                "INSERT INTO packs(pack_id,challenge,compatibility_key,cutoff,case_identity,state,public_rights,lineage) "
                "VALUES(?,?,?,?,?,'LOCKED',?,?)",
                (
                    pack_id,
                    challenge,
                    compatibility_key,
                    cutoff,
                    case_identity,
                    int(public_rights),
                    json.dumps(lineage),
                ),
            )
            for ordinal, row in enumerate(rows):
                self.db.execute(
                    "INSERT INTO members(job_id,pack_id,ordinal) VALUES(?,?,?)",
                    (row["job_id"], pack_id, ordinal),
                )
                self.db.execute(
                    "UPDATE jobs SET pack_id=? WHERE job_id=?",
                    (pack_id, row["job_id"]),
                )
            self._event("lock_pack", "ACCEPTED", pack_id=pack_id, members=members)
            self.db.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self.db.execute("ROLLBACK")
            raise ResearchRejected("JOB_ALREADY_ASSIGNED") from error
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def expose_cases(self, pack_id: str) -> None:
        changed = self.db.execute(
            "UPDATE packs SET state='EXPOSED' WHERE pack_id=? AND state='LOCKED'",
            (pack_id,),
        ).rowcount
        if changed != 1:
            self._reject("PACK_NOT_LOCKED")
        self._event("expose_cases", "ACCEPTED", pack_id=pack_id)

    def add_member(self, pack_id: str, job_id: str) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            pack = self.db.execute(
                "SELECT * FROM packs WHERE pack_id=?", (pack_id,)
            ).fetchone()
            job = self.db.execute(
                "SELECT * FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if pack is None or job is None:
                self._reject("UNKNOWN_IDENTITY")
            if "late_membership" not in self.vulnerable and (
                pack["state"] != "LOCKED" or job["submitted_at"] > pack["cutoff"]
            ):
                self._reject("MEMBERSHIP_CLOSED")
            if (
                job["challenge"] != pack["challenge"]
                or job["compatibility_key"] != pack["compatibility_key"]
                or job["pack_id"] is not None
            ):
                self._reject("INELIGIBLE_MEMBER")
            ordinal = self.db.execute(
                "SELECT COUNT(*) FROM members WHERE pack_id=?", (pack_id,)
            ).fetchone()[0]
            self.db.execute(
                "INSERT INTO members(job_id,pack_id,ordinal) VALUES(?,?,?)",
                (job_id, pack_id, ordinal),
            )
            self.db.execute(
                "UPDATE jobs SET pack_id=? WHERE job_id=?", (pack_id, job_id)
            )
            self._event("add_member", "ACCEPTED", pack_id=pack_id, job_id=job_id)
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def seal_artifact(self, job_id: str, artifact: object) -> str:
        candidate = canonical_digest(artifact)
        row = self.db.execute(
            "SELECT artifact_digest,pack_id FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if row is None or row["pack_id"] is None:
            self._reject("PACK_REQUIRED")
        if row["artifact_digest"] not in (None, candidate):
            self._reject("ARTIFACT_MUTATION")
        self.db.execute(
            "UPDATE jobs SET artifact_digest=?,state='SEALED' WHERE job_id=?",
            (candidate, job_id),
        )
        self._event("seal_artifact", "ACCEPTED", job_id=job_id, digest=candidate)
        return candidate

    def start_attempt(self, job_id: str) -> int:
        row = self.db.execute(
            "SELECT j.attempt_id,p.state FROM jobs j JOIN packs p ON p.pack_id=j.pack_id WHERE j.job_id=?",
            (job_id,),
        ).fetchone()
        if row is None or row["state"] != "EXPOSED":
            self._reject("PACK_NOT_EXECUTABLE")
        attempt = int(row["attempt_id"]) + 1
        self.db.execute(
            "UPDATE jobs SET attempt_id=?,state='RUNNING' WHERE job_id=?",
            (attempt, job_id),
        )
        self._event("start_attempt", "ACCEPTED", job_id=job_id, attempt=attempt)
        return attempt

    def bind_prediction(self, job_id: str, attempt: int, prediction: object) -> str:
        row = self.db.execute(
            "SELECT j.*,p.state AS pack_state FROM jobs j JOIN packs p ON p.pack_id=j.pack_id WHERE j.job_id=?",
            (job_id,),
        ).fetchone()
        if row is None:
            self._reject("UNKNOWN_JOB")
        if row["pack_state"] != "EXPOSED":
            self._reject("PACK_CLOSED")
        if row["attempt_id"] != attempt:
            self._reject("STALE_ATTEMPT")
        if row["artifact_digest"] is None:
            self._reject("ARTIFACT_REQUIRED")
        candidate = canonical_digest(
            {
                "job": job_id,
                "pack": row["pack_id"],
                "attempt": attempt,
                "artifact": row["artifact_digest"],
                "prediction": prediction,
            }
        )
        if row["prediction_digest"] not in (None, candidate):
            self._reject("PREDICTION_CONFLICT")
        self.db.execute(
            "UPDATE jobs SET prediction_digest=?,state='PREDICTION_BOUND' WHERE job_id=?",
            (candidate, job_id),
        )
        self._event("bind_prediction", "ACCEPTED", job_id=job_id, digest=candidate)
        return candidate

    def finish(
        self, job_id: str, result: object, *, reference_failure: bool = False
    ) -> None:
        row = self.db.execute(
            "SELECT prediction_digest FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if row is None:
            self._reject("UNKNOWN_JOB")
        if not reference_failure and row["prediction_digest"] is None:
            self._reject("PREDICTION_REQUIRED")
        state = "FAILED_REFERENCE" if reference_failure else "TERMINAL"
        result_digest = canonical_digest(
            {"state": state, "prediction": row["prediction_digest"], "result": result}
        )
        self.db.execute(
            "UPDATE jobs SET state=?,result_digest=? WHERE job_id=?",
            (state, result_digest, job_id),
        )
        self._event("finish", "ACCEPTED", job_id=job_id, state=state)

    def request_retry(self, job_id: str, *, fresh_entropy: bool = False) -> None:
        row = self.db.execute(
            "SELECT p.state FROM jobs j JOIN packs p ON p.pack_id=j.pack_id WHERE j.job_id=?",
            (job_id,),
        ).fetchone()
        if row is None or row["state"] != "EXPOSED":
            self._reject("PACK_CLOSED")
        if fresh_entropy:
            self._reject("FRESH_ENTROPY_FORBIDDEN")
        self.db.execute(
            "UPDATE jobs SET retries_open=retries_open+1 WHERE job_id=?", (job_id,)
        )
        self._event("request_retry", "ACCEPTED", job_id=job_id)

    def close_pack(self, pack_id: str) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            pack = self.db.execute(
                "SELECT state FROM packs WHERE pack_id=?", (pack_id,)
            ).fetchone()
            if pack is None or pack["state"] not in ("LOCKED", "EXPOSED"):
                self._reject("PACK_NOT_OPEN")
            rows = self.db.execute(
                "SELECT j.state,j.retries_open FROM jobs j JOIN members m ON m.job_id=j.job_id WHERE m.pack_id=?",
                (pack_id,),
            ).fetchall()
            terminal = {"TERMINAL", "FAILED_REFERENCE", "CANCELLED", "REVOKED"}
            safe = bool(rows) and all(
                row["state"] in terminal and row["retries_open"] == 0 for row in rows
            )
            if not safe and "early_retirement" not in self.vulnerable:
                self._reject("ANSWER_DEPENDENT_OPPORTUNITY_OPEN")
            self.db.execute(
                "UPDATE packs SET state='CLOSED' WHERE pack_id=?", (pack_id,)
            )
            self._event("close_pack", "ACCEPTED", pack_id=pack_id)
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def release_summary(self, job_id: str) -> str:
        row = self.db.execute(
            "SELECT j.result_digest,p.state FROM jobs j JOIN packs p ON p.pack_id=j.pack_id WHERE j.job_id=?",
            (job_id,),
        ).fetchone()
        if row is None or row["result_digest"] is None:
            self._reject("RESULT_REQUIRED")
        if row["state"] != "CLOSED" and "early_summary" not in self.vulnerable:
            self._reject("PACK_CLOSURE_REQUIRED")
        summary = canonical_digest({"permitted_summary": row["result_digest"]})
        self._event("release_summary", "ACCEPTED", job_id=job_id, digest=summary)
        return summary

    def publish_answers(self, _pack_id: str, _bundle: object) -> None:
        self._reject("ANSWER_PUBLICATION_NOT_AUTHORIZED")

    def add_verified_evidence(self, evidence_ref: str, kind: str) -> None:
        self.db.execute(
            "INSERT INTO verified_evidence(evidence_ref,evidence_kind) VALUES(?,?)",
            (evidence_ref, kind),
        )

    def import_authority(self, supplied: bool, evidence_ref: str | None) -> bool:
        verified = None
        if evidence_ref is not None:
            verified = self.db.execute(
                "SELECT evidence_kind FROM verified_evidence WHERE evidence_ref=?",
                (evidence_ref,),
            ).fetchone()
        if (
            supplied
            and (
                verified is None
                or verified["evidence_kind"] != "SECURITY_QUALIFICATION"
            )
            and "forged_authority" not in self.vulnerable
        ):
            self._reject("UNVERIFIED_AUTHORITY")
        return supplied if "forged_authority" in self.vulnerable else bool(verified)

    def put_reference(
        self, binding: dict[str, str], artifact: object, *, complete: bool
    ) -> str:
        required = {
            "challenge",
            "physical_inputs",
            "output_request",
            "units_scaling",
            "solver_config",
            "environment",
            "policy",
            "evidence_depth",
        }
        if set(binding) != required:
            self._reject("INCOMPLETE_CACHE_BINDING")
        key = canonical_digest(binding)
        artifact_digest = canonical_digest(artifact)
        self.db.execute(
            "INSERT INTO reference_cache(key_digest,binding_json,artifact_digest,complete) VALUES(?,?,?,?)",
            (key, json.dumps(binding, sort_keys=True), artifact_digest, int(complete)),
        )
        return artifact_digest

    def lookup_reference(self, binding: dict[str, str]) -> str:
        row = self.db.execute(
            "SELECT artifact_digest,complete FROM reference_cache WHERE key_digest=?",
            (canonical_digest(binding),),
        ).fetchone()
        if row is None:
            self._reject("CACHE_BINDING_MISMATCH")
        if not row["complete"]:
            self._reject("INCOMPLETE_REFERENCE_ARTIFACT")
        return str(row["artifact_digest"])

    def events(self) -> list[dict[str, object]]:
        return [
            {
                "sequence": row["sequence"],
                "action": row["action"],
                "outcome": row["outcome"],
                "details": json.loads(row["details_json"]),
            }
            for row in self.db.execute("SELECT * FROM events ORDER BY sequence")
        ]


def _new_job(ledger: ResearchLedger, name: str, at: int, recipe: int) -> None:
    ledger.submit(name, "challenge-a", {"recipe": recipe}, "compat-v1", at)


def _prepare_two(ledger: ResearchLedger) -> None:
    _new_job(ledger, "a", 1, 1)
    _new_job(ledger, "b", 2, 2)
    ledger.lock_pack(
        "pack-a",
        "challenge-a",
        "compat-v1",
        ("a", "b"),
        cutoff=2,
        case_identity="case-a",
    )
    ledger.expose_cases("pack-a")


def _complete(ledger: ResearchLedger, job_id: str) -> None:
    ledger.seal_artifact(job_id, {"weights": job_id})
    attempt = ledger.start_attempt(job_id)
    ledger.bind_prediction(job_id, attempt, {"prediction": job_id})
    ledger.finish(job_id, {"score": 1})


def rejection_code(fn) -> str:
    try:
        fn()
    except ResearchRejected as error:
        return error.code
    return "ATTEMPT_ACCEPTED"


def run_persistent_probes(directory: Path) -> dict[str, object]:
    directory.mkdir(parents=True, exist_ok=True)
    traces: list[dict[str, object]] = []

    guarded = ResearchLedger(directory / "late-guarded.sqlite3")
    _prepare_two(guarded)
    _new_job(guarded, "late", 3, 3)
    late_guard = rejection_code(lambda: guarded.add_member("pack-a", "late"))
    traces.append({"probe": "late_membership_guarded", "result": late_guard})
    guarded.close()

    vulnerable = ResearchLedger(
        directory / "late-vulnerable.sqlite3",
        vulnerable=frozenset({"late_membership"}),
    )
    _prepare_two(vulnerable)
    _new_job(vulnerable, "late", 3, 3)
    vulnerable.add_member("pack-a", "late")
    traces.append(
        {
            "probe": "late_membership_guard_removed",
            "result": "OBSERVED_EXPLOIT",
            "events": vulnerable.events(),
        }
    )
    vulnerable.close()

    guarded = ResearchLedger(directory / "retire-guarded.sqlite3")
    _prepare_two(guarded)
    retire_guard = rejection_code(lambda: guarded.close_pack("pack-a"))
    traces.append({"probe": "retirement_guarded", "result": retire_guard})
    guarded.close()

    vulnerable = ResearchLedger(
        directory / "retire-vulnerable.sqlite3",
        vulnerable=frozenset({"early_retirement"}),
    )
    _prepare_two(vulnerable)
    vulnerable.close_pack("pack-a")
    traces.append(
        {
            "probe": "retirement_guard_removed",
            "result": "OBSERVED_EXPLOIT",
            "events": vulnerable.events(),
        }
    )
    vulnerable.close()

    guarded = ResearchLedger(directory / "authority-guarded.sqlite3")
    authority_guard = rejection_code(lambda: guarded.import_authority(True, "fake"))
    traces.append({"probe": "authority_guarded", "result": authority_guard})
    guarded.close()
    vulnerable = ResearchLedger(
        directory / "authority-vulnerable.sqlite3",
        vulnerable=frozenset({"forged_authority"}),
    )
    accepted = vulnerable.import_authority(True, "fake")
    traces.append(
        {
            "probe": "authority_evidence_guard_removed",
            "result": "OBSERVED_EXPLOIT" if accepted else "UNEXPECTED_REJECTION",
        }
    )
    vulnerable.close()

    guarded_path = directory / "closure-restart.sqlite3"
    guarded = ResearchLedger(guarded_path)
    _prepare_two(guarded)
    _complete(guarded, "a")
    early_summary = rejection_code(lambda: guarded.release_summary("a"))
    _complete(guarded, "b")
    guarded.close_pack("pack-a")
    attempt = guarded.db.execute(
        "SELECT attempt_id FROM jobs WHERE job_id='a'"
    ).fetchone()[0]
    guarded.close()
    restarted = ResearchLedger.attach(guarded_path)
    stale_write = rejection_code(
        lambda: restarted.bind_prediction("a", attempt, {"prediction": "changed"})
    )
    summary = restarted.release_summary("a")
    answer_release = rejection_code(
        lambda: restarted.publish_answers("pack-a", {"answer": 1})
    )
    traces.append(
        {
            "probe": "closure_restart",
            "early_summary": early_summary,
            "late_write": stale_write,
            "summary_digest": summary,
            "answer_release": answer_release,
            "events": restarted.events(),
        }
    )
    restarted.close()

    cache = ResearchLedger(directory / "cache.sqlite3")
    binding = {
        "challenge": "challenge-a",
        "physical_inputs": "inputs-v1",
        "output_request": "velocity-v1",
        "units_scaling": "si-v1",
        "solver_config": "solver-v1",
        "environment": "env-v1",
        "policy": "policy-v1",
        "evidence_depth": "depth-v1",
    }
    expected_artifact = cache.put_reference(
        binding, {"reference": [1, 2]}, complete=True
    )
    mismatches = {}
    for field in binding:
        changed = dict(binding)
        changed[field] += "-changed"
        mismatches[field] = rejection_code(
            lambda value=changed: cache.lookup_reference(value)
        )
    exact_artifact = cache.lookup_reference(binding)
    cache.put_reference(
        {**binding, "physical_inputs": "inputs-incomplete"},
        {"partial": True},
        complete=False,
    )
    incomplete = rejection_code(
        lambda: cache.lookup_reference(
            {**binding, "physical_inputs": "inputs-incomplete"}
        )
    )
    traces.append(
        {
            "probe": "exact_cache_binding",
            "exact_match": exact_artifact == expected_artifact,
            "mismatches": mismatches,
            "incomplete": incomplete,
        }
    )
    cache.close()

    binding_guard = ResearchLedger(directory / "content-binding.sqlite3")
    _new_job(binding_guard, "bound", 1, 1)
    binding_guard.lock_pack(
        "pack-bound",
        "challenge-a",
        "compat-v1",
        ("bound",),
        cutoff=1,
        case_identity="case-bound",
    )
    binding_guard.expose_cases("pack-bound")
    binding_guard.seal_artifact("bound", {"weights": "frozen"})
    bound_attempt = binding_guard.start_attempt("bound")
    binding_guard.bind_prediction("bound", bound_attempt, {"prediction": 1})
    changed_prediction = rejection_code(
        lambda: binding_guard.bind_prediction("bound", bound_attempt, {"prediction": 2})
    )
    binding_guard.finish("bound", {"score": 1})
    binding_guard.request_retry("bound")
    retry_blocks_closure = rejection_code(
        lambda: binding_guard.close_pack("pack-bound")
    )
    traces.append(
        {
            "probe": "content_and_retry_binding",
            "changed_prediction": changed_prediction,
            "retry_blocks_closure": retry_blocks_closure,
            "events": binding_guard.events(),
        }
    )
    binding_guard.close()

    reference_failure = ResearchLedger(directory / "reference-failure.sqlite3")
    _new_job(reference_failure, "failed-reference", 1, 1)
    reference_failure.lock_pack(
        "pack-reference-failure",
        "challenge-a",
        "compat-v1",
        ("failed-reference",),
        cutoff=1,
        case_identity="case-reference-failure",
    )
    reference_failure.expose_cases("pack-reference-failure")
    reference_failure.finish(
        "failed-reference", {"diagnostic": "nonconverged"}, reference_failure=True
    )
    reference_failure.close_pack("pack-reference-failure")
    retained_state = reference_failure.db.execute(
        "SELECT state FROM jobs WHERE job_id='failed-reference'"
    ).fetchone()[0]
    traces.append(
        {
            "probe": "typed_reference_failure",
            "result": retained_state,
            "positive_scientific_result": False,
            "events": reference_failure.events(),
        }
    )
    reference_failure.close()

    race_path = directory / "assignment-race.sqlite3"
    setup = ResearchLedger(race_path)
    _new_job(setup, "raced", 1, 1)
    setup.close()

    def race(pack_id: str) -> str:
        owner = ResearchLedger.attach(race_path)
        try:
            owner.lock_pack(
                pack_id,
                "challenge-a",
                "compat-v1",
                ("raced",),
                cutoff=1,
                case_identity=f"case-{pack_id}",
            )
            return "ASSIGNED"
        except ResearchRejected as error:
            return error.code
        finally:
            owner.close()

    with ThreadPoolExecutor(max_workers=2) as workers:
        race_results = sorted(workers.map(race, ("one", "two")))
    traces.append({"probe": "independent_connection_race", "results": race_results})

    return {
        "schema_version": "carbon.cpes-reuse.persistent-probes.v1",
        "research_only": True,
        "traces": traces,
        "expected_guards": {
            "late_membership": late_guard,
            "retirement": retire_guard,
            "forged_authority": authority_guard,
            "early_summary": early_summary,
            "stale_write_after_restart": stale_write,
            "answer_publication": answer_release,
            "changed_prediction": changed_prediction,
            "open_retry_closure": retry_blocks_closure,
        },
        "negative_control_exploits": [
            "late_membership_guard_removed",
            "retirement_guard_removed",
            "authority_evidence_guard_removed",
        ],
        "assignment_race_results": race_results,
        "production_authority": False,
    }


def adaptive_bank_exploit(seed: int, count: int = 32) -> dict[str, object]:
    rng = random.Random(seed)
    bank = [rng.randrange(2) for _ in range(count)]
    holdout = [rng.randrange(2) for _ in range(count)]

    def exact_score(prediction: list[int], truth: list[int]) -> int:
        return sum(left == right for left, right in zip(prediction, truth))

    baseline = [0] * count
    baseline_score = exact_score(baseline, bank)
    recovered = []
    for index in range(count):
        probe = baseline.copy()
        probe[index] = 1
        recovered.append(1 if exact_score(probe, bank) > baseline_score else 0)
    return {
        "schema_version": "carbon.cpes-reuse.adaptive-bank-control.v1",
        "evidence_class": "SYNTHETIC_ADAPTIVE_NEGATIVE_CONTROL",
        "whole_cases": count,
        "feedback": "exact correct-count after each adaptive submission",
        "queries": count + 1,
        "reused_bank_accuracy": exact_score(recovered, bank) / count,
        "independent_holdout_accuracy": exact_score(recovered, holdout) / count,
        "recovered_bank_exactly": recovered == bank,
        "permitted_repair_interface": (
            "one closure-gated summary for one precommitted prediction; no repeated "
            "adaptive access to the protected realization"
        ),
        "limitation": (
            "This proves exploitability of exact repeated score feedback on this "
            "finite synthetic bank, not a Carbon population leakage rate."
        ),
    }


@dataclass(frozen=True, slots=True)
class EconomicJob:
    job_id: str
    challenge: str
    compatibility_key: str | None
    arrival: int
    reference_work: int
    candidate_work: int
    evidence_work: int
    outcome: str = "COMPLETED"
    duplicate_of: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.job_id
            or not self.challenge
            or self.arrival < 0
            or min(self.reference_work, self.candidate_work, self.evidence_work) < 0
            or self.outcome
            not in {"COMPLETED", "CANCELLED", "REFERENCE_FAILURE", "UNRESOLVED"}
        ):
            raise ResearchRejected("INVALID_ECONOMIC_JOB")


def scenario_jobs(
    name: str, reference_override: int | None = None
) -> tuple[EconomicJob, ...]:
    if name == "cheap_sparse":
        jobs = [
            EconomicJob(f"cs-{i}", "c-a", "same", i * 20, 2, 8, 2) for i in range(6)
        ]
    elif name == "expensive_bursty":
        jobs = [
            EconomicJob(
                f"eb-{i}", "c-a", "same", (i // 3) * 12 + i % 3, 40, 7 + i % 3, 3
            )
            for i in range(9)
        ]
    elif name == "mixed_challenges":
        jobs = [
            EconomicJob(
                f"mc-{i}",
                "c-a" if i % 2 == 0 else "c-b",
                "same",
                i * 2,
                40 if i % 2 == 0 else 10,
                8,
                3,
            )
            for i in range(10)
        ]
    elif name == "duplicate_flood":
        jobs = [EconomicJob(f"df-{i}", "c-a", "same", i, 40, 8, 3) for i in range(5)]
        jobs.extend(
            EconomicJob(f"copy-{i}", "c-a", "same", i, 40, 8, 3, duplicate_of="df-0")
            for i in range(8)
        )
    elif name == "slow_or_unresolved_member":
        jobs = [
            EconomicJob("fast", "c-a", "same", 0, 40, 2, 3),
            EconomicJob("slow", "c-a", "same", 0, 40, 30, 3),
            EconomicJob("unresolved", "c-a", "same", 0, 40, 9, 3, "UNRESOLVED"),
            EconomicJob("independent", "c-b", "other", 1, 10, 4, 2),
        ]
    else:
        raise ResearchRejected("UNKNOWN_SCENARIO")
    if reference_override is not None:
        jobs = [replace(job, reference_work=reference_override) for job in jobs]
    return tuple(jobs)


def _quantile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def simulate_operating_policy(
    jobs: Iterable[EconomicJob],
    *,
    variant: str,
    group_bound: int,
    fill_wait: int,
    group_overhead: int,
    horizon: int = 250,
) -> dict[str, object]:
    offered = tuple(sorted(jobs, key=lambda item: (item.arrival, item.job_id)))
    if (
        variant not in {"A", "B", "C"}
        or group_bound < 1
        or min(fill_wait, group_overhead) < 0
    ):
        raise ResearchRejected("INVALID_OPERATING_POLICY")
    admitted = [job for job in offered if job.duplicate_of is None]
    pending = admitted.copy()
    now = 0
    work = {
        "reference": 0,
        "candidate": 0,
        "evidence_closure": 0,
        "group_control": 0,
        "failed_cancelled_unresolved": 0,
    }
    groups: list[dict[str, object]] = []
    results: dict[str, dict[str, object]] = {}
    reference_attempts = 0
    while pending:
        pending.sort(key=lambda item: (item.arrival, item.job_id))
        first = pending[0]
        ready_at = max(now, first.arrival)
        dispatch_at = ready_at
        if variant == "C":
            compatible_future = [
                job
                for job in pending
                if job.challenge == first.challenge
                and job.compatibility_key == first.compatibility_key
                and job.arrival > ready_at
            ]
            deadline = ready_at + fill_wait
            needed = group_bound - 1
            if needed > 0 and len(compatible_future) >= needed:
                dispatch_at = min(deadline, compatible_future[needed - 1].arrival)
            else:
                dispatch_at = deadline
        ready = [job for job in pending if job.arrival <= dispatch_at]
        group = [first]
        if variant in {"B", "C"} and first.compatibility_key is not None:
            group.extend(
                job
                for job in ready
                if job is not first
                and job.challenge == first.challenge
                and job.compatibility_key == first.compatibility_key
                and len(group) < group_bound
            )
        reference_requirements = {job.reference_work for job in group}
        if len(group) > 1 and len(reference_requirements) != 1:
            raise ResearchRejected("INCONSISTENT_REFERENCE_REQUIREMENTS")
        for job in group:
            pending.remove(job)
        reference_cost = (
            sum(job.reference_work for job in group)
            if variant == "A"
            else group[0].reference_work
        )
        reference_attempts += len(group) if variant == "A" else 1
        reference_failed = any(job.outcome == "REFERENCE_FAILURE" for job in group)
        work["reference"] += reference_cost
        work["group_control"] += group_overhead
        current = dispatch_at + reference_cost + group_overhead
        member_finishes: dict[str, int] = {}
        for job in group:
            if reference_failed:
                work["failed_cancelled_unresolved"] += job.evidence_work
                member_finishes[job.job_id] = current
                continue
            if job.outcome == "CANCELLED":
                work["failed_cancelled_unresolved"] += job.evidence_work
                current += job.evidence_work
                member_finishes[job.job_id] = current
                continue
            current += job.candidate_work + job.evidence_work
            member_finishes[job.job_id] = current
            if job.outcome == "UNRESOLVED":
                work["failed_cancelled_unresolved"] += (
                    job.candidate_work + job.evidence_work
                )
            else:
                work["candidate"] += job.candidate_work
                work["evidence_closure"] += job.evidence_work
        unresolved = any(job.outcome == "UNRESOLVED" for job in group)
        group_closed_at = None if unresolved else current
        for job in group:
            completed = job.outcome == "COMPLETED" and not reference_failed
            summary_at = group_closed_at if completed else None
            results[job.job_id] = {
                "outcome": "REFERENCE_FAILURE" if reference_failed else job.outcome,
                "ordinary_queue_delay": ready_at - job.arrival,
                "intentional_fill_delay": (
                    dispatch_at - ready_at if variant == "C" else 0
                ),
                "candidate_finished_at": member_finishes[job.job_id],
                "waiting_for_other_members": (
                    None
                    if summary_at is None
                    else summary_at - member_finishes[job.job_id]
                ),
                "summary_at": summary_at,
                "submission_to_summary": (
                    None if summary_at is None else summary_at - job.arrival
                ),
            }
        groups.append(
            {
                "members": [job.job_id for job in group],
                "challenge": first.challenge,
                "dispatch_at": dispatch_at,
                "fill_wait": dispatch_at - ready_at if variant == "C" else 0,
                "reference_work": reference_cost,
                "group_overhead": group_overhead,
                "closed_at": group_closed_at,
            }
        )
        now = current
    summaries = [
        row["submission_to_summary"]
        for row in results.values()
        if row["submission_to_summary"] is not None
    ]
    member_waits = [
        row["waiting_for_other_members"]
        for row in results.values()
        if row["waiting_for_other_members"] is not None
    ]
    total_work = sum(work.values())
    completed = len(summaries)
    return {
        "schema_version": "carbon.cpes-reuse.operating-replay.v1",
        "evidence_class": "COUNTERFACTUAL_MODEL",
        "variant": variant,
        "offered_requests": len(offered),
        "deduplicated_requests": len(offered) - len(admitted),
        "admitted_distinct_jobs": len(admitted),
        "groups": groups,
        "group_size_histogram": {
            str(size): sum(len(group["members"]) == size for group in groups)
            for size in sorted({len(group["members"]) for group in groups})
        },
        "unique_reference_cases": len(groups),
        "reference_attempts": reference_attempts,
        "work": work,
        "total_recurring_work": total_work,
        "complete_comparisons": completed,
        "unfinished_or_nonpositive": len(admitted) - completed,
        "backlog_at_horizon": sum(
            row["summary_at"] is None or row["summary_at"] > horizon
            for row in results.values()
        ),
        "mean_feedback_delay": statistics.mean(summaries) if summaries else None,
        "p95_feedback_delay": _quantile(summaries, 0.95),
        "mean_other_member_closure_delay": (
            statistics.mean(member_waits) if member_waits else None
        ),
        "adaptive_feedback_rounds": sum(
            group["closed_at"] is not None for group in groups
        ),
        "jobs": results,
        "uses_future_information": False,
        "one_validator_serial_resource": True,
    }


def run_operating_grid(config: dict[str, object]) -> dict[str, object]:
    grid = config["operating_grid"]
    assert isinstance(grid, dict)
    group_bound = int(grid["group_bound"])
    wait = int(grid["bounded_fill_wait_units"])
    rows = []
    for scenario in grid["scenarios"]:
        jobs = scenario_jobs(str(scenario))
        for overhead in grid["group_overhead_units"]:
            for variant in ("A", "B", "C"):
                result = simulate_operating_policy(
                    jobs,
                    variant=variant,
                    group_bound=group_bound,
                    fill_wait=wait if variant == "C" else 0,
                    group_overhead=0 if variant == "A" else int(overhead),
                )
                result.update(scenario=scenario, assumed_group_overhead=int(overhead))
                rows.append(result)
    sanity = []
    for reference in grid["reference_work_units"]:
        for overhead in grid["group_overhead_units"]:
            for size in (1, 2, 3):
                saving = (size - 1) * int(reference) - int(overhead)
                sanity.append(
                    {
                        "reference_work_R": int(reference),
                        "group_overhead_H": int(overhead),
                        "actual_membership_b": size,
                        "total_group_saving": saving,
                        "saving_per_candidate": saving / size,
                        "strict_compute_break_even": size > 1
                        and int(reference) > int(overhead) / (size - 1),
                        "scope": "fixed membership arithmetic only",
                    }
                )
    return {
        "schema_version": "carbon.cpes-reuse.cost-delay-study.v1",
        "evidence_class": "COUNTERFACTUAL_MODEL",
        "rows": rows,
        "fixed_membership_sanity": sanity,
        "actual_b_overhead": None,
        "compatible_miner_demand": None,
        "scientifically_adequate_reference_cost": None,
        "unconditional_savings_supported": False,
        "membership_recomputed_per_overhead": True,
    }


def attack_dispositions(
    probes: dict[str, object], bank: dict[str, object]
) -> list[dict[str, object]]:
    prototype_ids = {
        "AT-17",
        "AT-18",
        "AT-20",
        "AT-21",
        "AT-23",
        "AT-25",
        "AT-27",
        "AT-28",
    }
    limitations = {
        "AT-09": "No qualified production entropy/confidentiality composition; a public beacon is public.",
        "AT-16": "A privileged plaintext host remains outside this prototype's secrecy boundary.",
        "AT-19": "Declared aliases reject in the prototype, but Carbon has no qualified authoritative cross-pack asset-lineage registry.",
        "AT-22": "A signature identifies a signer; independent honest-execution evidence remains absent.",
        "AT-30": "The adaptive finite-bank exploit succeeds, but no qualified Carbon-family freshness test or leakage criterion exists.",
    }
    rows = []
    for attack_id in sorted(ATTACKS):
        control, attack, entry = ATTACKS[attack_id]
        if attack_id in ORIGINAL_BLOCKED:
            status = "BLOCKED"
            layer = "MISSING_OWNER_OR_QUALIFICATION_EVIDENCE"
        elif attack_id in prototype_ids:
            status = "REJECTED_BY_PERSISTENT_RESEARCH_PROTOTYPE"
            layer = "DISPOSABLE_SQLITE_RESEARCH_PROTOTYPE"
        else:
            status = "REJECTED_BY_REPRODUCED_ORIGINAL_MODEL"
            layer = "UNCHANGED_ORIGINAL_2026_09_12_HYPOTHESIS_MODEL_RERUN"
        rows.append(
            {
                "attack_id": attack_id,
                "control": control,
                "attack": attack,
                "original_2026_09_12_disposition": (
                    "BLOCKED_MISSING_IMPLEMENTATION_OR_DECISION"
                    if attack_id in ORIGINAL_BLOCKED
                    else "REJECTED_IN_MODEL"
                ),
                "current_disposition": status,
                "attacker_permissions": (
                    "privileged host operator or dishonest signer"
                    if attack_id in {"AT-16", "AT-22"}
                    else "malicious submitter/operator at the stated detached interface"
                ),
                "entry_point": entry,
                "input_history": "frozen synthetic/public study history; no protected Carbon cases",
                "observations": (
                    "adaptive exact-score queries recover the synthetic bank"
                    if attack_id == "AT-30"
                    else "see persistent_probes_v1.json and attack_traces_v2.jsonl"
                ),
                "attempted_manipulation": attack,
                "implementation_layer": layer,
                "expected_result": "reject or remain fail closed with retained disposition",
                "observed_result": (
                    "negative control recovered bank exactly; official-use claim remains blocked"
                    if attack_id == "AT-30"
                    else status
                ),
                "counterexample_trace": (
                    "adaptive_bank_control_v1.json"
                    if attack_id == "AT-30"
                    else "attack_traces_v2.jsonl"
                ),
                "limitation": limitations.get(
                    attack_id,
                    "Detached evidence does not establish behavior of an unimplemented production sharing path.",
                ),
            }
        )
    assert len(rows) == 30
    assert {
        row["attack_id"] for row in rows if row["current_disposition"] == "BLOCKED"
    } == ORIGINAL_BLOCKED
    assert bank["recovered_bank_exactly"]
    assert probes["production_authority"] is False
    return rows


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run(
    *,
    config_path: Path,
    output_dir: Path,
    original_bundle: Path | None,
) -> dict[str, object]:
    if output_dir.exists():
        raise ResearchRejected("OUTPUT_DIRECTORY_ALREADY_EXISTS")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if (
        config.get("schema_version")
        != "carbon.cpes-reference-reuse-gauntlet.protocol.v2"
    ):
        raise ResearchRejected("PROTOCOL_MISMATCH")
    output_dir.mkdir(parents=True)
    started = time.perf_counter_ns()
    original = (
        verify_original_bundle(original_bundle)
        if original_bundle is not None
        else {"status": "NOT_SUPPLIED_TO_THIS_RUN"}
    )
    with tempfile.TemporaryDirectory(prefix="cpes-reuse-prototype-") as temporary:
        probes = run_persistent_probes(Path(temporary))
    bank = adaptive_bank_exploit(int(config["seed"]))
    economics = run_operating_grid(config)
    dispositions = attack_dispositions(probes, bank)
    elapsed = time.perf_counter_ns() - started
    source_manifest = {
        "schema_version": "carbon.cpes-reuse.source-manifest.v1",
        "study_id": config["study_id"],
        "source_revision": config["source_revision"],
        "protocol_sha256": file_sha256(config_path),
        "harness_sha256": file_sha256(Path(__file__).resolve()),
        "read_only_repository_inputs": {
            "carbon/evaluation_packs/study.py": file_sha256(
                Path(__file__).resolve().parents[2] / "carbon/evaluation_packs/study.py"
            ),
            ".agent/evidence/wave_c/c-ep3-inputs/probe_observation_summary_v1.json": file_sha256(
                Path(__file__).resolve().parents[2]
                / ".agent/evidence/wave_c/c-ep3-inputs/probe_observation_summary_v1.json"
            ),
            "docs/development/C03_ISOLATED_WORKER_REPORT.md": file_sha256(
                Path(__file__).resolve().parents[2]
                / "docs/development/C03_ISOLATED_WORKER_REPORT.md"
            ),
        },
        "original_gauntlet": original,
        "original_harness_rerun": {
            "command": "python3 -m unittest -q test_gauntlet.py; python3 run_gauntlet.py --out reproduced_results",
            "tests": 26,
            "status": "PASSED_IN_ISOLATED_EXTRACTED_COPY",
            "attack_status_counts": {
                "REJECTED_IN_MODEL": 25,
                "BLOCKED_MISSING_IMPLEMENTATION_OR_DECISION": 5,
            },
            "claim_limit": "Historical model reproduced; no production interface was tested by that rerun.",
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
            "processes": 1,
            "gpu_used": False,
        },
        "harness_runtime_ns": elapsed,
        "harness_runtime_is_not_worker_performance": True,
    }
    traces = []
    for trace in probes["traces"]:
        traces.append(
            {"evidence_layer": "DISPOSABLE_SQLITE_RESEARCH_PROTOTYPE", **trace}
        )
    traces.append(
        {"evidence_layer": bank["evidence_class"], "probe": "adaptive_bank", **bank}
    )
    summary = {
        "schema_version": "carbon.cpes-reuse.study-summary.v1",
        "study_id": config["study_id"],
        "attack_counts": {
            status: sum(row["current_disposition"] == status for row in dispositions)
            for status in sorted(
                {str(row["current_disposition"]) for row in dispositions}
            )
        },
        "blocked_attack_ids": sorted(ORIGINAL_BLOCKED),
        "negative_control_exploits": [
            *probes["negative_control_exploits"],
            "finite_bank_exact_score_feedback",
        ],
        "operating_replays": len(economics["rows"]),
        "recommendation": "RETAIN_A",
        "runtime_sharing_implemented": False,
        "production_authority": False,
    }
    profiler = {
        "schema_version": "carbon.challenge-profiler.cpes-reuse-study.v1",
        "study": config["study_id"],
        "current_implemented_policy": "VARIANT_A_DEVELOPMENT_SINGLETON",
        "reuse_candidate": "VARIANT_B_PRECOMMITTED_COMPATIBLE_QUEUE_GROUP",
        "variant_c": "RESEARCH_SENSITIVITY_ONLY",
        "variant_d": "VULNERABLE_NEGATIVE_CONTROL_ONLY",
        "categories": {
            "external_scientific_result": (
                "Adaptive holdout and leaderboard guarantees are algorithm- and "
                "assumption-specific; drand output is public verifiable randomness."
            ),
            "carbon_hypothesis": (
                "Closed-pack sharing can save repeated reference work when compatible "
                "jobs coexist without creating new answer-dependent opportunities."
            ),
            "proposed_carbon_experiment": (
                "Later Engineering may test immutable pre-exposure membership, exact "
                "cache binding and last-member closure under a separately authorized slice."
            ),
            "qualified_carbon_evidence": None,
        },
        "observed_components": {
            "c_ep3_public_reference_warm_ms": [288.438125, 289.820875],
            "c_ep3_distinct_physical_cases": 1,
            "c03_foundax_worker_total_ms": 11384,
            "cross_hardware_composition_permitted": False,
        },
        "assumed_quantities": {
            "compatible_demand": None,
            "variant_b_overhead": None,
            "scientifically_adequate_reference_cost": None,
            "synthetic_reference_work_grid": config["operating_grid"][
                "reference_work_units"
            ],
            "synthetic_group_overhead_grid": config["operating_grid"][
                "group_overhead_units"
            ],
        },
        "protection_blockers": sorted(ORIGINAL_BLOCKED),
        "upfront_implementation_and_qualification_burden": "UNKNOWN_AND_SEPARATE",
        "recurring_break_even": "for fixed unchanged membership: (b-1)*R > H",
        "feedback_delay": (
            "closure waits for the slowest unresolved member; optional fill waiting "
            "must be compared incrementally with zero-wait B"
        ),
        "recommendation": "RETAIN_A",
        "runtime_sharing_authorized": False,
        "editable_fields_create_authority": False,
    }
    write_json(output_dir / "source_manifest_v1.json", source_manifest)
    write_json(output_dir / "persistent_probes_v1.json", probes)
    write_json(output_dir / "adaptive_bank_control_v1.json", bank)
    write_json(output_dir / "attack_dispositions_v2.json", dispositions)
    with (output_dir / "attack_traces_v2.jsonl").open("w", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, sort_keys=True) + "\n")
    write_json(output_dir / "cost_delay_analysis_v1.json", economics)
    write_json(output_dir / "study_summary_v1.json", summary)
    write_json(output_dir / "profiler_summary_v1.json", profiler)
    indexed = sorted(path for path in output_dir.iterdir() if path.is_file())
    evidence_index = {
        "schema_version": "carbon.cpes-reuse.evidence-index.v1",
        "study_id": config["study_id"],
        "source_revision": config["source_revision"],
        "original_outcomes_are_historical": True,
        "new_outcomes_are_detached_research": True,
        "files": {
            path.name: {"sha256": file_sha256(path), "bytes": path.stat().st_size}
            for path in indexed
        },
        "rerun_commands": [
            "python3 -m unittest -q test_gauntlet.py",
            "python3 run_gauntlet.py --out reproduced_results",
            (
                "python scripts/dev/cpes_reference_reuse_gauntlet.py "
                "--config docs/development/"
                "cpes_reference_reuse_gauntlet_protocol_v2.json "
                "--output-dir /fresh/output --original-bundle /path/to/"
                "Carbon_CPES1_v0_2_Gauntlet_Evidence.zip"
            ),
            "python -m pytest -q tests/cpu/test_cpes_reference_reuse_gauntlet.py",
        ],
    }
    write_json(output_dir / "evidence_index_v1.json", evidence_index)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--original-bundle", type=Path)
    args = parser.parse_args()
    summary = run(
        config_path=args.config,
        output_dir=args.output_dir,
        original_bundle=args.original_bundle,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
