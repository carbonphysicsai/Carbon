"""Motor's hidden batches for the producer (VALIDATOR-21;
OWNER-MOTOR-HIDDEN-POOL-01). Producer-only: no validator surface imports it.

- **Custody (WRAP).** The producer's motor root and append-only journal are a
  `confirmation.ConfirmationCustody` of their own, separate from battery's
  root and from every confirmation set's. Its root commitment is the
  commitment's public `seed_pin`.
- **Draw (WRAP).** `confirmation.make_batch` with motor's
  `PopulationSource`: uniform draws (Q = P) keyed by the root and the role,
  with opaque case ids, no strata and no hidden duplicates. The batch is
  committed to the journal before any use. A role is never redrawn
  differently, and a case that repeats a published motor case is refused.
- **Solve.** `scripts/dev/motor/reference/run_batch.py` in the image pinned
  by OWNER-DATA-MOTOR-01, only for cases with no terminal record yet, into a
  fresh `solve-<n>/` directory whose records are appended to
  `records.jsonl`. A rerun therefore resumes. `FAILED_INFRA` is retried,
  never stored.
- **Seal.** The terminal records are checked (their own inputs, the pinned
  image, an `OK` record's curve) and stored once. The references digest is
  the validator's own (`hidden_batch_store.references_digest`).

    python -m carbon.challenge_validator.motor_source init --deployment DEPLOYMENT.json

`init` creates the custody once and prints only its public `seed_pin`.
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from .batch_source import BatchSource, ProducerRefused
from .interface import canonical_role, digest, role_reserved
from .motor import MotorAdapterError
from .motor_hidden import (
    ACTIVE_BATCHES,
    BATCH_CASES,
    DOCUMENT_SCHEMA,
    KINDS,
    ROTATION_EVERY_BLOCKS,
    SOLVER_IMAGE,
    TERMINAL,
    check_document,
    check_reference,
    hidden_rule,
    load_deployment,
    open_store,
    overlap_key,
    published_keys,
)

REPOSITORY = Path(__file__).resolve().parents[2]
RUN_BATCH = Path("scripts/dev/motor/reference/run_batch.py")


def _producer_code(error):
    return "producer_" + error.code.removeprefix("motor_")


class MotorBatchSource(BatchSource):
    """Motor's hidden batches, drawn and solved once on the producer."""

    def __init__(self, deployment, *, repository=REPOSITORY, runner=None):
        from carbon.motor.challenge import CHALLENGE, PublicMaterial
        from carbon.reconstruction.capability_registry import contract

        from .confirmation import ConfirmationCustody, ConfirmationRefused
        from .confirmation_sources import source_for

        self.challenge_id = CHALLENGE.challenge_id
        self.repository = Path(repository)
        self.runner = runner
        config = load_deployment(deployment)
        if "custody" not in config:
            raise ProducerRefused("producer_motor_no_custody")
        try:
            self.custody = ConfirmationCustody(config["custody"], self.challenge_id)
        except ConfirmationRefused as refused:
            raise ProducerRefused("producer_" + refused.code) from None
        try:
            self.store = open_store(config["store"])
        except MotorAdapterError as refused:
            raise ProducerRefused(_producer_code(refused)) from None
        self.population = source_for(self.challenge_id)
        self.rule = hidden_rule(PublicMaterial.load(self.repository))
        self.rule_digest = digest(self.rule)
        self.contract_digest = contract(self.challenge_id).digest
        self._published = None

    @staticmethod
    def init(deployment):
        """Create the producer's motor custody once; return its public pin."""
        from carbon.motor.challenge import CHALLENGE

        from .confirmation import ConfirmationCustody, ConfirmationRefused

        config = load_deployment(deployment)
        if "custody" not in config:
            raise ProducerRefused("producer_motor_no_custody")
        try:
            custody, _entry = ConfirmationCustody.init(
                config["custody"], CHALLENGE.challenge_id
            )
        except ConfirmationRefused as refused:
            raise ProducerRefused("producer_" + refused.code) from None
        open_store(config["store"])
        return {"seed_pin": custody.root().commitment()}

    def identities(self):
        return {
            "contract_digest": self.contract_digest,
            "rule_digest": self.rule_digest,
            "seed_pin": self.custody.root().commitment(),
        }

    def kinds(self):
        return KINDS

    def cadence(self):
        return {"every_blocks": ROTATION_EVERY_BLOCKS, "active": ACTIVE_BATCHES}

    # --- draw -----------------------------------------------------------------

    def _item(self, role):
        from carbon.motor.population import POPULATION_VERSION

        return SimpleNamespace(
            challenge_id=self.challenge_id,
            role=role,
            cases=BATCH_CASES,
            hidden_duplicates=0,
            strata=[],
            sampling_law={"id": POPULATION_VERSION},
            digest=self.rule_digest,
        )

    def _document(self, role, kind):
        """The batch `role` draws from the root: deterministic."""
        from carbon.motor.population import POPULATION_VERSION

        from .confirmation import make_batch
        from .motor import CHALLENGE

        sealed = make_batch(self.custody.root(), self.population, self._item(role))
        return {
            "schema": DOCUMENT_SCHEMA,
            "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
            "role": role,
            "kind": kind,
            "population": POPULATION_VERSION,
            "cases": [
                {"case_id": case_id, "inputs": inputs}
                for case_id, inputs in sorted(sealed.inputs().items())
            ],
        }

    def _journaled(self, role):
        return [
            entry
            for entry in self.custody.batches()
            if canonical_role(entry.get("role")) == canonical_role(role)
        ]

    def draw(self, role, *, kind, size=None):
        if kind not in KINDS:
            raise ProducerRefused("producer_kind_refused")
        if size not in (None, BATCH_CASES):
            raise ProducerRefused("producer_size_not_registered")
        if type(role) is not str or not role or role_reserved(role):
            raise ProducerRefused("seed_role_reserved")
        with self.custody.writer():
            document = self._document(role, kind)
            fingerprint = digest(document)
            if self._published is None:
                self._published = published_keys(self.repository)
            if any(
                overlap_key(case["inputs"]) in self._published
                for case in document["cases"]
            ):
                raise ProducerRefused("producer_published_case")
            journaled = self._journaled(role)
            if any(entry["fingerprint"] != fingerprint for entry in journaled):
                raise ProducerRefused("producer_role_reused")
            if journaled:
                entry = journaled[0]
            else:
                entry = self.custody.commit(
                    SimpleNamespace(
                        challenge_id=self.challenge_id,
                        role=role,
                        fingerprint=fingerprint,
                        cases=document["cases"],
                    ),
                    self._item(role),
                )
            try:
                return self.store.add(
                    document, role=role, kind=kind, sequence=entry["sequence"]
                )
            except MotorAdapterError as refused:
                raise ProducerRefused(_producer_code(refused)) from None

    def _batch(self, fingerprint):
        try:
            return self.store.batch(fingerprint)
        except MotorAdapterError:
            raise ProducerRefused("producer_unknown_batch") from None

    def jobs(self, fingerprint):
        cases = check_document(self._batch(fingerprint)["document"])
        pending = set(self.store.pending(fingerprint))
        return [
            {"case_id": case_id, "inputs": inputs}
            for case_id, inputs in sorted(cases.items())
            if case_id in pending
        ]

    # --- solve ----------------------------------------------------------------

    @staticmethod
    def _records(path):
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line]

    def solve(self, work, *, workers=6, timeout_s=7200.0):
        """Solve every job with no terminal record yet, in the pinned image.
        Resumable: each run plans only what is left, in its own directory."""
        work = Path(work)
        jobs = json.loads((work / "jobs.json").read_text())["jobs"]
        done = {
            record.get("case_id")
            for record in self._records(work / "records.jsonl")
            if record.get("status") in TERMINAL
        }
        left = [job for job in jobs if job["case_id"] not in done]
        if not left:
            return {"returncode": 0, "solved": 0}
        attempt = len(list(work.glob("solve-*")))
        plan = work / f"plan-{attempt}.json"
        fd = os.open(plan, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(
                {
                    "batch": f"hidden-{attempt}",
                    "cases": [
                        {
                            "case_id": j["case_id"],
                            "kind": "ordinary",
                            "inputs": j["inputs"],
                        }
                        for j in left
                    ],
                },
                handle,
            )
        out = work / f"solve-{attempt}"
        out.mkdir(mode=0o700)
        command = [
            sys.executable,
            str(self.repository / RUN_BATCH),
            str(plan),
            "--out",
            str(out),
            "--parallel",
            str(workers),
            "--timeout-s",
            str(timeout_s),
            "--keep",
            "none",
        ]
        completed = (self.runner or subprocess.run)(
            command,
            check=False,
            cwd=self.repository,
            env={**os.environ, "CARBON_MOTOR_IMAGE": SOLVER_IMAGE},
        )
        solved = self._records(out / "records.jsonl")
        fd = os.open(
            work / "records.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600
        )
        with os.fdopen(fd, "a") as handle:
            for record in solved:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        return {"returncode": completed.returncode, "solved": len(solved)}

    # --- seal -----------------------------------------------------------------

    def ingest(self, fingerprint, records):
        """The first terminal record per case, checked, stored once. Later
        attempts' records for a case are ignored; a non-terminal one is
        retried, never stored."""
        cases = check_document(self._batch(fingerprint)["document"])
        chosen = {}
        for record in records:
            case_id = record.get("case_id") if type(record) is dict else None
            if case_id not in cases:
                raise ProducerRefused("producer_reference_case_not_in_batch")
            if record.get("status") not in TERMINAL or case_id in chosen:
                continue
            try:
                check_reference(record, cases[case_id])
            except ValueError:
                raise ProducerRefused("producer_reference_malformed") from None
            chosen[case_id] = record
        try:
            return self.store.ingest(
                fingerprint, list(chosen.values()), terminal=TERMINAL
            )
        except MotorAdapterError as refused:
            raise ProducerRefused(_producer_code(refused)) from None

    def sealed(self, fingerprint):
        batch = self._batch(fingerprint)
        try:
            references = self.store.complete_digest(fingerprint)
        except MotorAdapterError as refused:
            raise ProducerRefused(_producer_code(refused)) from None
        if references is None:
            return None
        return {
            "role": batch["role"],
            "kind": batch["kind"],
            "journal_sequence": batch["sequence"],
            "cases": len(batch["document"]["cases"]),
            "references_digest": references,
        }

    def export(self, fingerprint):
        if self.sealed(fingerprint) is None:
            raise ProducerRefused("producer_references_pending")
        return {
            "document": self._batch(fingerprint)["document"],
            "references": self.store.references(fingerprint),
        }

    def check(self, fingerprint):
        """The stored batch is the one its role draws from the root, and the
        journal committed it under that sequence."""
        batch = self._batch(fingerprint)
        if digest(batch["document"]) != fingerprint:
            raise ProducerRefused("producer_fingerprint_mismatch")
        if self._document(batch["role"], batch["kind"]) != batch["document"]:
            raise ProducerRefused("producer_fingerprint_mismatch")
        journaled = [
            e for e in self._journaled(batch["role"]) if e["fingerprint"] == fingerprint
        ]
        if not journaled:
            raise ProducerRefused("producer_not_committed")
        if journaled[0]["sequence"] != batch["sequence"]:
            raise ProducerRefused("producer_sequence_mismatch")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.motor_source")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("--deployment", required=True)
    args = parser.parse_args(argv)
    try:
        result = MotorBatchSource.init(args.deployment)
    except (ProducerRefused, MotorAdapterError) as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    import sys

    from carbon.challenge_validator.motor_source import main as _main

    sys.exit(_main())


__all__ = ["MotorBatchSource"]
