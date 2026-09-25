"""The battery evaluation deployment: where a submitted recipe is judged.

The operator configures it; a miner cannot reach any of its inputs. The
configuration names owner-only files:
- the private root (`seeds.PrivateRoot`);
- the append-only seed journal;
- the plaintext of the batches the operator generated and committed;
- the truth service's reference records;
- a private results log.

Evaluation authority is separate from research access. The grading reference
is Carbon's own, from the truth service. A miner supplies only a declarative
recipe, so no miner artifact can stand in for a reference, a case or a
prediction.

Everything fails closed before any score:
- a batch whose fingerprint is not in the journal is refused (`recall`);
- a retired batch is never scored again;
- a case with no terminal reference stops the deployment from loading.

A rebuild or prediction failure is `FAILED_INFRA`, and a contract refusal is
`REFUSED`. Neither is a score.

Limitation, stated rather than hidden: the rebuild runs in this trusted
process (`DIRECT_TRUSTED_PROCESS`), not in the validator's isolated
reconstruction worker. Each result says so. The screening pool's rotation
state lives for the life of the process. A restart resumes from the journal:
retired batches stay retired, but the admitted-since-rotation count starts
again. The persistent validator daemon (M3) owns durable pool state.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.challenge_contracts import SubmissionRefused

from . import exam
from .challenge import CHALLENGE, PublicMaterial
from .seeds import PrivateBatch, PrivateRoot, SeedJournal, reconstruction_seed
from .shadow import DIRECT_RECONSTRUCTION, ShadowPool

SCHEMA = "carbon.battery.evaluation-deployment.v1"
RESULT_SCHEMA = "carbon.battery.evaluation-outcome.v1"


class EvaluationUnavailable(RuntimeError):
    """The deployment cannot evaluate: an infrastructure state, never a score."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _private(path):
    path = Path(path)
    try:
        info = os.lstat(path)
    except OSError:
        raise EvaluationUnavailable("evaluation_input_missing") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise EvaluationUnavailable("evaluation_input_not_regular")
    if info.st_mode & 0o077:
        raise EvaluationUnavailable("evaluation_input_not_owner_only")
    return path


def _json_default(value):
    import numpy as np

    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


@dataclass
class EvaluationDeployment:
    root: PrivateRoot
    journal: SeedJournal
    pool: ShadowPool
    results: Path

    @staticmethod
    def load(config_path, *, repository="."):
        """Load an operator configuration; refuse anything incomplete."""
        config = json.loads(_private(config_path).read_bytes())
        if config.get("schema") != SCHEMA:
            raise EvaluationUnavailable("evaluation_config_schema")
        root = PrivateRoot.load(_private(config["private_root"]))
        journal = SeedJournal(config["journal"])
        journal.root_pin(root)  # the root this deployment holds was committed
        retired = journal.retired()
        committed = []
        for document in json.loads(_private(config["batches"]).read_bytes()):
            batch = PrivateBatch.from_document(document)
            if batch.fingerprint in retired:
                continue
            try:
                committed.append(journal.recall(batch))
            except ValueError:
                raise EvaluationUnavailable("evaluation_batch_uncommitted") from None
        references = {}
        for line in _private(config["references"]).read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                if not record.get("refined"):
                    references[record["case_id"]] = record
        needed = {c for item in committed for c, _ in item.batch.cases}
        needed -= {d for item in committed for d, _ in item.batch.duplicates}
        terminal = {"OK", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT"}
        if any(references.get(c, {}).get("status") not in terminal for c in needed):
            raise EvaluationUnavailable("evaluation_references_incomplete")
        if len(committed) < exam.DEVELOPMENT_RULE["active_batches"]:
            raise EvaluationUnavailable("evaluation_pool_exhausted")
        pool = ShadowPool(
            committed,
            references,
            PublicMaterial.load(repository),
            journal,
            root=repository,
        )
        return EvaluationDeployment(root, journal, pool, Path(config["results"]))

    def _log(self, record):
        path = self.results
        new = not path.exists()
        with path.open("a") as handle:
            handle.write(
                json.dumps(record, sort_keys=True, default=_json_default) + "\n"
            )
        if new:
            path.chmod(0o600)

    def evaluate(self, submission_id, strategy, contract_digest):
        """Judge one submission. Returns its public outcome."""
        seed = reconstruction_seed(self.root, submission_id)
        base = {
            "schema": RESULT_SCHEMA,
            "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
            "submission_id": submission_id,
        }
        try:
            internal, public = self.pool.score(
                submission_id,
                strategy,
                contract_digest,
                seed,
                reconstruction=DIRECT_RECONSTRUCTION,
            )
        except SubmissionRefused as refused:
            outcome = {
                **base,
                "status": "REFUSED",
                "issues": [{"code": i.code, "path": i.path} for i in refused.issues],
                "scored": False,
            }
            self._log({**outcome, "private": None})
            return outcome
        except Exception as failure:  # noqa: BLE001 - infrastructure, typed
            # The submission was admitted but could not be rebuilt or run.
            # Never a scientific result; the submitter may retry.
            self.pool.bank.predictors.pop(submission_id, None)
            outcome = {
                **base,
                "status": "FAILED_INFRA",
                "scored": False,
                "retryable": True,
            }
            self._log({**outcome, "private": {"error": type(failure).__name__}})
            return outcome
        outcome = {**base, "status": "SCORED", "scored": True, "result": public}
        self._log({**outcome, "private": internal})
        return outcome
