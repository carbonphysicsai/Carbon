"""Miner-side signed submission to the bounded DEVELOPMENT recipe receiver.

This client has a separate wire contract from Battery. It records the first
admitted task before polling so a restart can only ask about that task. A
reconstructed result is construction evidence, never a scored verdict.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from carbon.chain.auth import BittensorMessageSigner
from carbon.chain.models import ChainContext
from carbon.challenge_validator.dispatch import RESULT_SCHEMA
from carbon.challenge_validator.interface import (
    OutcomeContractViolation,
    check_outcome,
    is_digest,
)
from carbon.challenge_validator.lean_recipe import OUTCOME_SCHEMA
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.development_session.data import write_once
from carbon.registry.model import ChallengeKey
from carbon.research.refs import ResearchTaskId
from carbon.transport.models import MAX_BODY, message

RECORD_SCHEMA = "carbon.construction.intake-submission.v1"
INFO_PATH = "/carbon/v1/construction/intake"
SUBMIT_PATH = "/carbon/v1/mcp"
PUBLIC_SCHEMA = "carbon.construction.intake-public.v1"
SUBMIT_TOOL = "construction_submit"
STATUS_TOOL = "construction_status"
SOURCE_TOOL = "carbon_research_v2"
RETRY_CAPABILITY = {
    "schema": "carbon.construction.infrastructure-retry.v1",
    "field": "retry_of_submission_id",
    "eligible_state": "FAILED_INFRA",
    "idempotency": "ONE_CHILD_PER_FAILED_TASK",
}
TERMINAL = frozenset({"RECONSTRUCTED", "RECONSTRUCTION_FAILED", "FAILED_INFRA"})
PINNED_FIELDS = frozenset(
    {"contract_digest", "rule_digest", "implementation_digest", "identities_digest"}
)
RESULT_FIELDS = frozenset(
    {
        "schema",
        "kind",
        "code",
        "pinned",
        "outcome",
        "evidence",
        "qualification",
        "reward",
    }
)
WAIT_S = 1800.0
POLL_S = 30.0


class DirectIntakeRefusal(ValueError):
    """Closed reason; neither a model score nor a scientific failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class DirectConstructionPending(DirectIntakeRefusal):
    """Admission is pending for this already validated remote task identity."""

    def __init__(self, task_id: str):
        super().__init__("construction_task_queued")
        self.task_id = task_id


class DirectIntakeRateLimit(DirectIntakeRefusal):
    """Only the receiver's explicit pre-admission HTTP 429 rate envelope."""

    def __init__(self):
        super().__init__("rate")


def retry_rate_limited(operation, *, deadline, clock=time.monotonic, sleep=time.sleep):
    """Retry only an explicit pre-admission HTTP rate refusal, within a deadline.

    The operation must rebuild and sign its request on every attempt. Other
    refusals and ambiguous network failures propagate without replay.
    """
    last = None
    for attempt in range(31):
        if clock() >= deadline:
            if last is not None:
                raise last
            raise DirectIntakeRefusal("construction_request_deadline")
        try:
            return operation()
        except DirectIntakeRateLimit as refused:
            last = refused
            remaining = deadline - clock()
            if remaining <= 0 or attempt == 30:
                raise
            sleep(min(1.0, remaining))
            if clock() >= deadline:
                raise


def read_intake(url: str, *, timeout: float = 10.0) -> dict:
    from carbon.development_session.intake_targets import intake_url

    if not intake_url(url):
        raise DirectIntakeRefusal("construction_intake_url_invalid")
    try:
        with urllib.request.urlopen(
            url.rstrip("/") + INFO_PATH, timeout=timeout
        ) as response:
            facts = json.loads(response.read(65536))
    except urllib.error.HTTPError as refused:
        if refused.code == 429:
            answer = json.loads(refused.read(65536) or b"{}")
            if type(answer) is dict and answer.get("refused") == "rate":
                raise DirectIntakeRateLimit() from None
        raise
    if type(facts) is not dict or facts.get("schema") != PUBLIC_SCHEMA:
        raise DirectIntakeRefusal("construction_intake_wrong_schema")
    return facts


def post(url, body, headers, *, timeout=30.0):
    request = urllib.request.Request(
        url.rstrip("/") + SUBMIT_PATH,
        data=body,
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read(65536))
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read(65536) or b"{}")


def _checked(facts, *, recipe, contract_digest, receiver, context):
    if type(facts) is not dict or facts.get("schema") != PUBLIC_SCHEMA:
        raise DirectIntakeRefusal("construction_intake_wrong_schema")
    if type(context) is not ChainContext:
        raise DirectIntakeRefusal("construction_chain_context_required")
    if type(receiver) is not str or not receiver or facts.get("receiver") != receiver:
        raise DirectIntakeRefusal("intake_receiver_mismatch")
    if (facts.get("network"), facts.get("genesis"), facts.get("netuid")) != (
        context.network,
        context.genesis_hash,
        context.netuid,
    ):
        raise DirectIntakeRefusal("construction_intake_chain_mismatch")
    challenge = recipe.to_dict()["challenge"]
    if facts.get("challenge") != {
        "id": challenge["id"],
        "version": challenge["version"],
    }:
        raise DirectIntakeRefusal("construction_intake_challenge_mismatch")
    if (
        facts.get("discovery_path") != INFO_PATH
        or facts.get("path") != SUBMIT_PATH
        or facts.get("tools")
        not in ([SUBMIT_TOOL, STATUS_TOOL], [SUBMIT_TOOL, STATUS_TOOL, SOURCE_TOOL])
        or facts.get("score_pack") is not None
        or facts.get("qualification") is not False
        or facts.get("reward") is not False
    ):
        raise DirectIntakeRefusal("construction_intake_contract_mismatch")
    served_contracts = facts.get("served_contracts")
    if type(served_contracts) is not list or not any(
        type(served) is dict and served.get("digest") == contract_digest
        for served in served_contracts
    ):
        raise DirectIntakeRefusal("construction_contract_not_served")
    snapshot = facts.get("snapshot")
    if type(snapshot) is not dict or type(snapshot.get("id")) is not str:
        raise DirectIntakeRefusal("construction_snapshot_unavailable")
    return ChallengeKey(challenge["id"], challenge["version"]), snapshot["id"]


def _refusal_code(answer, fallback):
    if type(answer) is dict:
        code = answer.get("code") or answer.get("refused")
        if type(code) is str and code:
            return code
    return fallback


def _outcome(
    answer,
    *,
    contract_digest,
    challenge,
    task_id=None,
    pinned=None,
    evidence_label="DEVELOPMENT_PUBLIC_SYNTHETIC",
):
    """Check the existing public validator envelope and lean outcome contract."""
    if (
        type(answer) is not dict
        or set(answer) != RESULT_FIELDS
        or answer.get("schema") != RESULT_SCHEMA
        or answer.get("kind") != "OUTCOME"
        or answer.get("code") is not None
        or answer.get("evidence") != "DEVELOPMENT"
        or answer.get("qualification") is not False
        or answer.get("reward") is not False
    ):
        raise DirectIntakeRefusal("construction_intake_answer_unrecognised")
    identities = answer.get("pinned")
    if (
        type(identities) is not dict
        or set(identities) != PINNED_FIELDS
        or identities.get("contract_digest") != contract_digest
        or not all(is_digest(value) for value in identities.values())
        or (pinned is not None and identities != pinned)
    ):
        raise DirectIntakeRefusal("construction_intake_identity_mismatch")
    result = answer.get("outcome")
    try:
        check_outcome(
            result,
            SimpleNamespace(
                challenge_id=challenge.challenge_id,
                challenge_version=challenge.version,
                disclosure_fields=frozenset(
                    {"task_id", "state_digest", "predictions_digest"}
                ),
            ),
        )
    except OutcomeContractViolation:
        raise DirectIntakeRefusal("construction_intake_answer_unrecognised") from None
    if (
        result.get("schema") != OUTCOME_SCHEMA
        or result.get("evidence") != evidence_label
        or result.get("state") not in (TERMINAL | {"ADMITTED"})
        or type(result.get("task_id")) is not str
        or not result["task_id"]
        or result.get("submission_id") != result["task_id"]
        or (task_id is not None and result["task_id"] != task_id)
    ):
        raise DirectIntakeRefusal("construction_intake_answer_unrecognised")
    state = result["state"]
    if state == "RECONSTRUCTED":
        if (
            not is_digest(result.get("state_digest"))
            or not is_digest(result.get("predictions_digest"))
            or "failure" in result
        ):
            raise DirectIntakeRefusal("construction_intake_answer_unrecognised")
    elif state == "ADMITTED":
        if any(
            key in result for key in ("state_digest", "predictions_digest", "failure")
        ):
            raise DirectIntakeRefusal("construction_intake_answer_unrecognised")
    else:
        failure = result.get("failure")
        if (
            type(failure) is not dict
            or type(failure.get("code")) is not str
            or not 0 < len(failure["code"]) <= 128
            or not failure["code"].isprintable()
            or any(key in result for key in ("state_digest", "predictions_digest"))
        ):
            raise DirectIntakeRefusal("construction_intake_answer_unrecognised")
    return result, identities


def _body(facts, *, recipe, contract_digest, receiver, context, tool, fields, request):
    challenge, snapshot = _checked(
        facts,
        recipe=recipe,
        contract_digest=contract_digest,
        receiver=receiver,
        context=context,
    )
    body = message(
        context,
        snapshot,
        challenge,
        session="carbon-construction-intake",
        request=request,
        tool=tool,
        fields=fields,
    )
    if len(body) > MAX_BODY:
        raise DirectIntakeRefusal("construction_intake_body_oversized")
    return body


def _record_path(root, epoch, *, retry_of=None):
    suffix = "" if retry_of is None else f"-retry-{retry_of}"
    return Path(root) / f"construction-intake-epoch-{int(epoch)}{suffix}.json"


def _binding(url, recipe, contract_digest, receiver, context, epoch, retry_of=None):
    binding = {
        "schema": RECORD_SCHEMA,
        "url": url,
        "epoch": int(epoch),
        "receiver": receiver,
        "context": asdict(context),
        "challenge": {
            "id": recipe.to_dict()["challenge"]["id"],
            "version": recipe.to_dict()["challenge"]["version"],
        },
        "recipe_digest": recipe.digest,
        "contract_digest": contract_digest,
    }
    if retry_of is not None:
        binding["retry_of_submission_id"] = retry_of
    return binding


def _retry_child(task_id, retry_of):
    try:
        ResearchTaskId(task_id)
    except (TypeError, ValueError):
        raise DirectIntakeRefusal("construction_retry_child_invalid") from None
    if task_id == retry_of:
        raise DirectIntakeRefusal("construction_retry_child_invalid")


def submit_and_wait(
    url,
    signer,
    *,
    root,
    epoch,
    recipe,
    contract_digest,
    receiver,
    context,
    read=read_intake,
    send=post,
    clock=time.monotonic,
    sleep=time.sleep,
    wait_s=WAIT_S,
    observe_only=False,
    retry_of=None,
):
    """Submit one frozen recipe, then poll its owner-bound DEVELOPMENT task.

    Reopening an admitted attempt polls its recorded task. An explicit
    ``retry_of`` creates one child of an infrastructure-failed task only when
    the receiver advertises the exact retry capability. A distinct attempt
    journal binds that predecessor; response-loss replay is idempotent at the
    receiver. Neither polling nor an ordinary submit starts a new attempt.
    """
    if retry_of is not None:
        try:
            ResearchTaskId(retry_of)
        except (TypeError, ValueError):
            raise DirectIntakeRefusal(
                "construction_retry_predecessor_invalid"
            ) from None
    if type(observe_only) is not bool:
        raise DirectIntakeRefusal("construction_observation_mode_invalid")
    if observe_only and (type(wait_s) not in (int, float) or not 0 < wait_s <= 30):
        raise DirectIntakeRefusal("construction_observation_wait_invalid")
    if type(recipe) is not ConstructionRecipe:
        recipe = ConstructionRecipe.from_dict(recipe)
    if type(context) is not ChainContext:
        raise DirectIntakeRefusal("construction_chain_context_required")
    from carbon.development_session.intake_targets import intake_url
    from carbon.reconstruction.served_recipe_contract import registered

    if not intake_url(url):
        raise DirectIntakeRefusal("construction_intake_url_invalid")
    challenge = recipe.to_dict()["challenge"]
    expected_challenge = ChallengeKey(challenge["id"], challenge["version"])
    try:
        registered_contract = registered(challenge["id"], challenge["version"])
    except LookupError:
        raise DirectIntakeRefusal("construction_contract_not_registered") from None
    if (
        registered_contract.construction_kit != challenge
        or registered_contract.digest != contract_digest
    ):
        raise DirectIntakeRefusal("construction_contract_binding_mismatch")
    binding = _binding(url, recipe, contract_digest, receiver, context, epoch, retry_of)
    record_path = _record_path(root, epoch, retry_of=retry_of)
    if observe_only and (
        record_path.is_symlink()
        or not record_path.is_file()
        or not 0 < record_path.stat().st_size <= 65536
    ):
        raise DirectIntakeRefusal("construction_admission_record_required")
    if record_path.exists():
        recorded = json.loads(record_path.read_bytes())
        if (
            type(recorded) is not dict
            or any(recorded.get(key) != value for key, value in binding.items())
            or ("retry_of_submission_id" in recorded) != (retry_of is not None)
        ):
            raise DirectIntakeRefusal("construction_intake_changed_since_submission")
        task_id = recorded.get("submission_id")
        pinned = recorded.get("pinned")
        if (
            type(task_id) is not str
            or not task_id
            or type(pinned) is not dict
            or set(pinned) != PINNED_FIELDS
            or pinned.get("contract_digest") != contract_digest
            or not all(is_digest(value) for value in pinned.values())
        ):
            raise DirectIntakeRefusal("construction_intake_record_invalid")
        if retry_of is not None:
            _retry_child(task_id, retry_of)
    else:
        # Even if a retained file disappears after preflight, an observation
        # must never enter the submission branch.
        if observe_only:
            raise DirectIntakeRefusal("construction_admission_record_required")
        admission_deadline = clock() + min(WAIT_S, max(30.0, wait_s))

        admission_attempts = 0

        def admit():
            nonlocal admission_attempts
            admission_attempts += 1
            facts = (
                read(url, timeout=min(10.0, admission_deadline - clock()))
                if read is read_intake
                else read(url)
            )
            if admission_attempts > 1:
                if admission_deadline - clock() <= 1.05:
                    raise DirectIntakeRateLimit()
                sleep(1.05)
            if admission_deadline <= clock():
                raise DirectIntakeRefusal("construction_request_deadline")
            fields = {
                "strategy_json": recipe.canonical_bytes.decode("utf-8"),
                "contract_digest": contract_digest,
            }
            if retry_of is not None:
                if (
                    type(facts) is not dict
                    or facts.get("construction_retry") != RETRY_CAPABILITY
                ):
                    raise DirectIntakeRefusal("construction_retry_unavailable")
                fields["retry_of_submission_id"] = retry_of
            body = _body(
                facts,
                recipe=recipe,
                contract_digest=contract_digest,
                receiver=receiver,
                context=context,
                tool=SUBMIT_TOOL,
                fields=fields,
                # A fresh transmission must not replay the gateway receipt.
                # Only the durable provider key identifies the retry attempt.
                request=(
                    f"construction-submit-{epoch}-{recipe.digest[7:39]}-{time.time_ns()}"
                    if retry_of is None
                    else f"construction-retry-{epoch}-{time.time_ns()}"
                ),
            )
            headers = BittensorMessageSigner(signer).sign(
                body, receiver=receiver, nonce_ns=time.time_ns()
            )
            remaining = admission_deadline - clock()
            if remaining <= 0:
                raise DirectIntakeRefusal("construction_request_deadline")
            status, answer = (
                send(url, body, headers, timeout=min(30.0, remaining))
                if send is post
                else send(url, body, headers)
            )
            if (
                status == 429
                and type(answer) is dict
                and answer.get("refused") == "rate"
            ):
                raise DirectIntakeRateLimit()
            if (
                status != 202
                or type(answer) is not dict
                or answer.get("kind") != "OUTCOME"
            ):
                raise DirectIntakeRefusal(
                    _refusal_code(answer, "construction_intake_unavailable")
                )
            outcome, pinned = _outcome(
                answer,
                contract_digest=contract_digest,
                challenge=expected_challenge,
                evidence_label=registered_contract.evidence_label,
            )
            if retry_of is not None:
                _retry_child(outcome["task_id"], retry_of)
            return outcome, pinned

        outcome, pinned = retry_rate_limited(
            admit,
            deadline=admission_deadline,
            clock=clock,
            sleep=sleep,
        )
        task_id = outcome["task_id"]
        write_once(
            record_path,
            json.dumps(
                {**binding, "submission_id": task_id, "pinned": pinned}, sort_keys=True
            ).encode(),
        )
        record_path.chmod(0o600)
        if outcome["state"] in TERMINAL:
            return outcome
    if wait_s == 0:
        # The tool door requests admission only. A same-moment STATUS call can
        # hit the signed transport's rate limit, even though SUBMIT succeeded.
        raise DirectConstructionPending(task_id)
    deadline = clock() + wait_s
    while True:
        observation_attempts = 0

        def observe():
            nonlocal observation_attempts
            observation_attempts += 1
            facts = (
                read(url, timeout=min(10.0, deadline - clock()))
                if read is read_intake
                else read(url)
            )
            if observation_attempts > 1:
                if deadline - clock() <= 1.05:
                    raise DirectIntakeRateLimit()
                sleep(1.05)
            if deadline <= clock():
                raise DirectIntakeRefusal("construction_request_deadline")
            body = _body(
                facts,
                recipe=recipe,
                contract_digest=contract_digest,
                receiver=receiver,
                context=context,
                tool=STATUS_TOOL,
                fields={"submission_id": task_id},
                request=f"construction-status-{epoch}-{time.time_ns()}",
            )
            # The signer currently has a read-only kind only for battery_status.
            # This DEVELOPMENT status uses its ordinary signed-call kind.
            headers = BittensorMessageSigner(signer).sign(
                body, receiver=receiver, nonce_ns=time.time_ns()
            )
            remaining = deadline - clock()
            if remaining <= 0:
                raise DirectIntakeRefusal("construction_request_deadline")
            status, answer = (
                send(url, body, headers, timeout=min(30.0, remaining))
                if send is post
                else send(url, body, headers)
            )
            if (
                status == 429
                and type(answer) is dict
                and answer.get("refused") == "rate"
            ):
                raise DirectIntakeRateLimit()
            if (
                status != 200
                or type(answer) is not dict
                or answer.get("kind") != "OUTCOME"
            ):
                raise DirectIntakeRefusal(
                    _refusal_code(answer, "construction_status_unavailable")
                )
            outcome, _ = _outcome(
                answer,
                contract_digest=contract_digest,
                challenge=expected_challenge,
                task_id=task_id,
                pinned=pinned,
                evidence_label=registered_contract.evidence_label,
            )
            return outcome

        outcome = retry_rate_limited(
            observe, deadline=deadline, clock=clock, sleep=sleep
        )
        if outcome.get("state") in TERMINAL:
            return outcome
        if outcome.get("state") != "ADMITTED":
            raise DirectIntakeRefusal("construction_intake_answer_unrecognised")
        if clock() >= deadline:
            raise DirectConstructionPending(task_id)
        sleep(min(POLL_S, max(0.0, deadline - clock())))
        if clock() >= deadline:
            raise DirectConstructionPending(task_id)
