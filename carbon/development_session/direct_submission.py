"""Miner-side signed submission to the bounded DEVELOPMENT recipe receiver.

This client has a separate wire contract from Battery. It records the first
admitted task before polling so a restart can only ask about that task. A
reconstructed result is construction evidence, never a scored verdict.
"""

from __future__ import annotations

import json
import os
import random
import re
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
from carbon.miner_agent import MINER_HEADERS
from carbon.registry.model import ChallengeKey
from carbon.transport.models import MAX_BODY, message

#: The most bytes read from one door reply (CAPS.md 3 item 7: was 64 KiB, which cut a larger reply mid-JSON and broke the
#: client; no harm named). A reply is still parsed whole or refused.
REPLY_READ_BYTES = 1024 * 1024
RECORD_SCHEMA = "carbon.construction.intake-submission.v1"
INFO_PATH = "/carbon/v1/construction/intake"
SUBMIT_PATH = "/carbon/v1/mcp"
PUBLIC_SCHEMA = "carbon.construction.intake-public.v1"
SUBMIT_TOOL = "construction_submit"
STATUS_TOOL = "construction_status"
SOURCE_TOOL = "carbon_research_v2"
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
    """Closed reason; neither a model score nor a scientific failure.

    ``retry`` is the receiver's public scheduling facts for a limit refusal (the next round's block and time,
    and its plain sentence); empty for every other refusal."""

    def __init__(self, code: str, retry=None):
        super().__init__(code)
        self.code = code
        self.retry = dict(retry or {})


class DirectConstructionPending(DirectIntakeRefusal):
    """Admission is pending for this already validated remote task identity."""

    def __init__(self, task_id: str):
        super().__init__("construction_task_queued")
        self.task_id = task_id


class DirectSameRecipeSubmitted(DirectIntakeRefusal):
    """The receiver already graded this hotkey's recipe on its current exam
    set (Validator ruling (a)): nothing was graded and no exam was used.
    `earlier` is that submission's own checked outcome."""

    code_name = "same_recipe_already_submitted"

    def __init__(self, earlier: dict):
        super().__init__(self.code_name)
        self.earlier = earlier


class DirectIntakeRateLimit(DirectIntakeRefusal):
    """Only the receiver's explicit pre-admission HTTP 429 rate envelope."""

    def __init__(self):
        super().__init__("rate")


#: The receiver's typed transport refusal for a request that lost the door's ordering check (store.admit: a request whose
#: time or chain snapshot is behind one it already admitted, which concurrent requests on a busy door can do). It is refused
#: BEFORE admission, nothing was recorded, so a rebuilt, re-signed request is safe to send again. It is not the miner's clock.
TRANSPORT_STALE = "TRANSPORT_STALE"
#: Automatic resends of a request refused TRANSPORT_STALE, each rebuilt and signed afresh, after a short jittered wait.
BUSY_RETRIES = 2


class DirectIntakeDoorBusy(DirectIntakeRateLimit):
    """The door's connection cap refused this request before reading it: HTTP 503 `intake_busy` with Retry-After.

    Nothing was admitted, charged or recorded, so a rebuilt, re-signed request may be sent again (bounded, jittered).
    """

    def __init__(self, retry_after_s=None, code="intake_busy"):
        DirectIntakeRefusal.__init__(self, code)
        self.retry_after_s = retry_after_s


#: The door's 503 while it is drained for an update: ``{"status": "updating", "message", "retry_after_s"}``. The client
#: names it ``door_updating`` (a refusal code, so the miner's page and kit say what to do, not a bare HTTP status).
DOOR_UPDATING_STATUS = "updating"
DOOR_UPDATING = "door_updating"
#: Tries (the first send included) and the longest single wait for a door that answers `intake_busy` (about a minute in all).
DOOR_BUSY_TRIES = 6
#: The door's row-free 503 refusals (nothing read, admitted, recorded or charged): its connection cap and its in-flight bound.
DOOR_BUSY_CODES = ("intake_busy", "capacity")
DOOR_BUSY_MAX_WAIT_S = 30.0


def _door_busy_wait(attempt, retry_after_s):
    """Seconds to wait after the `attempt`-th (1-based) `intake_busy`: Retry-After, doubling, capped, plus jitter."""
    base = min(
        max(float(retry_after_s or 1.0), 1.0) * 2 ** (attempt - 1), DOOR_BUSY_MAX_WAIT_S
    )
    return base + random.uniform(0.0, 0.25 * base)


def _raise_if_pre_admission_refusal(status, answer):
    """Raise the typed pre-admission refusal for HTTP 429 `rate` or HTTP 503 `intake_busy`; otherwise return."""
    if type(answer) is not dict:
        return
    if status == 429 and answer.get("refused") == "rate":
        raise DirectIntakeRateLimit()
    if status == 503 and answer.get("refused") in DOOR_BUSY_CODES:
        raise DirectIntakeDoorBusy(answer.get("retry_after_s"), answer["refused"])
    if status == 503 and answer.get("status") == DOOR_UPDATING_STATUS:
        # The door is drained for an update and says so at once (`battery.intake.updating_answer`): nothing was read,
        # admitted or charged. Its own sentence and retry hint reach the miner; no automatic resend (a drain lasts
        # minutes, not the seconds `intake_busy` backs off for).
        raise DirectIntakeRefusal(
            DOOR_UPDATING, _refusal_retry({"retry": answer}, DOOR_UPDATING)
        )


class DirectIntakeBusy(DirectIntakeRefusal):
    """The door was busy: it refused the request as TRANSPORT_STALE before admitting anything."""

    def __init__(self):
        super().__init__(TRANSPORT_STALE)


def _busy_wait():
    """The jittered pause before a resend after TRANSPORT_STALE (seconds)."""
    return random.uniform(0.25, 0.75)


def retry_rate_limited(operation, *, deadline, clock=time.monotonic, sleep=time.sleep):
    """Retry only an explicit pre-admission HTTP rate refusal (and a TRANSPORT_STALE one, a few times), within a deadline.

    The operation must rebuild and sign its request on every attempt. Other
    refusals and ambiguous network failures propagate without replay.
    """
    last = None
    busy = 0
    door_busy = 0
    for attempt in range(31):
        if clock() >= deadline:
            if last is not None:
                raise last
            raise DirectIntakeRefusal("construction_request_deadline")
        try:
            return operation()
        except DirectIntakeBusy as refused:
            # TRANSPORT_STALE: refused before admission, so the rebuilt and re-signed request may be sent again, at most
            # BUSY_RETRIES times, after a short jittered wait; then the typed refusal reaches the miner.
            last = refused
            busy += 1
            remaining = deadline - clock()
            if busy > BUSY_RETRIES or remaining <= 0:
                raise
            sleep(min(_busy_wait(), remaining))
            if clock() >= deadline:
                raise
        except DirectIntakeDoorBusy as refused:
            # intake_busy: refused before the body was read, so nothing happened. At most DOOR_BUSY_TRIES sends, each
            # rebuilt and signed afresh, waiting Retry-After (doubling, capped, jittered); then the typed refusal.
            last = refused
            door_busy += 1
            remaining = deadline - clock()
            if door_busy >= DOOR_BUSY_TRIES or remaining <= 0:
                raise
            sleep(min(_door_busy_wait(door_busy, refused.retry_after_s), remaining))
            if clock() >= deadline:
                raise
        except DirectIntakeRateLimit as refused:
            last = refused
            remaining = deadline - clock()
            if remaining <= 0 or attempt == 30:
                raise
            sleep(min(1.0, remaining))
            if clock() >= deadline:
                raise


def _preflight_catalog(recipe, facts):
    """Refuse a catalog recipe the door would refuse, naming the fix."""
    from carbon.development_session import catalog_preflight

    try:
        catalog_preflight.check(recipe.to_dict(), facts)
    except catalog_preflight.CatalogPreflightRefused as refused:
        error = DirectIntakeRefusal(refused.code)
        error.fix = refused.fix
        raise error from None


def _terms_fields(facts):
    """The signed acceptance fields for the submission terms the door requires (owner G-LEAD-50); refuses typed, before
    anything is signed, when this machine holds no acceptance of exactly that version and text.
    """
    from carbon.development_session import submission_terms

    try:
        return submission_terms.submission_fields(facts)
    except submission_terms.TermsRefused as refused:
        raise DirectIntakeRefusal(refused.code) from None


PREFLIGHT_TOOL = "construction_preflight"
PREFLIGHT_REPLY_SCHEMA = "carbon.construction.preflight-reply.v1"
STALE_BURN_REFUSALS = frozenset(
    {
        "fee_already_spent",
        "fee_extrinsic_expired",
        "fee_burn_not_found",
        "fee_before_policy_min_block",
    }
)


class _StaleBurnReceipt(Exception):
    def __init__(self, extrinsic_id: str):
        super().__init__(extrinsic_id)
        self.extrinsic_id = extrinsic_id


def _validate_fee_facts(
    facts, context, expected_challenge, *, receiver: str | None = None
) -> dict | None:
    """Return validated ``facts['fee']`` dict, or None when the door requires no fee (`N5`)."""
    if type(facts) is not dict:
        raise DirectIntakeRefusal("fee_facts_invalid")
    fee = facts.get("fee")
    if fee is None:
        return None
    if type(fee) is not dict:
        raise DirectIntakeRefusal("fee_facts_invalid")
    remark_ver = fee.get("remark_version")
    fee_receiver = fee.get("receiver")
    lookback = fee.get("max_lookback_blocks", 21_600)
    if (
        type(fee.get("policy_version")) is not str
        or not fee["policy_version"]
        or type(fee.get("amount_rao")) is not int
        or isinstance(fee.get("amount_rao"), bool)
        or fee["amount_rao"] <= 0
        or fee.get("netuid") != context.netuid
        or fee.get("challenge_id") != expected_challenge.challenge_id
        or type(fee.get("min_block")) is not int
        or isinstance(fee.get("min_block"), bool)
        or type(lookback) is not int
        or isinstance(lookback, bool)
        or not 1 <= lookback <= 2_600_000
        or fee.get("preflight_tool") != PREFLIGHT_TOOL
        or (remark_ver is not None and remark_ver != "carbon.fee.v2")
        or (
            receiver is not None
            and fee_receiver is not None
            and fee_receiver != receiver
        )
    ):
        raise DirectIntakeRefusal("fee_facts_invalid")
    return fee


def _preflight_and_resolve_fee(
    url,
    signer,
    *,
    facts,
    root,
    epoch,
    recipe,
    contract_digest,
    receiver,
    context,
    expected_challenge,
    registered_contract,
    terms_fields,
    read,
    send,
    clock,
    sleep,
    admission_deadline,
    fee_extrinsic=None,
    fee_credit_id=None,
    fee_poster=None,
    limit_price_rao=None,
    ignore_unspent_extrinsic: str | None = None,
):
    """Run 0-TAO ``construction_preflight`` and obtain credit or finalized burn fields.

    Returns ``(updated_facts, payment_fields_dict, used_extrinsic_or_None, poster_or_None, payment_elapsed_s)``.
    - Burns `pf_answer["fee"]["amount_rao"]` (never stale cached `/info`, `H1`).
    - Runs preflight in its own `retry_rate_limited` loop (`H13`).
    - Returns `payment_elapsed_s` so TTY confirmation + chain finalization are excluded
      from the HTTP `admission_deadline` (`B9`).
    """
    fee_info = _validate_fee_facts(
        facts, context, expected_challenge, receiver=receiver
    )
    if fee_info is None:
        if fee_extrinsic is not None or fee_credit_id is not None:
            raise DirectIntakeRefusal("fee_not_required_by_door")
        return facts, {}, None, None, 0.0, False

    if fee_extrinsic is not None and fee_credit_id is not None:
        raise DirectIntakeRefusal("fee_fields_invalid")

    pf_attempts = 0
    pf_stale = False
    cur_facts = facts

    def send_preflight():
        nonlocal pf_attempts, pf_stale, cur_facts
        pf_attempts += 1
        paced = pf_attempts > 1 and not pf_stale
        pf_stale = False
        if pf_attempts > 1:
            cur_facts = (
                read(url, timeout=min(10.0, max(1.0, admission_deadline - clock())))
                if read is read_intake
                else read(url)
            )
            if (
                _validate_fee_facts(
                    cur_facts, context, expected_challenge, receiver=receiver
                )
                is None
            ):
                return None
        if paced:
            if admission_deadline - clock() <= 1.05:
                raise DirectIntakeRateLimit()
            sleep(1.05)
        remaining = admission_deadline - clock()
        if remaining <= 0:
            raise DirectIntakeRefusal("construction_request_deadline")
        pf_body = _body(
            cur_facts,
            recipe=recipe,
            contract_digest=contract_digest,
            receiver=receiver,
            context=context,
            tool=PREFLIGHT_TOOL,
            fields={
                "strategy_json": recipe.canonical_bytes.decode("utf-8"),
                "contract_digest": contract_digest,
                **terms_fields,
            },
            request=f"construction-preflight-{int(epoch)}-{time.time_ns()}",
        )
        pf_headers = BittensorMessageSigner(signer).sign(
            pf_body, receiver=receiver, nonce_ns=time.time_ns()
        )
        pf_status, pf_answer = (
            send(url, pf_body, pf_headers, timeout=min(30.0, remaining))
            if send is post
            else send(url, pf_body, pf_headers)
        )
        _raise_if_pre_admission_refusal(pf_status, pf_answer)
        if (
            pf_status == 400
            and type(pf_answer) is dict
            and pf_answer.get("kind") == "REFUSED"
            and pf_answer.get("code") == DirectSameRecipeSubmitted.code_name
        ):
            earlier, _ = _outcome(
                pf_answer,
                contract_digest=contract_digest,
                challenge=expected_challenge,
                evidence_label=registered_contract.evidence_label,
                kind="REFUSED",
                code=DirectSameRecipeSubmitted.code_name,
            )
            raise DirectSameRecipeSubmitted(earlier)
        if pf_status != 200 or type(pf_answer) is not dict:
            code = _refusal_code(pf_answer, "fee_preflight_unavailable")
            if code == TRANSPORT_STALE:
                pf_stale = True
                raise DirectIntakeBusy()
            raise DirectIntakeRefusal(code, _refusal_retry(pf_answer, code))
        return pf_answer

    pf_answer = retry_rate_limited(
        send_preflight,
        deadline=admission_deadline,
        clock=clock,
        sleep=sleep,
    )
    if pf_answer is None:
        # Door hot-disabled its fee mid-preflight (`H3`).
        return cur_facts, {}, None, None, 0.0, False

    if (
        pf_answer.get("schema") != PREFLIGHT_REPLY_SCHEMA
        or pf_answer.get("admissible") is not True
    ):
        raise DirectIntakeRefusal("fee_preflight_reply_invalid")

    live_fee = _validate_fee_facts(
        {"fee": pf_answer.get("fee")},
        context,
        expected_challenge,
        receiver=receiver,
    )
    if live_fee is None:
        raise DirectIntakeRefusal("fee_preflight_reply_invalid")

    if fee_credit_id is not None:
        return (
            cur_facts,
            {"fee_credit_id": fee_credit_id},
            None,
            None,
            0.0,
            False,
        )
    if fee_extrinsic is not None:
        return (
            cur_facts,
            {"fee_extrinsic": fee_extrinsic},
            fee_extrinsic,
            None,
            0.0,
            False,
        )

    if (
        pf_answer.get("fee_status") == "CREDIT_AVAILABLE"
        and type(pf_answer.get("credit_id")) is str
    ):
        return (
            cur_facts,
            {"fee_credit_id": pf_answer["credit_id"]},
            None,
            None,
            0.0,
            False,
        )

    server_unspent = [
        x
        for x in (pf_answer.get("unspent_extrinsics") or [])
        if type(x) is str and x != ignore_unspent_extrinsic
    ]

    poster = fee_poster
    if poster is None:
        from carbon.chain.external_signer import ExternalSigner, request_fee_burn
        from carbon.chain.fee_poster import FeePoster, SdkFeeBurnChain

        if type(signer) is ExternalSigner:
            poster = FeePoster(
                hotkey=signer.ss58_address,
                receiver=receiver,
                netuid=context.netuid,
                challenge_id=expected_challenge.challenge_id,
                chain=SdkFeeBurnChain(context),
                sign=lambda req: request_fee_burn(signer, req),
            )
        elif server_unspent:
            return (
                cur_facts,
                {"fee_extrinsic": server_unspent[0]},
                server_unspent[0],
                None,
                0.0,
                False,
            )
        else:
            raise DirectIntakeRefusal("fee_poster_required")

    from carbon.chain.external_signer import SignerFailure
    from carbon.chain.models import ChainFailure

    pay_started = clock()
    try:
        obtained = poster.obtain_extrinsic(
            amount_rao=int(live_fee["amount_rao"]),
            min_block=int(live_fee["min_block"]),
            max_lookback_blocks=int(live_fee.get("max_lookback_blocks", 21_600)),
            limit_price_rao=limit_price_rao,
            server_unspent=server_unspent,
        )
    except SignerFailure as sf:
        raise DirectIntakeRefusal(sf.refusal or sf.code) from None
    except ChainFailure as cf:
        raise DirectIntakeRefusal(cf.code.value) from None
    payment_elapsed_s = max(0.0, clock() - pay_started)
    from carbon.chain.fee_poster import DONE as _FEE_DONE

    if (
        obtained.get("code") not in _FEE_DONE
        or type(obtained.get("extrinsic_id")) is not str
    ):
        retry_hint = (
            {"retry_after_s": int(obtained["retry_after_s"])}
            if type(obtained.get("retry_after_s")) is int
            else None
        )
        raise DirectIntakeRefusal(
            str(obtained.get("code") or "fee_burn_failed"), retry_hint
        )

    ext_id = obtained["extrinsic_id"]
    freshly_burned = obtained.get("code") == "fee_burn_finalized"
    if freshly_burned:
        cur_facts = read(url, timeout=10.0) if read is read_intake else read(url)
    return (
        cur_facts,
        {"fee_extrinsic": ext_id},
        ext_id,
        poster,
        payment_elapsed_s,
        freshly_burned,
    )


def read_intake(url: str, *, timeout: float = 10.0) -> dict:
    from carbon.development_session.intake_targets import intake_url

    if not intake_url(url):
        raise DirectIntakeRefusal("construction_intake_url_invalid")
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                url.rstrip("/") + INFO_PATH, headers=MINER_HEADERS, method="GET"
            ),
            timeout=timeout,
        ) as response:
            facts = json.loads(response.read(REPLY_READ_BYTES))
    except urllib.error.HTTPError as refused:
        if refused.code in (429, 503):
            answer = json.loads(refused.read(REPLY_READ_BYTES) or b"{}")
            if type(answer) is dict and refused.code == 503:
                answer["retry_after_s"] = _retry_after_s(refused.headers)
            _raise_if_pre_admission_refusal(refused.code, answer)
        raise
    if type(facts) is not dict or facts.get("schema") != PUBLIC_SCHEMA:
        raise DirectIntakeRefusal("construction_intake_wrong_schema")
    return facts


def post(url, body, headers, *, timeout=30.0):
    request = urllib.request.Request(
        url.rstrip("/") + SUBMIT_PATH,
        data=body,
        headers={**MINER_HEADERS, **headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read(REPLY_READ_BYTES))
    except urllib.error.HTTPError as refused:
        answer = json.loads(refused.read(REPLY_READ_BYTES) or b"{}")
        if refused.code == 503 and type(answer) is dict:
            answer["retry_after_s"] = _retry_after_s(refused.headers)
        return refused.code, answer


def _retry_after_s(headers):
    """The Retry-After header as seconds (a plain number), or None."""
    try:
        return float(headers.get("Retry-After")) if headers is not None else None
    except (TypeError, ValueError):
        return None


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


#: The receiver's public facts a limit refusal may carry (`exam_cap`): a number, two short strings; the door's own
#: retry hint in whole seconds (`door_updating`).
_RETRY_FIELDS = {
    "next_block": int,
    "next_utc": str,
    "message": str,
    "retry_after_s": int,
}
#: The refusals whose receiver sentence (`retry.message`) the client keeps: the two round and daily limits, the
#: one-waiting-submission rule (per coldkey or per hotkey), the allowance-group refusals, and a door drained for an
#: update. Each is refused before anything is built or graded, so the sentence is the miner's whole answer.
LIMIT_CODES = (
    "epoch_limit_reached",
    "exam_daily_allowance_reached",
    "hotkey_submission_waiting",
    "coldkey_submission_waiting",
    "allowance_group_unmapped",
    "allowance_group_unresolved",
    DOOR_UPDATING,
)


def _refusal_retry(answer, code):
    """The closed ``retry`` facts of a limit refusal, else {}: only these fields, only these types."""
    retry = answer.get("retry") if type(answer) is dict else None
    if code not in LIMIT_CODES or type(retry) is not dict:
        return {}
    return {
        name: retry[name]
        for name, kind in _RETRY_FIELDS.items()
        if type(retry.get(name)) is kind and len(str(retry[name])) <= 600
    }


def _refusal_code(answer, fallback):
    if type(answer) is dict:
        code = answer.get("code") or answer.get("refused")
        if type(code) is str and code:
            return code
    return fallback


#: What a result read of an already-recorded submission must still match (owner via the Lead, 15 Nov 2026: results must
#: survive a door update). The door's CODE identity (implementation_digest, and identities_digest over the door's whole
#: identity document) moves with every door update that touches its served source; the task id already binds the
#: hotkey, contract, recipe and pack. So a status read requires the SAME contract and the SAME score rule as recorded,
#: and accepts a changed code identity. A submission still requires the door's exact identities (no pinned record yet).
_RESULT_READ_FIELDS = ("contract_digest", "rule_digest")


def _same_task_rule(identities, pinned):
    """Whether the door's ``identities`` answer for the task ``pinned`` was recorded for: same contract, same rule."""
    return type(pinned) is dict and all(
        identities.get(field) == pinned.get(field) for field in _RESULT_READ_FIELDS
    )


def _outcome(
    answer,
    *,
    contract_digest,
    challenge,
    task_id=None,
    pinned=None,
    evidence_label="DEVELOPMENT_PUBLIC_SYNTHETIC",
    kind="OUTCOME",
    code=None,
):
    """Check the existing public validator envelope and lean outcome contract
    (an OUTCOME, or a refusal that carries an earlier outcome)."""
    if (
        type(answer) is not dict
        or set(answer) != RESULT_FIELDS
        or answer.get("schema") != RESULT_SCHEMA
        or answer.get("kind") != kind
        or answer.get("code") != code
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
        or (pinned is not None and not _same_task_rule(identities, pinned))
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


def _attempt_path(root, epoch):
    return Path(root) / f"construction-intake-epoch-{int(epoch)}.attempt"


def _submit_attempt(root, epoch):
    path = _attempt_path(root, epoch)
    try:
        value = int(path.read_text(encoding="ascii"))
    except (OSError, ValueError):
        return 0
    return value if 0 <= value < 1000 else 0


def _cancelled_by_stop(outcome):
    """Whether a terminal outcome is the validator's own cancellation of the task (`direct_task_cancelled`: a stop before it
    ran), not a result about the candidate."""
    failure = outcome.get("failure")
    return (
        outcome.get("state") == "FAILED_INFRA"
        and type(failure) is dict
        and failure.get("code") == "direct_task_cancelled"
    )


def _withdrawn_by_miner(outcome):
    """Whether a terminal outcome is the miner's OWN withdrawal of the queued task (`withdrawn_by_miner`): never a verdict."""
    failure = outcome.get("failure") if type(outcome) is dict else None
    return (
        outcome.get("state") == "FAILED_INFRA"
        and type(failure) is dict
        and failure.get("code") == WITHDRAWN_CODE
    )


def _record_names(record_path, task_id):
    """Whether the admission record at ``record_path`` exists now and names ``task_id`` (read again, never assumed)."""
    try:
        if record_path.is_symlink():
            return False
        recorded = json.loads(record_path.read_bytes())
    except (OSError, ValueError):
        return False
    return type(recorded) is dict and recorded.get("submission_id") == task_id


def _set_cancelled_record_aside(
    root, epoch, record_path, label="cancelled", task_id=None
):
    """Keep the cancelled (or, ``label`` "withdrawn", the miner-withdrawn) task's admission record under its own name (never
    deleted) and make the next submit a NEW request (a bumped request id), so the frozen recipe is submitted again for a
    fresh task. With ``task_id``, only while the record still names that task: a record another call already set aside,
    or one that names a newer task, is left alone (returns False). The aside name is taken with a hard link, which never
    replaces an existing file, so two callers can never write over each other's aside copy.
    """
    if task_id is not None and not _record_names(record_path, task_id):
        return False
    for n in range(1, 1000):
        aside = record_path.with_name(record_path.stem + f".{label}-{n}.json")
        try:
            os.link(record_path, aside)
        except FileExistsError:
            continue
        except FileNotFoundError:
            return False  # another call set it aside first
        break
    else:  # pragma: no cover - a thousand cancelled generations of one epoch
        raise DirectIntakeRefusal("construction_cancelled_records_exhausted")
    try:
        os.unlink(record_path)
    except FileNotFoundError:
        return False  # another call set it aside first (its own aside copy is kept)
    _bump_submit_attempt(root, epoch)
    return True


def _bump_submit_attempt(root, epoch):
    path = _attempt_path(root, epoch)
    if path.is_symlink():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(_submit_attempt(root, epoch) + 1), encoding="ascii")


def _submit_request(root, epoch, recipe):
    """The submit's request id: this campaign's, this epoch's and this
    recipe's, so two campaigns on one hotkey that freeze the same recipe never
    share one (M1 E2E H16: the second read TRANSPORT_CONFLICT forever), and a
    new one after the receiver reports a conflict. A retry of the same body
    keeps the same id (exact replay)."""
    import hashlib

    campaign = hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:16]
    request = f"construction-submit-{int(epoch)}-{recipe.digest[7:39]}-{campaign}"
    attempt = _submit_attempt(root, epoch)
    return request if attempt == 0 else f"{request}-r{attempt}"


def _record_path(root, epoch):
    return Path(root) / f"construction-intake-epoch-{int(epoch)}.json"


def _binding(url, recipe, contract_digest, receiver, context, epoch):
    return {
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


FEEDBACK_TOOL = "exam_feedback"
FEEDBACK_REPLY_SCHEMA = "carbon.private-exam.ladder-feedback-reply.v1"
FEEDBACK_FACTS = {
    "tool": FEEDBACK_TOOL,
    "fields": [],
    "reply_schema": FEEDBACK_REPLY_SCHEMA,
    "path": SUBMIT_PATH,
    "owner": "authenticated_hotkey",
}
#: The same read for one of the signer's own submissions, with its grade state: advertised only by
#: a receiver that grades its own submissions (`direct_intake.FEEDBACK_REPLY_SCHEMA_V2`).
FEEDBACK_REPLY_SCHEMA_V2 = "carbon.private-exam.ladder-feedback-reply.v2"
FEEDBACK_V2_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V2,
}
GRADE_STATES = (
    "GRADED",
    "QUEUED",
    "SUPERSEDED_BY_OWN_LATER_SUBMIT",
    "ROUND_LIMIT_REACHED",
)
#: v3: v2 plus CANDIDATE_FAILED (`direct_intake.FEEDBACK_REPLY_SCHEMA_V3`); asked for only where advertised.
FEEDBACK_REPLY_SCHEMA_V3 = "carbon.private-exam.ladder-feedback-reply.v3"
FEEDBACK_V3_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V3,
}
GRADE_STATES_V3 = (*GRADE_STATES, "CANDIDATE_FAILED")
#: v4: v3's states plus RECONSTRUCTION_FAILED, FAILED_INFRA and NOT_GRADED, and the allow-listed ``failure`` of a
#: failed candidate run (`direct_intake.FEEDBACK_REPLY_SCHEMA_V4`); asked for only where advertised.
FEEDBACK_REPLY_SCHEMA_V4 = "carbon.private-exam.ladder-feedback-reply.v4"
FEEDBACK_V4_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V4,
}
GRADE_STATES_V4 = (
    *GRADE_STATES_V3,
    "RECONSTRUCTION_FAILED",
    "FAILED_INFRA",
    "NOT_GRADED",
)
#: v5: v4 plus CROWN_HELD_FOR_REVIEW (the caller's own submission is a filed contender while a menu-D version's crown
#: change is held for review, `crown_hold`) and ``held_position`` {place, of} or None (`direct_intake`
#: FEEDBACK_REPLY_SCHEMA_V5, TE-B 7 Nov); asked for only where advertised.
FEEDBACK_REPLY_SCHEMA_V5 = "carbon.private-exam.ladder-feedback-reply.v5"
FEEDBACK_V5_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V5,
}
#: v6: v5 plus ``submission.gate_failures`` (`direct_intake` FEEDBACK_REPLY_SCHEMA_V6, owner 14 Nov): for the caller's own gate-failed grade the
#: failing OUTPUTS with one closed reason each (`gate_failure_feedback`), else None; asked for only where advertised.
FEEDBACK_REPLY_SCHEMA_V6 = "carbon.private-exam.ladder-feedback-reply.v6"
FEEDBACK_V6_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V6,
}
#: v7: v6 whose Ladder documents may carry the NOT_SCORED reasons TIMED_OUT / STOPPED_EARLY (`direct_intake`
#: FEEDBACK_REPLY_SCHEMA_V7, Validator-2 15 Nov); asked for only where advertised. An older reply withholds those documents.
FEEDBACK_REPLY_SCHEMA_V7 = "carbon.private-exam.ladder-feedback-reply.v7"
FEEDBACK_V7_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V7,
}
#: v8: v7 plus the failure's ``pass`` (which pass of a counted grade a wall stop ended) and ``grade_worker`` (the public facts of
#: the grading machine) (`direct_intake` FEEDBACK_REPLY_SCHEMA_V8, Lead 15 Nov); asked for only where advertised.
FEEDBACK_REPLY_SCHEMA_V8 = "carbon.private-exam.ladder-feedback-reply.v8"
FEEDBACK_V8_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V8,
}
#: v9: v8 plus the grade state WITHDRAWN_BY_MINER (the signer withdrew this submission while it was still queued, `withdraw_submission`)
#: (`direct_intake` FEEDBACK_REPLY_SCHEMA_V9, owner GO 15 Nov); asked for only where advertised. An older reply says NOT_GRADED.
FEEDBACK_REPLY_SCHEMA_V9 = "carbon.private-exam.ladder-feedback-reply.v9"
FEEDBACK_V9_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V9,
}
WITHDRAWN_STATE = "WITHDRAWN_BY_MINER"
#: v10: v9 plus ``submission.failure_class``: for the signer's own FAILED_INFRA build, the closed public row of its failure
#: class (`FAILURE_CLASS_KEYS`; side ``carbon``), else None (`direct_intake` FEEDBACK_REPLY_SCHEMA_V10, owner P0 20 Nov).
FEEDBACK_REPLY_SCHEMA_V10 = "carbon.private-exam.ladder-feedback-reply.v10"
FEEDBACK_V10_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V10,
}
#: v11: v10 plus the recipe-side row (side ``yours``) in ``failure_class`` for the signer's own RECONSTRUCTION_FAILED build whose
#: daily spot was used (`direct_intake` FEEDBACK_REPLY_SCHEMA_V11, G-LEAD-10 row 1).
FEEDBACK_REPLY_SCHEMA_V11 = "carbon.private-exam.ladder-feedback-reply.v11"
FEEDBACK_V11_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V11,
}
#: v12: v11 plus ``submission.rerun_task_id``: when the DOOR re-ran the signer's own submission as a new task, grade state
#: ``RERUN`` and the new id (read that id for the result), else None (`direct_intake` FEEDBACK_REPLY_SCHEMA_V12, miner-ux 6054,
#: v2 6039 (3) / FINAL 885). Asked for only where advertised.
FEEDBACK_REPLY_SCHEMA_V12 = "carbon.private-exam.ladder-feedback-reply.v12"
FEEDBACK_V12_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V12,
}
#: v13: v12 plus ``submission.refusal_detail``: for the signer's own refused graph build (RECONSTRUCTION_FAILED), the closed
#: public detail code of that refusal (for example ``graph_route_nonfinite_state``), else None (`direct_intake`
#: FEEDBACK_REPLY_SCHEMA_V13, owner G-LEAD-78). Asked for only where advertised.
FEEDBACK_REPLY_SCHEMA_V13 = "carbon.private-exam.ladder-feedback-reply.v13"
FEEDBACK_V13_FACTS = {
    **FEEDBACK_FACTS,
    "fields": ["reply", "submission_id"],
    "reply_schema": FEEDBACK_REPLY_SCHEMA_V13,
}
RERUN_STATE = "RERUN"
#: The closed keys of a failure-class row (`infra_diagnosis.PUBLIC_ROW_KEYS`; a test holds them equal).
FAILURE_CLASS_KEYS = (
    "code",
    "what_happened",
    "side",
    "charged",
    "next_step",
    "retried_or_owed",
)
#: A bound on one sentence of a failure-class row (a resource bound, not a policy value).
MAX_FAILURE_CLASS_TEXT = 400
FAILURE_PASSES = ("graded_pass", "inference_pair", "menu_rowcheck", "early_stop")
GRADE_WORKER_KEYS = ("cpu_model", "cpu_count", "memory_bytes", "gpu")
HELD_STATE = "CROWN_HELD_FOR_REVIEW"
GRADE_STATES_V5 = (*GRADE_STATES_V4, HELD_STATE)
GRADE_STATES_V9 = (*GRADE_STATES_V5, WITHDRAWN_STATE)
GRADE_STATES_V12 = (*GRADE_STATES_V9, RERUN_STATE)
#: A task id a v12 reply may name as the re-run (the door's own ids; a resource bound on anything else).
_TASK_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
#: A refused build's closed detail code (a resource bound on its shape; the door checks it against its own closed table).
_DETAIL_CODE = re.compile(r"[a-z0-9_]{1,64}")
#: A bound on the held count a reply may name (a resource bound, not a policy value).
MAX_HELD = 100000
FAILURE_CHILDREN = ("build", "inference")
FAILURE_OBSERVATIONS = (
    "WORKER_MEMORY_LIMIT_REACHED",
    "WORKER_WALL_LIMIT_REACHED",
    "OOM_KILLED",
    "NONZERO_EXIT",
    "OWN_ALLOWANCE_ELAPSED",
)
FAILURE_LIMITS = (
    "memory_bytes_max",
    "build_wall_seconds_max",
    "inference_wall_seconds_max",
)
FAILURE_KEYS = ("child", "observation", "limit", "code")


def _failure_v4(value):
    """Whether a v4 reply's ``failure`` is None or exactly its allow-listed shape (closed values only)."""
    if value is None:
        return True
    if type(value) is not dict or set(value) != set(FAILURE_KEYS):
        return False
    limit = value["limit"]
    return (
        (value["child"] is None or value["child"] in FAILURE_CHILDREN)
        and (
            value["observation"] is None or value["observation"] in FAILURE_OBSERVATIONS
        )
        and (
            limit is None
            or (
                type(limit) is dict
                and set(limit) == {"name", "value"}
                and limit["name"] in FAILURE_LIMITS
                and type(limit["value"]) is int
                and limit["value"] > 0
            )
        )
        and (
            value["code"] is None
            or (
                type(value["code"]) is str
                and re.fullmatch(r"[a-z0-9_]{1,64}", value["code"]) is not None
            )
        )
    )


def _gate_failures_v6(failures):
    """A v6 reply's ``gate_failures``: None, or exactly the closed list `gate_failure_feedback` emits (output names and one of two
    reasons, nothing else)."""
    from carbon.challenge_validator import gate_failure_feedback

    return failures is None or gate_failure_feedback.valid(failures)


def _failure_v8(value):
    """Whether a v8 reply's ``failure`` is None or v4's allow-listed shape plus ``pass`` (one of `FAILURE_PASSES` or None)."""
    if value is None:
        return True
    if type(value) is not dict or set(value) != {*FAILURE_KEYS, "pass"}:
        return False
    if value["pass"] is not None and value["pass"] not in FAILURE_PASSES:
        return False
    return _failure_v4({k: value[k] for k in FAILURE_KEYS})


def _grade_worker_v8(value):
    """Whether a v8 reply's ``grade_worker`` is exactly its public shape: a printable CPU model of at most 96 characters or None,
    positive integer CPU count and memory bytes or None, and a Boolean GPU flag."""

    def positive(item):
        return item is None or (
            type(item) is int and not isinstance(item, bool) and item > 0
        )

    return (
        type(value) is dict
        and set(value) == set(GRADE_WORKER_KEYS)
        and (
            value["cpu_model"] is None
            or (
                type(value["cpu_model"]) is str
                and 0 < len(value["cpu_model"]) <= 96
                and value["cpu_model"].isprintable()
            )
        )
        and positive(value["cpu_count"])
        and positive(value["memory_bytes"])
        and type(value["gpu"]) is bool
    )


def _held_position_v5(grade_state, held):
    """A v5 reply's ``held_position``: {place, of} with 1 <= place <= of exactly when the submission is held, else
    None. Anything else is refused, never trimmed."""
    if grade_state != HELD_STATE:
        return held is None
    return (
        type(held) is dict
        and set(held) == {"place", "of"}
        and type(held["place"]) is int
        and type(held["of"]) is int
        and 1 <= held["place"] <= held["of"] <= MAX_HELD
    )


def _failure_class_v10(grade_state, row, *, v11):
    """A v10 / v11 reply's ``failure_class``: None, or exactly the closed public row (`FAILURE_CLASS_KEYS`, plain bounded
    sentences) on the one state that carries it: FAILED_INFRA (Carbon's side), or from v11 RECONSTRUCTION_FAILED (the
    recipe's side). Anything else is refused, never trimmed."""
    if row is None:
        return True
    if type(row) is not dict or set(row) != set(FAILURE_CLASS_KEYS):
        return False
    sentences = (row["what_happened"], row["next_step"], row["retried_or_owed"])
    if not (
        type(row["code"]) is str
        and re.fullmatch(r"[a-z0-9_]{1,64}", row["code"]) is not None
        and type(row["charged"]) is bool
        and all(
            type(text) is str
            and 0 < len(text) <= MAX_FAILURE_CLASS_TEXT
            and text.isprintable()
            for text in sentences
        )
    ):
        return False
    if grade_state == "FAILED_INFRA":
        return row["side"] == "carbon"
    return v11 and grade_state == "RECONSTRUCTION_FAILED" and row["side"] == "yours"


def _rerun_v12(grade_state, rerun_task_id, submission_id):
    """A v12 reply's ``rerun_task_id``: a task id other than the asked one exactly when the state is RERUN, else None."""
    if grade_state != RERUN_STATE:
        return rerun_task_id is None
    return (
        type(rerun_task_id) is str
        and _TASK_ID.fullmatch(rerun_task_id) is not None
        and rerun_task_id != submission_id
    )


def _refusal_detail_v13(grade_state, code):
    """A v13 reply's ``refusal_detail``: None, or a closed code on RECONSTRUCTION_FAILED only."""
    if code is None:
        return True
    return (
        grade_state == "RECONSTRUCTION_FAILED"
        and type(code) is str
        and _DETAIL_CODE.fullmatch(code) is not None
    )


#: Each feedback reply after v1, newest first: its number, what a door that offers it advertises, and its schema. A kit asks
#: for the newest one advertised; a door that offers vN offers every older field too.
FEEDBACK_REPLIES = (
    (13, FEEDBACK_V13_FACTS, FEEDBACK_REPLY_SCHEMA_V13),
    (12, FEEDBACK_V12_FACTS, FEEDBACK_REPLY_SCHEMA_V12),
    (11, FEEDBACK_V11_FACTS, FEEDBACK_REPLY_SCHEMA_V11),
    (10, FEEDBACK_V10_FACTS, FEEDBACK_REPLY_SCHEMA_V10),
    (9, FEEDBACK_V9_FACTS, FEEDBACK_REPLY_SCHEMA_V9),
    (8, FEEDBACK_V8_FACTS, FEEDBACK_REPLY_SCHEMA_V8),
    (7, FEEDBACK_V7_FACTS, FEEDBACK_REPLY_SCHEMA_V7),
    (6, FEEDBACK_V6_FACTS, FEEDBACK_REPLY_SCHEMA_V6),
    (5, FEEDBACK_V5_FACTS, FEEDBACK_REPLY_SCHEMA_V5),
    (4, FEEDBACK_V4_FACTS, FEEDBACK_REPLY_SCHEMA_V4),
    (3, FEEDBACK_V3_FACTS, FEEDBACK_REPLY_SCHEMA_V3),
    (2, FEEDBACK_V2_FACTS, FEEDBACK_REPLY_SCHEMA_V2),
)
#: The grade states a reply may name, by the number it starts at, newest first.
_STATES_FROM = (
    (12, GRADE_STATES_V12),
    (9, GRADE_STATES_V9),
    (5, GRADE_STATES_V5),
    (4, GRADE_STATES_V4),
    (3, GRADE_STATES_V3),
    (0, GRADE_STATES),
)


def _submission_valid(number, submission, submission_id, states):
    """Whether a v``number`` reply's ``submission`` is exactly the closed shape that reply may carry for ``submission_id``."""
    keys = {"submission_id", "grade_state"}
    for start, name in (
        (4, "failure"),
        (5, "held_position"),
        (6, "gate_failures"),
        (8, "grade_worker"),
        (10, "failure_class"),
        (12, "rerun_task_id"),
        (13, "refusal_detail"),
    ):
        if number >= start:
            keys.add(name)
    if type(submission) is not dict or set(submission) != keys:
        return False
    if submission["submission_id"] != submission_id:
        return False
    state = submission["grade_state"]
    if state is None:
        return number < 4
    if state not in states:
        return False
    if number >= 4:
        failure = _failure_v8 if number >= 8 else _failure_v4
        if not failure(submission["failure"]):
            return False
    if number >= 5 and not _held_position_v5(state, submission["held_position"]):
        return False
    if number >= 6 and not _gate_failures_v6(submission["gate_failures"]):
        return False
    if number >= 8 and not _grade_worker_v8(submission["grade_worker"]):
        return False
    if number >= 10 and not _failure_class_v10(
        state, submission["failure_class"], v11=number >= 11
    ):
        return False
    if number >= 12 and not _rerun_v12(
        state, submission["rerun_task_id"], submission_id
    ):
        return False
    return number < 13 or _refusal_detail_v13(state, submission["refusal_detail"])


def read_exam_feedback(
    url,
    signer,
    *,
    recipe,
    contract_digest,
    receiver,
    context,
    read=read_intake,
    send=post,
    submission_id=None,
):
    """The signer's own private-exam Ladder documents for the active exam
    (OWNER-GRADE-FEEDBACK-LADDER-01): ``{"best", "latest"}``, the best None
    before a result improved it and the latest None before any graded result.
    With ``submission_id`` and a receiver that advertises the v2 read, also
    ``"submission": {"submission_id", "grade_state"}`` (one of `GRADE_STATES`, or
    None for none of them); a receiver without it answers the v1 read. Where v4 is
    advertised it is asked for: the grade state is then never None (`GRADE_STATES_V4`)
    and ``"failure"`` says why a candidate run failed (`_failure_v4`, closed values).

    Only the builder's allow-listed fields are accepted back: a reply of any
    other shape is refused, never trimmed."""
    from carbon.challenge_validator.ladder_store import LadderStoreRefused, checked

    if type(recipe) is not ConstructionRecipe:
        raise DirectIntakeRefusal("construction_recipe_required")
    facts = read(url)
    if facts.get("exam_feedback") != FEEDBACK_FACTS:
        raise DirectIntakeRefusal("exam_feedback_unavailable")
    number, schema = 1, FEEDBACK_REPLY_SCHEMA
    if submission_id is not None:
        for offered, advertised, reply_schema in FEEDBACK_REPLIES:
            if facts.get(f"exam_feedback_v{offered}") == advertised:
                number, schema = offered, reply_schema
                break
    fields = {} if number < 2 else {"submission_id": submission_id}
    if number >= 3:
        fields["reply"] = f"v{number}"
    states = next(known for start, known in _STATES_FROM if number >= start)
    body = _body(
        facts,
        recipe=recipe,
        contract_digest=contract_digest,
        receiver=receiver,
        context=context,
        tool=FEEDBACK_TOOL,
        fields=fields,
        request=f"exam-feedback-{time.time_ns()}",
    )
    headers = BittensorMessageSigner(signer).sign(
        body, receiver=receiver, nonce_ns=time.time_ns()
    )
    status, answer = send(url, body, headers)
    if status != 200 or type(answer) is not dict:
        raise DirectIntakeRefusal(_refusal_code(answer, "exam_feedback_unavailable"))
    challenge = recipe.to_dict()["challenge"]
    keys = {"schema", "challenge", "best", "latest"}
    if number >= 2:
        keys.add("submission")
    if (
        set(answer) != keys
        or answer["schema"] != schema
        or answer["challenge"]
        != {"id": challenge["id"], "version": challenge["version"]}
    ):
        raise DirectIntakeRefusal("exam_feedback_reply_invalid")
    if number >= 2 and not _submission_valid(
        number, answer["submission"], submission_id, states
    ):
        raise DirectIntakeRefusal("exam_feedback_reply_invalid")
    try:
        return {
            **({"submission": dict(answer["submission"])} if number >= 2 else {}),
            "best": None if answer["best"] is None else checked(answer["best"]),
            "latest": (
                None
                if answer["latest"] is None
                else checked(answer["latest"], latest=True)
            ),
        }
    except LadderStoreRefused:
        raise DirectIntakeRefusal("exam_feedback_reply_invalid") from None


def _refuse_withdrawn(root, epoch, record_path, outcome):
    """A task its miner withdrew while queued is never this epoch's verdict: its admission record is set aside (only while
    it still names that task), so the next submit is a fresh task of the same frozen candidate, and the read is refused
    ``withdrawn_by_miner`` (an observation too), so no caller stores it as the epoch's feedback.
    """
    if _withdrawn_by_miner(outcome):
        _set_cancelled_record_aside(
            root, epoch, record_path, label="withdrawn", task_id=outcome.get("task_id")
        )
        raise DirectWithdrawRefused(WITHDRAWN_CODE)


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
    fee_extrinsic=None,
    fee_credit_id=None,
    fee_poster=None,
    limit_price_rao=None,
    _after_cancel=False,
):
    """Submit one frozen recipe, then poll its owner-bound DEVELOPMENT task.

    A recorded task the validator CANCELLED (a restart or door switch stopped it before it ran) is not the candidate's result:
    the old record is kept aside and ONE new task is submitted from the same frozen recipe (the validator starts a fresh
    generation of a task that ended on its own side), instead of polling the cancelled id for ever.

    A retry after admission polls the recorded task; it never signs another
    submission. A lost HTTP response can be retried because the validator's
    task identity is derived from owner and recipe, not this request nonce.
    """
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
    binding = _binding(url, recipe, contract_digest, receiver, context, epoch)
    record_path = _record_path(root, epoch)
    if observe_only and (
        record_path.is_symlink()
        or not record_path.is_file()
        or not 0 < record_path.stat().st_size <= 65536
    ):
        raise DirectIntakeRefusal("construction_admission_record_required")
    if record_path.exists():
        recorded = json.loads(record_path.read_bytes())
        if type(recorded) is not dict or any(
            recorded.get(key) != value for key, value in binding.items()
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
    else:
        # Even if a retained file disappears after preflight, an observation
        # must never enter the submission branch.
        if observe_only:
            raise DirectIntakeRefusal("construction_admission_record_required")
        admission_deadline = clock() + min(WAIT_S, max(30.0, wait_s))
        ignored_unspent: str | None = None
        outcome = pinned = None

        def _run_submit_phase(
            attempt_index,
            initial_submit_facts,
            initial_terms_fields,
            resolved_fee_fields,
            resolved_extrinsic,
            resolved_poster,
            freshly_burned,
        ):
            nonlocal admission_deadline
            admission_attempts = 0
            stale = False
            cur_submit_facts = initial_submit_facts
            cur_terms_fields = initial_terms_fields

            def admit():
                nonlocal admission_attempts, stale, admission_deadline, cur_submit_facts, cur_terms_fields
                admission_attempts += 1
                paced = admission_attempts > 1 and not stale
                stale = False
                if admission_attempts == 1:
                    facts = cur_submit_facts
                else:
                    facts = (
                        read(
                            url,
                            timeout=min(10.0, max(1.0, admission_deadline - clock())),
                        )
                        if read is read_intake
                        else read(url)
                    )
                    _preflight_catalog(recipe, facts)
                    cur_terms_fields = _terms_fields(facts)
                if paced:
                    if admission_deadline - clock() <= 1.05:
                        raise DirectIntakeRateLimit()
                    sleep(1.05)

                # `B9`: Dedicated inner finality-lag retry loop (up to 5 * 6s = 30s)
                # so `409 fee_not_finalized` NEVER consumes `BUSY_RETRIES` or stale `deadline`!
                for finality_try in range(6):
                    if finality_try > 0:
                        _bump_submit_attempt(root, epoch)
                        admission_deadline += 6.0
                        sleep(6.0)
                        facts = (
                            read(
                                url,
                                timeout=min(
                                    10.0, max(1.0, admission_deadline - clock())
                                ),
                            )
                            if read is read_intake
                            else read(url)
                        )
                        _preflight_catalog(recipe, facts)
                        cur_terms_fields = _terms_fields(facts)

                    if admission_deadline <= clock():
                        raise DirectIntakeRefusal("construction_request_deadline")
                    body = _body(
                        facts,
                        recipe=recipe,
                        contract_digest=contract_digest,
                        receiver=receiver,
                        context=context,
                        tool=SUBMIT_TOOL,
                        fields={
                            "strategy_json": recipe.canonical_bytes.decode("utf-8"),
                            "contract_digest": contract_digest,
                            **cur_terms_fields,
                            **(
                                resolved_fee_fields
                                if facts.get("fee") is not None
                                else {}
                            ),
                        },
                        request=_submit_request(root, epoch, recipe),
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
                    _raise_if_pre_admission_refusal(status, answer)
                    if (
                        status == 400
                        and type(answer) is dict
                        and answer.get("kind") == "REFUSED"
                        and answer.get("code") == DirectSameRecipeSubmitted.code_name
                    ):
                        earlier, _ = _outcome(
                            answer,
                            contract_digest=contract_digest,
                            challenge=expected_challenge,
                            evidence_label=registered_contract.evidence_label,
                            kind="REFUSED",
                            code=DirectSameRecipeSubmitted.code_name,
                        )
                        raise DirectSameRecipeSubmitted(earlier)
                    if (
                        status != 202
                        or type(answer) is not dict
                        or answer.get("kind") != "OUTCOME"
                    ):
                        code = _refusal_code(answer, "construction_intake_unavailable")
                        if (
                            status == 409
                            and code == "fee_not_finalized"
                            and finality_try < 5
                        ):
                            continue
                        if code == TRANSPORT_STALE:
                            stale = True
                            raise DirectIntakeBusy()
                        if code == "TRANSPORT_CONFLICT":
                            _bump_submit_attempt(root, epoch)
                        # `M1` & `B7(b)`: NEVER auto-prune or re-burn a receipt freshly
                        # minted in THIS call! For cached `REUSED_UNSPENT` receipts,
                        # prune on `fee_already_spent` / `fee_before_policy_min_block`,
                        # and on `fee_burn_not_found` / `fee_extrinsic_expired` ONLY when
                        # the poster's own chain reader confirms the extrinsic is absent!
                        if (
                            code in STALE_BURN_REFUSALS
                            and not freshly_burned
                            and resolved_extrinsic is not None
                            and fee_extrinsic is None
                            and attempt_index == 0
                        ):
                            can_prune = code in (
                                "fee_already_spent",
                                "fee_before_policy_min_block",
                            )
                            if not can_prune and resolved_poster is not None:
                                check_fn = getattr(
                                    resolved_poster,
                                    "confirm_extrinsic_missing_on_chain",
                                    None,
                                )
                                if callable(check_fn):
                                    can_prune = bool(check_fn(resolved_extrinsic))
                            if can_prune:
                                _bump_submit_attempt(root, epoch)
                                raise _StaleBurnReceipt(resolved_extrinsic)
                        raise DirectIntakeRefusal(code, _refusal_retry(answer, code))
                    return _outcome(
                        answer,
                        contract_digest=contract_digest,
                        challenge=expected_challenge,
                        evidence_label=registered_contract.evidence_label,
                    )
                raise DirectIntakeRefusal("fee_not_finalized")

            return retry_rate_limited(
                admit,
                deadline=admission_deadline,
                clock=clock,
                sleep=sleep,
            )

        used_extrinsic = None
        active_poster = None
        for stale_burn_attempt in range(2):
            initial_facts = (
                read(url, timeout=min(10.0, max(1.0, admission_deadline - clock())))
                if read is read_intake
                else read(url)
            )
            _preflight_catalog(recipe, initial_facts)
            terms_fields = _terms_fields(initial_facts)
            (
                submit_facts,
                fee_fields,
                used_extrinsic,
                active_poster,
                payment_elapsed_s,
                freshly_burned,
            ) = _preflight_and_resolve_fee(
                url,
                signer,
                facts=initial_facts,
                root=root,
                epoch=epoch,
                recipe=recipe,
                contract_digest=contract_digest,
                receiver=receiver,
                context=context,
                expected_challenge=expected_challenge,
                registered_contract=registered_contract,
                terms_fields=terms_fields,
                read=read,
                send=send,
                clock=clock,
                sleep=sleep,
                admission_deadline=admission_deadline,
                fee_extrinsic=fee_extrinsic,
                fee_credit_id=fee_credit_id,
                fee_poster=fee_poster,
                limit_price_rao=limit_price_rao,
                ignore_unspent_extrinsic=ignored_unspent,
            )
            # Exclude TTY confirmation + chain finalization from HTTP deadline (`B9`).
            admission_deadline += payment_elapsed_s

            try:
                outcome, pinned = _run_submit_phase(
                    stale_burn_attempt,
                    submit_facts,
                    terms_fields,
                    fee_fields,
                    used_extrinsic,
                    active_poster,
                    freshly_burned,
                )
                break
            except _StaleBurnReceipt as stale_burn:
                ignored_unspent = stale_burn.extrinsic_id
                if active_poster is not None:
                    active_poster.prune_unspent(stale_burn.extrinsic_id)
                continue
        task_id = outcome["task_id"]
        # `M3`: Persist `record_path` FIRST, before best-effort `note_spent`!
        write_once(
            record_path,
            json.dumps(
                {**binding, "submission_id": task_id, "pinned": pinned}, sort_keys=True
            ).encode(),
        )
        record_path.chmod(0o600)
        if used_extrinsic is not None and active_poster is not None:
            import contextlib

            with contextlib.suppress(Exception):
                active_poster.note_spent(used_extrinsic)
        if outcome["state"] in TERMINAL:
            _refuse_withdrawn(root, epoch, record_path, outcome)
            return outcome
    if wait_s == 0:
        # The tool door requests admission only. A same-moment STATUS call can
        # hit the signed transport's rate limit, even though SUBMIT succeeded.
        raise DirectConstructionPending(task_id)
    deadline = clock() + wait_s
    while True:
        observation_attempts = 0
        stale = False

        def observe():
            nonlocal observation_attempts, stale
            observation_attempts += 1
            paced = observation_attempts > 1 and not stale
            stale = False
            facts = (
                read(url, timeout=min(10.0, deadline - clock()))
                if read is read_intake
                else read(url)
            )
            if paced:
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
            _raise_if_pre_admission_refusal(status, answer)
            if (
                status != 200
                or type(answer) is not dict
                or answer.get("kind") != "OUTCOME"
            ):
                code = _refusal_code(answer, "construction_status_unavailable")
                if code == TRANSPORT_STALE:
                    stale = True
                    raise DirectIntakeBusy()
                raise DirectIntakeRefusal(code)
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
            _refuse_withdrawn(root, epoch, record_path, outcome)
            if _cancelled_by_stop(outcome) and not observe_only and not _after_cancel:
                _set_cancelled_record_aside(
                    root, epoch, record_path, task_id=outcome.get("task_id")
                )
                return submit_and_wait(
                    url,
                    signer,
                    root=root,
                    epoch=epoch,
                    recipe=recipe,
                    contract_digest=contract_digest,
                    receiver=receiver,
                    context=context,
                    read=read,
                    send=send,
                    clock=clock,
                    sleep=sleep,
                    wait_s=wait_s,
                    observe_only=observe_only,
                    fee_extrinsic=fee_extrinsic,
                    fee_credit_id=fee_credit_id,
                    fee_poster=fee_poster,
                    limit_price_rao=limit_price_rao,
                    _after_cancel=True,
                )
            return outcome
        if outcome.get("state") != "ADMITTED":
            raise DirectIntakeRefusal("construction_intake_answer_unrecognised")
        if clock() >= deadline:
            raise DirectConstructionPending(task_id)
        sleep(min(POLL_S, max(0.0, deadline - clock())))
        if clock() >= deadline:
            raise DirectConstructionPending(task_id)


#: A miner withdraws its OWN queued, not-yet-building official submission (owner GO 15 Nov 2026 via the Lead): the door's
#: tool and its public facts entry, pinned exactly (`direct_intake.withdraw_facts`), never part of the pinned `tools` list.
WITHDRAW_TOOL = "construction_withdraw"
#: The outcome code of a task its miner withdrew (`lean_recipe.WITHDRAWN_CODE`).
WITHDRAWN_CODE = "withdrawn_by_miner"
WITHDRAW_FACTS_NAME = "construction_withdraw_v1"
WITHDRAW_FACTS = {
    "tool": WITHDRAW_TOOL,
    "fields": ["submission_id"],
    "states": ["QUEUED"],
    "path": SUBMIT_PATH,
    "owner": "authenticated_hotkey",
}
#: The door's withdraw refusals, and this kit's own, in plain words for the miner.
#: Said with every withdrawal (owner GO 15 Nov 2026): a withdrawal is not free of consequence for the same model.
WITHDRAW_RETRY_WORDS = "Each withdrawal of the same model counts toward the validator's limit of retries for that model on this exam."
#: What the miner reads when a withdrawal went through (the kit's answer, the Launchpad's message).
WITHDRAWN_WORDS = (
    "Withdrawn: it was not built or graded and used no try or allowance, and your waiting place is free. Your frozen "
    "candidate is kept: submit again when ready. " + WITHDRAW_RETRY_WORDS
)
WITHDRAW_WORDS = {
    "withdraw_not_offered": (
        "This validator does not take withdrawals yet; nothing was changed. Check for the result instead."
    ),
    "withdraw_unavailable": (
        "The validator could not complete the withdrawal just now: it may have happened but not be fully recorded "
        "yet. Run withdraw again (it is safe to repeat) or check_result."
    ),
    # A submit or result read that met the miner's own withdrawal: never the epoch's verdict.
    "withdrawn_by_miner": (
        "You withdrew this submission while it was still queued: it was not built or graded and used no try. Your "
        "frozen candidate is kept: submit again when ready. " + WITHDRAW_RETRY_WORDS
    ),
    "withdraw_too_late": (
        "This submission is already building or built (or has already ended); it can no longer be withdrawn. "
        "Check for the result instead."
    ),
    "withdraw_submission_unknown": (
        "This validator holds no queued submission of yours with this id, so there is nothing to withdraw. "
        "Check for the result of your latest submit."
    ),
    "withdraw_fields": (
        "The withdraw request was not one the validator reads (this kit and the validator disagree); nothing was "
        "withdrawn. Update your kit and try again."
    ),
    "no_queued_submission": (
        "No submit of this campaign reached a validator yet, so there is nothing to withdraw."
    ),
}


class DirectWithdrawRefused(DirectIntakeRefusal):
    """A withdrawal the door (or this kit) refused: its closed ``code`` and plain ``words`` for the miner."""

    def __init__(self, code):
        super().__init__(code)
        self.words = WITHDRAW_WORDS.get(
            code,
            "The validator refused the withdrawal ("
            + code
            + "); nothing was changed on your side.",
        )


def withdraw_submission(root, epoch, signer, *, read=read_intake, send=post):
    """Withdraw the epoch's own queued submission at the validator it was submitted to; returns the door's answer
    ``{"withdrawn": <submission id>, "grade_state": "WITHDRAWN_BY_MINER"}``.

    Everything the request binds (intake, receiver, chain context, contract, the submission id) comes from the epoch's own
    admission record and its frozen selection, as `refresh_exam_feedback` reads them; it is signed by the miner's signer,
    as every signed read and submit is. Refused `withdraw_unavailable` before anything is signed where the door does not
    advertise `WITHDRAW_FACTS` exactly. A withdrawal uses no try and no allowance; the validator frees the waiting place.
    On success the admission record is set aside under its own name (kept, never deleted) and the next submit is a NEW
    request, so the same frozen recipe can be submitted again as a fresh task. A withdrawn task is never resubmitted by
    itself (its code is ``withdrawn_by_miner``, not a stop's cancellation)."""
    root = Path(root)
    folder = root / ("epoch-" + str(int(epoch)))
    record_path = _record_path(root, epoch)
    try:
        if record_path.is_symlink():
            raise ValueError("record is a link")
        record = json.loads(record_path.read_bytes())
        selected = json.loads((folder / "selected-recipe.json").read_bytes())
        recipe = ConstructionRecipe.from_dict(selected["strategy"])
        context = ChainContext(**record["context"])
    except (OSError, ValueError, TypeError, KeyError):
        raise DirectWithdrawRefused("no_queued_submission") from None
    if type(record) is not dict:
        raise DirectWithdrawRefused("no_queued_submission")
    submission_id = record.get("submission_id")
    if (
        record.get("schema") != RECORD_SCHEMA
        or record.get("epoch") != int(epoch)
        or record.get("recipe_digest") != recipe.digest
        or type(submission_id) is not str
        or not submission_id
    ):
        raise DirectWithdrawRefused("no_queued_submission")
    url = record["url"]
    deadline = time.monotonic() + 60.0

    def once():
        facts = read(url)
        if facts.get(WITHDRAW_FACTS_NAME) != WITHDRAW_FACTS:
            raise DirectWithdrawRefused("withdraw_not_offered")
        body = _body(
            facts,
            recipe=recipe,
            contract_digest=record["contract_digest"],
            receiver=record["receiver"],
            context=context,
            tool=WITHDRAW_TOOL,
            fields={"submission_id": submission_id},
            request=f"construction-withdraw-{int(epoch)}-{time.time_ns()}",
        )
        headers = BittensorMessageSigner(signer).sign(
            body, receiver=record["receiver"], nonce_ns=time.time_ns()
        )
        status, answer = send(url, body, headers)
        _raise_if_pre_admission_refusal(status, answer)
        if status != 200 or type(answer) is not dict:
            code = _refusal_code(answer, "withdraw_unavailable")
            if code == TRANSPORT_STALE:
                raise DirectIntakeBusy()
            raise DirectWithdrawRefused(code)
        if answer != {"withdrawn": submission_id, "grade_state": WITHDRAWN_STATE}:
            raise DirectWithdrawRefused("withdraw_reply_invalid")
        return answer

    answer = retry_rate_limited(once, deadline=deadline)
    _set_cancelled_record_aside(
        root, epoch, record_path, label="withdrawn", task_id=submission_id
    )
    return answer


#: An epoch's Ladder as last read again by the miner (M1 E2E U53): the
#: permitted feedback is written once at submit, often before the receiver
#: grades it, so "Check for result" stores the fresh read beside it.
EXAM_FEEDBACK_FILE = "exam-feedback.json"
EXAM_FEEDBACK_SCHEMA = "carbon.construction.exam-feedback-read.v1"


def refresh_exam_feedback(root, epoch, signer, *, read=read_intake, send=post):
    """Read the miner's own Ladder again for a submitted epoch and store it
    beside the epoch's permitted feedback; returns the Ladder.

    Everything the read binds - intake, receiver, chain context, contract -
    comes from the epoch's own admission record, written when it was
    submitted, and the recipe from its frozen selection, so nothing here is
    chosen anew. Signed by the miner's signer, as the submit's own read is
    (Validator: a miner-pressed operation, no signer-scope change)."""
    from carbon.development_session.profile import canonical

    root = Path(root)
    folder = root / ("epoch-" + str(int(epoch)))
    record_path = _record_path(root, epoch)
    try:
        record = json.loads(record_path.read_bytes())
        stored = json.loads((folder / "permitted-final-feedback.json").read_bytes())
        selected = json.loads((folder / "selected-recipe.json").read_bytes())
        recipe = ConstructionRecipe.from_dict(selected["strategy"])
        context = ChainContext(**record["context"])
    except (OSError, ValueError, TypeError, KeyError):
        raise DirectIntakeRefusal("construction_admission_record_required") from None
    if (
        record_path.is_symlink()
        or record.get("schema") != RECORD_SCHEMA
        or record.get("epoch") != int(epoch)
        or record.get("recipe_digest") != recipe.digest
        or stored.get("recipe_digest") != recipe.digest
    ):
        raise DirectIntakeRefusal("construction_admission_record_required")
    ladder = read_exam_feedback(
        record["url"],
        signer,
        recipe=recipe,
        contract_digest=record["contract_digest"],
        receiver=record["receiver"],
        context=context,
        read=read,
        send=send,
        # the epoch's own submission, as recorded at admission: its grade state where the receiver serves it
        submission_id=(
            record["submission_id"]
            if type(record.get("submission_id")) is str
            else None
        ),
    )
    target = folder / EXAM_FEEDBACK_FILE
    staged = folder / (EXAM_FEEDBACK_FILE + ".tmp")
    staged.write_bytes(
        canonical(
            {
                "schema": EXAM_FEEDBACK_SCHEMA,
                "epoch": int(epoch),
                "recipe_digest": recipe.digest,
                "exam_feedback": ladder,
            }
        )
    )
    staged.replace(target)
    return ladder
