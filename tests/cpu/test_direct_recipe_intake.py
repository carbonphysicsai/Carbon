"""The normal signed DEVELOPMENT recipe intake uses the existing gateway."""

from __future__ import annotations

import json
import threading

import pytest
from test_c08_authenticated_miner_mcp import (
    CONTEXT,
    NOW,
    _headers,
    _snapshot,
    _Verifier,
)
from test_direct_v3_durable_tasks import _fixture

from carbon.battery.intake import SnapshotWindow
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator.direct_intake import (
    INFO_PATH,
    STATUS_TOOL,
    SUBMIT_TOOL,
    DirectRecipeIntake,
    serve_loopback,
)
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal


def _signed(state, challenge, tool, fields, *, request, nonce=NOW):
    body = message(
        CONTEXT,
        state.snapshot_id,
        challenge,
        session="direct-recipe-intake",
        request=request,
        tool=tool,
        fields=fields,
    )
    return body, _headers(body, nonce)


def test_signed_recipe_receiver_admits_and_retains_owner_bound_task(
    tmp_path, monkeypatch
):
    request, provider_factory, discovery = _fixture(
        tmp_path / "direct", monkeypatch, material=bundle_material_v5()
    )
    provider = provider_factory()
    try:
        root = tmp_path / "attempts"
        root.mkdir(mode=0o700)
        root.chmod(0o700)
        ledger = AttemptLedger(root / "ledger.sqlite3")
        state = _snapshot()
        window = SnapshotWindow(clock=lambda: NOW / 1_000_000_000)
        window.add(state)
        intake = DirectRecipeIntake(
            context=CONTEXT,
            receiver="validator",
            journal=ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT),
            verifier=_Verifier(),
            window=window,
            discovery=discovery,
            provider_for=lambda owner: provider if owner == "miner" else None,
            attempt_ledger=ledger,
            clock_ns=lambda: NOW,
        )
        public = intake.handle("GET", INFO_PATH, {}, b"", "127.0.0.1")
        assert public.status == 200
        assert public.body["served_contracts"] == [
            {"level": 0, "digest": intake.adapter.contract_digest}
        ]
        assert public.body["score_pack"] is None
        assert public.body["qualification"] is public.body["reward"] is False

        body, headers = _signed(
            state,
            request.challenge_key,
            SUBMIT_TOOL,
            {
                "strategy_json": json.dumps(request.recipe, sort_keys=True),
                "contract_digest": intake.adapter.contract_digest,
            },
            request="signed-recipe-submit-0001",
        )
        admitted = intake.handle("POST", INFO_PATH, headers, body, "127.0.0.1")
        assert admitted.status == 202
        assert admitted.body["kind"] == "OUTCOME"
        assert admitted.body["outcome"]["state"] == "ADMITTED"
        assert admitted.body["outcome"]["qualification"] is False
        assert len(provider.queued_tasks()) == 1
        task_id = admitted.body["outcome"]["task_id"]

        status_body, status_headers = _signed(
            state,
            request.challenge_key,
            STATUS_TOOL,
            {"submission_id": task_id},
            request="signed-recipe-status-0001",
            nonce=NOW + 1,
        )
        observed = intake.handle(
            "POST", INFO_PATH, status_headers, status_body, "127.0.0.1"
        )
        assert observed.status == 200
        assert observed.body["kind"] == "OUTCOME"
        assert observed.body["outcome"]["task_id"] == task_id
        assert observed.body["outcome"]["state"] == "ADMITTED"

        replay = intake.handle(
            "POST", INFO_PATH, status_headers, status_body, "127.0.0.1"
        )
        assert replay.status == 401
        assert replay.body["code"] == "AUTH_REPLAY"

        altered_headers = _headers(status_body, NOW + 3)
        altered_headers["body"] = "sha256:" + "0" * 64
        invalid_signature = intake.handle(
            "POST", INFO_PATH, altered_headers, status_body, "127.0.0.1"
        )
        assert invalid_signature.status == 401
        assert invalid_signature.body["code"] == "AUTH_BAD_SIGNATURE"

        tampered = json.loads(json.dumps(request.recipe))
        tampered["challenge"]["train_digest"] = "sha256:" + "f" * 64
        bad_body, bad_headers = _signed(
            state,
            request.challenge_key,
            SUBMIT_TOOL,
            {
                "strategy_json": json.dumps(tampered),
                "contract_digest": intake.adapter.contract_digest,
            },
            request="signed-recipe-wrong-train-0001",
            nonce=NOW + 2,
        )
        refused = intake.handle("POST", INFO_PATH, bad_headers, bad_body, "127.0.0.1")
        assert refused.status == 400
        assert (refused.body["kind"], refused.body["code"]) == (
            "REFUSED",
            "construction_recipe_binding_mismatch",
        )
        assert len(provider.queued_tasks()) == 1
    finally:
        provider.close()


def test_direct_receiver_refuses_public_bind(tmp_path):
    with pytest.raises(Exception, match="direct_intake_loopback_required"):
        serve_loopback(
            object.__new__(DirectRecipeIntake),
            {"host": "0.0.0.0", "port": 0},
            stop=threading.Event(),
        )
