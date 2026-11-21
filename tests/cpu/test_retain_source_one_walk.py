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


def test_an_uncapped_owner_retains_with_one_walk(tmp_path, monkeypatch):
    ledger = campaign(tmp_path / "ledger")
    assert ledger.storage_capped() is False
    provider = _provider(ledger, tmp_path)
    walks = _counting(monkeypatch)
    _retain(provider, "task-a", b"graph bytes")
    assert len(walks) == 1
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
def test_a_symlink_in_the_tree_still_refuses_before_any_write(tmp_path):
    ledger = campaign(tmp_path / "ledger")
    os.symlink(tmp_path, ledger.root / "link")
    provider = _provider(ledger, tmp_path)
    with pytest.raises(ValueError, match="campaign symlink rejected"):
        _retain(provider, "task-a", b"graph bytes")
    assert not (tmp_path / "sources" / "task-a").exists()
