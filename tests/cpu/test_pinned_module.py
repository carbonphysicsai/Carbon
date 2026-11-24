"""A host-named module is imported only after its file hashes to the named sha256 (v2 ruling row 4033)."""

from __future__ import annotations

import hashlib
import sys

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
