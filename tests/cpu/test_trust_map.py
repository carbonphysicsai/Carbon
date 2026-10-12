"""Synthetic public projections only; never scientific evidence or LIVE inputs."""

from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET

import pytest

from carbon.trust_map.core import (
    PANEL_SCHEMA,
    MapRefused,
    build_maps,
    render_svg,
    write_maps,
)


def fixture():
    spec = {
        "axes": [
            {"name": "c1", "edges": [0, 1, 2]},
            {"name": "ambient", "edges": [0, 10, 20]},
        ],
        "bands": {"name": "soc0", "edges": [0, 0.3, 0.6, 1]},
        "marginalized": ["c2"],
        "outputs": {"temperature": {"length": 2, "unit": "C"}},
        "near_limit": [
            {"output": "temperature", "statistic": "max", "operator": "ge", "value": 55}
        ],
    }
    cases = [
        {
            "id": "first",
            "inputs": {"c1": 0, "ambient": 0, "soc0": 0, "c2": 0.2},
            "reference": {"temperature": [55, 55]},
        },
        {
            "id": "second",
            "inputs": {"c1": 0.5, "ambient": 1, "soc0": 0.1, "c2": 0.9},
            "reference": {"temperature": [55, 55]},
        },
        {
            "id": "last",
            "inputs": {"c1": 2, "ambient": 20, "soc0": 1, "c2": 0.4},
            "reference": {"temperature": [55, 55]},
        },
    ]
    panel = {
        "schema": PANEL_SCHEMA,
        "disclosure": {
            "kind": "PUBLIC",
            "evidence": "synthetic public fixture only",
            "source_sha256": "a" * 64,
        },
        "reference_image": "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940",
        "reference_verification": {
            "family": "battery-v3",
            "criteria_digest": "sha256:2182e04bce3612f898e00184ce1e491cca8a54334192e35c4f2cd6fc1d1870c5",
            "image_digest": "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940",
            "evidence": "synthetic fixture; not real reference acceptance",
        },
        "cases": cases,
        "models": {
            "a": {c["id"]: {"temperature": [56, 56]} for c in cases},
            "b": {c["id"]: {"temperature": [58, 58]} for c in cases},
        },
        "top_models": ["a", "b"],
    }
    return panel, spec


def test_known_errors_disagreement_pooling_and_boundary_bins():
    panel, spec = fixture()
    before = copy.deepcopy(panel)
    maps = build_maps(panel, spec)
    assert panel == before
    cells = maps["a"]["cells"]
    assert len(cells) == 12
    assert cells[0]["count"] == 2  # c2 is pooled, never filtered or weighted.
    assert cells[0]["error"]["temperature"] == {"median": 1, "p90": 1}
    assert cells[0]["disagreement"]["temperature"] == {"median": 1, "p90": 1}
    assert maps["b"]["cells"][0]["error"]["temperature"]["median"] == pytest.approx(3)
    assert cells[-1]["count"] == 1  # the upper bounds belong to the final bin.
    assert cells[1]["status"] == "NO_DATA"
    assert cells[1]["error"]["temperature"]["median"] is None
    assert maps["a"]["scored_case_selection"] == "FORBIDDEN"
    serialized = json.dumps(maps)
    assert '"id"' not in serialized and '"reference"' not in serialized


def test_quantiles_and_released_cases():
    panel, spec = fixture()
    panel["disclosure"]["kind"] = "RELEASED"
    panel["models"]["a"]["second"]["temperature"] = [59, 59]
    error = build_maps(panel, spec)["a"]["cells"][0]["error"]["temperature"]
    assert error["median"] == 2.5
    assert error["p90"] == pytest.approx(3.7)


def test_missing_acceptance_link_refuses_maps(tmp_path, monkeypatch):
    from functools import partial

    from carbon.trust_map.acceptance import load_acceptance

    monkeypatch.setattr(
        "carbon.trust_map.core.load_acceptance", partial(load_acceptance, root=tmp_path)
    )
    panel, spec = fixture()
    with pytest.raises(MapRefused, match="acceptance_link_unavailable"):
        build_maps(panel, spec)


def test_wrong_criteria_and_repinned_image_refuse_maps():
    panel, spec = fixture()
    panel["reference_verification"]["criteria_digest"] = "sha256:" + "c" * 64
    with pytest.raises(MapRefused, match="acceptance_criteria_mismatch"):
        build_maps(panel, spec)
    panel, spec = fixture()
    panel["reference_image"] = "sha256:" + "c" * 64
    panel["reference_verification"]["image_digest"] = panel["reference_image"]
    with pytest.raises(MapRefused, match="acceptance_image_mismatch"):
        build_maps(panel, spec)


def test_battery_adapter_and_cli_emit_json_and_svg(tmp_path, capsys):
    from carbon.battery.trust_map import battery_spec, main

    panel, _spec = fixture()
    spec = battery_spec()
    outputs = {
        k: ([1.0] * d["length"] if d["length"] > 1 else 0.0)
        for k, d in spec["outputs"].items()
    }
    panel["cases"] = [
        {
            "id": "public-fixture",
            "inputs": {"c1": 2.0, "c2": 1.0, "t_amb_c": 40.0, "soc0": 0.5},
            "reference": outputs,
        }
    ]
    panel["models"] = {name: {"public-fixture": outputs} for name in ("a", "b")}
    source = tmp_path / "panel.json"
    source.write_text(json.dumps(panel), encoding="utf-8")
    target = tmp_path / "maps"
    assert main(["--panel", str(source), "--out", str(target)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["maturity"] == "DEVELOPMENT" and len(summary["maps"]) == 2
    result = json.loads(next(target.glob("*.json")).read_text())
    assert len(result["cells"]) == 126
    assert result["cells"][-1]["count"] == 1
    assert result["cells"][-1]["near_limit_count"] == 1
    assert [a["name"] for a in result["spec"]["axes"]] == ["c1", "t_amb_c"]
    assert result["spec"]["marginalized"] == ["c2"]
    assert len(result["spec"]["bands"]["edges"]) == 4
    from carbon.battery.trust_map import build_battery_maps

    panel["cases"][0]["inputs"]["c2"] = 1.1
    with pytest.raises(MapRefused, match="c2_outside_public_bounds"):
        build_battery_maps(panel)


@pytest.mark.parametrize("kind", ["HIDDEN", "SEALED", "PRIVATE", "TRAIN", None])
def test_undisclosed_material_is_refused(kind):
    panel, spec = fixture()
    panel["disclosure"]["kind"] = kind
    with pytest.raises(MapRefused, match="public_or_released_only"):
        build_maps(panel, spec)


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "HUMAN_INPUT"),
        ("accepted_development_pass", False),
        ("image_digest", "another-image"),
    ],
)
def test_unaccepted_or_wrong_reference_is_refused(field, value):
    panel, spec = fixture()
    panel["reference_verification"][field] = value
    with pytest.raises(MapRefused, match="reference_verification"):
        build_maps(panel, spec)


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "nan", "shape", "outside", "metadata", "one_top"],
)
def test_malformed_or_incomplete_evidence_is_not_a_pass(mutation):
    panel, spec = fixture()
    if mutation == "missing":
        del panel["models"]["a"]["first"]
    elif mutation == "duplicate":
        panel["cases"][1]["id"] = "first"
    elif mutation == "nan":
        panel["models"]["a"]["first"]["temperature"][0] = float("nan")
    elif mutation == "shape":
        panel["models"]["a"]["first"]["temperature"] = [1]
    elif mutation == "outside":
        panel["cases"][0]["inputs"]["c1"] = -1
    elif mutation == "metadata":
        panel["cases"][0]["seed"] = "forbidden"
    else:
        panel["top_models"] = ["a"]
    with pytest.raises(MapRefused):
        build_maps(panel, spec)


def test_svg_layers_near_limit_outlines_escape_and_safe_filenames(tmp_path):
    panel, spec = fixture()
    panel["models"]["../../a<script>"] = panel["models"].pop("a")
    panel["top_models"][0] = "../../a<script>"
    maps = build_maps(panel, spec)
    svg = render_svg(maps["../../a<script>"])
    ET.fromstring(svg)
    assert "&lt;script&gt;" in svg and "<script>" not in svg
    assert 'stroke="#d97706"' in svg
    assert "error median" in svg and "error p90" in svg and "disagreement" in svg
    assert "color range" in svg
    paths = write_maps(maps, tmp_path)
    assert len(paths) == 2 and len(list(tmp_path.glob("*.svg"))) == 2
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    write_maps(maps, tmp_path)
    assert first == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
