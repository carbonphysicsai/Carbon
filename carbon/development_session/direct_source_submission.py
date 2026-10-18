"""Send an owner's bounded graph bytes to the pinned DEVELOPMENT receiver.

The local research workspace remains the source of bytes. Each chunk uses the
receiver's ordinary signed gateway and its existing ``carbon_research_v2``
staging operation. A transport acknowledgement alone never establishes that
staging succeeded: the canonical nested ``ServiceReply`` must be OK.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path

from carbon import research
from carbon.chain.auth import BittensorMessageSigner
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    graph_envelope_from_workspace,
)
from carbon.level4 import staging
from carbon.transport.models import MAX_BODY, message

from .direct_submission import (
    SOURCE_TOOL,
    SUBMIT_PATH,
    DirectIntakeRateLimit,
    DirectIntakeRefusal,
    _checked,
    _refusal_code,
    post,
    read_intake,
    retry_rate_limited,
)
from .library_bundles import bundle_ref, load_pinned_bundle_directory

STAGE_REPLY_SCHEMA = "carbon.construction.source-stage-reply.v1"
STAGE_OPERATION = "stage_research_source"
STAGE_REQUEST_SCHEMA = "direct_stage_source_request_v1"
CHUNK_BYTES = 8192
MATERIAL_OPERATION = "stage_research_material"
MATERIAL_REQUEST_SCHEMA = "direct_stage_material_request_v1"
MATERIAL_CHUNK_BYTES = 24576


def _transfer_deadline(files, chunk_bytes):
    """Finite budget for the actual request count at the intake's 1/s refill."""
    calls = sum(
        max(1, (len(body) + chunk_bytes - 1) // chunk_bytes) for _, body in files
    )
    return time.monotonic() + max(120.0, 3.0 * calls + 120.0)


class _UploadPacer:
    """Use the receiver's observed 1/s refill after an explicit rate refusal."""

    def __init__(self):
        self.paced = False
        self.next_call = 0.0

    def before_call(self):
        if not self.paced:
            return
        delay = self.next_call - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self.next_call = time.monotonic() + 1.05

    def saw_rate(self):
        self.paced = True
        self.next_call = time.monotonic() + 1.05


def _stage_offered(facts):
    offered = facts.get("source_staging")
    if (
        type(offered) is not dict
        or offered.get("tool") != SOURCE_TOOL
        or offered.get("operation") != STAGE_OPERATION
        or offered.get("request_schema") != STAGE_REQUEST_SCHEMA
        or offered.get("reply_schema") != STAGE_REPLY_SCHEMA
        or offered.get("path") != SUBMIT_PATH
        or offered.get("owner") != "authenticated_hotkey"
        or SOURCE_TOOL not in facts.get("tools", ())
    ):
        raise DirectIntakeRefusal("construction_source_staging_unavailable")


def _stage_one(
    url,
    signer,
    *,
    recipe,
    contract_digest,
    receiver,
    context,
    name,
    body,
    expected_digest,
    read,
    send,
    deadline,
    pacer,
):
    fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    total = len(body)
    offset = 0
    while True:
        chunk = body[offset : offset + CHUNK_BYTES]

        def attempt(offset=offset, chunk=chunk):
            pacer.before_call()
            try:
                facts = read(url)
            except DirectIntakeRateLimit:
                pacer.saw_rate()
                raise
            challenge, snapshot = _checked(
                facts,
                recipe=recipe,
                contract_digest=contract_digest,
                receiver=receiver,
                context=context,
            )
            _stage_offered(facts)
            call = research.ServiceCall(
                research.RESEARCH_NAMESPACE,
                STAGE_OPERATION,
                research.DirectStageSourceRequestV1(
                    challenge,
                    name,
                    offset,
                    total,
                    fingerprint,
                    expected_digest,
                    chunk,
                ),
            )
            wire = message(
                context,
                snapshot,
                challenge,
                session="carbon-construction-source",
                request=f"construction-source-{time.time_ns()}",
                tool=SOURCE_TOOL,
                fields={
                    "call_base64": base64.b64encode(
                        research.canonical_bytes(call)
                    ).decode("ascii")
                },
            )
            if len(wire) > MAX_BODY:
                raise DirectIntakeRefusal("construction_source_chunk_oversized")
            headers = BittensorMessageSigner(signer).sign(
                wire, receiver=receiver, nonce_ns=time.time_ns()
            )
            pacer.before_call()
            status, answer = send(url, wire, headers)
            if (
                status == 429
                and type(answer) is dict
                and answer.get("refused") == "rate"
            ):
                pacer.saw_rate()
                raise DirectIntakeRateLimit()
            if status != 200 or type(answer) is not dict:
                raise DirectIntakeRefusal(
                    _refusal_code(answer, "construction_source_staging_unavailable")
                )
            if (
                answer.get("schema") != STAGE_REPLY_SCHEMA
                or type(answer.get("protocol_reply_base64")) is not str
            ):
                raise DirectIntakeRefusal("construction_source_reply_invalid")
            try:
                reply = research.load_canonical(
                    base64.b64decode(answer["protocol_reply_base64"], validate=True),
                    research.ServiceReply,
                )
            except (ValueError, TypeError):
                raise DirectIntakeRefusal("construction_source_reply_invalid") from None
            if reply.status is research.ReplyStatus.ERROR:
                raise DirectIntakeRefusal(
                    "construction_source_" + reply.result.code.value.lower()
                )
            result = reply.result
            if (
                type(result) is not research.DirectStageSourceResultV1
                or result.name != name
                or result.content_digest != fingerprint
                or not offset + len(chunk) <= result.received_bytes <= total
                or result.complete != (result.received_bytes == total)
            ):
                raise DirectIntakeRefusal("construction_source_reply_invalid")
            return result

        result = retry_rate_limited(attempt, deadline=deadline)
        if result.complete:
            return fingerprint
        # An earlier interrupted transfer can already hold many chunks. The
        # receiver's digest-bound offset is the next byte to send.
        offset = result.received_bytes


def stage_graph(
    url,
    signer,
    *,
    ledger,
    owner,
    recipe,
    contract_digest,
    receiver,
    context,
    expected_manifest_digest=None,
    read=read_intake,
    send=post,
):
    """Stage exact local graph files, documents first and manifest last.

    A second graph for the same owner can replace its remote manifest only
    when the caller supplies the prior manifest digest as a compare-and-swap
    expectation. Partial transfer can safely be retried with identical input.
    """
    if type(recipe) is not ConstructionRecipe:
        recipe = ConstructionRecipe.from_dict(recipe)
    challenge = recipe.to_dict()["challenge"]
    from carbon.reconstruction.served_recipe_contract import registered

    try:
        bound = registered(challenge["id"], challenge["version"])
    except LookupError:
        raise DirectIntakeRefusal("construction_contract_not_registered") from None
    if bound.construction_kit != challenge or bound.digest != contract_digest:
        raise DirectIntakeRefusal("construction_contract_binding_mismatch")
    if recipe.to_dict()["source"]["kind"] != "graph":
        raise DirectIntakeRefusal("construction_graph_source_required")
    if expected_manifest_digest is not None and (
        type(expected_manifest_digest) is not str
        or len(expected_manifest_digest) != 71
        or not expected_manifest_digest.startswith("sha256:")
        or any(c not in "0123456789abcdef" for c in expected_manifest_digest[7:])
    ):
        raise DirectIntakeRefusal("construction_expected_manifest_invalid")
    raw = graph_envelope_from_workspace(ledger, owner, recipe)
    submission, manifest, documents = staging.from_envelope(json.loads(raw))
    if submission != recipe.to_dict()["source"]["submission_digest"]:
        raise DirectIntakeRefusal("construction_graph_digest_mismatch")
    files = staging.workspace(manifest, documents)
    ordered = sorted(name for name in files if name != staging.WORKSPACE_MANIFEST)
    ordered.append(staging.WORKSPACE_MANIFEST)
    deadline = _transfer_deadline(
        [(name, files[name]) for name in ordered], CHUNK_BYTES
    )
    pacer = _UploadPacer()
    digests = {}
    for name in ordered:
        digests[name] = _stage_one(
            url,
            signer,
            recipe=recipe,
            contract_digest=contract_digest,
            receiver=receiver,
            context=context,
            name=name,
            body=files[name],
            expected_digest=(
                expected_manifest_digest if name == staging.WORKSPACE_MANIFEST else None
            ),
            read=read,
            send=send,
            deadline=deadline,
            pacer=pacer,
        )
    return {
        "schema": "carbon.construction.source-stage-result.v1",
        "submission_digest": submission,
        "manifest_digest": digests[staging.WORKSPACE_MANIFEST],
        "files": len(files),
        "bytes": sum(map(len, files.values())),
        "complete": True,
        "official_eligible": False,
    }


def _material_stage_offered(facts):
    offered = facts.get("material_staging")
    if (
        type(offered) is not dict
        or offered.get("tool") != SOURCE_TOOL
        or offered.get("operation") != MATERIAL_OPERATION
        or offered.get("request_schema") != MATERIAL_REQUEST_SCHEMA
        or offered.get("reply_schema") != STAGE_REPLY_SCHEMA
        or offered.get("path") != SUBMIT_PATH
        or offered.get("owner") != "authenticated_hotkey"
        or SOURCE_TOOL not in facts.get("tools", ())
    ):
        raise DirectIntakeRefusal("construction_material_staging_unavailable")


def _stage_material_one(
    url,
    signer,
    *,
    recipe,
    contract_digest,
    receiver,
    context,
    bundle_digest,
    name,
    body,
    final,
    read,
    send,
    deadline,
    pacer,
):
    fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    offset = 0
    while True:
        chunk = body[offset : offset + MATERIAL_CHUNK_BYTES]

        def attempt(offset=offset, chunk=chunk):
            pacer.before_call()
            try:
                facts = read(url)
            except DirectIntakeRateLimit:
                pacer.saw_rate()
                raise
            challenge, snapshot = _checked(
                facts,
                recipe=recipe,
                contract_digest=contract_digest,
                receiver=receiver,
                context=context,
            )
            _material_stage_offered(facts)
            call = research.ServiceCall(
                research.RESEARCH_NAMESPACE,
                MATERIAL_OPERATION,
                research.DirectStageMaterialRequestV1(
                    challenge,
                    bundle_digest,
                    name,
                    offset,
                    len(body),
                    fingerprint,
                    chunk,
                ),
            )
            wire = message(
                context,
                snapshot,
                challenge,
                session="carbon-construction-material",
                request=f"construction-material-{time.time_ns()}",
                tool=SOURCE_TOOL,
                fields={
                    "call_base64": base64.b64encode(
                        research.canonical_bytes(call)
                    ).decode("ascii")
                },
            )
            if len(wire) > MAX_BODY:
                raise DirectIntakeRefusal("construction_material_chunk_oversized")
            headers = BittensorMessageSigner(signer).sign(
                wire, receiver=receiver, nonce_ns=time.time_ns()
            )
            pacer.before_call()
            status, answer = send(url, wire, headers)
            if (
                status == 429
                and type(answer) is dict
                and answer.get("refused") == "rate"
            ):
                pacer.saw_rate()
                raise DirectIntakeRateLimit()
            if status != 200 or type(answer) is not dict:
                raise DirectIntakeRefusal(
                    _refusal_code(answer, "construction_material_staging_unavailable")
                )
            if (
                answer.get("schema") != STAGE_REPLY_SCHEMA
                or type(answer.get("protocol_reply_base64")) is not str
            ):
                raise DirectIntakeRefusal("construction_material_reply_invalid")
            try:
                reply = research.load_canonical(
                    base64.b64decode(answer["protocol_reply_base64"], validate=True),
                    research.ServiceReply,
                )
            except (ValueError, TypeError):
                raise DirectIntakeRefusal(
                    "construction_material_reply_invalid"
                ) from None
            if reply.status is research.ReplyStatus.ERROR:
                raise DirectIntakeRefusal(
                    "construction_material_" + reply.result.code.value.lower()
                )
            result = reply.result
            if (
                type(result) is not research.DirectStageMaterialResultV1
                or result.name != name
                or result.content_digest != fingerprint
                or not offset + len(chunk) <= result.received_bytes <= len(body)
                or result.complete != (result.received_bytes == len(body))
                or (result.bundle_complete and not result.complete)
            ):
                raise DirectIntakeRefusal("construction_material_reply_invalid")
            return result

        result = retry_rate_limited(attempt, deadline=deadline)
        if result.complete:
            if final and not result.bundle_complete:
                raise DirectIntakeRefusal("construction_material_closure_incomplete")
            return fingerprint
        offset = result.received_bytes


def stage_bundle(
    url,
    signer,
    *,
    directory: Path,
    recipe,
    contract_digest,
    receiver,
    context,
    read=read_intake,
    send=post,
):
    """Send one exact local closure through the ordinary signed direct intake."""
    if type(recipe) is not ConstructionRecipe:
        recipe = ConstructionRecipe.from_dict(recipe)
    source = recipe.to_dict()["source"]
    if source["kind"] != "bundle":
        raise DirectIntakeRefusal("construction_bundle_source_required")
    manifest, archive, wheels, lock, license_text = load_pinned_bundle_directory(
        directory
    )
    selected = bundle_ref(manifest, archive, wheels, lock, license_text)
    if selected.to_dict() != source["bundle_ref"]:
        raise DirectIntakeRefusal("construction_bundle_binding_mismatch")
    canonical_manifest = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    files = [
        ("source.tar.gz", archive),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
        *sorted(wheels.items()),
        ("bundle.json", canonical_manifest),
    ]
    deadline = _transfer_deadline(files, MATERIAL_CHUNK_BYTES)
    pacer = _UploadPacer()
    for name, body in files:
        _stage_material_one(
            url,
            signer,
            recipe=recipe,
            contract_digest=contract_digest,
            receiver=receiver,
            context=context,
            bundle_digest=selected.bundle_digest,
            name=name,
            body=body,
            final=name == "bundle.json",
            read=read,
            send=send,
            deadline=deadline,
            pacer=pacer,
        )
    return {
        "schema": "carbon.construction.material-stage-result.v1",
        "bundle_ref": selected.to_dict(),
        "files": len(files),
        "bytes": sum(len(body) for _, body in files),
        "complete": True,
        "official_eligible": False,
    }
