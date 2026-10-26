"""A pool-graded version refuses to grade until the owner registers its constants (M2; V8_RULINGS section 11),
and a version offers another's catalog entries only when the two differ by identity alone (item 3).
"""

from __future__ import annotations

import json

import pytest

from carbon.backbone_catalog import carries
from carbon.backbone_catalog.entries import CatalogRefused
from carbon.challenge_kit import version_registry
from carbon.scoring import pool_exam, pool_version

POOL = [
    ("f08-ribbed-bracket", "1.6"),
    ("f02", "2.5"),
    ("electric-motor-magnetics", "1.5"),
    ("chip-cold-plate", "1.5"),
]


def _entry(**overrides):
    entry = {
        "optimizer": {"budget": 40, "sigma0": 0.3, "population": 8},
        "honesty": {"scale": 1.0, "reduction": "max"},
        "agen_scales": {"x": 1.0},
        "a_rule": {"kind": "test_fixture"},
        "c_rule": {"kind": "min"},
    }
    entry.update(overrides)
    return entry


def _file(tmp_path, versions, schema=pool_version.SCHEMA):
    path = tmp_path / "pool_constants.json"
    path.write_text(json.dumps({"schema": schema, "versions": versions}))
    return path


@pytest.mark.parametrize(("challenge_id", "version"), POOL)
def test_the_shipped_file_registers_no_owner_constant_so_every_pool_version_refuses(
    challenge_id, version
):
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    entry = document["versions"][f"{challenge_id} {version}"]
    assert entry["c_rule"] == {"kind": "min"}
    assert pool_version.HUMAN_INPUT in json.dumps(entry)
    with pytest.raises(pool_version.PoolConstantsNotRegistered) as refused:
        pool_version.registered_policies(challenge_id, version)
    assert str(refused.value) == "pool_constants_not_registered"
    assert isinstance(refused.value, pool_exam.ExamRefused)


def test_a_fully_registered_version_returns_its_policies(tmp_path):
    path = _file(tmp_path, {"f02 2.5": _entry()})
    policies = pool_version.registered_policies("f02", "2.5", path=path)
    assert policies.optimizer.budget == 40 and policies.honesty.reduction == "max"
    assert policies.c_rule == {"kind": "min"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e["optimizer"].update(budget=pool_version.HUMAN_INPUT),
        lambda e: e["honesty"].update(scale=pool_version.HUMAN_INPUT),
        lambda e: e.update(a_rule=pool_version.HUMAN_INPUT),
        lambda e: e.update(agen_scales=pool_version.HUMAN_INPUT),
    ],
)
def test_one_unpicked_constant_refuses_the_whole_version(tmp_path, mutate):
    entry = _entry()
    mutate(entry)
    path = _file(tmp_path, {"f02 2.5": entry})
    with pytest.raises(pool_version.PoolConstantsNotRegistered) as refused:
        pool_version.registered_policies("f02", "2.5", path=path)
    assert str(refused.value) == "pool_constants_not_registered"


@pytest.mark.parametrize(
    "path_for",
    [
        lambda tmp: tmp / "missing.json",
        lambda tmp: _file(tmp, {}),
        lambda tmp: _file(tmp, {"f02 2.5": _entry()}, schema="other"),
        lambda tmp: _file(tmp, {"f02 2.5": {"optimizer": {}}}),
    ],
)
def test_an_unregistered_or_unreadable_file_refuses_never_defaults(tmp_path, path_for):
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version.registered_policies("f02", "2.5", path=path_for(tmp_path))


@pytest.mark.parametrize("bad", [{"budget": 0}, {"sigma0": -1.0}, {"population": 1}])
def test_a_malformed_constant_is_refused_not_clamped(tmp_path, bad):
    entry = _entry()
    entry["optimizer"].update(bad)
    path = _file(tmp_path, {"f02 2.5": entry})
    with pytest.raises(pool_exam.ExamRefused):
        pool_version.registered_policies("f02", "2.5", path=path)


# --- the cross-version pair rule ------------------------------------------------------------------------


@pytest.mark.parametrize(("challenge_id", "version"), POOL)
def test_a_pool_version_carries_its_predecessors_entries_by_identity_alone(
    challenge_id, version
):
    found = carries.require_identity_only(challenge_id, version)
    assert found, "a pool version offers its predecessor's catalog entries"
    for diff in found.values():
        assert set(diff) <= carries.ALLOWED_INTERFACE_DIFF


def test_motor_and_cooling_interfaces_do_not_name_their_version_so_nothing_differs():
    for challenge_id in ("electric-motor-magnetics", "chip-cold-plate"):
        for diff in carries.require_identity_only(challenge_id, "1.5").values():
            assert diff == []


def test_f08_and_f02_differ_by_their_own_version_label_alone():
    for challenge_id, version in (("f08-ribbed-bracket", "1.6"), ("f02", "2.5")):
        for diff in carries.require_identity_only(challenge_id, version).values():
            assert diff == ["/challenge/version"]


def test_a_carry_whose_interface_differs_elsewhere_is_refused(monkeypatch):
    monkeypatch.setattr(
        carries,
        "interface_diff",
        lambda *_: ["/challenge/version", "/inputs/0/range"],
    )
    carries.require_identity_only.cache_clear()
    try:
        with pytest.raises(CatalogRefused) as refused:
            carries.require_identity_only("f02", "2.5")
        assert refused.value.code == "catalog_entry_unknown"
        assert "beyond identity" in refused.value.detail
    finally:
        carries.require_identity_only.cache_clear()


def test_a_carry_from_a_version_with_a_different_train_is_refused(monkeypatch):
    real = version_registry.find

    def other_train(challenge_id, version):
        entry = real(challenge_id, version)
        if version == "2.4":
            from dataclasses import replace

            return replace(entry, train="not-the-same-train")
        return entry

    monkeypatch.setattr(version_registry, "find", other_train)
    carries.require_identity_only.cache_clear()
    try:
        with pytest.raises(CatalogRefused) as refused:
            carries.require_identity_only("f02", "2.5")
        assert refused.value.code == "catalog_entry_unknown"
        assert "train differs" in refused.value.detail
    finally:
        carries.require_identity_only.cache_clear()
