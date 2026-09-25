"""The battery validator daemon (M3): admission, screening and finalist comparison.

It implements the approved battery exam (OWNER-BATTERY-TESTNET-01, OD-2), with
every rule taken from `exam` unchanged.

**Admission** (`admit`) takes a request the signed transport has already
authenticated, then:
1. checks the miner's on-chain commitment when one is required (OD-7);
2. resolves the Challenge and version;
3. checks the construction-contract digest;
4. compiles through battery's own compiler;
5. binds the approved identities to the admission record: public TRAIN v1,
   the OCV table, the recipe, Carbon's implementation, the rule, the frozen
   calibration, the backend and the resource envelope.

A refused construction is recorded as `INVALID_CONSTRUCTION`; it is never
scored and never counted.

**Screening** (`process`):
1. rebuild once in an isolated worker, with Carbon's seed;
2. infer the whole active pool - three batches, 300 cases - in a separate
   worker that sees inputs only;
3. apply every gate across the full pool, and score it on the trusted host
   against the validator-owned references;
4. bring the incumbent onto the same pool version by inference, never by
   retraining, and apply `exam.nominate`.

The score, the admitted count and any due rotation are committed together.

**Finalist comparison** (`process_finals`) runs only for a nominee:
1. freeze the comparison rule and both identities;
2. assign a prepared set of fresh private cases;
3. rebuild incumbent and challenger freshly, with matched seeds;
4. infer both on the fresh cases, gate them, and apply `exam.final_compare`.

Only IMPROVEMENT promotes, and the actual outcome is recorded, whatever it is.

**Outcomes are kept distinct:** invalid construction, candidate reconstruction
or prediction failure, gate failure, reference failure (withdrawn for every
model), infrastructure failure (retried, never a score) and insufficient
evidence.

**Operational resolutions** (named, reversible, recorded as M3-D decisions;
none of them changes the rule):
- `ROTATION_PENDING`: when a rotation is due and no complete batch is
  prepared, admissions queue and nothing is scored until a batch is ready.
- The first eligible screened submission on an empty frontier becomes the
  incumbent, as in the approved campaign replay.
- Each finalist comparison uses one prepared fresh set, which is consumed.

Scientific results never become chain actions here. The only weight intent is
Phase A all-burn (OD-4a), signed with the Carbon service key and handed to the
owner publisher. Winner weights (OD-4b) are not authorized.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass

import numpy as np

from carbon.challenge_registry import ResolutionError, resolve
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
)

from . import exam
from .challenge import (
    CHALLENGE,
    OCV_TABLE_SHA256,
    TRAIN_V1_SHA256,
    PublicMaterial,
)
from .pool_store import PoolStore, StateError, canonical
from .seeds import PrivateBatch, make_batch, reconstruction_seed
from .shadow import PREPARE_SHA256, SHAPES, frozen_calibration
from .worker import WorkerFailure

SCHEMA = "carbon.battery.validator-outcome.v1"
SUBMIT_TOOL = "battery_submit"
RULE = exam.DEVELOPMENT_RULE


def _digest(value):
    body = value if type(value) is bytes else canonical(value).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def rule_digest():
    return _digest(RULE)


def commitment_digest(challenge, contract_digest, strategy_hash):
    """What a miner commits on chain for a battery submission (OD-7)."""
    return _digest(
        {
            "schema": "carbon.battery.commitment.v1",
            "challenge": challenge,
            "contract_digest": contract_digest,
            "strategy_hash": strategy_hash,
        }
    )


@dataclass(frozen=True)
class AuthenticatedSubmission:
    """A submission whose signer the transport has verified.

    Built only from a gateway `ReceivedCall` (`from_received`): the hotkey is
    the journal-resolved identity, never a field the miner typed.
    """

    hotkey: str
    receipt: dict
    challenge_id: str
    challenge_version: str
    strategy: object
    contract_digest: object

    @staticmethod
    def from_received(received, gateway):
        call = received.call
        if call.tool != SUBMIT_TOOL:
            raise ValueError("not a battery submission call")
        fields = {f.name: f.value for f in call.fields}
        if set(fields) != {"strategy_json", "contract_digest"}:
            raise ValueError("closed submission fields required")
        strategy = json.loads(fields["strategy_json"])
        receipt = received.receipt
        return AuthenticatedSubmission(
            hotkey=receipt.hotkey,
            receipt={"sequence": receipt.ref.sequence, "digest": receipt.ref.digest},
            challenge_id=gateway.challenge.challenge_id,
            challenge_version=gateway.challenge.version,
            strategy=strategy,
            contract_digest=fields["contract_digest"],
        )


class CommitmentRequired(PermissionError):
    """The miner has not committed this submission on chain."""


class PublishedCaseRefused(ValueError):
    """A batch that repeats a published campaign case cannot be hidden."""


EVIDENCE = "docs/development/evidence/exam-design-2026-09-24"


def published_inputs(repository="."):
    """Every input tuple the exam-design campaign published, rounded as drawn.

    Its TRAIN, PRACTICE, FINAL and VERIFY roles and its revealed private
    screening and finalist cases are development examples, never fresh hidden
    testnet cases.
    """
    from pathlib import Path

    from .challenge import INPUTS

    root = Path(repository) / EVIDENCE
    seen = set()
    cases = json.loads((root / "datasets/inputs.json").read_text())["cases"]
    seen.update(tuple(round(c[k], 4) for k in INPUTS) for c in cases)
    for path in root.glob("refs-*/out/**/records.jsonl"):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            if record.get("inputs") and set(INPUTS) <= set(record["inputs"]):
                seen.add(tuple(round(record["inputs"][k], 4) for k in INPUTS))
    return seen


class BatteryValidator:
    """One validator instance over one durable state file."""

    def __init__(
        self,
        *,
        store,
        backend,
        root,
        journal,
        repository=".",
        commitments=None,
        require_commitment=True,
        service_key=None,
        allow_published_cases=False,
    ):
        if type(store) is not PoolStore:
            raise TypeError("a PoolStore is required")
        self.store, self.backend, self.root, self.journal = (
            store,
            backend,
            root,
            journal,
        )
        self.repository = repository
        self.commitments = commitments
        self.require_commitment = require_commitment
        self.service_key = service_key
        self.allow_published_cases = allow_published_cases
        self.material = PublicMaterial.load(repository)
        self.tol, self.scales = frozen_calibration(repository)
        self.pin = journal.root_pin(root)

    # --- identities -------------------------------------------------------------

    def identities(self):
        from carbon.reconstruction.capability_registry import contract

        from .contracts import implementation_digest

        registered = contract(CHALLENGE.challenge_id)
        return {
            "schema": "carbon.battery.validator-identities.v1",
            "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
            "contract_digest": registered.digest,
            "rule": RULE,
            "rule_digest": rule_digest(),
            "calibration_sha256": PREPARE_SHA256,
            "train_v1_sha256": TRAIN_V1_SHA256,
            "ocv_table_sha256": OCV_TABLE_SHA256,
            "implementation_digest": implementation_digest(),
            "backend": dict(self.backend.identity),
            "envelope": registered.document()["envelope"],
            "seed_pin": self.pin,
        }

    def start(self):
        """Bind identities (refused if they changed) and resume recovery."""
        self.store.bind(self.identities())
        self.recover()
        return self.status()

    def recover(self):
        """Settle what a crash may have left mid-way. Never dispatches work."""
        ledger = getattr(self.backend, "ledger", None)
        if ledger is not None:
            for identity in ledger.unresolved():
                # A run left RESERVED had its container removed by the carrier's
                # own cleanup or will be removed by the operator's reconcile; it
                # is infrastructure, and the retry uses a new attempt identity.
                ledger.abandon(identity)
        self.store.settle_retirements(self.journal, self._committed)

    def _committed(self, fingerprint):
        document = self.store.batch(fingerprint)["document"]
        return self.journal.recall(PrivateBatch.from_document(document))

    # --- batches ------------------------------------------------------------------

    def prepare_batch(self, role, *, kind, count=None, duplicates=2):
        """Generate, commit and record one private batch (idempotent by role).

        The plaintext is generated from the private root, committed to the
        journal before any use, and kept only in the validator state.
        """
        count = RULE["screening_batch_size"] if count is None else count
        batch = make_batch(self.root, self.pin, role, count, duplicates)
        try:
            committed = self.journal.recall(batch)
        except ValueError:
            committed = self.journal.commit(batch, pool_version=self._pool_version())
        self.store.add_batch(committed, kind=kind)
        return committed.fingerprint

    def import_batch(self, batch, *, kind):
        """Commit and record an externally built batch (tests, replays).

        Refused when any case repeats a published campaign case, unless this
        validator was built with `allow_published_cases=True` - which only a
        test fixture does, never a deployment.
        """
        from .challenge import INPUTS

        if type(batch) is not PrivateBatch:
            raise TypeError("a PrivateBatch is required")
        if not self.allow_published_cases:
            published = published_inputs(self.repository)
            for _case_id, inputs in batch.cases:
                values = dict(inputs)
                if tuple(round(values[k], 4) for k in INPUTS) in published:
                    raise PublishedCaseRefused(
                        "a published campaign case cannot be a hidden case"
                    )
        try:
            committed = self.journal.recall(batch)
        except ValueError:
            committed = self.journal.commit(batch, pool_version=self._pool_version())
        self.store.add_batch(committed, kind=kind)
        return committed.fingerprint

    def _pool_version(self):
        pool = self.store.pool()
        return 0 if pool is None else pool["version"]

    def reference_jobs(self, fingerprint):
        """What the truth service must solve for a batch: each distinct input
        once (hidden duplicates reuse their original's solve)."""
        needed = set(self.store.needed_cases(fingerprint))
        document = self.store.batch(fingerprint)["document"]
        return [
            {"case_id": c["case_id"], **c["inputs"]}
            for c in document["cases"]
            if c["case_id"] in needed
        ]

    def ingest_references(self, fingerprint, records):
        """Store truth-service records; returns whether the batch is complete."""
        self.store.record_references(fingerprint, records)
        return self.store.complete_references(fingerprint)

    def open_pool(self):
        return self.store.open_pool()

    # --- admission ------------------------------------------------------------------

    def admit(self, submission):
        """Admit one authenticated submission, or refuse it by name.

        Idempotent: the same hotkey resubmitting the same recipe under the same
        contract is the same submission, whatever its transport receipt.
        """
        if type(submission) is not AuthenticatedSubmission:
            raise TypeError("an AuthenticatedSubmission is required")
        request = {
            "hotkey": submission.hotkey,
            "challenge": [submission.challenge_id, submission.challenge_version],
            "strategy": submission.strategy,
            "contract_digest": submission.contract_digest,
        }
        request_digest = _digest(request)
        submission_id = "bsub-" + request_digest[7:39]
        base = {
            "request_digest": request_digest,
            "hotkey": submission.hotkey,
            "challenge": f"{submission.challenge_id}/{submission.challenge_version}",
            "strategy": submission.strategy,
        }

        def refuse(code, issues=()):
            row = self.store.refuse(
                submission_id,
                failure={"code": code, "issues": list(issues)},
                **base,
            )
            return self.outcome(row["submission_id"])

        try:
            resolve(
                submission.challenge_id, submission.challenge_version, "cpu_research"
            )
        except ResolutionError as refused:
            return refuse(refused.code)
        if (submission.challenge_id, submission.challenge_version) != (
            CHALLENGE.challenge_id,
            CHALLENGE.version,
        ) or not isinstance(submission.strategy, dict):
            return refuse("challenge_not_served_here")
        if submission.strategy.get("challenge_id") != CHALLENGE.challenge_id:
            # A strategy naming another Challenge is never reinterpreted here.
            return refuse("cross_challenge_submission")
        try:
            admitted = compile_submission(
                submission.strategy, contract_digest=submission.contract_digest
            )
        except SubmissionRefused as refused:
            return refuse(
                "contract_refused",
                [{"code": i.code, "path": i.path} for i in refused.issues],
            )
        except ValueError as refused:  # RecipeRejected carries named issues
            issues = getattr(getattr(refused, "rejected", None), "issues", ())
            return refuse(
                "recipe_refused",
                [{"code": i.code, "path": list(i.path)} for i in issues],
            )
        recipe = admitted.construction
        commitment = None
        expected = commitment_digest(
            submission.strategy["challenge_id"],
            admitted.contract_digest,
            recipe.strategy_hash,
        )
        if self.require_commitment:
            observed = (
                None
                if self.commitments is None
                else self.commitments.read(submission.hotkey)
            )
            if observed is None or observed.get("digest") != expected:
                raise CommitmentRequired(
                    "commit " + expected + " on chain before submitting"
                )
            commitment = {"digest": expected, "block": observed.get("block")}
        identities = self.identities()
        binding = {
            **{
                k: identities[k]
                for k in (
                    "challenge",
                    "contract_digest",
                    "rule_digest",
                    "calibration_sha256",
                    "train_v1_sha256",
                    "ocv_table_sha256",
                    "implementation_digest",
                    "backend",
                    "envelope",
                )
            },
            "recipe_digest": recipe.recipe_digest,
            "strategy_hash": recipe.strategy_hash,
            "plan_digest": recipe.plan_digest,
            "commitment": commitment,
            "receipt": submission.receipt,
            "attempt": 0,
        }
        row, _new = self.store.admit(submission_id, binding=binding, **base)
        return self.outcome(row["submission_id"])

    # --- screening --------------------------------------------------------------------

    def _recipe(self, row):
        from .compile import compile_recipe

        _, recipe = compile_recipe(row["strategy"])
        if recipe.recipe_digest != row["binding"]["recipe_digest"]:
            # The recipe Carbon would build now is not the one admitted: the
            # compiler or contract changed underneath. Never build silently.
            raise StateError(
                "artifact_mismatch", "recipe digest differs from admission"
            )
        return recipe

    def _seed(self, label):
        tag = hmac.new(self.root._bytes, label.encode(), hashlib.sha256).digest()
        return int.from_bytes(tag[:4], "big")

    def _infer(self, model_id, case_ids, inputs, tag):
        """Stored predictions, completed by inference only for missing cases."""
        have = self.store.predictions(model_id, case_ids)
        missing = [c for c in case_ids if c not in have]
        if missing:
            state = self.store.model_state(model_id)
            if state is None:
                raise StateError("model_not_retained", model_id)
            predictions = self.backend.infer(
                f"inf-{model_id}-{tag}", state["state"], {c: inputs[c] for c in missing}
            )
            if set(predictions) != set(missing):
                raise WorkerFailure("prediction_cases_differ", candidate=True)
            self.store.store_predictions(model_id, predictions)
            have.update(predictions)
        return have

    def _case_store(self, fingerprints):
        refs = self.store.references(fingerprints)
        twins = {}
        for fingerprint in fingerprints:
            twins.update(self.store.batch(fingerprint)["document"]["duplicates"])
        ocv = {
            c: float(
                np.interp(
                    r["inputs"]["soc0"], self.material.ocv_soc, self.material.ocv_v
                )
            )
            for c, r in refs.items()
            if r.get("inputs")
        }
        return exam.CaseStore(refs, ocv, self.tol, self.scales, SHAPES, twins)

    def _reference_identity(self, fingerprints):
        return {f: self.store.batch(f)["references_digest"] for f in fingerprints}

    def process(self, submission_id):
        """Advance one submission as far as it can go now. Restart-safe."""
        row = self.store.submission(submission_id)
        if row["state"] in ("SCORED", "INVALID_CONSTRUCTION", "RECONSTRUCTION_FAILED"):
            return self.outcome(submission_id)
        pool = self.store.pool()
        if pool is None or pool["status"] != "OPEN":
            return self.outcome(submission_id)
        # The attempt number names every worker run. An infrastructure
        # failure moves the submission to the next attempt, so a retry never
        # reuses a run identity that might still be unresolved.
        attempt = row["binding"]["attempt"]
        try:
            recipe = self._recipe(row)
            if self.store.model_state(submission_id) is None:
                state, stats = self.backend.reconstruct(
                    f"rec-{submission_id}-a{attempt}",
                    recipe,
                    reconstruction_seed(self.root, submission_id),
                )
                self.store.retain_model(
                    submission_id,
                    recipe_digest=recipe.recipe_digest,
                    seed=reconstruction_seed(self.root, submission_id),
                    state=state,
                    reconstruction={**self.backend.identity, "fit": stats},
                )
                self.store.mark(submission_id, "RECONSTRUCTED")
            return self._screen(submission_id, attempt)
        except WorkerFailure as failure:
            state = "RECONSTRUCTION_FAILED" if failure.candidate else "FAILED_INFRA"
            self.store.mark(
                submission_id, state, {"code": failure.code, "attempt": attempt}
            )
            if not failure.candidate:
                self._bump_attempt(submission_id, attempt + 1)
            return self.outcome(submission_id)

    def _bump_attempt(self, submission_id, attempt):
        with self.store.transaction() as db:
            binding = json.loads(
                db.execute(
                    "SELECT binding FROM submissions WHERE submission_id=?",
                    (submission_id,),
                ).fetchone()[0]
            )
            binding["attempt"] = attempt
            db.execute(
                "UPDATE submissions SET binding=? WHERE submission_id=?",
                (canonical(binding), submission_id),
            )

    def _screen(self, submission_id, attempt):
        while True:
            pool = self.store.pool()
            if pool["status"] != "OPEN":
                return self.outcome(submission_id)
            ids = self.store.active_case_ids(pool)
            inputs = self.store.case_inputs(pool["active"])
            store = self._case_store(pool["active"])
            preds = self._infer(
                submission_id, ids, inputs, f"v{pool['version']}a{attempt}"
            )
            _rows, agg = exam.evaluate(preds, ids, store)
            incumbent = self.store.incumbent()
            inc_rec = None
            if incumbent is not None and incumbent["model_id"] != submission_id:
                try:
                    inc_preds = self._infer(
                        incumbent["model_id"], ids, inputs, f"v{pool['version']}"
                    )
                except WorkerFailure as failure:
                    # The incumbent's inference, not this candidate's: never
                    # charged to the challenger, which is retried.
                    raise WorkerFailure(
                        "incumbent_inference:" + failure.code, candidate=False
                    ) from None
                _, inc_agg = exam.evaluate(inc_preds, ids, store)
                inc_rec = {**inc_agg, "pool_version": pool["version"]}
            record = {
                "model_id": submission_id,
                "pool_version": pool["version"],
                "active_batches": list(pool["active"]),
                "references": self._reference_identity(pool["active"]),
                "rule_digest": rule_digest(),
                **agg,
            }
            nominated, why = exam.nominate(
                record, inc_rec, RULE["equivalence_margin_rel"]
            )
            record["nomination"] = {
                "nominated": nominated,
                "reason": why,
                "incumbent": None if incumbent is None else incumbent["model_id"],
                "incumbent_score": None if inc_rec is None else inc_rec["score"],
            }
            try:
                self.store.record_score(
                    submission_id,
                    record,
                    self._public_score(record),
                    expected_version=pool["version"],
                )
            except StateError as moved:
                if moved.code == "pool_moved":
                    continue  # another admission rotated the pool; screen again
                raise
            break
        self.store.settle_retirements(self.journal, self._committed)
        if nominated:
            self._nominated(submission_id, incumbent, record)
        return self.outcome(submission_id)

    def _public_score(self, record):
        return {
            "pool_version": int(record["pool_version"]),
            "eligible": bool(record["eligible"]),
            "score": None
            if record["score"] is None
            else round(float(record["score"]), 4),
            "important_score": None
            if record["important_score"] is None
            else round(float(record["important_score"]), 4),
            "gates_failed": sorted(record["gate_failures"]),
            "cases": {
                "scored": int(record["n_scored"]),
                "reference_invalid": int(record["n_reference_invalid"]),
                "failed_infra": int(record["n_failed_infra"]),
            },
        }

    def _nominated(self, submission_id, incumbent, record):
        if incumbent is None:
            self.store.set_incumbent(
                submission_id, "first eligible screened submission", expected=None
            )
            return
        final_id = "final-" + _digest([incumbent["model_id"], submission_id])[7:31]
        frozen = {
            "schema": "carbon.battery.final-freeze.v1",
            "rule": exam.ComparisonRule(RULE["equivalence_margin_rel"]).__dict__,
            "rule_digest": rule_digest(),
            "incumbent": incumbent["model_id"],
            "incumbent_recipe": self.store.model_state(incumbent["model_id"])[
                "recipe_digest"
            ],
            "challenger": submission_id,
            "challenger_recipe": self.store.submission(submission_id)["binding"][
                "recipe_digest"
            ],
            "screening": {
                "pool_version": record["pool_version"],
                "score": record["score"],
                "incumbent_score": record["nomination"]["incumbent_score"],
            },
            "seed": self._seed("final/" + final_id),
        }
        self.store.freeze_final(
            final_id,
            challenger=submission_id,
            incumbent=incumbent["model_id"],
            frozen=frozen,
        )

    def run_pending(self):
        """Advance every queued submission and open final, in order."""
        results = [self.process(s) for s in self.store.pending_submissions()]
        results += [self.process_final(f) for f in self.store.open_finals()]
        return results

    # --- finalist comparison --------------------------------------------------------------

    def process_final(self, final_id):
        final = self.store.final(final_id)
        if final["state"] == "DECIDED":
            return final
        fingerprint = self.store.claim_finalist_set(final_id)
        if fingerprint is None:
            return {**final, "status": "WAITING_FOR_FINALIST_SET"}
        frozen = final["frozen"]
        seed = frozen["seed"]
        inputs = self.store.case_inputs([fingerprint])
        ids = [c["case_id"] for c in self.store.batch(fingerprint)["document"]["cases"]]
        store = self._case_store([fingerprint])
        rows = {}
        try:
            for role, model in (
                ("incumbent", final["incumbent"]),
                ("challenger", final["challenger"]),
            ):
                source = self.store.submission(model)
                recipe = self._recipe(source)
                if recipe.recipe_digest != frozen[role + "_recipe"]:
                    raise StateError("artifact_mismatch", role)
                fresh = f"{final_id}-{role}"
                if self.store.model_state(fresh) is None:
                    state, stats = self.backend.reconstruct(
                        "rec-" + fresh, recipe, seed
                    )
                    self.store.retain_model(
                        fresh,
                        recipe_digest=recipe.recipe_digest,
                        seed=seed,
                        state=state,
                        reconstruction={**self.backend.identity, "fit": stats},
                    )
                preds = self._infer(fresh, ids, inputs, "final")
                rows[role] = exam.evaluate(preds, ids, store)
        except WorkerFailure as failure:
            if failure.candidate:
                # The challenger's (or incumbent's) own rebuild failed: the
                # comparison records it, never infers a result for it.
                outcome = {
                    "outcome": exam.REGRESSION
                    if role == "challenger"
                    else exam.INSUFFICIENT,
                    "reason": f"{role} {failure.code}",
                    "promotable": False,
                }
                return self._decide(final_id, final, outcome, fingerprint)
            return {**final, "status": "FAILED_INFRA", "code": failure.code}

        def errors(case_rows):
            return {r["case_id"]: r["error"] for r in case_rows if "error" in r}

        def components(case_rows):
            return {
                r["case_id"]: r["components"] for r in case_rows if "components" in r
            }

        (inc_rows, _inc_agg), (chal_rows, chal_agg) = (
            rows["incumbent"],
            rows["challenger"],
        )
        rule = exam.ComparisonRule(**frozen["rule"])
        outcome = exam.final_compare(
            errors(inc_rows),
            errors(chal_rows),
            {c: store.important(c) for c in ids if store.refs[c].get("status") == "OK"},
            rule,
            chal_eligible=bool(chal_agg["eligible"]),
            inc_components=components(inc_rows),
            chal_components=components(chal_rows),
        )
        return self._decide(final_id, final, outcome, fingerprint)

    def _decide(self, final_id, final, outcome, fingerprint):
        outcome = {
            **outcome,
            "finalist_set": fingerprint,
            "references": self._reference_identity([fingerprint]),
        }
        self.store.complete_final(final_id, outcome)
        if outcome.get("promotable"):
            self.store.set_incumbent(
                final["challenger"],
                "IMPROVEMENT in the finalist comparison",
                expected=final["incumbent"],
            )
        self.store.settle_retirements(self.journal, self._committed)
        return self.store.final(final_id)

    # --- disclosure -------------------------------------------------------------------------

    def outcome(self, submission_id):
        """The miner-visible outcome: an allow-list, never the internal record."""
        row = self.store.submission(submission_id)
        out = {
            "schema": SCHEMA,
            "submission_id": submission_id,
            "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
            "state": row["state"],
            "evidence": "DEVELOPMENT_SHADOW",
            "rule": RULE["status"],
            "qualification": False,
            "reward": False,
        }
        if row["failure"]:
            out["failure"] = {
                "code": row["failure"].get("code"),
                "issues": row["failure"].get("issues", []),
            }
        if row["binding"]:
            out["recipe_digest"] = row["binding"].get("recipe_digest")
            out["contract_digest"] = row["binding"].get("contract_digest")
            out["reconstruction"] = {
                "backend": row["binding"]["backend"]["backend"],
                "validator_path": bool(row["binding"]["backend"]["validator_path"]),
            }
        score = self.store.score(submission_id)
        pool = self.store.pool()
        if score is not None:
            out["screening"] = score["public"]
            out["nominated"] = bool(score["record"]["nomination"]["nominated"])
        elif row["state"] in ("ADMITTED", "RECONSTRUCTED", "FAILED_INFRA"):
            out["waiting"] = (
                "POOL_NOT_OPEN"
                if pool is None
                else ("ROTATION_PENDING" if pool["status"] != "OPEN" else "QUEUED")
            )
        finals = [self.store.final(f) for (f,) in self._finals_for(submission_id)]
        if finals:
            out["finals"] = [
                {
                    "state": f["state"],
                    "outcome": None if not f["outcome"] else f["outcome"]["outcome"],
                    "promoted": bool(f["outcome"] and f["outcome"].get("promotable")),
                }
                for f in finals
            ]
        return out

    def _finals_for(self, submission_id):
        with self.store.db() as db:
            return db.execute(
                "SELECT final_id FROM finals WHERE challenger=? ORDER BY rowid",
                (submission_id,),
            ).fetchall()

    def signed_outcome(self, submission_id):
        if self.service_key is None:
            raise PermissionError("no service key configured")
        return self.service_key.sign("screening_result", self.outcome(submission_id))

    def status(self):
        pool = self.store.pool()
        return {
            "identities": self.store.identities(),
            "pool": None
            if pool is None
            else {
                "version": pool["version"],
                "admitted": pool["admitted"],
                "status": pool["status"],
                "active": len(pool["active"]),
            },
            "incumbent": self.store.incumbent(),
            "batches": {
                kind: {
                    state: len(self.store.batches(kind=kind, state=state))
                    for state in (
                        "PREPARED",
                        "ACTIVE",
                        "RETIRED",
                        "FINALIST",
                        "CONSUMED",
                        "RELEASED",
                    )
                }
                for kind in ("screening", "finalist")
            },
            "pending": len(self.store.pending_submissions()),
            "open_finals": len(self.store.open_finals()),
        }


__all__ = [
    "AuthenticatedSubmission",
    "BatteryValidator",
    "CommitmentRequired",
    "PublishedCaseRefused",
    "commitment_digest",
]
