"""Selftest for the DRAFT carbon/cold_plate/taper.py (exam-cooling, 21 Nov). Runner only. No solver run, no hidden data."""

import re

import pytest

from carbon.cold_plate import domain, mesh_family, openfoam, taper


def _case(t):
    c = dict(domain.NOMINAL)
    c["taper"] = t
    return c


def _vertices(text):
    block = text.split("vertices (", 1)[1].split(");", 1)[0]
    return [
        tuple(float(v) for v in m.split()) for m in re.findall(r"\(([^()]*)\)", block)
    ]


@pytest.mark.parametrize("family", [None, mesh_family.GRADED_HOTSPOT_V1])
def test_taper_one_is_the_straight_case_byte_for_byte(family):
    base = dict(domain.NOMINAL)
    straight = (
        openfoam.files(base)
        if family is None
        else mesh_family.files(base, mesh_family=family)
    )
    tapered = taper.files(_case(1.0), mesh_family=family)
    assert tapered[0] == straight[0]
    assert {
        k: v
        for k, v in tapered[1].items()
        if k not in ("taper", "channel_width_out_mm", "fin_width_out_mm")
    } == straight[1]


@pytest.mark.parametrize("family", [None, mesh_family.GRADED_HOTSPOT_V1])
@pytest.mark.parametrize("t", [0.5, 0.8, 1.5])
def test_only_the_outlet_channel_vertices_move_and_the_period_holds(family, t):
    base = dict(domain.NOMINAL)
    straight = (
        openfoam.files(base)
        if family is None
        else mesh_family.files(base, mesh_family=family)
    )
    texts, record = taper.files(_case(t), mesh_family=family)
    a, b = _vertices(straight[0]["system/blockMeshDict"]), _vertices(
        texts["system/blockMeshDict"]
    )
    assert len(a) == len(b)
    length = domain.FIXED["footprint_mm"]
    half_in, half_out = base["channel_width_mm"] / 2, base["channel_width_mm"] * t / 2
    period_half = (base["channel_width_mm"] + base["fin_width_mm"]) / 2
    moved = [(u, v) for u, v in zip(a, b) if u != v]
    assert moved and all(
        u[0] == length and abs(u[1] - half_in) < 1e-6 and abs(v[1] - half_out) < 1e-6
        for u, v in moved
    )
    assert max(v[1] for v in b) == pytest.approx(
        period_half, abs=1e-6
    )  # the symmetry plane at the half period stays
    assert record["channel_width_out_mm"] == pytest.approx(base["channel_width_mm"] * t)
    for name, text in texts.items():  # everything but the mesh is the straight case's
        if name != "system/blockMeshDict":
            assert text == straight[0][name]


@pytest.mark.parametrize("bad", [0.49, 2.01, float("nan"), True, "1"])
def test_refuses_a_taper_outside_the_proposed_bounds_or_not_a_number(bad):
    with pytest.raises(ValueError):
        taper.split(_case(bad))


def test_refuses_an_outlet_fin_below_the_floor():
    c = _case(2.0)
    c["channel_width_mm"], c["fin_width_mm"] = 0.5, 0.2  # w_out 1.0 > period 0.7
    with pytest.raises(ValueError):
        taper.split(c)


def test_refuses_missing_or_extra_inputs():
    with pytest.raises(ValueError):
        taper.split(dict(domain.NOMINAL))
    c = _case(1.0)
    c["extra"] = 1.0
    with pytest.raises(ValueError):
        taper.split(c)


@pytest.mark.parametrize("family", [None, mesh_family.GRADED_HOTSPOT_V1])
def test_mesh_vertices_only_at_inlet_and_outlet_so_the_taper_is_linear(family):
    """v2 pre-read condition 2: blockMesh interpolates linearly between x = 0 and x = L vertices, so moving the x = L ones is an
    exactly linear wall only if no vertex lies between them, in every mesh family the probe uses.
    """
    texts, _ = taper.files(_case(0.6), mesh_family=family)
    xs = {v[0] for v in _vertices(texts["system/blockMeshDict"])}
    assert xs == {0.0, domain.FIXED["footprint_mm"]}


def test_files_swaps_no_module_global():
    """v2 pre-read condition 1: taper.files never rebinds openfoam.block_mesh (safe for concurrent callers)."""
    before = openfoam.block_mesh
    seen = []

    def spy(*a, **k):
        seen.append(
            openfoam.block_mesh is spy
        )  # still OUR binding while taper.files runs: nobody swapped it again
        return before(*a, **k)

    openfoam.block_mesh = spy
    try:
        taper.files(_case(0.7))
        after = openfoam.block_mesh
    finally:
        openfoam.block_mesh = before
    assert seen and all(seen)
    assert after is spy  # and taper.files left the module binding as it found it
