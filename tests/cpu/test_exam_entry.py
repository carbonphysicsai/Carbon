"""The catalog entry of a version registered by data: offered as a pool version is, retired by one word, live entries unmoved."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from carbon.challenge_kit import version_registry
from carbon.challenge_registry import (
    exam_build,
    exam_entry,
    exam_registry,
    published_exam,
    registry,
)

KEY = ("zz-synthetic", "0.1")
ROW = {
    "title": "Synthetic exam",
    "portfolio": "launch_pending_readiness",
    "status": "open",
}
#: main fe148ac4: the sha256 of each live entry's summary on a host with no facts, read before this change.
LIVE = {
    (
        "electric-motor-magnetics",
        "1.8",
    ): "3fb28df925846fa046b949ae8ca4f505fce51656c3574a1d0d4031005a70971a",
    (
        "chip-cold-plate",
        "1.8",
    ): "6fdfdfdedc5730036b67b3dd9e5996790e48297ab14759275f434e1dd32c6e06",
    (
        "f08-ribbed-bracket",
        "1.7",
    ): "da82d675fe1d20a45aa7bf8d14627b52f64d53067e8f78e75f14be9cc941b34e",
    ("f02", "2.5"): "ea9cbadf71668ef7d2e656d0180b1a7c74126ee591cda0f61631ba098c445f33",
}


@pytest.fixture
def rows(monkeypatch):
    """One synthetic entry row with a good build row; the test changes what it holds."""
    held = {"entry": dict(ROW), "build": {"good": True}, "key": KEY}
    monkeypatch.setattr(exam_entry, "REFUSED", {})
    monkeypatch.setattr(
        exam_registry,
        "keys",
        lambda name: (held["key"],) if name == "entry" and held["entry"] else (),
    )
    monkeypatch.setattr(exam_registry, "field", lambda *asked: dict(held["entry"]))
    real = exam_build.code_serves
    monkeypatch.setattr(
        exam_build, "code_serves", lambda *key: key != KEY and real(*key)
    )

    def block(*key):
        if isinstance(held["build"], Exception):
            raise held["build"]
        return held["build"]

    monkeypatch.setattr(exam_build, "block", block)
    return held


def _entry():
    found = [e for e in registry.entries() if (e.challenge_id, e.version) == KEY]
    return found[0] if found else None


def _digest(entry):
    body = json.dumps(
        entry.summary(registry.HostFacts()), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(body.encode()).hexdigest()


def test_the_committed_registry_adds_no_entry():
    assert exam_entry.rows() == {}
    assert registry.entries() == registry._code_entries()


@pytest.mark.parametrize("key", sorted(LIVE))
def test_every_live_entry_is_mains(key):
    (entry,) = [e for e in registry.entries() if (e.challenge_id, e.version) == key]
    assert _digest(entry) == LIVE[key]


def test_an_open_row_is_reserved_until_its_constants_are_published(rows, monkeypatch):
    entry = _entry()
    assert (entry.title, entry.portfolio) == (ROW["title"], ROW["portfolio"])
    assert entry.status == registry.RESERVED
    with pytest.raises(registry.ChallengeNotImplemented):
        registry._find(*KEY)
    real = published_exam.registered_pool
    monkeypatch.setattr(
        published_exam,
        "registered_pool",
        lambda *key: {"kind": "any"} if key == KEY else real(*key),
    )
    assert _entry().status == registry.IMPLEMENTED
    assert registry._find(*KEY).version == KEY[1]
    listed = registry.catalog(registry.HostFacts())["challenges"]
    mine = [c for c in listed if (c["challenge_id"], c["version"]) == KEY]
    assert len(mine) == 1 and registry.is_offered(mine[0])


def test_a_retired_row_is_listed_and_never_selected_whatever_its_constants_say(
    rows, monkeypatch
):
    before = {(e.challenge_id, e.version): _digest(e) for e in registry._code_entries()}
    real = published_exam.registered_pool
    monkeypatch.setattr(
        published_exam,
        "registered_pool",
        lambda *key: {"kind": "any"} if key == KEY else real(*key),
    )
    rows["entry"]["status"] = "retired"
    assert _entry().status == registry.RETIRED
    for ask in (
        lambda: registry._find(*KEY),
        lambda: registry.resolve(*KEY, registry.CPU_RESEARCH),
        lambda: registry.describe(*KEY),
        lambda: registry.published_description(*KEY),
    ):
        with pytest.raises(registry.ChallengeRetired):
            ask()
    # dropping it moves nothing else
    after = {
        (e.challenge_id, e.version): _digest(e)
        for e in registry.entries()
        if (e.challenge_id, e.version) != KEY
    }
    assert after == before


def test_a_row_that_gives_no_entry_leaves_the_version_unknown(rows):
    for build in (None, exam_build.ExamBuildRefused("build_block_fields")):
        rows["build"] = build
        assert _entry() is None and KEY in exam_entry.REFUSED
        with pytest.raises(registry.UnknownChallenge):
            registry._find(*KEY)


def test_a_version_the_code_serves_keeps_its_own_entry(rows):
    rows["key"] = ("electric-motor-magnetics", "1.8")
    assert exam_entry.rows() == {}
    assert exam_entry.REFUSED[rows["key"]] == "entry_version_is_code_served"
    assert registry.entries() == registry._code_entries()


@pytest.mark.parametrize(
    "change",
    [
        {"title": ""},
        {"title": "x" * 121},
        {"title": "<b>bold</b>"},
        {"title": 1},
        {"portfolio": "other"},
        {"portfolio": ["launch"]},
        {"status": "live"},
        {"extra": 1},
    ],
)
def test_the_row_s_shape_is_closed(change):
    check = exam_registry.FIELDS["entry"]
    assert check(ROW)
    assert not check({**ROW, **change})
    assert not check({name: ROW[name] for name in ("title", "status")})


def test_the_description_holds_only_what_the_build_module_serves(rows, monkeypatch):
    served = {
        "interface_document": {"schema": "i"},
        "construction_kit": {"id": KEY[0], "version": KEY[1]},
        "construction_limits_document": {"schema": "l"},
        "load_public_train": {"case_ids": ("a", "b")},
    }
    module = SimpleNamespace(
        **{name: (lambda *key, value=value: value) for name, value in served.items()}
    )
    monkeypatch.setattr(exam_build, "module", lambda *key: module)
    monkeypatch.setattr(
        version_registry, "entry", lambda *key: SimpleNamespace(train="zz-train")
    )
    described = exam_entry.describe(*KEY)
    assert described["interface"] == {"schema": "i"}
    assert described["construction_kit"] == {"id": KEY[0], "version": KEY[1]}
    assert described["construction_limits"] == {"schema": "l"}
    assert described["public_material"] == {"train": {"name": "zz-train", "cases": 2}}
    assert json.loads(json.dumps(described)) == described
