"""R0 (23 Nov 2026 rehearsal, release 5211 F2): the analysis image build bound covers the
slowest image build measured on containerd's native snapshotter (Lium pods), with margin.

The old 600 s bound timed out a first miner install there; the measured builds are in
codex-queue/reports/REHEARSAL_R0_20261123/pod1_carbon-ada-r0/ (k5install.1.out and
k5install.snap.out)."""

from __future__ import annotations

from pathlib import Path

from carbon.development_session import research_image

#: The PyTorch GPU worker build on that store (its unpack alone 817.3 s).
SLOWEST_MEASURED_BUILD_S = 889.9


def test_the_bound_is_about_twice_the_slowest_measured_native_store_build():
    assert research_image.ANALYSIS_BUILD_TIMEOUT >= 2 * SLOWEST_MEASURED_BUILD_S


def test_the_analysis_build_uses_the_named_bound():
    source = Path(research_image.__file__).read_text(encoding="utf-8")
    assert "timeout=ANALYSIS_BUILD_TIMEOUT," in source
    assert "timeout=600" not in source
