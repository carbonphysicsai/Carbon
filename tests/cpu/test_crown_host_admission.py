"""The host-owned campaign of the crown average's derived rebuilds records a CLOSED host admission, not a registration.

The TL's box run failed every derived rebuild at 0.0 s: the host owner's manifest had `admission=None` and
`research_ledger._check_product` refused it. A fake chain registration would be false provenance and a bypass flag would
unguard the miner path, so `HOST_REBUILD_ADMISSION` is a third closed kind next to the registration and the practice
admission. These tests run it through a REAL `OwnerProviders` and a REAL `CampaignLedger` (no patched `_manifest` or
`freeze`), the seam the earlier mock-only tests missed."""

from __future__ import annotations

import copy
import json

import pytest
from test_crown_infra_retry import _pool, posix
from test_direct_receiver import OWNER

from carbon.challenge_validator import crown_average as ca
from carbon.development_session.research_ledger import (
    HOST_REBUILD_ADMISSION,
    PRODUCT_ADMISSION,
    CampaignLedger,
)


def _frozen(provider):
    with provider.ledger.db() as db:
        return json.loads(
            db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()[0]
        )


def _fresh(tmp_path, name):
    return CampaignLedger(tmp_path / name)


@posix
def test_the_real_pool_opens_the_host_owner_and_the_seam_reaches_a_provider_and_a_reservation(
    tmp_path,
):
    pool = _pool(tmp_path)()
    provider = pool(
        ca.HOST_OWNER
    )  # real OwnerProviders -> real _manifest -> real CampaignLedger.freeze
    manifest = _frozen(provider)
    assert manifest["owner"] == manifest["principal"] == ca.HOST_OWNER
    assert manifest["admission"] == {
        "admission": HOST_REBUILD_ADMISSION,
        "challenge_id": manifest["challenge"]["id"],
    }
    assert "grant" not in manifest
    # every later line the dispatch takes: authority, the control checkpoint, the owner check and a reservation
    assert provider.ledger.authority(manifest) == {
        "kind": HOST_REBUILD_ADMISSION,
        "expires_unix": None,
    }
    provider.ledger.checkpoint()
    result = provider.ledger.reserve(
        "seam-operation",
        owner=ca.HOST_OWNER,
        phase="research",
        request={"seam": True},
        resources={},
    )
    assert result["dispatch"] is True
    with pytest.raises(ValueError, match="authenticated campaign owner differs"):
        provider.ledger.reserve(
            "seam-other", owner=OWNER, phase="research", request={}, resources={}
        )
    # the reservation above is deliberately left open: `close` would (rightly) demand its reconciliation
    pool.cancel()


@posix
def test_a_host_manifest_freezes_on_a_fresh_ledger_and_survives_a_restart(tmp_path):
    make = _pool(tmp_path)
    pool = make()
    manifest = _frozen(pool(ca.HOST_OWNER))
    ledger = _fresh(tmp_path, "fresh")
    assert ledger.freeze(manifest)  # (1) accepted
    assert ledger.freeze(manifest) == ledger.freeze(copy.deepcopy(manifest))
    pool.cancel()
    pool.close()
    restarted = make()
    restarted.restore()
    assert restarted(ca.HOST_OWNER).owner == ca.HOST_OWNER
    restarted.cancel()
    restarted.close()


def variants(manifest):
    """The host manifests that must NOT freeze (2)."""

    def with_(**changes):
        value = copy.deepcopy(manifest)
        for key, new in changes.items():
            value[key] = new
        return value

    host = manifest["admission"]
    return {
        "ss58 owner and principal": with_(owner=OWNER, principal=OWNER),
        "ss58 owner only": with_(owner=OWNER),
        "ss58 principal only": with_(principal=OWNER),
        "extra hotkey key": with_(admission={**host, "hotkey": OWNER}),
        "extra uid key": with_(admission={**host, "uid": 1}),
        "extra block keys": with_(
            admission={**host, "registered_at_block": 1, "observed_block": 2}
        ),
        "missing challenge_id": with_(admission={"admission": HOST_REBUILD_ADMISSION}),
        "challenge_id of another challenge": with_(
            admission={**host, "challenge_id": "another-challenge"}
        ),
        "challenge_id not a string": with_(admission={**host, "challenge_id": 5}),
        "host kind plus a grant": with_(grant={"anything": 1}),
        "a lookalike host owner": with_(
            owner=ca.HOST_OWNER + "2", principal=ca.HOST_OWNER + "2"
        ),
    }


@posix
def test_the_host_kind_is_refused_for_any_other_owner_or_shape(tmp_path):
    pool = _pool(tmp_path)()
    manifest = _frozen(pool(ca.HOST_OWNER))
    for label, bad in variants(manifest).items():
        with pytest.raises(ValueError):
            _fresh(tmp_path, label.replace(" ", "_")).freeze(bad)
    pool.cancel()
    pool.close()


@posix
def test_the_miner_path_is_unchanged_a_product_manifest_without_admission_still_rejects(
    tmp_path,
):
    pool = _pool(tmp_path)()
    miner = _frozen(pool(OWNER))
    assert (
        miner["admission"]["admission"] == PRODUCT_ADMISSION
    )  # the registration, as before
    unadmitted = copy.deepcopy(miner)
    unadmitted["admission"] = None
    with pytest.raises(ValueError, match="must record its registration admission"):
        _fresh(tmp_path, "none").freeze(unadmitted)
    # the host kind on a miner's manifest is refused (the owner is an ss58 address)
    forged = copy.deepcopy(miner)
    forged["admission"] = {
        "admission": HOST_REBUILD_ADMISSION,
        "challenge_id": miner["challenge"]["id"],
    }
    with pytest.raises(ValueError, match="host admission"):
        _fresh(tmp_path, "forged").freeze(forged)
    pool.cancel()
    pool.close()
