"""Cooling's public DEVELOPMENT `ChallengeAdapter` (Interface v1).

This adapter wraps existing Cooling authority. It does not define a new
population, gate, scale, recipe or reference:

- construction is the registered Level-0 cold-plate compiler and deterministic
  Gaussian kernel-ridge rebuild;
- the only preparable batch is the digest-pinned public PRACTICE artifact;
- reference ingestion accepts only a record equal to that pinned artifact;
- scoring is `carbon.cold_plate.exam`, using its TRAIN-derived scales; and
- miner disclosure is a small aggregate outcome. Cases, predictions, gates,
  recipes and full identities remain operator-only.

The evidence is public, adaptive DEVELOPMENT evidence. The reserved Cooling
Graphite confirmation role has no set here. Nothing in this module prepares,
loads or scores private/counting/confirmation evidence, and nothing confers
qualification, reward, customer acceptance or LIVE authority.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import stat
from pathlib import Path

from carbon.cold_plate import exam
from carbon.cold_plate.challenge import (
    CALIBRATION_SHA256,
    CHALLENGE,
    PRACTICE_SHA256,
    TRAIN_SHA256,
    PublicMaterial,
)
from carbon.cold_plate.compile import compile_recipe, rebuild
from carbon.cold_plate.contracts import implementation_digest as model_digest
from carbon.cold_plate.openfoam import IMAGE
from carbon.development_session.research_catalog import RecipeRejected
from carbon.reconstruction.capability_registry import contract

from .interface import Admitted, ChallengeAdapter, Unavailable, digest

ADAPTER_SCHEMA = "carbon.cold-plate.validator-adapter.v1"
BATCH_SCHEMA = "carbon.cold-plate.validator-public-batch.v1"
OUTCOME_SCHEMA = "carbon.cold-plate.validator-outcome.v1"
SCORE_RECORD_SCHEMA = "carbon.cold-plate.operator-score-record.v1"
STORE_SCHEMA = "carbon.cold-plate.validator-store.v1"
PUBLIC_BATCH_KIND = "public_practice"
EVIDENCE = "DEVELOPMENT_PUBLIC_ADAPTIVE"
MAX_STRATEGY_BYTES = 16_384


class CoolingAdapterError(ValueError):
    """A typed operator/store refusal. Its code contains no submitted data."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _copy(value):
    return json.loads(_canonical(value))


def _sha256_file(path):
    import hashlib

    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def implementation_digest():
    """Pin the adapter and every executable Cooling component it invokes."""

    from carbon import learned_baseline
    from carbon.cold_plate import compile as compiler
    from carbon.cold_plate import recipes

    files = {
        "adapter": Path(__file__),
        "compiler": Path(compiler.__file__),
        "exam": Path(exam.__file__),
        "learned_baseline": Path(learned_baseline.__file__),
        "recipes": Path(recipes.__file__),
    }
    return digest(
        {
            "schema": ADAPTER_SCHEMA,
            "files": {name: _sha256_file(path) for name, path in sorted(files.items())},
            "model_implementation_digest": model_digest(),
        }
    )


def rule_document(material):
    """The existing exam rule represented as pinned, finite JSON."""

    return {
        "schema": "carbon.cold-plate.development-exam-rule.v1",
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "evidence": EVIDENCE,
        "gates": [
            {"gate_id": gate.gate_id, "formula": gate.formula, "basis": gate.basis}
            for gate in exam.GATES
        ],
        "components": list(exam.COMPONENTS),
        "aggregate": "mean of three TRAIN-normalized errors; mandatory gate failure is ineligible",
        "important_peak_c": exam.T_IMPORTANT_C,
        "scales": exam.scales_from_train(material.train),
        "public_material": {
            "train_sha256": "sha256:" + TRAIN_SHA256,
            "practice_sha256": "sha256:" + PRACTICE_SHA256,
            "calibration_sha256": "sha256:" + CALIBRATION_SHA256,
        },
    }


def _private_directory(path):
    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True, mode=0o700)
    try:
        info = os.lstat(path)
    except OSError:
        raise CoolingAdapterError("cooling_store_directory_unavailable") from None
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise CoolingAdapterError("cooling_store_directory_not_owner_only")
    return path


class CoolingStore:
    """Owner-only SQLite custody for batches, outcomes and score records."""

    DDL = """
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS batches(
        fingerprint TEXT PRIMARY KEY,
        role TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL,
        document TEXT NOT NULL,
        state TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS refs(
        fingerprint TEXT NOT NULL,
        case_id TEXT NOT NULL,
        record TEXT NOT NULL,
        PRIMARY KEY(fingerprint, case_id),
        FOREIGN KEY(fingerprint) REFERENCES batches(fingerprint)
    );
    CREATE TABLE IF NOT EXISTS pool(
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        fingerprint TEXT NOT NULL,
        FOREIGN KEY(fingerprint) REFERENCES batches(fingerprint)
    );
    CREATE TABLE IF NOT EXISTS submissions(
        submission_id TEXT PRIMARY KEY,
        hotkey TEXT NOT NULL,
        strategy TEXT NOT NULL,
        outcome TEXT NOT NULL,
        score_record TEXT
    );
    """

    def __init__(self, root):
        self.root = _private_directory(root)
        self.path = self.root / "cooling-validator.sqlite3"
        if self.path.exists():
            info = os.lstat(self.path)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise CoolingAdapterError("cooling_store_not_owner_only")
        else:
            os.close(os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600))
        database = sqlite3.connect(self.path, isolation_level=None)
        try:
            database.execute("PRAGMA foreign_keys = ON")
            database.executescript(self.DDL)
        finally:
            database.close()
        with self._db() as database:
            database.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema', ?)",
                (STORE_SCHEMA,),
            )
            found = database.execute(
                "SELECT value FROM meta WHERE key = 'schema'"
            ).fetchone()[0]
        if found != STORE_SCHEMA:
            raise CoolingAdapterError("cooling_store_schema")

    @contextlib.contextmanager
    def _db(self):
        database = sqlite3.connect(self.path, timeout=30)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA busy_timeout = 30000")
        database.execute("PRAGMA foreign_keys = ON")
        try:
            yield database
            database.commit()
        except Exception:
            database.rollback()
            raise
        finally:
            database.close()

    def prepare(self, role, kind, document):
        fingerprint = digest(document)
        with self._db() as database:
            same = database.execute(
                "SELECT fingerprint, kind, document FROM batches WHERE role = ?",
                (role,),
            ).fetchone()
            if same is not None:
                if same["kind"] != kind or same["document"] != _canonical(document):
                    raise CoolingAdapterError("cooling_batch_role_changed")
                return same["fingerprint"]
            if database.execute("SELECT 1 FROM batches LIMIT 1").fetchone() is not None:
                raise CoolingAdapterError("cooling_public_batch_already_prepared")
            database.execute(
                "INSERT INTO batches VALUES (?, ?, ?, ?, 'PREPARED')",
                (fingerprint, role, kind, _canonical(document)),
            )
        return fingerprint

    def batch(self, fingerprint):
        with self._db() as database:
            row = database.execute(
                "SELECT document, state FROM batches WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        if row is None:
            raise CoolingAdapterError("cooling_batch_unknown")
        return _copy(json.loads(row["document"])), row["state"]

    def references(self, fingerprint):
        self.batch(fingerprint)
        with self._db() as database:
            rows = database.execute(
                "SELECT case_id, record FROM refs WHERE fingerprint = ? ORDER BY case_id",
                (fingerprint,),
            ).fetchall()
        return {row["case_id"]: json.loads(row["record"]) for row in rows}

    def ingest(self, fingerprint, records):
        self.batch(fingerprint)
        with self._db() as database:
            for case_id, record in records.items():
                encoded = _canonical(record)
                existing = database.execute(
                    "SELECT record FROM refs WHERE fingerprint = ? AND case_id = ?",
                    (fingerprint, case_id),
                ).fetchone()
                if existing is not None and existing["record"] != encoded:
                    raise CoolingAdapterError("cooling_reference_changed")
                database.execute(
                    "INSERT OR IGNORE INTO refs VALUES (?, ?, ?)",
                    (fingerprint, case_id, encoded),
                )

    def open_pool(self, case_count):
        with self._db() as database:
            batches = database.execute(
                "SELECT fingerprint FROM batches ORDER BY fingerprint"
            ).fetchall()
            complete = []
            for row in batches:
                count = database.execute(
                    "SELECT COUNT(*) FROM refs WHERE fingerprint = ?",
                    (row["fingerprint"],),
                ).fetchone()[0]
                if count == case_count:
                    complete.append(row["fingerprint"])
            if len(complete) != 1:
                raise CoolingAdapterError("cooling_public_references_incomplete")
            fingerprint = complete[0]
            current = database.execute(
                "SELECT fingerprint FROM pool WHERE singleton = 1"
            ).fetchone()
            if current is not None and current["fingerprint"] != fingerprint:
                raise CoolingAdapterError("cooling_pool_identity_changed")
            database.execute(
                "INSERT OR IGNORE INTO pool VALUES (1, ?)", (fingerprint,)
            )
            database.execute(
                "UPDATE batches SET state = 'OPEN' WHERE fingerprint = ?",
                (fingerprint,),
            )
        return fingerprint

    def active_pool(self):
        with self._db() as database:
            row = database.execute(
                "SELECT fingerprint FROM pool WHERE singleton = 1"
            ).fetchone()
        return None if row is None else row["fingerprint"]

    def record_submission(self, submission_id, hotkey, strategy, outcome, score_record):
        values = (
            submission_id,
            hotkey,
            _canonical(strategy),
            _canonical(outcome),
            None if score_record is None else _canonical(score_record),
        )
        with self._db() as database:
            existing = database.execute(
                "SELECT hotkey, strategy, outcome, score_record FROM submissions "
                "WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != values[1:]:
                    raise CoolingAdapterError("cooling_submission_identity_collision")
                return
            database.execute("INSERT INTO submissions VALUES (?, ?, ?, ?, ?)", values)

    def submission(self, submission_id):
        with self._db() as database:
            row = database.execute(
                "SELECT hotkey, outcome, score_record FROM submissions "
                "WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "hotkey": row["hotkey"],
            "outcome": json.loads(row["outcome"]),
            "score_record": (
                None if row["score_record"] is None else json.loads(row["score_record"])
            ),
        }

    def status(self):
        with self._db() as database:
            batches = database.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
            references = database.execute("SELECT COUNT(*) FROM refs").fetchone()[0]
            submissions = database.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0]
            scored = database.execute(
                "SELECT COUNT(*) FROM submissions WHERE score_record IS NOT NULL"
            ).fetchone()[0]
            pool = database.execute(
                "SELECT fingerprint FROM pool WHERE singleton = 1"
            ).fetchone()
        return {
            "batches": batches,
            "references": references,
            "pool_open": pool is not None,
            "submissions": submissions,
            "scored": scored,
        }


class CoolingAdapter(ChallengeAdapter):
    """The registered Cooling Level-0 contract behind Interface v1."""

    challenge_id = CHALLENGE.challenge_id
    challenge_version = CHALLENGE.version
    contract_digest = contract(CHALLENGE.challenge_id).digest
    max_strategy_bytes = MAX_STRATEGY_BYTES
    disclosure_fields = frozenset(
        {"score", "eligible", "n_cases", "n_scored", "n_gate_failed"}
    )

    def __init__(self, root, *, repository="."):
        self.repository = Path(repository)
        self.material = PublicMaterial.load(self.repository)
        self.store = CoolingStore(root)
        rule = rule_document(self.material)
        self._identities = {
            "schema": ADAPTER_SCHEMA,
            "contract_digest": self.contract_digest,
            "rule_digest": digest(rule),
            "implementation_digest": implementation_digest(),
            "public_material": rule["public_material"],
            "reference_solver_image": IMAGE,
            "evidence": EVIDENCE,
        }
        self._practice = {
            record["case_id"]: _copy(record) for record in self.material.practice
        }

    def identities(self):
        return _copy(self._identities)

    def disclosure_budget(self):
        return None

    def _submission_id(self, submission):
        identity = digest(
            {
                "hotkey": submission.hotkey,
                "receipt": submission.receipt,
                "challenge_id": submission.challenge_id,
                "challenge_version": submission.challenge_version,
                "strategy": submission.strategy,
                "contract_digest": submission.contract_digest,
            }
        )
        return "cooling-" + identity.removeprefix("sha256:")

    def _outcome(self, submission_id, state, *, failure=None, summary=None):
        outcome = {
            "schema": OUTCOME_SCHEMA,
            "submission_id": submission_id,
            "challenge": {"id": self.challenge_id, "version": self.challenge_version},
            "state": state,
            "evidence": EVIDENCE,
            "qualification": False,
            "reward": False,
        }
        if failure is not None:
            outcome["failure"] = failure
        if summary is not None:
            outcome.update(
                score=summary["score"],
                eligible=summary["eligible"],
                n_cases=summary["n_cases"],
                n_scored=summary["n_scored"],
                n_gate_failed=summary["n_gate_failed"],
            )
        return outcome

    @staticmethod
    def _issues(refused):
        issues = []
        for issue in refused.rejected.issues:
            path = issue.path
            if type(path) is tuple:
                path = list(path)
            issues.append({"code": issue.code, "path": path})
        return issues

    def evaluate(self, submission):
        if type(submission) is not Admitted:
            raise TypeError("an admitted submission is required")
        fingerprint = self.store.active_pool()
        if fingerprint is None:
            raise Unavailable("cooling_public_practice_pool_not_open")
        submission_id = self._submission_id(submission)
        existing = self.store.submission(submission_id)
        if existing is not None:
            return existing["outcome"]
        try:
            _compiled, recipe = compile_recipe(submission.strategy)
        except RecipeRejected as refused:
            outcome = self._outcome(
                submission_id,
                "INVALID_CONSTRUCTION",
                failure={"code": "recipe_rejected", "issues": self._issues(refused)},
            )
            self.store.record_submission(
                submission_id, submission.hotkey, submission.strategy, outcome, None
            )
            return outcome

        model = rebuild(recipe, self.material)
        references = self.store.references(fingerprint)
        predictions = {
            case_id: model.predict(record["inputs"])
            for case_id, record in references.items()
        }
        scales = exam.scales_from_train(self.material.train)
        rows = [
            exam.score_case(predictions[case_id], references[case_id], scales)
            for case_id in sorted(references)
        ]
        summary = exam.aggregate(rows)
        outcome = self._outcome(submission_id, "SCORED", summary=summary)
        score_record = {
            "schema": SCORE_RECORD_SCHEMA,
            "submission_id": submission_id,
            "pool_fingerprint": fingerprint,
            "rule_digest": self._identities["rule_digest"],
            "implementation_digest": self._identities["implementation_digest"],
            "recipe": recipe.document(),
            "recipe_digest": recipe.recipe_digest,
            "aggregate": summary,
            "cases": rows,
            "predictions": predictions,
        }
        self.store.record_submission(
            submission_id, submission.hotkey, submission.strategy, outcome, score_record
        )
        return outcome

    def outcome(self, submission_id):
        record = self.store.submission(submission_id)
        if record is None:
            raise LookupError("unknown_submission")
        return record["outcome"]

    def owner(self, submission_id):
        record = self.store.submission(submission_id)
        return None if record is None else record["hotkey"]

    def advance(self):
        return 0

    def score_record(self, submission_id):
        record = self.store.submission(submission_id)
        if record is None or record["score_record"] is None:
            raise LookupError("not_scored")
        return record["score_record"]

    def sealed_roles(self):
        return set()

    def _prepare_batch(self, role, *, kind, **options):
        if kind != PUBLIC_BATCH_KIND:
            raise CoolingAdapterError("cooling_batch_kind_not_served")
        if options:
            raise CoolingAdapterError("cooling_public_batch_takes_no_options")
        document = {
            "schema": BATCH_SCHEMA,
            "challenge": {"id": self.challenge_id, "version": self.challenge_version},
            "role": role,
            "kind": kind,
            "evidence": EVIDENCE,
            "practice_sha256": "sha256:" + PRACTICE_SHA256,
            "cases": [
                {"case_id": record["case_id"], "inputs": record["inputs"]}
                for record in self.material.practice
            ],
        }
        return self.store.prepare(role, kind, document)

    def reference_jobs(self, fingerprint):
        document, _state = self.store.batch(fingerprint)
        found = self.store.references(fingerprint)
        return [
            {
                "case_id": case["case_id"],
                "inputs": case["inputs"],
                "reference": "PINNED_PUBLIC_PRACTICE",
                "solver_image": IMAGE,
            }
            for case in document["cases"]
            if case["case_id"] not in found
        ]

    def ingest_references(self, fingerprint, records):
        document, _state = self.store.batch(fingerprint)
        cases = {case["case_id"] for case in document["cases"]}
        if type(records) not in (list, tuple):
            raise CoolingAdapterError("cooling_reference_records_malformed")
        validated = {}
        for record in records:
            if type(record) is not dict or type(record.get("case_id")) is not str:
                raise CoolingAdapterError("cooling_reference_record_malformed")
            case_id = record["case_id"]
            if case_id in validated:
                raise CoolingAdapterError("cooling_reference_case_duplicate")
            if case_id not in cases:
                raise CoolingAdapterError("cooling_reference_case_not_in_batch")
            if _canonical(record) != _canonical(self._practice[case_id]):
                raise CoolingAdapterError("cooling_reference_record_mismatch")
            validated[case_id] = record
        self.store.ingest(fingerprint, validated)
        return not self.reference_jobs(fingerprint)

    def open_pool(self):
        return self.store.open_pool(len(self.material.practice))

    def status(self):
        return {
            "schema": STORE_SCHEMA,
            "evidence": EVIDENCE,
            **self.store.status(),
        }


__all__ = [
    "EVIDENCE",
    "PUBLIC_BATCH_KIND",
    "CoolingAdapter",
    "CoolingAdapterError",
    "CoolingStore",
    "implementation_digest",
    "rule_document",
]
