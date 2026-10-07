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

**The quiz report** (VALIDATOR-19 slice Q, part 2): once a score is
committed, the retained model infers the quizzes its active batches carry,
and an operator-only report is stored beside the score (`quiz_report`), with
measures an operator entry point injects. It gates nothing and never reaches
a miner outcome.

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

Scientific results never become chain actions here. Weights are published
elsewhere: Phase A all-burn (OD-4a) through the owner publisher, and winner
weights (OWNER-WEIGHTS-AUTHORITY-01) through
`carbon.rewards.testnet_winner_publication`, which reads this validator's
incumbent and its promotions read-only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass

import numpy as np

from carbon.challenge_registry import ResolutionError, resolve
from carbon.challenge_validator.scoring import COVERAGE_RULE
from carbon.reconstruction.capability_registry import (
    DEVELOPMENT_VARIANT_NOT_SERVED,
    is_development_variant,
)
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
)

from . import exam
from .calibration import PREPARE_SHA256, SHAPES, frozen_calibration
from .challenge import (
    CHALLENGE,
    OCV_TABLE_SHA256,
    TRAIN_V1_SHA256,
    PublicMaterial,
)
from .pool_store import (
    MAX_INFRA_ATTEMPTS,
    WITHDRAWN,
    HotkeyWindowUsed,
    PoolStore,
    StateError,
    canonical,
)
from .research import EVALUATION_FEEDBACK_FIELDS, SCREENING_FEEDBACK_FIELDS
from .seeds import PrivateBatch, make_batch, reconstruction_seed, shared_seed
from .worker import WorkerFailure

SCHEMA = "carbon.battery.validator-outcome.v1"
SUBMIT_TOOL = "battery_submit"
RULE = exam.DEVELOPMENT_RULE


def _digest(value):
    body = value if type(value) is bytes else canonical(value).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def rule_digest(rule=RULE):
    return _digest(rule)


def incomplete(predictions, asked):
    """Whether a worker's predictions fail to cover the cases it was asked
    for: a case absent, an extra case, or a case given no prediction (None).
    Each is the candidate's (`prediction_cases_differ`, candidate-charged),
    never FAILED_INFRA and never excluded from the score
    (GRAPHITE-COVERAGE-PARITY-01; Track A: a partial artifact is never graded
    as valid). Before that ruling a case given None passed this check and was
    typed FAILED_INFRA by `exam.evaluate`, so it was excluded."""
    if type(predictions) is not dict or set(predictions) != set(asked):
        return True
    return any(predictions[case] is None for case in asked)


#: The coverage rule's identity, recorded on every submission binding, refusal
#: and score record this validator writes from GRAPHITE-COVERAGE-PARITY-01 on,
#: and so on every miner outcome derived from them (`coverage_rule`). It
#: changes outcomes (`incomplete`) without changing `RULE` or `rule_digest`,
#: which the deployment's seed pin fixes, so each record says which typing
#: made it. A record without it was typed before the ruling: read as written.
COVERAGE_IDENTITY = {
    "name": COVERAGE_RULE,
    "digest": _digest({"coverage_rule": COVERAGE_RULE, "check": "daemon.incomplete"}),
}


def coverage_rule_of(row):
    """The coverage rule a stored submission row was typed under, or None
    for a row written before it (absent field)."""
    for part in (row.get("binding"), row.get("failure")):
        if isinstance(part, dict) and part.get("coverage_rule") is not None:
            return part["coverage_rule"]
    return None


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
            receipt={
                "sequence": receipt.ref.sequence,
                "digest": receipt.ref.digest,
                # The finalized block of the validator-observed snapshot the
                # request was authenticated against: rule v2's clock.
                "block": receipt.finalized_block,
            },
            challenge_id=gateway.challenge.challenge_id,
            challenge_version=gateway.challenge.version,
            strategy=strategy,
            contract_digest=fields["contract_digest"],
        )


def submission_identity(submission):
    """`(request_digest, submission_id)` for an authenticated submission.

    The same hotkey, recipe and contract always name the same submission, so
    an intake can tell a miner its submission id before admission runs.
    """
    if type(submission) is not AuthenticatedSubmission:
        raise TypeError("an AuthenticatedSubmission is required")
    request_digest = _digest(
        {
            "hotkey": submission.hotkey,
            "challenge": [submission.challenge_id, submission.challenge_version],
            "strategy": submission.strategy,
            "contract_digest": submission.contract_digest,
        }
    )
    return request_digest, "bsub-" + request_digest[7:39]


class CommitmentRequired(PermissionError):
    """The miner has not committed this submission on chain."""


class BackendNotServed(PermissionError):
    """This validator has no worker image for the recipe's backend.

    Not a refusal of the recipe: nothing is recorded, and the miner may
    submit it to a validator that serves the backend (OWNER-PYTORCH-BACKEND-01).
    """

    def __init__(self, backend):
        super().__init__(backend)
        self.backend = backend


class ContractRevised(ValueError):
    """A recipe admitted under an earlier contract that the current one refuses.

    Raised only for a carried-over deployment. It is Carbon's revision, never
    the miner's failure: the submission is closed with its named issues and
    nothing is scored.
    """

    def __init__(self, issues):
        super().__init__("contract_revised")
        self.issues = issues


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
        development_only=False,
        import_only=False,
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
        #: A Graphite development deployment (VALIDATOR-13, the owner's opt-in
        #: field `development_only`): it may admit a registered development
        #: variant from a `graphite-dev:` identity, compiled by the
        #: `development_compiler` the Graphite side supplies. This module never
        #: names the variant module. Off by default; never sets weights.
        self.development_only = development_only is True
        #: Import-only (VALIDATOR-19 slice 2): every batch comes from Carbon's
        #: shared answer key (`challenge_validator.answer_key`); this
        #: validator never draws or seals one itself.
        self.import_only = import_only is True
        # Its pool rotates by the producer's windows, never its own clock.
        self.store.windowed = self.import_only
        self.development_compiler = None
        #: The near-limit quiz's measures (VALIDATOR-19 slice Q), injected by
        #: an operator entry point (`challenge_validator.battery_quiz.install`);
        #: None measures nothing. They never touch a score.
        self.quiz_measures = None
        self.material = PublicMaterial.load(repository)
        self.tol, self.scales = frozen_calibration(repository)
        self.pin = journal.root_pin(root)
        self.rule = store.rule
        if self.pin.get("scoring_digest") != rule_digest(self.rule):
            # The root was committed for another rule: its seeds and batches
            # belong to that rule's pools, never to this one.
            raise StateError("rule_mismatch", "seed pin names another exam rule")

    # --- identities -------------------------------------------------------------

    def identities(self):
        from carbon.reconstruction.capability_registry import contract

        from .contracts import implementation_digest

        registered = contract(CHALLENGE.challenge_id)
        if is_development_variant(registered.digest):
            # The daemon binds only a miner-facing contract, never a
            # development-only variant (OWNER-GRAPHITE-TEST-WAVE-03 §1).
            raise StateError(DEVELOPMENT_VARIANT_NOT_SERVED, registered.digest)
        return {
            "schema": "carbon.battery.validator-identities.v1",
            "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
            "contract_digest": registered.digest,
            "rule": self.rule,
            "rule_digest": rule_digest(self.rule),
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
        self._settle()

    def _committed(self, fingerprint):
        document = self.store.batch(fingerprint)["document"]
        return self.journal.recall(PrivateBatch.from_document(document))

    # --- batches ------------------------------------------------------------------

    def prepare_batch(self, role, *, kind, count=None, duplicates=2):
        """Generate, commit and record one private batch (idempotent by role).

        The plaintext is generated from the private root, committed to the
        journal before any use, and kept only in the validator state.
        """
        from carbon.challenge_validator.interface import role_reserved

        if role_reserved(role):
            raise StateError("seed_role_reserved")
        if role_reserved(role, self.sealed_roles()):
            # The role's batch was sealed outside the pool (a study's
            # confirmation set, `seal_batch`): preparing it would recall that
            # batch into scoring. Refused in any spelling.
            raise StateError("seed_role_sealed")
        count = self.rule["screening_batch_size"] if count is None else count
        committed = self.seal_batch(role, count=count, duplicates=duplicates)
        self.store.add_batch(committed, kind=kind)
        return committed.fingerprint

    def sealed_roles(self):
        """Roles committed in the journal for a batch the pool does not hold:
        sealed outside it by `seal_batch`. Public journal metadata only."""
        pooled = {batch["fingerprint"] for batch in self.store.batches()}
        return {
            entry["role"]
            for entry in self.journal.public()
            if entry["kind"] == "batch" and entry["fingerprint"] not in pooled
        }

    def seal_batch(self, role, *, count, duplicates):
        """Generate and commit one private batch, outside the pool (idempotent
        by role).

        The plaintext is generated from the private root and committed to the
        journal; the batch is never recorded in the validator state, so no
        screening rotation or finalist comparison can claim it. A study that
        uses it (EV5's confirmation set) regenerates it from the root and
        recalls it by fingerprint.
        """
        if self.import_only:
            raise StateError("batch_import_only")
        batch = make_batch(self.root, self.pin, role, count, duplicates)
        self._refuse_published(batch)
        try:
            return self.journal.recall(batch)
        except ValueError:
            return self.journal.commit(batch, pool_version=self._pool_version())

    def import_batch(self, batch, *, kind):
        """Commit and record an externally built batch (tests, replays).

        Refused when any case repeats a published campaign case, unless this
        validator was built with `allow_published_cases=True` - which only a
        test fixture does, never a deployment.
        """
        if type(batch) is not PrivateBatch:
            raise TypeError("a PrivateBatch is required")
        from carbon.challenge_validator.interface import role_reserved

        if role_reserved(batch.role):
            # Refused before the journal commits anything.
            raise StateError("seed_role_reserved")
        self._refuse_published(batch)
        try:
            committed = self.journal.recall(batch)
        except ValueError:
            committed = self.journal.commit(batch, pool_version=self._pool_version())
        self.store.add_batch(committed, kind=kind)
        return committed.fingerprint

    def _refuse_published(self, batch):
        from .challenge import INPUTS

        if self.allow_published_cases:
            return
        published = published_inputs(self.repository)
        for _case_id, inputs in batch.cases:
            values = dict(inputs)
            if tuple(round(values[k], 4) for k in INPUTS) in published:
                raise PublishedCaseRefused(
                    "a published campaign case cannot be a hidden case"
                )

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
        """Store truth-service records; returns whether the batch is complete.

        A newly complete screening batch resumes a pending rotation.
        """
        self.store.record_references(fingerprint, records)
        complete = self.store.complete_references(fingerprint)
        if complete:
            self._settle()
        return complete

    def open_pool(self):
        return self.store.open_pool()

    # --- admission ------------------------------------------------------------------

    def admit(self, submission):
        """Admit one authenticated submission, or refuse it by name.

        Idempotent: the same hotkey resubmitting the same recipe under the same
        contract is the same submission, whatever its transport receipt.
        """
        request_digest, submission_id = submission_identity(submission)
        base = {
            "request_digest": request_digest,
            "hotkey": submission.hotkey,
            "challenge": f"{submission.challenge_id}/{submission.challenge_version}",
            "strategy": submission.strategy,
        }

        def refuse(code, issues=()):
            row = self.store.refuse(
                submission_id,
                failure={
                    "code": code,
                    "issues": list(issues),
                    "coverage_rule": dict(COVERAGE_IDENTITY),
                },
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
        development = None
        try:
            if is_development_variant(submission.contract_digest):
                if not self._serves_development(submission.hotkey):
                    # A development-only contract variant is never served to a
                    # miner (OWNER-GRAPHITE-TEST-WAVE-03 §1).
                    return refuse(DEVELOPMENT_VARIANT_NOT_SERVED)
                admitted = self.development_compiler(
                    submission.strategy, submission.contract_digest
                )
                development = {
                    **admitted.development,
                    "variant_contract_digest": submission.contract_digest,
                }
            else:
                admitted = compile_submission(
                    submission.strategy, contract_digest=submission.contract_digest
                )
        except SubmissionRefused as refused:
            return refuse(
                "contract_refused",
                [{"code": i.code, "path": i.path} for i in refused.issues],
            )
        except ValueError as refused:  # RecipeRejected carries named issues
            if development is None and is_development_variant(
                submission.contract_digest
            ):
                # The supplied development compiler refused it, by code.
                return refuse(
                    "development_variant_refused",
                    [{"code": getattr(refused, "code", type(refused).__name__)}],
                )
            issues = getattr(getattr(refused, "rejected", None), "issues", ())
            return refuse(
                "recipe_refused",
                [{"code": i.code, "path": list(i.path)} for i in issues],
            )
        recipe = admitted.construction
        backend = recipe.settings.get("backend", "jax")
        if backend not in getattr(self.backend, "backends", ("jax",)):
            raise BackendNotServed(backend)
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
            "coverage_rule": dict(COVERAGE_IDENTITY),
        }
        if development is not None:
            # Stamped beside the base fields; a Level-0 binding is unchanged.
            binding["development"] = development
        window = None
        block = (submission.receipt or {}).get("block")
        if self.rule.get("per_hotkey") is not None:
            if type(block) is not int:
                # Rule v2 counts by block; a receipt without one cannot be
                # placed in a window, so it is not admitted (and not recorded).
                raise HotkeyWindowUsed(None)
            start, end = exam.hotkey_window(self.rule, block)
            window = (start, end, self.rule["per_hotkey"]["scored_per_window"])
        row, _new = self.store.admit(
            submission_id, binding=binding, window=window, **base
        )
        return self.outcome(row["submission_id"])

    def _serves_development(self, hotkey):
        """Whether this deployment admits a development variant from `hotkey`:
        opted in, given a compiler, and a Graphite development identity."""
        return (
            self.development_only
            and callable(self.development_compiler)
            and type(hotkey) is str
            and hotkey.startswith("graphite-dev:")
        )

    def _development(self, row):
        """`(recipe, record)` for a development row, recompiled through the
        supplied compiler and checked against what admission bound; None for
        a Level-0 row."""
        bound = row["binding"].get("development")
        if bound is None:
            return None
        if not self._serves_development(row["hotkey"]):
            raise StateError("development_compiler_unavailable")
        compiled = self.development_compiler(
            row["strategy"], bound["variant_contract_digest"]
        )
        if (
            compiled.development["widened_digest"] != bound["widened_digest"]
            or compiled.construction.recipe_digest != row["binding"]["recipe_digest"]
        ):
            raise StateError("artifact_mismatch", "development recompile differs")
        from .level1_worker import expression_record

        return compiled.construction, expression_record(compiled.reconstruction)

    # --- screening --------------------------------------------------------------------

    def _carried(self, binding):
        """Whether `binding` was made under an identity this deployment was
        carried over from (`PoolStore.rebind`, OWNER-BATTERY-CARRYOVER-01).

        Only a recorded earlier identity counts: a binding whose contract or
        implementation matches neither the current identity nor one the
        operator carried over from is a mismatch, never a carry-over.
        """
        keys = ("contract_digest", "implementation_digest")
        current = self.store.identities() or {}
        if all(binding.get(k) == current.get(k) for k in keys):
            return False
        return any(
            all(binding.get(k) == old.get(k) for k in keys)
            for old in self.store.identity_history()
        )

    def _recipe(self, row):
        from .compile import compile_recipe

        development = self._development(row)
        if development is not None:
            return development[0]
        carried = self._carried(row["binding"])
        try:
            _, recipe = compile_recipe(row["strategy"])
        except ValueError as refused:
            if not carried:
                raise
            # The recipe was admitted under an earlier contract and the
            # current one refuses it: Carbon's revision, not the miner's.
            issues = getattr(getattr(refused, "rejected", None), "issues", ())
            raise ContractRevised(
                [{"code": i.code, "path": list(i.path)} for i in issues]
            ) from None
        if recipe.recipe_digest != row["binding"]["recipe_digest"]:
            if not carried:
                # The recipe Carbon would build now is not the one admitted:
                # the compiler or contract changed underneath. Never build
                # silently.
                raise StateError(
                    "artifact_mismatch", "recipe digest differs from admission"
                )
            # Carried over: rebuilt under the current contract, and recorded.
            self.store.note(
                "recompiled",
                {
                    "submission_id": row["submission_id"],
                    "from": row["binding"]["recipe_digest"],
                    "to": recipe.recipe_digest,
                },
            )
        return recipe

    def _seed(self, label):
        if self.import_only:
            return shared_seed(self._active_salts(), label)
        tag = hmac.new(self.root._bytes, label.encode(), hashlib.sha256).digest()
        return int.from_bytes(tag[:4], "big")

    def _reconstruction_seed(self, submission_id):
        """Import-only validators seed from the active batches' shared salts
        (VALIDATOR-19 slice 4), so every validator with the same batches
        rebuilds a submission alike; others from their own root, as before."""
        if self.import_only:
            return shared_seed(self._active_salts(), "reconstruction/" + submission_id)
        return reconstruction_seed(self.root, submission_id)

    def _active_salts(self):
        pool = self.store.pool()
        active = [] if pool is None else pool["active"]
        salts = self.store.salts(active)
        if not active or len(salts) != len(active):
            raise StateError("answer_key_salt_missing")
        return salts

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
            if incomplete(predictions, missing):
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

    def _settle(self):
        """Resume a pending rotation and complete journal retirements."""
        self.store.rotate_if_ready()
        self.store.settle_retirements(self.journal, self._committed)

    def process(self, submission_id):
        """Advance one submission as far as it can go now. Restart-safe."""
        row = self.store.submission(submission_id)
        if row["state"] in (
            "SCORED",
            "INVALID_CONSTRUCTION",
            "RECONSTRUCTION_FAILED",
            "FAILED_INFRA_EXHAUSTED",
        ):
            return self.outcome(submission_id)
        self._settle()
        pool = self.store.pool()
        if pool is None or pool["status"] != "OPEN":
            return self.outcome(submission_id)
        # The attempt number names every worker run. An infrastructure
        # failure moves the submission to the next attempt, so a retry never
        # reuses a run identity that might still be unresolved.
        attempt = row["binding"]["attempt"]
        try:
            try:
                recipe = self._recipe(row)
            except ContractRevised as revised:
                self.store.mark(
                    submission_id,
                    "INVALID_CONSTRUCTION",
                    {"code": "contract_revised", "issues": revised.issues},
                )
                return self.outcome(submission_id)
            if self.store.model_state(submission_id) is None:
                development = self._development(row)
                state, stats = self.backend.reconstruct(
                    f"rec-{submission_id}-a{attempt}",
                    recipe,
                    self._reconstruction_seed(submission_id),
                    # Level 0 calls the backend exactly as before.
                    **({} if development is None else {"development": development[1]}),
                )
                self.store.retain_model(
                    submission_id,
                    recipe_digest=recipe.recipe_digest,
                    seed=self._reconstruction_seed(submission_id),
                    state=state,
                    reconstruction={**self.backend.identity, "fit": stats},
                )
                self.store.mark(submission_id, "RECONSTRUCTED")
            return self._screen(submission_id, attempt)
        except WorkerFailure as failure:
            if failure.candidate:
                self.store.mark(
                    submission_id,
                    "RECONSTRUCTION_FAILED",
                    {"code": failure.code, "attempt": attempt},
                )
            else:
                exhausted = attempt + 1 >= MAX_INFRA_ATTEMPTS
                self.store.mark(
                    submission_id,
                    "FAILED_INFRA_EXHAUSTED" if exhausted else "FAILED_INFRA",
                    {"code": failure.code, "attempt": attempt},
                )
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

    def _pool_records(self, pool, challenger, incumbent_id, tag):
        """Score a challenger and (inference only) the incumbent on a pool."""
        ids = self.store.active_case_ids(pool)
        inputs = self.store.case_inputs(pool["active"])
        store = self._case_store(pool["active"])
        preds = self._infer(challenger, ids, inputs, f"v{pool['version']}{tag}")
        _rows, agg = exam.evaluate(preds, ids, store)
        inc_rec = None
        if incumbent_id is not None and incumbent_id != challenger:
            try:
                # Named with the challenger and its attempt: the incumbent's
                # run on this pool never blocks a later challenger's retry.
                inc_preds = self._infer(
                    incumbent_id,
                    ids,
                    inputs,
                    f"v{pool['version']}-for-{challenger}{tag}",
                )
            except WorkerFailure as failure:
                # The incumbent's inference, not this candidate's: never
                # charged to the challenger, which is retried.
                raise WorkerFailure(
                    "incumbent_inference:" + failure.code, candidate=False
                ) from None
            _, inc_agg = exam.evaluate(inc_preds, ids, store)
            inc_rec = {
                **inc_agg,
                "pool_version": pool["version"],
                "rebuild": self._rebuild(incumbent_id),
            }
        record = {
            "model_id": challenger,
            "pool_version": pool["version"],
            # Which image and device class rebuilt the scored model: scores
            # are compared only within one device class (TORCH-GPU-01).
            "rebuild": self._rebuild(challenger),
            "active_batches": list(pool["active"]),
            "references": self._reference_identity(pool["active"]),
            "rule_digest": rule_digest(self.rule),
            "coverage_rule": dict(COVERAGE_IDENTITY),
            **agg,
        }
        if inc_rec is not None and inc_rec["score"] is None:
            # The rule compares against the incumbent's score; with none on
            # this pool, "better than the incumbent" cannot be shown (M3-D15).
            nominated, why = False, "the incumbent has no scorable result on this pool"
        else:
            nominated, why = exam.nominate(
                record, inc_rec, self.rule["equivalence_margin_rel"]
            )
        record["nomination"] = {
            "nominated": nominated,
            "reason": why,
            "incumbent": incumbent_id,
            "incumbent_score": None if inc_rec is None else inc_rec["score"],
        }
        return record

    def _labelled_incumbent(self):
        """The incumbent, labelled with its rebuild device class."""
        incumbent = self.store.incumbent()
        if incumbent is None:
            return None
        return {
            **incumbent,
            "device_class": self._rebuild(incumbent["model_id"])["device_class"],
        }

    def _rebuild(self, model_id):
        """The rebuild identity of a retained model (`rebuild_identity`)."""
        from .rebuild_identity import from_reconstruction

        state = self.store.model_state(model_id)
        return from_reconstruction(None if state is None else state["reconstruction"])

    def _screen(self, submission_id, attempt):
        while True:
            pool = self.store.pool()
            if pool["status"] != "OPEN":
                return self.outcome(submission_id)
            incumbent = self.store.incumbent()
            incumbent_id = None if incumbent is None else incumbent["model_id"]
            record = self._pool_records(
                pool, submission_id, incumbent_id, f"a{attempt}"
            )
            if "development" in self.store.submission(submission_id)["binding"]:
                # A development level is never nominated, never an incumbent
                # and never in standings or weights (VALIDATOR-13 separation).
                record["nomination"] = {
                    **record["nomination"],
                    "nominated": False,
                    "excluded": "DEVELOPMENT_LEVEL",
                }
            nomination = (
                self._nomination(submission_id, incumbent_id, record)
                if record["nomination"]["nominated"]
                else None
            )
            try:
                # Score, count, nomination and any due rotation: one commit.
                self.store.record_score(
                    submission_id,
                    record,
                    self._public_score(record),
                    expected_version=pool["version"],
                    expected_incumbent=incumbent_id,
                    nomination=nomination,
                )
            except StateError as moved:
                if moved.code == "pool_moved":
                    continue  # the pool or incumbent moved; screen again
                raise
            break
        # After the score is committed, and apart from it: never a gate, and
        # nothing it raises reaches the submission.
        try:
            self.quiz_report(submission_id)
        except Exception as failure:  # noqa: BLE001 - recorded, never scored
            self.store.note(
                "quiz_report_failed",
                {"submission_id": submission_id, "failure": type(failure).__name__},
            )
        self._settle()
        return self.outcome(submission_id)

    # --- the near-limit quiz (VALIDATOR-19 slice Q, part 2) ------------------------------

    #: Quiz predictions are stored under this prefix plus the submission id,
    #: never a scored model's id, so they never collide with a scored case.
    QUIZ_PREDICTIONS = "quiz/"
    QUIZ_REPORT_SCHEMA = "carbon.battery.quiz-report.v1"

    def quiz_report(self, submission_id):
        """The operator-only quiz report for a scored submission, on the
        quizzes its score's active batches carry; None when none carries one,
        or when this validator was given no quiz measures.

        The measures are injected (`quiz_measures`, set by
        `challenge_validator.battery_quiz.install` on operator entry points):
        this module never names the quiz's science, which loads the
        value-analysis code no miner surface may reach.

        The retained model infers each quiz's inputs (Q2 cases and every Q3
        grid candidate) through the backend, then the measures give Q2's and
        Q3's per batch and pooled. The report gates nothing and never reaches
        a miner outcome: the score, state, nomination and finals are already
        committed and never read it (rule v3 is the owner's). A quiz
        inference failure is the quiz's own FAILED_INFRA, retried by the next
        call."""
        from .quiz_document import QuizRefused, inputs

        stored = self.store.quiz_report(submission_id)
        if stored is not None and stored.get("state") != "FAILED_INFRA":
            return stored
        score = self.store.score(submission_id)
        if score is None or self.quiz_measures is None:
            return None
        batches = list(score["record"]["active_batches"])
        quizzes = {f: self.store.quiz(f) for f in batches}
        quizzes = {f: q for f, q in quizzes.items() if q is not None}
        if not quizzes:
            return None
        report = {
            "schema": self.QUIZ_REPORT_SCHEMA,
            "submission_id": submission_id,
            "pool_version": score["pool_version"],
            # Drawn and reported only: no gate, threshold or margin applies
            # until the owner adopts rule v3 (HUMAN_INPUT).
            "gates": "NONE",
            "batches": {
                f: {
                    "quiz_digest": q["quiz_digest"],
                    "panel_version": q["panel_version"],
                }
                for f, q in quizzes.items()
            },
        }
        asked = {}
        for quiz in quizzes.values():
            asked.update(inputs(quiz["document"]))
        try:
            predictions = self._quiz_predictions(
                submission_id, asked, f"v{score['pool_version']}"
            )
            measures = self.quiz_measures(quizzes, predictions)
        except WorkerFailure as failure:
            return self.store.record_quiz_report(
                submission_id,
                {
                    **report,
                    "state": "FAILED_INFRA",
                    "code": failure.code,
                    "candidate": bool(failure.candidate),
                },
            )
        except (StateError, QuizRefused) as refused:
            return self.store.record_quiz_report(
                submission_id, {**report, "state": "REFUSED", "code": refused.code}
            )
        for fingerprint, found in measures["batches"].items():
            report["batches"][fingerprint].update(found)
        return self.store.record_quiz_report(
            submission_id, {**report, "state": "MEASURED", "pooled": measures["pooled"]}
        )

    def _quiz_predictions(self, submission_id, inputs, tag):
        """The retained model's predictions on the quiz inputs, through the
        backend's `infer` as scoring uses it, stored apart from every scored
        prediction (`QUIZ_PREDICTIONS`)."""
        key = self.QUIZ_PREDICTIONS + submission_id
        have = self.store.predictions(key, list(inputs))
        missing = [c for c in inputs if c not in have]
        if missing:
            state = self.store.model_state(submission_id)
            if state is None:
                raise StateError("model_not_retained", submission_id)
            predictions = self.backend.infer(
                f"quiz-{submission_id}-{tag}",
                state["state"],
                {c: inputs[c] for c in missing},
            )
            if incomplete(predictions, missing):
                raise WorkerFailure("prediction_cases_differ", candidate=True)
            self.store.store_predictions(key, predictions)
            have.update(predictions)
        return have

    def _public_score(self, record):
        return {
            "pool_version": int(record["pool_version"]),
            "eligible": bool(record["eligible"]),
            "score": (
                None if record["score"] is None else round(float(record["score"]), 4)
            ),
            "important_score": (
                None
                if record["important_score"] is None
                else round(float(record["important_score"]), 4)
            ),
            "gates_failed": sorted(record["gate_failures"]),
            "cases": {
                "scored": int(record["n_scored"]),
                "reference_invalid": int(record["n_reference_invalid"]),
                "failed_infra": int(record["n_failed_infra"]),
            },
        }

    def _nomination(self, submission_id, incumbent_id, record):
        """What a nomination commits with its score."""
        if incumbent_id is None:
            return {
                "kind": "first_incumbent",
                "reason": "first eligible screened submission",
            }
        final_id = "final-" + _digest([incumbent_id, submission_id])[7:31]
        return {
            "kind": "final",
            "final_id": final_id,
            "incumbent": incumbent_id,
            "frozen": self._frozen(final_id, incumbent_id, submission_id, record),
        }

    def _frozen(self, final_id, incumbent_id, submission_id, record):
        return {
            "schema": "carbon.battery.final-freeze.v1",
            "rule": exam.ComparisonRule(self.rule["equivalence_margin_rel"]).__dict__,
            "rule_digest": rule_digest(self.rule),
            "incumbent": incumbent_id,
            "incumbent_recipe": self.store.model_state(incumbent_id)["recipe_digest"],
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

    def run_pending(self):
        """Advance every queued submission and open final, in order."""
        self._settle()
        results = [self.process(s) for s in self.store.pending_submissions()]
        results += [self.process_final(f) for f in self.store.open_finals()]
        return results

    # --- finalist comparison --------------------------------------------------------------

    def process_final(self, final_id):
        final = self.store.final(final_id)
        if final["state"] == "DECIDED":
            return final
        attempt = self.store.final_attempt(final_id)
        if attempt >= MAX_INFRA_ATTEMPTS:
            return {**final, "status": "FAILED_INFRA_EXHAUSTED"}
        current = self.store.incumbent()
        if current is None or current["model_id"] != final["incumbent"]:
            # Frozen against an incumbent that has since been replaced: the
            # comparison no longer answers the question (M3-D13).
            return self._withdraw(final_id, final, current, attempt)
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
                try:
                    recipe = self._recipe(source)
                except ContractRevised:
                    # OWNER-BATTERY-CARRYOVER-01: the incumbent stays the
                    # winner; a side the current contract refuses is not
                    # compared, and nothing is promoted.
                    return self._decide(
                        final_id,
                        {
                            "outcome": exam.INSUFFICIENT,
                            "reason": f"{role} contract_revised",
                            "promotable": False,
                        },
                        fingerprint,
                    )
                if recipe.recipe_digest != frozen[role + "_recipe"] and not (
                    self._carried(source["binding"])
                ):
                    raise StateError("artifact_mismatch", role)
                fresh = f"{final_id}-{role}"
                if self.store.model_state(fresh) is None:
                    state, stats = self.backend.reconstruct(
                        f"rec-{fresh}-a{attempt}", recipe, seed
                    )
                    self.store.retain_model(
                        fresh,
                        recipe_digest=recipe.recipe_digest,
                        seed=seed,
                        state=state,
                        reconstruction={**self.backend.identity, "fit": stats},
                    )
                preds = self._infer(fresh, ids, inputs, f"final-a{attempt}")
                rows[role] = exam.evaluate(preds, ids, store)
        except WorkerFailure as failure:
            if failure.candidate:
                # The challenger's (or incumbent's) own rebuild failed: the
                # comparison records it, never infers a result for it.
                outcome = {
                    "outcome": (
                        exam.REGRESSION if role == "challenger" else exam.INSUFFICIENT
                    ),
                    "reason": f"{role} {failure.code}",
                    "promotable": False,
                }
                return self._decide(final_id, outcome, fingerprint)
            self.store.bump_final_attempt(final_id, attempt + 1)
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
        # The comparison above always runs and its outcome is kept. Only then
        # does the device-class partition apply: two rebuilds of different
        # classes promote nothing (TORCH-GPU-01).
        from .rebuild_identity import comparable

        if not comparable(
            *[
                {"rebuild": self._rebuild(f"{final_id}-{role}")}
                for role in ("incumbent", "challenger")
            ]
        ):
            outcome = {
                **outcome,
                "promotable": False,
                "device_class": "DIFFERS",
            }
        return self._decide(final_id, outcome, fingerprint)

    def _withdraw(self, final_id, final, current, attempt):
        """Withdraw a stale final and re-nominate its challenger now.

        The challenger is screened against the current incumbent on the
        current pool, by inference only. A nomination freezes a new final in
        the same commit that withdraws the old one.
        """
        challenger = final["challenger"]
        pool = self.store.pool()
        new_final, why = None, None
        if current is not None and current["model_id"] == challenger:
            why = "the challenger is already the incumbent"
        elif pool is None or pool["status"] != "OPEN":
            return {**final, "status": "WAITING_FOR_POOL"}
        else:
            incumbent_id = None if current is None else current["model_id"]
            try:
                record = self._pool_records(
                    pool, challenger, incumbent_id, f"-{final_id}-a{attempt}"
                )
            except WorkerFailure as failure:
                if not failure.candidate:
                    self.store.bump_final_attempt(final_id, attempt + 1)
                    return {**final, "status": "FAILED_INFRA", "code": failure.code}
                why = "challenger inference failed: " + failure.code
            else:
                why = record["nomination"]["reason"]
                if record["nomination"]["nominated"] and incumbent_id is not None:
                    new_id = "final-" + _digest([incumbent_id, challenger])[7:31]
                    new_final = {
                        "final_id": new_id,
                        "challenger": challenger,
                        "incumbent": incumbent_id,
                        "frozen": self._frozen(
                            new_id, incumbent_id, challenger, record
                        ),
                    }
        outcome = {
            "outcome": WITHDRAWN,
            "reason": "the incumbent changed before the comparison was decided",
            "promotable": False,
            "renominated": new_final is not None,
            "renomination": why,
            "new_final": None if new_final is None else new_final["final_id"],
        }
        self.store.complete_final(final_id, outcome, new_final=new_final)
        self._settle()
        return self.store.final(final_id)

    def _decide(self, final_id, outcome, fingerprint):
        outcome = {
            **outcome,
            "finalist_set": fingerprint,
            "references": self._reference_identity([fingerprint]),
        }
        # The decision and any promotion commit together.
        self.store.complete_final(final_id, outcome)
        self._settle()
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
            "rule": self.rule["status"],
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
        # A sealed rule (v2) shows a miner nothing computed from a hidden
        # batch: no screening, nomination or finals. No release path exists
        # yet, so they stay sealed (OWNER-BATTERY-3B-AND-EXPOSURE-01).
        sealed = exam.sealed(self.rule)
        if score is not None:
            if not sealed:
                out["screening"] = score["public"]
                out["nominated"] = bool(score["record"]["nomination"]["nominated"])
        elif row["state"] in ("ADMITTED", "RECONSTRUCTED", "FAILED_INFRA"):
            out["waiting"] = (
                "POOL_NOT_OPEN"
                if pool is None
                else ("ROTATION_PENDING" if pool["status"] != "OPEN" else "QUEUED")
            )
        finals = (
            []
            if sealed
            else [self.store.final(f) for (f,) in self._finals_for(submission_id)]
        )
        if finals:
            out["finals"] = [
                {
                    "state": f["state"],
                    "outcome": None if not f["outcome"] else f["outcome"]["outcome"],
                    "promoted": bool(f["outcome"] and f["outcome"].get("promotable")),
                }
                for f in finals
            ]
        coverage = coverage_rule_of(row)
        if coverage is not None:
            # Absent on a row typed before GRAPHITE-COVERAGE-PARITY-01.
            out["coverage_rule"] = coverage
        if set(out) - set(EVALUATION_FEEDBACK_FIELDS) or set(
            out.get("screening", {})
        ) - set(SCREENING_FEEDBACK_FIELDS):
            raise RuntimeError("outcome field outside the disclosure allow-list")
        return out

    def fresh_rerun(self, submission_id):
        """Score a screened submission's retained model once on a fresh hidden
        batch (VALIDATOR-13, `fresh_cases_rerun`): a prepared finalist batch no
        result has used, consumed by this rerun and never scored again.
        Operator-only; nothing here reaches a miner outcome.

        One rerun per submission, idempotent: a replay returns the recorded
        result. Returns `{"state": "WAITING_FOR_FRESH_SET"}` when no batch is
        ready and `{"state": "FAILED_INFRA", ...}` for an infrastructure
        failure, which is retried on the same batch. A candidate's own
        inference failure is recorded, never inferred over.
        """
        rerun_id = "rerun-" + submission_id
        done = self.store.rerun(rerun_id)
        if done is not None:
            return done
        if self.store.score(submission_id) is None:
            raise StateError("rerun_not_scored", submission_id)
        fingerprint = self.store.claim_rerun_set(rerun_id)
        if fingerprint is None:
            return {"state": "WAITING_FOR_FRESH_SET"}
        inputs = self.store.case_inputs([fingerprint])
        ids = [c["case_id"] for c in self.store.batch(fingerprint)["document"]["cases"]]
        try:
            predictions = self._infer(submission_id, ids, inputs, rerun_id)
        except WorkerFailure as failure:
            if not failure.candidate:
                return {"state": "FAILED_INFRA", "code": failure.code}
            return self.store.record_rerun(
                rerun_id,
                {
                    "state": "CANDIDATE_FAILED",
                    "submission_id": submission_id,
                    "code": failure.code,
                },
            )
        _rows, aggregate = exam.evaluate(
            predictions, ids, self._case_store([fingerprint])
        )
        return self.store.record_rerun(
            rerun_id,
            {
                "state": "SCORED",
                "submission_id": submission_id,
                "rule_digest": rule_digest(self.rule),
                "references": self._reference_identity([fingerprint]),
                "aggregate": aggregate,
            },
        )

    def _finals_for(self, submission_id):
        with self.store.db() as db:
            return db.execute(
                "SELECT final_id FROM finals WHERE challenger=? ORDER BY rowid",
                (submission_id,),
            ).fetchall()

    def signed_final(self, final_id):
        """A decided final for the owner publisher: identities and outcome
        only, never its fresh cases or seed."""
        if self.service_key is None:
            raise PermissionError("no service key configured")
        final = self.store.final(final_id)
        if final["state"] != "DECIDED":
            raise StateError("final_not_decided", final_id)
        return self.service_key.sign(
            "final_result",
            {
                "schema": "carbon.battery.final-result.v1",
                "final_id": final_id,
                "challenger": final["challenger"],
                "incumbent": final["incumbent"],
                "outcome": final["outcome"]["outcome"],
                "promotable": bool(final["outcome"].get("promotable")),
                "rule_digest": final["frozen"]["rule_digest"],
                "qualification": False,
                "reward": False,
            },
        )

    def signed_outcome(self, submission_id):
        if self.service_key is None:
            raise PermissionError("no service key configured")
        return self.service_key.sign("screening_result", self.outcome(submission_id))

    def status(self):
        pool = self.store.pool()
        return {
            "identities": self.store.identities(),
            "pool": (
                None
                if pool is None
                else {
                    "version": pool["version"],
                    "admitted": pool["admitted"],
                    "status": pool["status"],
                    "active": len(pool["active"]),
                }
            ),
            "incumbent": self._labelled_incumbent(),
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
