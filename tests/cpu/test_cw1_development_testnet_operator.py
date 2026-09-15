"""Read-only, secret-free C-W1-D1 operator preflight."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest
from test_cw1_development_testnet import authenticated_fixture

from carbon.chain import MetagraphSnapshot, Participant
from carbon.chain.publication import RuntimeCapabilities
from carbon.development_testnet import DevelopmentTestnetFailure
from carbon.development_testnet.execution import (
    execute_resume,
    execute_run,
    execution_status,
    load_source_handoff,
    write_source_handoff,
)
from carbon.development_testnet.operator import (
    DEFAULT_ENDPOINT,
    TESTNET_GENESIS,
    doctor,
    load_config,
    main,
)
from carbon.orchestration import write_report_bundle

DIGEST = "sha256:" + "1" * 64
HOTKEY = "5E48fhGnyi4C94bsAc64s2bgshyJb7bfP59pRbidghc1pAyQ"
COLDKEY = "5CmGx8PFzfL7EvrvqFgV2Sv2HGok53YkGUsBw1atTD5hw7N8"


def document(*, netuid=None, authorization=None):
    return {
        "schema": "carbon.development-testnet.operator.v1",
        "profile_id": "carbon.public-synthetic-testnet.development.v1",
        "stage": "PUBLIC_TESTNET_DEVELOPMENT",
        "context": {
            "network": "testnet",
            "endpoint": DEFAULT_ENDPOINT,
            "chain_id": "bittensor-official-test",
            "genesis_hash": TESTNET_GENESIS,
            "netuid": netuid,
        },
        "expected_runtime_spec": 458,
        "publisher": {"hotkey": HOTKEY, "coldkey": COLDKEY},
        "wallet": {"name": "miner1", "hotkey_name": "default"},
        "execution": {
            "worker_profile": "carbon.c03.linux-x86_64-cpu.development.v1",
            "worker_image_digest": DIGEST,
            "resource_policy_digest": DIGEST,
        },
        "retention": {
            "root": "evidence",
            "export_root": "evidence/export",
            "max_retained_bytes": 2 * 1024 * 1024,
            "host_loss_recoverable": False,
        },
        "transaction_authorization": authorization,
    }


def write(tmp_path: Path, value):
    path = tmp_path / "operator.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def source_handoff(tmp_path: Path, *, transport_context=None):
    retained = tmp_path / "evidence"
    fixture = authenticated_fixture(
        retained / "source", transport_context=transport_context
    )
    report = write_report_bundle(retained / "report", fixture.primary_result)[0]
    export = retained / "export"
    export.mkdir(parents=True)
    exported_report = export / "private-operational-account.json"
    exported_report.write_bytes(report.read_bytes())
    entries = [
        {
            "path": exported_report.name,
            "bytes": exported_report.stat().st_size,
            "digest": "sha256:"
            + hashlib.sha256(exported_report.read_bytes()).hexdigest(),
        }
    ]
    manifest = export / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "carbon.development-testnet.bounded-export-manifest.v1",
                "entries": entries,
            },
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="ascii",
    )
    key = next(iter(fixture.ledger._keys.values()))
    path = retained / "source-handoff.json"
    write_source_handoff(
        path,
        intent_identity="public-synthetic-development-demo-1",
        publication_journal=retained / "publication.sqlite3",
        transport_journal=fixture.associations.journal,
        evidence_ledger=fixture.ledger,
        verification_keys=(key,),
        account_report=exported_report,
        ledger_reference=fixture.primary_result.ledger_reference,
        authenticated_request_receipt=fixture.transport_receipt,
        export_manifest=manifest,
    )
    return path, fixture.primary_result.signed_receipt.receipt.binding


def test_shipped_example_is_valid_and_deliberately_not_transaction_ready(capsys):
    path = (
        Path(__file__).parents[2]
        / "docs/development/CW1_DEVELOPMENT_TESTNET_OPERATOR.example.json"
    ).absolute()
    config = load_config(path)
    assert config.netuid is None
    assert config.transaction_authorization is None
    assert main(["validate", "--config", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["configuration"] == "VALID_WITH_MISSING_EXTERNAL_INPUTS"
    assert report["wallet_or_secret_read"] is False
    assert report["writes_performed"] is False


def test_draft_doctor_reports_host_facts_without_chain_or_wallet_access(tmp_path):
    config = load_config(write(tmp_path, document()))
    report = asyncio.run(doctor(config, online=False))
    assert report["chain"]["checked"] is False
    assert report["chain"]["registered"] is None
    assert report["chain"]["endpoint_genesis_compatible"] is None
    assert report["missing_external_inputs"] == [
        "context.netuid",
        "transaction_authorization",
    ]
    assert report["transaction_ready"] is False
    assert report["chain_transaction_ready"] is False
    assert report["full_execution_prerequisites_ready"] is False
    assert report["writes_performed"] is False
    assert report["protected_or_official_eligible"] is False


def test_exact_authorization_and_observed_runtime_enable_only_readiness(
    tmp_path, monkeypatch
):
    authorization = {
        "authorization_id": "owner-testnet-demo-1",
        "authority_record_digest": DIGEST,
        "publisher_hotkey": HOTKEY,
        "expected_runtime_spec": 458,
        "valid_from_block": 100,
        "valid_through_block": 120,
    }
    config = load_config(
        write(tmp_path, document(netuid=77, authorization=authorization))
    )
    context = config.context
    snapshot = MetagraphSnapshot(
        context,
        101,
        "0x" + "2" * 64,
        1,
        (
            Participant(0, "owner-hotkey", "owner-coldkey", 1),
            Participant(1, HOTKEY, COLDKEY, 2),
        ),
    )
    capabilities = RuntimeCapabilities(
        snapshot.snapshot_id,
        458,
        1,
        2,
        "Burn",
        "owner-coldkey",
        "owner-hotkey",
        ("owner-hotkey",),
        1,
        65535,
        0,
        0,
        0,
        False,
        True,
        True,
    )

    class Backend:
        def __init__(self, *args, **kwargs):
            pass

        async def observe(self):
            return snapshot, replace(capabilities)

        async def close(self):
            pass

    monkeypatch.setattr(
        "carbon.development_testnet.operator.BittensorPublicationBackend", Backend
    )
    monkeypatch.setattr(
        "carbon.development_testnet.operator.version", lambda name: "11.1.0"
    )
    monkeypatch.setattr(
        "carbon.development_testnet.operator.platform.system", lambda: "Darwin"
    )
    report = asyncio.run(doctor(config, online=True))
    assert report["chain"]["checked"] is True
    assert report["chain"]["uid"] == 1
    assert report["chain"]["configured_coldkey_matches"] is True
    assert report["chain"]["burn_recipient_uid"] == 0
    assert report["chain"]["publication_method"] == "SET_MECHANISM_WEIGHTS"
    assert report["chain"]["publication_capability_eligible"] is True
    assert report["authorization"]["valid_at_observed_block"] is True
    # Chain readiness is independently observable on an ineligible host.
    assert report["full_execution_prerequisites_ready"] is False
    assert report["transaction_ready"] is True
    assert report["writes_performed"] is False


def test_registered_but_ineligible_retains_observed_identity(tmp_path, monkeypatch):
    authorization = {
        "authorization_id": "owner-testnet-demo-1",
        "authority_record_digest": DIGEST,
        "publisher_hotkey": HOTKEY,
        "expected_runtime_spec": 458,
        "valid_from_block": 100,
        "valid_through_block": 120,
    }
    config = load_config(
        write(tmp_path, document(netuid=77, authorization=authorization))
    )
    snapshot = MetagraphSnapshot(
        config.context,
        101,
        "0x" + "2" * 64,
        1,
        (
            Participant(0, "owner-hotkey", "owner-coldkey", 1),
            Participant(1, HOTKEY, COLDKEY, 2),
        ),
    )
    capabilities = RuntimeCapabilities(
        snapshot.snapshot_id,
        458,
        1,
        2,
        "Burn",
        "owner-coldkey",
        "owner-hotkey",
        ("owner-hotkey",),
        1,
        65535,
        0,
        0,
        0,
        False,
        False,
        True,
    )

    class Backend:
        def __init__(self, *args, **kwargs):
            pass

        async def observe(self):
            return snapshot, capabilities

        async def close(self):
            pass

    monkeypatch.setattr(
        "carbon.development_testnet.operator.BittensorPublicationBackend", Backend
    )
    monkeypatch.setattr(
        "carbon.development_testnet.operator.version", lambda name: "11.1.0"
    )
    report = asyncio.run(doctor(config, online=True))
    assert report["chain"]["registered"] is True
    assert report["chain"]["uid"] == 1
    assert report["chain"]["validator_permit"] is False
    assert report["chain"]["publication_capability_eligible"] is False
    assert report["chain"]["reason"] == "VALIDATOR_PERMIT_REQUIRED"
    assert report["chain_transaction_ready"] is False


def test_runtime_mismatch_and_expired_authorization_are_separate(tmp_path, monkeypatch):
    authorization = {
        "authorization_id": "owner-testnet-demo-1",
        "authority_record_digest": DIGEST,
        "publisher_hotkey": HOTKEY,
        "expected_runtime_spec": 458,
        "valid_from_block": 80,
        "valid_through_block": 99,
    }
    config = load_config(
        write(tmp_path, document(netuid=77, authorization=authorization))
    )
    snapshot = MetagraphSnapshot(
        config.context,
        101,
        "0x" + "2" * 64,
        1,
        (
            Participant(0, "owner-hotkey", "owner-coldkey", 1),
            Participant(1, HOTKEY, COLDKEY, 2),
        ),
    )
    capabilities = RuntimeCapabilities(
        snapshot.snapshot_id,
        459,
        1,
        2,
        "Burn",
        "owner-coldkey",
        "owner-hotkey",
        ("owner-hotkey",),
        1,
        65535,
        0,
        3,
        95,
        False,
        True,
        True,
    )

    class Backend:
        def __init__(self, *args, **kwargs):
            pass

        async def observe(self):
            return snapshot, capabilities

        async def close(self):
            pass

    monkeypatch.setattr(
        "carbon.development_testnet.operator.BittensorPublicationBackend", Backend
    )
    monkeypatch.setattr(
        "carbon.development_testnet.operator.version", lambda name: "11.1.0"
    )
    report = asyncio.run(doctor(config, online=True))
    assert report["chain"]["registered"] is True
    assert report["chain"]["runtime_spec"] == 459
    assert report["chain"]["runtime_compatible"] is False
    assert report["chain"]["reason"] == "UNSUPPORTED_RUNTIME_VERSION"
    assert report["authorization"]["valid_at_observed_block"] is False
    assert report["chain_transaction_ready"] is False


def test_main_fails_closed_without_echoing_invalid_input(tmp_path, capsys):
    path = write(tmp_path, {"secret": "do-not-echo"})
    assert main(["doctor", "--config", str(path)]) == 2
    assert "do-not-echo" not in capsys.readouterr().out


def test_closed_source_handoff_runs_once_and_status_never_resubmits(
    tmp_path, monkeypatch, capsys
):
    authorization = {
        "authorization_id": "owner-testnet-demo-1",
        "authority_record_digest": DIGEST,
        "publisher_hotkey": HOTKEY,
        "expected_runtime_spec": 458,
        "valid_from_block": 100,
        "valid_through_block": 120,
    }
    config = load_config(
        write(tmp_path, document(netuid=77, authorization=authorization))
    )
    source_path, binding = source_handoff(tmp_path, transport_context=config.context)
    handoff = load_source_handoff(source_path)
    config = replace(
        config,
        worker_image_digest=binding.worker_image_digest,
        resource_policy_digest=binding.resource_policy_digest,
    )
    state = MetagraphSnapshot(
        config.context,
        101,
        "0x" + "2" * 64,
        1,
        (
            Participant(0, "owner-hotkey", "owner-coldkey", 1),
            Participant(1, HOTKEY, COLDKEY, 2),
        ),
    )
    caps = RuntimeCapabilities(
        state.snapshot_id,
        458,
        1,
        2,
        "Burn",
        "owner-coldkey",
        "owner-hotkey",
        ("owner-hotkey",),
        1,
        65535,
        0,
        0,
        0,
        False,
        True,
        True,
    )

    class Backend:
        executions = 0
        tx_hash = "0x" + "a" * 64

        def __init__(self, context, publisher, wallet, *, network):
            assert network == "testnet"
            self.context = context
            self.publisher = publisher
            self.wallet = wallet

        async def observe(self):
            return state, caps

        async def execute(
            self, plan, integer_guard, call_checked, before_sign, before_dispatch
        ):
            type(self).executions += 1
            uids = [uid for uid, _ in plan.integers]
            values = [value for _, value in plan.integers]
            await integer_guard(
                uids,
                values,
                SimpleNamespace(
                    uid=1,
                    min_allowed_weights=1,
                    max_weight_limit=65535,
                    commit_reveal=False,
                ),
            )
            call = SimpleNamespace(data=b"checked", spec_version=458)
            await call_checked(call, {})
            await before_sign(call, HOTKEY)
            await before_dispatch(self.tx_hash)

        async def transaction(self, tx_hash, block):
            from carbon.chain.publisher import TransactionObservation

            if tx_hash == self.tx_hash and block == 101:
                return TransactionObservation(True, block, state.block_hash)
            return None

        async def revealed(self, publisher, block):
            return False

        async def weight_row(self, snapshot, uid):
            return [[0, 65535]], 101

        async def close(self):
            pass

    monkeypatch.setattr(
        "carbon.development_testnet.execution.BittensorPublicationBackend", Backend
    )
    result = asyncio.run(execute_run(config, handoff, object()))
    assert result["state"] == "ROW_VERIFIED"
    assert Backend.executions == 1
    status = execution_status(config, handoff)
    assert status["dispatch"]["state"] == "ROW_VERIFIED"
    assert status["operator_action"] == "NONE_TERMINAL"
    assert (
        asyncio.run(execute_run(config, handoff, object()))["state"] == "ROW_VERIFIED"
    )
    assert Backend.executions == 1
    assert (
        main(
            [
                "status",
                "--config",
                str(tmp_path / "operator.json"),
                "--source",
                str(source_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["operator_action"] == "NONE_TERMINAL"


def test_resume_reconciles_ambiguous_dispatch_without_wallet_or_resubmit(
    tmp_path, monkeypatch
):
    authorization = {
        "authorization_id": "owner-testnet-demo-1",
        "authority_record_digest": DIGEST,
        "publisher_hotkey": HOTKEY,
        "expected_runtime_spec": 458,
        "valid_from_block": 100,
        "valid_through_block": 120,
    }
    config = load_config(
        write(tmp_path, document(netuid=77, authorization=authorization))
    )
    source_path, binding = source_handoff(tmp_path, transport_context=config.context)
    handoff = load_source_handoff(source_path)
    config = replace(
        config,
        worker_image_digest=binding.worker_image_digest,
        resource_policy_digest=binding.resource_policy_digest,
    )
    state = MetagraphSnapshot(
        config.context,
        101,
        "0x" + "2" * 64,
        1,
        (
            Participant(0, "owner-hotkey", "owner-coldkey", 1),
            Participant(1, HOTKEY, COLDKEY, 2),
        ),
    )
    caps = RuntimeCapabilities(
        state.snapshot_id,
        458,
        1,
        2,
        "Burn",
        "owner-coldkey",
        "owner-hotkey",
        ("owner-hotkey",),
        1,
        65535,
        0,
        0,
        0,
        False,
        True,
        True,
    )

    class Backend:
        executions = 0
        wallets: ClassVar[list[object | None]] = []
        tx_hash = "0x" + "b" * 64

        def __init__(self, context, publisher, wallet, *, network):
            self.context, self.publisher = context, publisher
            type(self).wallets.append(wallet)

        async def observe(self):
            return state, caps

        async def execute(
            self, plan, integer_guard, call_checked, before_sign, before_dispatch
        ):
            type(self).executions += 1
            await integer_guard(
                [0],
                [65535],
                SimpleNamespace(
                    uid=1,
                    min_allowed_weights=1,
                    max_weight_limit=65535,
                    commit_reveal=False,
                ),
            )
            call = SimpleNamespace(data=b"checked", spec_version=458)
            await call_checked(call, {})
            await before_sign(call, HOTKEY)
            await before_dispatch(self.tx_hash)
            raise RuntimeError("response lost")

        async def transaction(self, tx_hash, block):
            from carbon.chain.publisher import TransactionObservation

            if tx_hash == self.tx_hash and block == 101:
                return TransactionObservation(True, block, state.block_hash)
            return None

        async def revealed(self, publisher, block):
            return False

        async def weight_row(self, snapshot, uid):
            return [[0, 65535]], 101

        async def close(self):
            pass

    monkeypatch.setattr(
        "carbon.development_testnet.execution.BittensorPublicationBackend", Backend
    )
    first = asyncio.run(execute_run(config, handoff, object()))
    assert first["state"] == "AMBIGUOUS"
    resumed = asyncio.run(execute_resume(config, handoff))
    assert resumed["state"] == "ROW_VERIFIED"
    assert Backend.executions == 1
    assert Backend.wallets[0] is not None
    assert Backend.wallets[1] is None


def test_source_handoff_rejects_changed_export_bytes(tmp_path):
    source_path, _ = source_handoff(tmp_path)
    handoff = load_source_handoff(source_path)
    handoff.account_report.write_bytes(handoff.account_report.read_bytes() + b"\n")
    with pytest.raises(DevelopmentTestnetFailure, match="INVALID_SOURCE_HANDOFF"):
        load_source_handoff(source_path)


def test_source_handoff_context_and_configured_roots_are_mandatory(tmp_path):
    source_path, binding = source_handoff(tmp_path)
    handoff = load_source_handoff(source_path)
    config = load_config(write(tmp_path, document(netuid=77)))
    config = replace(
        config,
        worker_image_digest=binding.worker_image_digest,
        resource_policy_digest=binding.resource_policy_digest,
    )
    with pytest.raises(
        DevelopmentTestnetFailure, match="AUTHENTICATED_REQUEST_CONTEXT_MISMATCH"
    ):
        asyncio.run(execute_run(config, handoff, object()))
    with pytest.raises(
        DevelopmentTestnetFailure, match="SOURCE_OUTSIDE_BOUNDED_RETENTION_ROOT"
    ):
        load_source_handoff(
            source_path,
            retention_root=tmp_path / "different-retention-root",
            export_root=config.export_root,
        )
