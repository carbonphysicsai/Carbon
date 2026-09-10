"""NET-6 operator contracts use explicit chain doubles; never runtime evidence."""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_net2_transport import CONTEXT
from test_net4b_publication import publisher

from carbon.chain.operations import (
    GENESIS,
    config_document,
    load_config,
    main,
    supervise,
    verified_key,
)
from carbon.chain.operator_store import (
    OperatorFailure,
    backup,
    health,
    journal_view,
    publisher_lease,
    restore,
)
from carbon.traineval.model import FixtureRunRequestError
from carbon.transport.store import ReceiptJournal


def logical(path):
    with journal_view(path) as db:
        return tuple(db.iterdump())


def test_backup_restore_retains_every_owner_table_pending_dispatch_and_credit_age(
    tmp_path,
):
    pub, ref, backend = publisher(tmp_path)
    backend.mode = "ambiguous"
    result = asyncio.run(pub.publish(ref))
    assert result["state"] == "AMBIGUOUS"
    before = logical(pub.issuer.receipts.path)
    bundle = tmp_path / "backup"
    backup(pub.issuer.receipts.path, bundle)
    recovered = tmp_path / "restored.sqlite"
    restore(bundle, recovered, CONTEXT)
    assert logical(recovered) == before
    status = health(recovered, now_ms=200000)
    assert status["pending_dispatch"] == ref.digest
    assert status["stored_weights_may_remain_effective"] is True
    assert status["settlement"] == "OBSERVE_CHAIN_SEPARATELY"
    assert status["observation_health"] == "STALE"
    with pytest.raises(OperatorFailure, match="NEW_CANONICAL"):
        restore(bundle, recovered, CONTEXT)
    assert logical(recovered) == before


def test_backup_is_consistent_with_uncheckpointed_wal_and_uncommitted_writer(tmp_path):
    source = tmp_path / "source.sqlite"
    ReceiptJournal(source, CONTEXT)
    with sqlite3.connect(source, isolation_level=None) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE private_test (value TEXT)")
        writer.execute("INSERT INTO private_test VALUES ('committed')")
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("INSERT INTO private_test VALUES ('uncommitted')")
        bundle = tmp_path / "backup"
        backup(source, bundle)
        with journal_view(bundle / "journal.sqlite") as db:
            assert db.execute("SELECT value FROM private_test").fetchall() == [
                ("committed",)
            ]
        writer.rollback()


@pytest.mark.parametrize(
    "defect", ["payload", "context", "schema", "extra", "missing", "oversize"]
)
def test_restore_rejects_tamper_without_creating_destination(tmp_path, defect):
    source = tmp_path / "source.sqlite"
    ReceiptJournal(source, CONTEXT)
    bundle = tmp_path / "backup"
    backup(source, bundle)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    expected = CONTEXT
    if defect == "payload":
        with (bundle / "journal.sqlite").open("ab") as stream:
            stream.write(b"changed")
    elif defect == "context":
        expected = replace(CONTEXT, provider="other")
    elif defect == "schema":
        manifest["schema_sha256"] = "0" * 64
    elif defect == "extra":
        manifest["accepted"] = True
    elif defect == "missing":
        (bundle / "journal.sqlite").unlink()
    else:
        manifest["size"] += 1
    path.write_text(json.dumps(manifest))
    output = tmp_path / "restored.sqlite"
    with pytest.raises(OperatorFailure):
        restore(bundle, output, expected)
    assert not output.exists()


def test_exclusive_lease_rejects_second_owner_and_releases_without_inode_deletion(
    tmp_path,
):
    source = tmp_path / "source.sqlite"
    ReceiptJournal(source, CONTEXT)
    with publisher_lease(source):
        with (
            pytest.raises(OperatorFailure, match="ALREADY_OWNED"),
            publisher_lease(source),
        ):
            pytest.fail("second owner")
        inode = source.with_name(source.name + ".publisher.lock").stat().st_ino
    with publisher_lease(source):
        assert source.with_name(source.name + ".publisher.lock").stat().st_ino == inode


def test_os_releases_publisher_lock_after_process_death(tmp_path):
    source = tmp_path / "source.sqlite"
    ReceiptJournal(source, CONTEXT)
    program = "from pathlib import Path;from carbon.chain.operator_store import publisher_lease;import sys,os;\nwith publisher_lease(Path(sys.argv[1])): os._exit(0)"
    result = subprocess.run(
        [sys.executable, "-c", program, str(source)], check=False, capture_output=True
    )
    assert result.returncode == 0
    with publisher_lease(source):
        pass


@pytest.mark.skipif(os.name == "nt", reason="canonical Linux symlink boundary")
def test_journal_aliases_and_symlinks_are_rejected(tmp_path):
    source = tmp_path / "source.sqlite"
    ReceiptJournal(source, CONTEXT)
    alias = tmp_path / "alias"
    alias.symlink_to(source)
    with pytest.raises(OperatorFailure):
        health(alias)
    alias.unlink()
    os.link(source, alias)
    with pytest.raises(OperatorFailure):
        health(alias)


def test_health_and_cli_never_expose_private_journal_values_or_create_missing_db(
    tmp_path, capsys
):
    source = tmp_path / "source.sqlite"
    ReceiptJournal(source, CONTEXT)
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE private_payload (secret TEXT)")
        db.execute(
            "INSERT INTO private_payload VALUES ('hidden-case-and-key-material')"
        )
    assert main(["health", "--journal", str(source)]) == 0
    output = capsys.readouterr().out
    assert (
        "hidden-case-and-key-material" not in output
        and "stored_weights_may_remain_effective" in output
    )
    missing = tmp_path / "absent.sqlite"
    assert main(["health", "--journal", str(missing)]) == 2
    assert not missing.exists()


def config_fixture(tmp_path):
    from test_traineval_stub import _environment

    from carbon.candidates.model import FixtureEvaluationContext
    from carbon.traineval import FixtureStubProfile

    context = replace(
        CONTEXT, genesis_hash=GENESIS, netuid=2, endpoint="ws://127.0.0.1:40001"
    )
    receipts = ReceiptJournal(tmp_path / "receipts.sqlite", context)
    evaluation = FixtureEvaluationContext(
        FixtureStubProfile().score_pack_pin(), _environment()
    )
    value = config_document(
        receipts,
        "carbon-localnet-test",
        "validator",
        (evaluation,),
        (context.endpoint, "ws://127.0.0.1:40002"),
        "a" * 64,
    )
    path = tmp_path / "operator.json"
    path.write_text(json.dumps(value))
    return path, value


@pytest.mark.parametrize(
    "defect",
    [
        None,
        "public",
        "genesis",
        "port",
        "treasury",
        "interval",
        "fixture",
        "unknown",
        "duplicate",
    ],
)
def test_operator_config_is_finite_local_only_and_reads_no_key(tmp_path, defect):
    path, value = config_fixture(tmp_path)
    if defect == "public":
        value["context"]["network"] = "finney"
    elif defect == "genesis":
        value["context"]["genesis_hash"] = "0x" + "f" * 64
    elif defect == "port":
        value["relay_ports"][0] = 9944
    elif defect == "treasury":
        value["treasury"] = "reserve"
    elif defect == "interval":
        value["interval_seconds"] = True
    elif defect == "fixture":
        value["evaluations"][0]["localnet_fixture"] = "LIVE"
    elif defect == "unknown":
        value["accepted"] = True
    elif defect == "duplicate":
        value["evaluations"] *= 2
    path.write_text(json.dumps(value))
    if defect:
        with pytest.raises((OperatorFailure, FixtureRunRequestError)):
            load_config(path)
    else:
        config = load_config(path)
        assert config.context.genesis_hash == GENESIS and not config.key_file.exists()
        assert main(["validate", "--config", str(path)]) == 0


def test_verification_failure_precedes_even_keyfile_metadata_access(
    tmp_path, monkeypatch
):
    path, _ = config_fixture(tmp_path)
    config = load_config(path)
    seen = []

    async def verify():
        seen.append("verify")
        raise OperatorFailure("ISOLATION_MISMATCH")

    monkeypatch.setattr(
        "carbon.chain.operations.regular",
        lambda *_args, **_kwargs: pytest.fail("key access before verification"),
    )
    with pytest.raises(OperatorFailure, match="ISOLATION"):
        asyncio.run(verified_key(config, None, verify))
    assert seen == ["verify"]


def test_supervisor_reconciles_ambiguous_dispatch_before_any_new_signature(tmp_path):
    pub, ref, backend = publisher(tmp_path)
    backend.mode = "ambiguous"
    asyncio.run(pub.publish(ref))
    signatures = backend.signatures
    closed = []

    async def close():
        closed.append(True)

    backend.close = close

    async def verify():
        pass

    result = asyncio.run(supervise(pub, asyncio.Event(), verify, max_ticks=1))
    assert backend.signatures == signatures
    assert result["last_dispatch_state"] == "ROW_VERIFIED"
    assert (
        result["shutdown_clears_weights"] is False
        and result["stored_weights_may_remain_effective"]
    )
    assert closed


def test_supervisor_outage_shutdown_and_next_process_recovery(tmp_path):
    pub, _, backend = publisher(tmp_path)
    closed = []

    async def close():
        closed.append(True)

    backend.close = close

    async def outage():
        raise ConnectionError("private provider transcript")

    first = asyncio.run(supervise(pub, asyncio.Event(), outage, max_ticks=1))
    assert backend.signatures == 0 and "private" not in json.dumps(first)

    async def verify():
        pass

    second = asyncio.run(supervise(pub, asyncio.Event(), verify, max_ticks=1))
    assert backend.signatures == 1 and second["last_dispatch_state"] == "ROW_VERIFIED"
    stop = asyncio.Event()
    stop.set()
    third = asyncio.run(supervise(pub, stop, verify))
    assert third["ticks"] == 0 and backend.signatures == 1 and len(closed) >= 3


def test_supervisor_denies_second_process_before_verification_or_signing(tmp_path):
    pub, _, backend = publisher(tmp_path)

    async def verify():
        pytest.fail("second publisher entered")

    with (
        publisher_lease(pub.issuer.receipts.path),
        pytest.raises(OperatorFailure, match="ALREADY_OWNED"),
    ):
        asyncio.run(supervise(pub, asyncio.Event(), verify, max_ticks=1))
    assert backend.signatures == 0


@pytest.mark.parametrize(
    "interval,limit", [(True, 1), (0, 1), (31, 1), (5, 0), (5, True)]
)
def test_supervisor_rejects_invalid_development_schedule(tmp_path, interval, limit):
    pub, _, backend = publisher(tmp_path)

    async def verify():
        pytest.fail("invalid schedule entered")

    with pytest.raises(OperatorFailure):
        asyncio.run(
            supervise(
                pub, asyncio.Event(), verify, interval_seconds=interval, max_ticks=limit
            )
        )
    assert backend.signatures == 0


def test_restored_consumers_preserve_accepted_state_and_reject_missing_context(
    tmp_path,
):
    from carbon.chain.operations import OperatorConfig, restored_publisher

    pub, ref, backend = publisher(tmp_path)
    ledger = pub.issuer.ledger
    contexts = tuple(j.context for j in ledger.journals.values())
    config = OperatorConfig(
        CONTEXT,
        "carbon-localnet-test",
        "a" * 64,
        (40001, 40002),
        "validator",
        ledger.receipts.path,
        tmp_path / "absent-key",
        contexts,
        5,
    )
    restored = restored_publisher(config, backend, ledger.adapter)
    assert restored.issuer.resolve(ref, ledger.adapter.state) == pub.issuer.resolve(
        ref, ledger.adapter.state
    )
    with pytest.raises(OperatorFailure, match="INCOMPLETE"):
        restored_publisher(replace(config, evaluations=()), backend, ledger.adapter)
    with pytest.raises(OperatorFailure, match="CONTEXT"):
        restored_publisher(
            replace(config, context=replace(CONTEXT, provider="other")),
            backend,
            ledger.adapter,
        )


@pytest.mark.skipif(os.name == "nt", reason="canonical Linux external key permissions")
def test_installed_sdk_external_key_is_read_only_after_verified_context(tmp_path):
    import importlib.util

    if importlib.util.find_spec("bittensor_wallet") is None:
        assert os.environ.get("CARBON_REQUIRE_CHAIN_SDK") != "1"
        pytest.skip("installed SDK lane required separately")
    from bittensor_wallet import Keypair

    path, value = config_fixture(tmp_path)
    pair = Keypair.create_from_uri("//Alice_hk")
    value["publisher"] = pair.ss58_address
    path.write_text(json.dumps(value))
    config = load_config(path)
    config.key_file.write_text("//Alice_hk")
    config.key_file.chmod(0o600)
    order = []

    class Backend:
        async def observe(self):
            order.append("observe")
            return SimpleNamespace(context=config.context), SimpleNamespace(
                validate=lambda *_: order.append("caps")
            )

    async def verify():
        order.append("isolation")

    assert (
        asyncio.run(verified_key(config, Backend(), verify)).ss58_address
        == pair.ss58_address
    )
    assert order == ["isolation", "observe", "caps"]
    config.key_file.write_text("//Bob")
    with pytest.raises(OperatorFailure, match="KEY_IDENTITY"):
        asyncio.run(verified_key(config, Backend(), verify))
    config.key_file.chmod(0o644)
    with pytest.raises(OperatorFailure, match="PRIVATE_CANONICAL"):
        asyncio.run(verified_key(config, Backend(), verify))


def test_public_schema_is_inert_and_startup_preserves_verified_original():
    from pathlib import Path

    from carbon.chain.localnet import STARTUP

    schema = json.loads(
        Path("scripts/dev/public-network-config.schema.json").read_text()
    )
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["enabled"] == {"const": False}
    for key in set(schema["required"]) - {"schema", "enabled", "network"}:
        assert schema["properties"][key] == {"type": "null"}
    assert "sed -i" not in STARTUP
    assert "> /scripts/carbon-localnet.sh" in STARTUP
    assert "exec /scripts/carbon-localnet.sh True --no-purge" in STARTUP
