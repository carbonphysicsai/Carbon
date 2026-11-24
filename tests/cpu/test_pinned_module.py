"""A host-named module is imported only after its file hashes to the named sha256 (v2 ruling row 4033)."""

from __future__ import annotations

import hashlib
import importlib.machinery
import sys
import types

import pytest

import carbon
from carbon.challenge_registry import pinned_module

MODULE = "carbon.zz_pinned_module"
SOURCE = b"VALUE = 7\n"


@pytest.fixture
def source(tmp_path, monkeypatch):
    folder = tmp_path / "carbon"
    folder.mkdir()
    path = folder / "zz_pinned_module.py"
    path.write_bytes(SOURCE)
    monkeypatch.setattr(carbon, "__path__", [*carbon.__path__, str(folder)])
    monkeypatch.delitem(sys.modules, MODULE, raising=False)
    yield path
    sys.modules.pop(MODULE, None)


def _block(raw=SOURCE):
    return {"module": MODULE, "sha256": hashlib.sha256(raw).hexdigest()}


def test_a_matching_module_is_checked_without_import_then_loaded(source):
    pinned_module.check(_block())
    assert MODULE not in sys.modules
    assert pinned_module.load(_block()).VALUE == 7


def test_crlf_reads_as_lf(source):
    source.write_bytes(SOURCE.replace(b"\n", b"\r\n"))
    pinned_module.check(_block())


def test_a_changed_file_is_never_imported(source):
    source.write_bytes(b"raise SystemExit('ran')\n")
    with pytest.raises(pinned_module.PinnedModuleRefused, match="sha256 differs"):
        pinned_module.load(_block())
    assert MODULE not in sys.modules


@pytest.mark.parametrize("raw", [SOURCE, b"OTHER = 1\n"])
def test_a_parent_package_never_runs_before_the_hash(tmp_path, monkeypatch, raw):
    """A parent whose ``__init__`` raises: checking never runs it, and a mismatch refuses typed without running it."""
    package = tmp_path / "carbon" / "zz_pinned_parent"
    package.mkdir(parents=True)
    ran = tmp_path / "ran"
    (package / "__init__.py").write_text(
        f"open({str(ran)!r}, 'w').close()\nraise RuntimeError('parent ran')\n"
    )
    (package / "child.py").write_bytes(SOURCE)
    monkeypatch.setattr(
        carbon, "__path__", [*carbon.__path__, str(tmp_path / "carbon")]
    )
    block = {
        "module": "carbon.zz_pinned_parent.child",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if raw == SOURCE:
        pinned_module.check(block)
        assert not ran.exists()
        with pytest.raises(pinned_module.PinnedModuleRefused, match="does not import"):
            pinned_module.load(block)
    else:
        with pytest.raises(pinned_module.PinnedModuleRefused, match="sha256 differs"):
            pinned_module.load(block)
        assert not ran.exists()


def test_a_module_already_loaded_from_another_file_is_refused(source, monkeypatch):
    other = types.ModuleType(MODULE)
    other.__spec__ = importlib.machinery.ModuleSpec(
        MODULE, None, origin=str(source.with_name("other.py"))
    )
    monkeypatch.setitem(sys.modules, MODULE, other)
    with pytest.raises(pinned_module.PinnedModuleRefused, match="another file"):
        pinned_module.load(_block())


@pytest.mark.parametrize(
    "block",
    [
        None,
        {},
        {"module": MODULE},
        {"module": MODULE, "sha256": "0" * 64, "extra": 1},
        {"module": MODULE, "sha256": "0" * 63},
        {"module": MODULE, "sha256": 0},
        {"module": 1, "sha256": "0" * 64},
        {"module": "os", "sha256": "0" * 64},
        {"module": "carbon.Upper", "sha256": "0" * 64},
        {"module": "carbon.no_such_module", "sha256": "0" * 64},
        {"module": "carbon.no_such_package.module", "sha256": "0" * 64},
    ],
)
def test_a_malformed_or_unknown_block_is_refused(source, block):
    with pytest.raises(pinned_module.PinnedModuleRefused):
        pinned_module.check(block)
