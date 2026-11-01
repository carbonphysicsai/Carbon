"""The overlay's DISPATCH extension (image-move3d, Validator 2026-11-01): a new sealed adapter is reached through the sealed grader
module's existing tables with that module's bytes untouched; add-only; sha-pinned; every other version delegates unchanged.
"""

from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

from carbon.challenge_kit import version_overlay as overlay

KEY = ("electric-motor-magnetics", "1.6")
DISPATCH_SOURCE = """
def dispatch(config):
    calls = []
    return {
        "challenge": "electric-motor-magnetics",
        "version": "1.6",
        "pool_versions": ("fake-pool-sealed-v2", "fake-set"),
        "adapter": lambda version: ("mine", version, config),
        "adapter_for_bank": lambda bank, version: ("mine-bank", bank, version),
        "writer": lambda root, bank, *, version, **kw: ("mine-write", version, kw),
    }
"""


@pytest.fixture
def scene(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "carbon").mkdir(parents=True)
    (root / "carbon" / "__init__.py").write_text("")
    module = root / "carbon" / "fake_dispatch.py"
    module.write_text(DISPATCH_SOURCE)
    monkeypatch.setattr(overlay, "_ROOT", root)
    monkeypatch.syspath_prepend(str(root))
    # the real `carbon` package is already imported: make the fake module findable under it
    import carbon

    monkeypatch.setattr(carbon, "__path__", [*carbon.__path__, str(root / "carbon")])
    monkeypatch.delitem(sys.modules, "carbon.fake_dispatch", raising=False)
    monkeypatch.setattr(overlay, "_APPLIED", set())
    monkeypatch.setattr(overlay, "_ARMED", {})
    monkeypatch.setattr(overlay, "_DISPATCH", {})
    sha = hashlib.sha256(DISPATCH_SOURCE.encode()).hexdigest()
    target = types.ModuleType("fake_sealed")
    target.POOL_VERSIONS = {"1.5": ("fake-pool-sealed-v1", "fake-set")}
    target.VERSIONS = {"1.1": ("a", "b"), **target.POOL_VERSIONS}
    target.adapter = lambda version: ("original", version)
    target.adapter_for_bank = lambda bank, version: ("original-bank", bank, version)
    target.write_sealed_pack = lambda root, bank, *, version="1.1", **kw: (
        "original-write",
        version,
    )
    monkeypatch.setitem(overlay.SEALED_TARGET, KEY[0], "fake_sealed")
    monkeypatch.setitem(sys.modules, "fake_sealed", target)
    block = {"module": "carbon.fake_dispatch", "sha256": sha, "config": {"k": 1}}
    yield target, block, sha, module
    sys.modules.pop("carbon.fake_dispatch", None)


def _arm(block):
    overlay._arm(KEY, overlay._check_dispatch(KEY, block))


def test_a_dispatch_registers_the_version_and_every_other_version_delegates_unchanged(
    scene,
):
    target, block, _sha, _module = scene
    originals = (target.adapter, target.adapter_for_bank, target.write_sealed_pack)
    _arm(block)
    assert target.POOL_VERSIONS["1.6"] == ("fake-pool-sealed-v2", "fake-set")
    assert target.VERSIONS["1.6"] == ("fake-pool-sealed-v2", "fake-set")
    assert target.adapter("1.6") == ("mine", "1.6", {"k": 1})
    assert target.adapter_for_bank("B", "1.6") == ("mine-bank", "B", "1.6")
    assert target.write_sealed_pack("r", "B", version="1.6", calibration=True) == (
        "mine-write",
        "1.6",
        {"calibration": True},
    )
    # an image-registered version is served by the original function, untouched
    assert target.adapter("1.5") == ("original", "1.5")
    assert target.adapter_for_bank("B", "1.5") == ("original-bank", "B", "1.5")
    assert target.write_sealed_pack("r", "B", version="1.5") == (
        "original-write",
        "1.5",
    )
    assert target.write_sealed_pack("r", "B") == ("original-write", "1.1")
    assert (
        target.adapter.__wrapped__,
        target.adapter_for_bank.__wrapped__,
        target.write_sealed_pack.__wrapped__,
    ) == originals
    assert target.POOL_VERSIONS["1.5"] == ("fake-pool-sealed-v1", "fake-set")


def test_a_wrong_module_sha_is_refused_before_the_module_is_imported(scene):
    _target, block, _sha, _module = scene
    sys.modules.pop("carbon.fake_dispatch", None)
    with pytest.raises(overlay.OverlayRefused, match="sha256 does not match"):
        overlay._check_dispatch(KEY, {**block, "sha256": "0" * 64})
    assert "carbon.fake_dispatch" not in sys.modules


def test_a_changed_module_file_no_longer_matches_its_entry(scene):
    _target, block, _sha, module = scene
    module.write_text(DISPATCH_SOURCE + "\n# changed\n")
    with pytest.raises(overlay.OverlayRefused, match="sha256 does not match"):
        overlay._check_dispatch(KEY, block)


def test_crlf_checkouts_hash_the_same(scene):
    _target, block, _sha, module = scene
    module.write_bytes(DISPATCH_SOURCE.replace("\n", "\r\n").encode())
    assert overlay._check_dispatch(KEY, block)["module"] == "carbon.fake_dispatch"


def test_an_image_registered_version_cannot_be_dispatched(scene):
    target, block, _sha, _module = scene
    target.POOL_VERSIONS["1.6"] = ("image", "registered")
    with pytest.raises(overlay.OverlayRefused, match="may only add new versions"):
        _arm(block)
    assert target.POOL_VERSIONS["1.6"] == ("image", "registered")


def test_a_version_in_the_modules_versions_table_is_refused_too(scene):
    target, block, _sha, _module = scene
    target.VERSIONS["1.6"] = ("image", "registered")
    with pytest.raises(overlay.OverlayRefused, match="may only add new versions"):
        _arm(block)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: {**b, "extra": 1},
        lambda b: {k: v for k, v in b.items() if k != "sha256"},
        lambda b: {**b, "sha256": "ABC"},
        lambda b: {**b, "module": "os.path"},
        lambda b: {**b, "module": "carbon/fake_dispatch"},
        lambda b: {**b, "config": []},
        lambda b: "carbon.fake_dispatch",
    ],
)
def test_a_malformed_dispatch_block_is_refused(scene, mutate):
    _target, block, _sha, _module = scene
    with pytest.raises(overlay.OverlayRefused):
        overlay._check_dispatch(KEY, mutate(block))


def test_a_challenge_with_no_sealed_module_is_refused(scene):
    _target, block, _sha, _module = scene
    with pytest.raises(overlay.OverlayRefused, match="no sealed grader module"):
        overlay._check_dispatch(("unknown-challenge", "1.0"), block)


def test_the_dispatch_module_must_register_the_entrys_own_version(scene):
    _target, block, _sha, module = scene
    other = DISPATCH_SOURCE.replace('"version": "1.6"', '"version": "1.7"')
    module.write_text(other)
    block = {**block, "sha256": hashlib.sha256(other.encode()).hexdigest()}
    with pytest.raises(overlay.OverlayRefused, match="another version"):
        _arm(block)


def test_a_dispatch_applies_when_the_sealed_module_is_imported_later(
    scene, tmp_path, monkeypatch
):
    _target, block, _sha, _module = scene
    sys.modules.pop("fake_sealed")
    late = tmp_path / "late"
    late.mkdir()
    (late / "fake_sealed.py").write_text(
        'POOL_VERSIONS = {"1.5": ("p", "s")}\n'
        'def adapter(version):\n    return ("original", version)\n'
    )
    monkeypatch.syspath_prepend(str(late))
    _arm(block)  # not imported yet: armed, nothing applied
    assert KEY not in overlay._APPLIED
    monkeypatch.setattr(overlay, "_DISPATCH", {})
    try:
        import fake_sealed

        assert fake_sealed.POOL_VERSIONS["1.6"] == ("fake-pool-sealed-v2", "fake-set")
        assert fake_sealed.adapter("1.6")[0] == "mine"
        assert fake_sealed.adapter("1.5") == ("original", "1.5")
    finally:
        sys.modules.pop("fake_sealed", None)
        if overlay._FINDER in sys.meta_path:
            sys.meta_path.remove(overlay._FINDER)


def test_arming_twice_is_idempotent_and_a_different_block_is_refused(scene):
    target, block, _sha, _module = scene
    _arm(block)
    first = target.adapter
    _arm(block)
    assert target.adapter is first  # not wrapped a second time
    with pytest.raises(overlay.OverlayRefused, match="different dispatch"):
        overlay._arm(KEY, {"module": "carbon.fake_dispatch", "config": {"other": 1}})


def test_the_entry_digest_binds_the_dispatch_block(tmp_path):
    base = {
        "challenge_id": "x",
        "version": "1",
        "dispatch": {"module": "carbon.m", "sha256": "a" * 64},
    }
    changed = {**base, "dispatch": {"module": "carbon.m", "sha256": "b" * 64}}
    assert overlay.canonical_digest(base) != overlay.canonical_digest(changed)


def test_with_no_dispatch_entry_the_real_sealed_modules_are_untouched():
    """A sealed grader module's functions are the file's own unless the overlay file carries a dispatch for its Challenge."""
    from carbon.scoring import (
        cooling_encoded_dual_pack,
        f02_sealed_dual_pack,
        f08_sealed_dual_pack,
        motor_sealed_dual_pack,
    )

    entries = json.loads(overlay.OVERLAY_PATH.read_bytes())["versions"].values()
    served = {e["challenge_id"] for e in entries if "dispatch" in e}
    modules = {
        "electric-motor-magnetics": motor_sealed_dual_pack,
        "f02": f02_sealed_dual_pack,
        "f08-ribbed-bracket": f08_sealed_dual_pack,
        "chip-cold-plate": cooling_encoded_dual_pack,
    }
    for challenge, module in modules.items():
        if challenge in served:
            continue
        for name in (
            "adapter",
            "adapter_for_bank",
            "write_sealed_pack",
            "sealed_adapter",
        ):
            assert not hasattr(getattr(module, name, None), "__wrapped__"), (
                challenge,
                name,
            )


def test_load_reads_a_dispatch_entry_and_refuses_a_bad_sha(scene, tmp_path):
    _target, block, _sha, _module = scene
    entry = json.loads((Path(overlay.OVERLAY_PATH)).read_text("utf-8"))["versions"][
        "chip-cold-plate 1.7"
    ]
    good = {"schema": overlay.SCHEMA, "versions": {"chip-cold-plate 1.7": {**entry}}}
    path = tmp_path / "ok.json"
    path.write_text(json.dumps(good))
    assert ("chip-cold-plate", "1.7") in overlay.load(path)
    bad = {
        **good,
        "versions": {
            "chip-cold-plate 1.7": {
                **entry,
                "dispatch": {**block, "sha256": "1" * 64},
            }
        },
    }
    path.write_text(json.dumps(bad))
    with pytest.raises(overlay.OverlayRefused, match="sha256 does not match"):
        overlay.load(path)
