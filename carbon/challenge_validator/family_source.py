"""Producer sources for reference families (VALIDATOR-28). Producer-only: no
validator surface imports it.

A Challenge whose hidden batches are drawn from a registered population and
solved by a reference runner is a *family*. What a family supplies is a frozen
`ReferenceFamily`: its population, its reference runner and pinned image (one
CLI contract), its terminal statuses, its document and record checks, and its
registered rule. Everything else is generic and lives here, extracted from
motor's source (VALIDATOR-21) without changing what it commits:

- **Custody.** The family's own root and append-only journal
  (`confirmation.ConfirmationCustody`). Its root commitment is the public
  `seed_pin`.
- **Draw.** `confirmation.make_batch` with the family's population: draws
  keyed by the root and the role, opaque case ids, committed to the journal
  before any use. A role is never redrawn differently, and a case that repeats
  a published case of the family is refused.
- **Solve.** The family's runner, under one contract:
  `RUNNER PLAN --out DIR --parallel N --timeout-s S --keep none`, writing
  `DIR/records.jsonl`. Only cases with no terminal record yet are planned,
  each attempt in a fresh `solve-<n>/` directory, so a rerun resumes.
  `FAILED_INFRA` (any non-terminal status) is retried, never stored.
- **Seal.** The first terminal record per case, checked by the family, stored
  once; the references digest is the validator's own
  (`hidden_batch_store.references_digest`).

The producer looks a family up by Challenge (`family_source_class`); battery
keeps its own source (its quiz and duplicates). DEVELOPMENT only: no
qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .batch_source import BatchSource, ProducerRefused
from .interface import canonical_role, digest, role_reserved

REPOSITORY = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ReferenceFamily:
    """One family's registration. Values a family does not yet have stay
    unregistered: there is no default, so a family is served only once every
    field is set (fail closed)."""

    #: Short name: the store's name and the prefix of its error codes.
    name: str
    challenge_id: str
    challenge_version: str
    #: The hidden batch document's schema and the population version it names.
    document_schema: str
    population_version: str
    #: Registered rule values: served kinds, batch size, rotation cadence.
    kinds: tuple
    batch_cases: int
    every_blocks: int
    active_batches: int
    #: The reference runner (a path in the repository) and its pinned image,
    #: passed to the runner in `image_env`.
    runner: Path
    image: str
    image_env: str
    #: Terminal record statuses: anything else is retried, never stored.
    terminal: tuple
    #: The family's errors (its store, deployment and checks raise this type,
    #: with a `code` starting `<name>_`).
    error_type: type
    #: Callables, each the family's own.
    population: Callable[[], Any]
    rule: Callable[[Path], dict]
    contract_digest: Callable[[], str]
    load_deployment: Callable[[Any], dict]
    open_store: Callable[[Any], Any]
    check_document: Callable[[dict], dict]
    check_reference: Callable[[dict, dict], None]
    published_keys: Callable[[Path], set]
    overlap_key: Callable[[dict], Any]

    def code(self, error):
        """A family error's code as a producer refusal."""
        return "producer_" + error.code.removeprefix(self.name + "_")


class FamilySource(BatchSource):
    """A family's hidden batches, drawn and solved once on the producer."""

    def __init__(self, family, deployment, *, repository=REPOSITORY, runner=None):
        from .confirmation import ConfirmationCustody, ConfirmationRefused

        self.family = family
        self.challenge_id = family.challenge_id
        self.repository = Path(repository)
        self.runner = runner
        config = family.load_deployment(deployment)
        if "custody" not in config:
            raise ProducerRefused(f"producer_{family.name}_no_custody")
        try:
            self.custody = ConfirmationCustody(config["custody"], self.challenge_id)
        except ConfirmationRefused as refused:
            raise ProducerRefused("producer_" + refused.code) from None
        try:
            self.store = family.open_store(config["store"])
        except family.error_type as refused:
            raise ProducerRefused(family.code(refused)) from None
        self.population = family.population()
        self.rule = family.rule(self.repository)
        self.rule_digest = digest(self.rule)
        self.contract_digest = family.contract_digest()
        self._published = None

    @staticmethod
    def init_custody(family, deployment):
        """Create the family's producer custody once; return its public pin."""
        from .confirmation import ConfirmationCustody, ConfirmationRefused

        config = family.load_deployment(deployment)
        if "custody" not in config:
            raise ProducerRefused(f"producer_{family.name}_no_custody")
        try:
            custody, _entry = ConfirmationCustody.init(
                config["custody"], family.challenge_id
            )
        except ConfirmationRefused as refused:
            raise ProducerRefused("producer_" + refused.code) from None
        family.open_store(config["store"])
        return {"seed_pin": custody.root().commitment()}

    def identities(self):
        return {
            "contract_digest": self.contract_digest,
            "rule_digest": self.rule_digest,
            "seed_pin": self.custody.root().commitment(),
        }

    def kinds(self):
        return self.family.kinds

    def cadence(self):
        return {
            "every_blocks": self.family.every_blocks,
            "active": self.family.active_batches,
        }

    # --- draw -----------------------------------------------------------------

    def _item(self, role):
        return SimpleNamespace(
            challenge_id=self.challenge_id,
            role=role,
            cases=self.family.batch_cases,
            hidden_duplicates=0,
            strata=[],
            sampling_law={"id": self.family.population_version},
            digest=self.rule_digest,
        )

    def _document(self, role, kind):
        """The batch `role` draws from the root: deterministic."""
        from .confirmation import make_batch

        family = self.family
        sealed = make_batch(self.custody.root(), self.population, self._item(role))
        return {
            "schema": family.document_schema,
            "challenge": {
                "id": family.challenge_id,
                "version": family.challenge_version,
            },
            "role": role,
            "kind": kind,
            "population": family.population_version,
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
        family = self.family
        if kind not in family.kinds:
            raise ProducerRefused("producer_kind_refused")
        if size not in (None, family.batch_cases):
            raise ProducerRefused("producer_size_not_registered")
        if type(role) is not str or not role or role_reserved(role):
            raise ProducerRefused("seed_role_reserved")
        with self.custody.writer():
            document = self._document(role, kind)
            fingerprint = digest(document)
            if self._published is None:
                self._published = family.published_keys(self.repository)
            if any(
                family.overlap_key(case["inputs"]) in self._published
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
            except family.error_type as refused:
                raise ProducerRefused(family.code(refused)) from None

    def _batch(self, fingerprint):
        try:
            return self.store.batch(fingerprint)
        except self.family.error_type:
            raise ProducerRefused("producer_unknown_batch") from None

    def jobs(self, fingerprint):
        cases = self.family.check_document(self._batch(fingerprint)["document"])
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
        family = self.family
        work = Path(work)
        jobs = json.loads((work / "jobs.json").read_text())["jobs"]
        done = {
            record.get("case_id")
            for record in self._records(work / "records.jsonl")
            if record.get("status") in family.terminal
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
            str(self.repository / family.runner),
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
            env={**os.environ, family.image_env: family.image},
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
        family = self.family
        cases = family.check_document(self._batch(fingerprint)["document"])
        chosen = {}
        for record in records:
            case_id = record.get("case_id") if type(record) is dict else None
            if case_id not in cases:
                raise ProducerRefused("producer_reference_case_not_in_batch")
            if record.get("status") not in family.terminal or case_id in chosen:
                continue
            try:
                family.check_reference(record, cases[case_id])
            except ValueError:
                raise ProducerRefused("producer_reference_malformed") from None
            chosen[case_id] = record
        try:
            return self.store.ingest(
                fingerprint, list(chosen.values()), terminal=family.terminal
            )
        except family.error_type as refused:
            raise ProducerRefused(family.code(refused)) from None

    def sealed(self, fingerprint):
        batch = self._batch(fingerprint)
        try:
            references = self.store.complete_digest(fingerprint)
        except self.family.error_type as refused:
            raise ProducerRefused(self.family.code(refused)) from None
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


def _motor():
    from .motor_source import MotorBatchSource

    return MotorBatchSource


#: The registered families, by name: each a function returning its source
#: class, imported only when the producer serves that Challenge (a static
#: import, never a dynamic one).
FAMILY_SOURCES = {"motor": _motor}


def family_source_class(challenge_id):
    """The registered family source class for `challenge_id`, or None."""
    from carbon.reconstruction.capability_registry import MOTOR_CHALLENGE

    names = {MOTOR_CHALLENGE: "motor"}
    if challenge_id not in names:
        return None
    return FAMILY_SOURCES[names[challenge_id]]()


__all__ = ["FAMILY_SOURCES", "FamilySource", "ReferenceFamily", "family_source_class"]
