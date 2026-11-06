"""H8 / R71: weights survive a chain runtime upgrade whose used surface is unchanged; a changed one refuses + alerts."""

from __future__ import annotations

import asyncio
import json

import pytest

from carbon.chain import runtime_accept as ra

DIGEST = "sha256:" + "d" * 64
OTHER = "sha256:" + "e" * 64


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


def _no_probe():
    raise AssertionError("must not probe")


def test_before_any_baseline_the_configured_spec_is_the_only_one(store):
    assert ra.decide(store, 488, 488, _no_probe) == 488
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_BASELINE_MISSING"):
        ra.decide(store, 489, 488, _no_probe)


def test_a_spec_bump_with_the_same_surface_publishes_the_same_cycle(store):
    ra.baseline(store, _report(488))
    lines = []
    spec = ra.decide(
        store, 490, 488, lambda: _report(490), log=lambda *a, **k: lines.append((a, k))
    )
    assert spec == 490
    body = ra.receipt(store, 490)
    assert body["decision"] == ra.ACCEPTED and body["surface_digest"] == DIGEST
    assert body["claims"]["runtime_behaviour_verified"] is False
    assert lines and lines[0][0][0] == "runtime_auto_accepted"
    # the next cycle on 490 reuses the receipt: no new probe
    assert ra.decide(store, 490, 488, _no_probe) == 490


def test_a_changed_surface_refuses_before_signing_and_alerts_once(store):
    ra.baseline(store, _report(488))
    lines = []
    changed = _report(491, digest=OTHER)
    for _ in range(3):
        with pytest.raises(ra.RuntimeRefused, match="UNSUPPORTED_RUNTIME_SURFACE"):
            ra.decide(
                store, 491, 488, lambda: changed, log=lambda *a, **k: lines.append(a[0])
            )
    alert = json.loads((store / ra.ALERT_NAME).read_text(encoding="utf-8"))
    assert alert["decision"] == ra.REFUSED and alert["baseline_digest"] == DIGEST
    assert alert["surface_digest"] == OTHER and alert["reason"] == "surface_changed"
    assert lines == [
        "operator_alert"
    ]  # one alert for one changed digest, not one per cycle
    assert ra.receipt(store, 491) is None


def test_incompatible_with_the_sdk_refuses_even_with_the_same_digest(store):
    ra.baseline(store, _report(488))
    bad = _report(
        492, status="INCOMPATIBLE", differences=[{"item": "x", "issue": "changed"}]
    )
    with pytest.raises(ra.RuntimeRefused):
        ra.decide(store, 492, 488, lambda: bad)
    alert = json.loads((store / ra.ALERT_NAME).read_text(encoding="utf-8"))
    assert alert["reason"] == "incompatible_with_sdk" and alert["differences"]


def test_a_baseline_must_be_compatible_and_receipts_must_agree(store):
    with pytest.raises(ra.RuntimeRefused, match="BASELINE_NOT_COMPATIBLE"):
        ra.baseline(store, _report(488, status="INCOMPATIBLE"))
    ra.baseline(store, _report(488))
    ra.baseline(store, _report(489, digest=OTHER))
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_RECEIPTS_DISAGREE"):
        ra.decide(store, 493, 488, _no_probe)


def test_a_runtime_that_moves_during_the_probe_refuses(store):
    ra.baseline(store, _report(488))
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_CHANGED_DURING_PROBE"):
        ra.decide(store, 494, 488, lambda: _report(495))


def test_resolve_probes_only_a_new_spec_after_a_baseline(store, monkeypatch, tmp_path):
    from carbon.chain import runtime_probe

    journal = tmp_path / "publication.sqlite3"
    probes = []

    async def live(_endpoint):
        return 496

    async def probe(endpoint, genesis):
        probes.append(endpoint)
        return _report(496)

    monkeypatch.setattr(ra, "live_spec", live)
    monkeypatch.setattr(runtime_probe, "probe", probe)
    ra.baseline(ra.store_for(journal), _report(488))
    assert asyncio.run(ra.resolve("wss://x", "0xg", 488, journal)) == 496
    assert asyncio.run(ra.resolve("wss://x", "0xg", 488, journal)) == 496
    assert probes == ["wss://x"]  # the second cycle reuses the receipt


def _publisher_run(monkeypatch, tmp_path, report):
    """Drive testnet_winner_publication._run with the chain faked: live spec 497, the given probe report."""
    from types import SimpleNamespace

    from carbon.chain import runtime_probe
    from carbon.rewards import testnet_winner_publication as twp

    journal = tmp_path / "publication.sqlite3"
    ra.baseline(ra.store_for(journal), _report(488))
    seen = {"issuer_specs": [], "wallet": 0}

    async def live(_endpoint):
        return 497

    async def probe(_endpoint, _genesis):
        return report

    monkeypatch.setattr(ra, "live_spec", live)
    monkeypatch.setattr(runtime_probe, "probe", probe)
    config = SimpleNamespace(
        endpoint="wss://x", genesis_hash="0xg", expected_runtime_spec=488,
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


def test_the_publisher_refuses_a_changed_surface_before_the_wallet(
    monkeypatch, tmp_path
):
    from carbon.chain.publication import PublicationFailure

    seen = _publisher_run(monkeypatch, tmp_path, _report(497, digest=OTHER))
    assert isinstance(seen["raised"], PublicationFailure)
    assert str(seen["raised"]) == "UNSUPPORTED_RUNTIME_SURFACE"
    assert seen["wallet"] == 0 and seen["issuer_specs"] == [None]


def _journal_with(tmp_path, rows):
    import sqlite3

    path = tmp_path / "publication.sqlite3"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE publication_v1 (identity TEXT PRIMARY KEY, document TEXT, digest TEXT, state TEXT,"
        " tracking TEXT, tracking_digest TEXT)"
    )
    for n, (spec, state, reason) in enumerate(rows):
        db.execute(
            "INSERT INTO publication_v1 VALUES (?,?,?,?,?,?)",
            (
                str(n),
                json.dumps({"capabilities": {"spec_version": spec}}),
                "d",
                state,
                json.dumps({"reason": reason}),
                "t",
            ),
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


def test_an_auto_accepted_spec_stops_after_two_read_back_misses(tmp_path):
    journal = _journal_with(tmp_path, [])
    store = ra.store_for(journal)
    ra.baseline(store, _report(488))
    lines = []

    def note(*a, **_k):
        lines.append(a[0])

    assert (
        ra.decide(store, 497, 488, lambda: _report(497), journal=journal, log=note)
        == 497
    )
    _add(journal, "a", 497, "ROW_VERIFIED")
    assert ra.decide(store, 497, 488, _no_probe, journal=journal, log=note) == 497
    assert lines == ["runtime_auto_accepted"]  # verified: no alert
    _add(journal, "b", 497, "FINALIZED", "STORED_ROW_DIFFERS_FROM_TARGET")
    assert ra.decide(store, 497, 488, _no_probe, journal=journal, log=note) == 497
    assert ra.decide(store, 497, 488, _no_probe, journal=journal, log=note) == 497
    assert lines == [
        "runtime_auto_accepted",
        "operator_alert",
    ]  # the first miss alerts once, still used
    _add(journal, "c", 497, "CHAIN_REJECTED")
    with pytest.raises(ra.RuntimeRefused, match="RUNTIME_READBACK_FAILED"):
        ra.decide(store, 497, 488, _no_probe, journal=journal, log=note)
    # a baseline spec is a person's decision: its read-back is the operator's watch, never a stop here
    _add(journal, "d", 488, "CHAIN_REJECTED")
    _add(journal, "e", 488, "CHAIN_REJECTED")
    assert ra.decide(store, 488, 488, _no_probe, journal=journal) == 488
