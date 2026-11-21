"""Submit latency (live 116, 21 Nov 2026: st_retain ~2 s on the busiest owners after c9c94c42): a graph start retains its
source with ONE walk of the owner's campaign tree when the miner set no retained-bytes cap; with a cap it still re-checks
after the write and removes a source that went over it. A symlink in the tree is still refused by the walk before the write.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from test_miner_budget_surface import campaign

from carbon.development_session import research_ledger
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3


def _counting(monkeypatch):
    walks = []
    real = research_ledger._campaign_bytes

    def counted(root):
        walks.append(root)
        return real(root)

    monkeypatch.setattr(research_ledger, "_campaign_bytes", counted)
    return walks


def _provider(ledger, tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    return SimpleNamespace(
        ledger=ledger, _source_path=lambda identity: sources / identity
    )


def _retain(provider, identity, body):
    DirectDevelopmentTasksV3._retain_source(provider, identity, body)


def test_an_uncapped_owner_retains_with_no_walk_on_the_request(tmp_path, monkeypatch):
    ledger = campaign(tmp_path / "ledger")
    assert ledger.storage_capped() is False
    provider = _provider(ledger, tmp_path)
    walks = _counting(monkeypatch)
    _retain(provider, "task-a", b"graph bytes")
    assert walks == []  # the whole-tree walk is the reconcile's, off the request path
    assert (tmp_path / "sources" / "task-a").read_bytes() == b"graph bytes"


def test_a_capped_owner_still_rechecks_after_the_write(tmp_path, monkeypatch):
    ledger = campaign(tmp_path / "ledger", ceilings={"retained_bytes": 1024**3})
    assert ledger.storage_capped() is True
    provider = _provider(ledger, tmp_path)
    walks = _counting(monkeypatch)
    _retain(provider, "task-a", b"graph bytes")
    assert len(walks) == 2


def test_a_source_over_the_cap_after_the_write_is_removed(tmp_path, monkeypatch):
    ledger = campaign(tmp_path / "ledger", ceilings={"retained_bytes": 1024**3})
    provider = _provider(ledger, tmp_path)
    calls = []
    real = ledger.check_storage

    def second_refuses(additional=0):
        calls.append(additional)
        if len(calls) == 2:
            raise research_ledger.LedgerRefusal(
                "miner budget: retained_bytes",
                code=research_ledger.MINER_CEILING_REACHED,
                dimension="retained_bytes",
            )
        return real(additional)

    monkeypatch.setattr(ledger, "check_storage", second_refuses)
    with pytest.raises(research_ledger.LedgerRefusal):
        _retain(provider, "task-a", b"graph bytes")
    assert not (tmp_path / "sources" / "task-a").exists()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks here")
def test_a_symlink_found_by_the_reconcile_refuses_every_later_write(tmp_path):
    ledger = campaign(tmp_path / "ledger")
    os.symlink(tmp_path, ledger.root / "link")
    with pytest.raises(ValueError, match="campaign symlink rejected"):
        ledger.reconcile_storage()
    assert (ledger.root / ledger.STORAGE_FAULT).is_file()
    provider = _provider(ledger, tmp_path)
    with pytest.raises(ValueError, match="campaign symlink rejected"):
        _retain(provider, "task-a", b"graph bytes")
    assert not (tmp_path / "sources" / "task-a").exists()
    with pytest.raises(ValueError, match="campaign symlink rejected"):
        ledger.check_storage_fast(0)


def test_a_capped_owner_keeps_its_exact_limit_on_the_fast_check(tmp_path):
    from carbon.development_session.research_ledger import LedgerRefusal

    ledger = campaign(tmp_path / "ledger", ceilings={"retained_bytes": 4096})
    with pytest.raises(LedgerRefusal, match="retained_bytes"):
        ledger.check_storage_fast(1024**3)
    assert campaign(tmp_path / "uncapped").check_storage_fast(1024**4) is None


def test_the_reconcile_walks_and_counts(tmp_path):
    ledger = campaign(tmp_path / "ledger")
    (ledger.root / "blob").write_bytes(b"x" * 1000)
    assert ledger.reconcile_storage() >= 1000
    assert not (ledger.root / ledger.STORAGE_FAULT).exists()


def test_a_retain_inside_a_submit_names_its_parts(tmp_path):
    from carbon.challenge_validator import step_timing

    ledger = campaign(tmp_path / "ledger")
    provider = _provider(ledger, tmp_path)
    with step_timing.collecting() as steps:
        _retain(provider, "task-a", b"graph bytes")
    assert {
        "st_retain_walk",
        "st_retain_write",
        "st_retain_fsync",
        "st_retain_replace",
        "st_retain_verify",
        "st_retain_cap",
    } <= set(steps)
    assert all(type(ms) is int and ms >= 0 for ms in steps.values())
