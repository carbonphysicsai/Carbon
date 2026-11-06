"""H8 / R71: weights survive a chain runtime upgrade whose used surface is unchanged; a changed one refuses + alerts."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from carbon.chain import runtime_accept as ra

DIGEST = "sha256:" + "d" * 64
OTHER = "sha256:" + "e" * 64
GENESIS = "0x" + "1" * 64
CODE_A, CODE_B, CODE_C = "0x" + "a" * 64, "0x" + "b" * 64, "0x" + "c" * 64


def _report(spec, digest=DIGEST, status=ra.COMPATIBLE, differences=()):
    return {
        "spec_version": spec,
        "status": status,
        "surface_digest": digest,
        "differences": list(differences),
        "context": {"finalized_block": 1},
    }


@pytest.fixture
def store(tmp_path):
    return tmp_path / ra.RECEIPT_DIR


def _base(store, spec=488, digest=DIGEST, code=CODE_A):
    return ra.baseline(
        store,
        _report(spec, digest),
        owner_specs=(spec, spec),
        genesis_hash=GENESIS,
        code_hash=code,
    )


def _no_probe():
    raise AssertionError("must not probe")


def _decide(store, spec, code, probe=_no_probe, **kw):
    return ra.decide(store, spec, code, GENESIS, probe, **kw)


def test_without_a_baseline_nothing_is_decided_here(store, tmp_path):
    assert ra.has_baseline(tmp_path / "publication.sqlite3") is False
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_BASELINE_MISSING"):
        _decide(store, 488, CODE_A)


def test_the_baseline_names_only_the_owners_spec_and_a_compatible_surface(store):
    with pytest.raises(ra.RuntimeRefused, match="BASELINE_NOT_COMPATIBLE"):
        ra.baseline(
            store,
            _report(488, status="INCOMPATIBLE"),
            owner_specs=(488,),
            genesis_hash=GENESIS,
            code_hash=CODE_A,
        )
    with pytest.raises(ra.RuntimeRefused, match="BASELINE_NOT_THE_OWNERS_SPEC"):
        ra.baseline(
            store,
            _report(490),
            owner_specs=(488, 488),
            genesis_hash=GENESIS,
            code_hash=CODE_A,
        )
    with pytest.raises(ra.RuntimeRefused, match="BASELINE_NOT_THE_OWNERS_SPEC"):
        ra.baseline(
            store,
            _report(488),
            owner_specs=(488, 486),
            genesis_hash=GENESIS,
            code_hash=CODE_A,
        )
    _base(store)
    assert _decide(store, 488, CODE_A) == 488  # the baseline runtime itself: no probe


def test_a_spec_bump_with_the_same_surface_publishes_the_same_cycle(store):
    _base(store)
    lines = []
    spec = _decide(
        store, 490, CODE_B, lambda: _report(490), log=lambda *a, **k: lines.append(a[0])
    )
    assert spec == 490 and lines == ["runtime_auto_accepted"]
    body = ra.receipt(store, 490, CODE_B)
    assert body["decision"] == ra.ACCEPTED and body["baseline_digest"] == DIGEST
    assert (
        body["genesis_hash"] == GENESIS
        and body["claims"]["runtime_behaviour_verified"] is False
    )
    assert _decide(store, 490, CODE_B) == 490  # next cycle: the receipt, no probe


def test_the_same_spec_number_with_other_code_is_probed_again(store):
    _base(store)
    _decide(store, 490, CODE_B, lambda: _report(490))
    with pytest.raises(ra.RuntimeRefused, match="UNSUPPORTED_RUNTIME_SURFACE"):
        _decide(
            store, 490, CODE_C, lambda: _report(490, digest=OTHER)
        )  # a redeploy under 490


def test_a_changed_surface_refuses_and_alerts_once_until_cleared(store):
    _base(store)
    lines = []
    changed = _report(491, digest=OTHER)
    for _ in range(3):
        with pytest.raises(ra.RuntimeRefused, match="UNSUPPORTED_RUNTIME_SURFACE"):
            _decide(
                store,
                491,
                CODE_B,
                lambda: changed,
                log=lambda *a, **k: lines.append(a[0]),
            )
    alert = json.loads((store / ra.ALERT_NAME).read_text(encoding="utf-8"))
    assert alert["decision"] == ra.REFUSED and alert["reason"] == "surface_changed"
    assert alert["surface_digest"] == OTHER and alert["baseline_digest"] == DIGEST
    assert lines == ["operator_alert"]  # one alert per changed digest, not per cycle
    _decide(
        store, 492, CODE_C, lambda: _report(492)
    )  # an accepted runtime clears the alert
    assert not (store / ra.ALERT_NAME).exists()
    with pytest.raises(ra.RuntimeRefused):
        _decide(
            store, 491, CODE_B, lambda: changed, log=lambda *a, **k: lines.append(a[0])
        )
    assert lines == [
        "operator_alert",
        "operator_alert",
    ]  # the returning change alerts again


def test_incompatible_with_the_sdk_refuses_even_with_the_same_digest(store):
    _base(store)
    bad = _report(
        492, status="INCOMPATIBLE", differences=[{"item": "x", "issue": "changed"}]
    )
    with pytest.raises(ra.RuntimeRefused):
        _decide(store, 492, CODE_B, lambda: bad)
    alert = json.loads((store / ra.ALERT_NAME).read_text(encoding="utf-8"))
    assert alert["reason"] == "incompatible_with_sdk" and alert["differences"]


def test_a_reviewed_rebaseline_replaces_the_old_one(store):
    _base(store)
    _decide(store, 490, CODE_B, lambda: _report(490))
    with pytest.raises(ra.RuntimeRefused):
        _decide(store, 491, CODE_C, lambda: _report(491, digest=OTHER))
    # the owner reviews the change and re-pins 491; the new baseline replaces the old (no 'receipts disagree')
    _base(store, spec=491, digest=OTHER, code=CODE_C)
    assert _decide(store, 491, CODE_C) == 491
    # an old receipt made against the previous baseline no longer counts: re-probed against the new one
    with pytest.raises(ra.RuntimeRefused):
        _decide(store, 490, CODE_B, lambda: _report(490))


def test_another_chains_baseline_refuses(store):
    _base(store)
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_BASELINE_OTHER_CHAIN"):
        ra.decide(store, 488, CODE_A, "0x" + "2" * 64, _no_probe)


@pytest.mark.skipif(os.name != "posix", reason="posix modes and links")
def test_a_store_others_can_read_or_a_linked_receipt_refuses(store, tmp_path):
    _base(store)
    store.chmod(0o755)
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_RECEIPT_NOT_OWNER_ONLY"):
        _decide(store, 488, CODE_A)
    store.chmod(0o700)
    (store / ra.BASELINE_NAME).chmod(0o644)
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_RECEIPT_NOT_OWNER_ONLY"):
        _decide(store, 488, CODE_A)
    (store / ra.BASELINE_NAME).chmod(0o600)
    elsewhere = tmp_path / "planted.json"
    elsewhere.write_text(
        (store / ra.BASELINE_NAME).read_text(encoding="utf-8"), encoding="utf-8"
    )
    elsewhere.chmod(0o600)
    os.symlink(elsewhere, store / ra._receipt_name(490, CODE_B))
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_RECEIPT_NOT_OWNER_ONLY"):
        _decide(store, 490, CODE_B)


def test_a_runtime_that_moves_during_the_probe_refuses(store):
    _base(store)
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_CHANGED_DURING_PROBE"):
        _decide(store, 494, CODE_B, lambda: _report(495))


def _journal_with(tmp_path):
    import sqlite3

    path = tmp_path / "publication.sqlite3"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE publication_v1 (identity TEXT PRIMARY KEY, document TEXT, digest TEXT, state TEXT,"
        " tracking TEXT, tracking_digest TEXT)"
    )
    db.commit()
    db.close()
    return path


def _add(journal, identity, spec, state, reason=None):
    import sqlite3

    db = sqlite3.connect(journal)
    db.execute(
        "INSERT INTO publication_v1 VALUES (?,?,?,?,?,?)",
        (
            identity,
            json.dumps({"capabilities": {"spec_version": spec}}),
            "d",
            state,
            json.dumps({"reason": reason}),
            "t",
        ),
    )
    db.commit()
    db.close()


def test_an_auto_accepted_runtime_stops_after_two_read_back_misses(tmp_path):
    journal = _journal_with(tmp_path)
    store = ra.store_for(journal)
    _base(store)
    lines = []

    def note(*a, **_k):
        lines.append(a[0])

    assert (
        _decide(store, 497, CODE_B, lambda: _report(497), journal=journal, log=note)
        == 497
    )
    _add(journal, "a", 497, "ROW_VERIFIED")
    assert _decide(store, 497, CODE_B, journal=journal, log=note) == 497
    assert lines == ["runtime_auto_accepted"]
    _add(journal, "b", 497, "FINALIZED", "STORED_ROW_DIFFERS_FROM_TARGET")
    assert _decide(store, 497, CODE_B, journal=journal, log=note) == 497
    assert _decide(store, 497, CODE_B, journal=journal, log=note) == 497
    assert lines == ["runtime_auto_accepted", "operator_alert"]
    _add(journal, "c", 497, "CHAIN_REJECTED")
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_READBACK_FAILED"):
        _decide(store, 497, CODE_B, journal=journal, log=note)
    _add(journal, "d", 488, "CHAIN_REJECTED")
    _add(journal, "e", 488, "CHAIN_REJECTED")
    assert (
        _decide(store, 488, CODE_A, journal=journal) == 488
    )  # the baseline: a person's, never auto-stopped


def test_resolve_probes_only_a_runtime_without_a_valid_receipt(monkeypatch, tmp_path):
    from carbon.chain import runtime_probe

    journal = tmp_path / "publication.sqlite3"
    probes = []

    async def live(_endpoint):
        return 496, CODE_B

    async def probe(endpoint, genesis):
        probes.append(endpoint)
        return _report(496)

    monkeypatch.setattr(ra, "live_runtime", live)
    monkeypatch.setattr(runtime_probe, "probe", probe)
    _base(ra.store_for(journal))
    assert asyncio.run(ra.resolve("wss://x", GENESIS, journal, log=None)) == 496
    assert asyncio.run(ra.resolve("wss://x", GENESIS, journal, log=None)) == 496
    assert probes == ["wss://x"]


def _publisher_run(monkeypatch, tmp_path, report):
    """testnet_winner_publication._run with the chain faked: live runtime 497/CODE_B, the given probe report."""
    from types import SimpleNamespace

    from carbon.chain import runtime_probe
    from carbon.rewards import testnet_winner_publication as twp

    journal = tmp_path / "publication.sqlite3"
    _base(ra.store_for(journal))
    seen = {"issuer_specs": [], "wallet": 0}

    async def live(_endpoint):
        return 497, CODE_B

    async def probe(_endpoint, _genesis):
        return report

    monkeypatch.setattr(ra, "live_runtime", live)
    monkeypatch.setattr(runtime_probe, "probe", probe)
    config = SimpleNamespace(
        endpoint="wss://x", genesis_hash=GENESIS, expected_runtime_spec=488,
        context=SimpleNamespace(network="testnet"), publisher_hotkey="5P",
    )  # fmt: skip
    monkeypatch.setattr(
        "carbon.development_testnet.operator.load_config", lambda _p: config
    )

    def wallet(_c):
        seen["wallet"] += 1
        raise RuntimeError("stop after the wallet: this test ends here")

    monkeypatch.setattr("carbon.development_testnet.operator._wallet", wallet)

    def issuer(args, cfg, journal_path, *, runtime_spec=None):
        seen["issuer_specs"].append(runtime_spec)
        return SimpleNamespace()

    monkeypatch.setattr(twp, "_issuer", issuer)
    args = SimpleNamespace(config=str(tmp_path / "c"), journal=journal)
    try:
        asyncio.run(twp._run(args))
    except Exception as failure:  # noqa: BLE001
        seen["raised"] = failure
    return seen


def test_the_publisher_takes_an_accepted_upgrade_in_the_same_cycle(
    monkeypatch, tmp_path
):
    seen = _publisher_run(monkeypatch, tmp_path, _report(497))
    assert seen["issuer_specs"] == [
        None,
        497,
    ]  # rebuilt under the new spec before any wallet
    assert seen["wallet"] == 1


def test_the_publisher_refuses_a_changed_surface_typed_before_the_wallet(
    monkeypatch, tmp_path
):
    from carbon.rewards.testnet_winner_publication import WinnerPublicationRefused

    seen = _publisher_run(monkeypatch, tmp_path, _report(497, digest=OTHER))
    assert isinstance(
        seen["raised"], WinnerPublicationRefused
    )  # main() prints its code, not FAILED_CLOSED
    assert str(seen["raised"]) == "UNSUPPORTED_RUNTIME_SURFACE"
    assert seen["wallet"] == 0 and seen["issuer_specs"] == [None]
