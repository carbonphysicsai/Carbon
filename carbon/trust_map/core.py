"""Challenge-neutral, disclosed-case error and disagreement aggregates.

The input is an explicit public/released projection, never a validator record.
Source/release and reference verification evidence are supplied by the operator;
this offline reader validates their shape and binding, not their authenticity.
Nothing here draws, selects, ranks, scores or qualifies a case or model.
"""

from __future__ import annotations

import bisect
import copy
import hashlib
import json
import math
import re
from html import escape
from itertools import pairwise

from carbon.trust_map.acceptance import AcceptanceRefused, load_acceptance

PANEL_SCHEMA = "carbon.trust-map.disclosed-panel.v2"
MAP_SCHEMA = "carbon.trust-map.v2"


class MapRefused(ValueError):
    """An undisclosed, unverified or malformed panel cannot produce a map."""


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise MapRefused("finite_number_required")
    return float(value)


def _vector(value, length):
    values = value if isinstance(value, list) else [value]
    if len(values) != length:
        raise MapRefused("output_shape_mismatch")
    return [_number(v) for v in values]


def _edges(values):
    if not isinstance(values, list) or len(values) < 2:
        raise MapRefused("axis_edges_required")
    values = [_number(v) for v in values]
    if any(a >= b for a, b in pairwise(values)):
        raise MapRefused("axis_edges_not_increasing")
    return values


def _bin(value, edges):
    value = _number(value)
    if not edges[0] <= value <= edges[-1]:
        raise MapRefused("input_outside_map")
    return min(bisect.bisect_right(edges, value) - 1, len(edges) - 2)


def _quantile(values, probability):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * probability
    left = math.floor(position)
    right = math.ceil(position)
    return values[left] + (values[right] - values[left]) * (position - left)


def _summary(values):
    return {"median": _quantile(values, 0.5), "p90": _quantile(values, 0.9)}


def _rms(values):
    return _number(math.hypot(*values) / math.sqrt(len(values)))


def build_maps(panel, spec):
    """One aggregate-only map per model on the same disclosed cases.

    Error is per-case RMS error in each output's native units. Disagreement
    is RMS population standard deviation of the explicitly named top models
    at each output coordinate, then median/p90 over cases in each cell.
    Marginalization is empirical pooling, not population weighting.
    """
    if (
        type(panel) is not dict
        or set(panel)
        != {
            "schema",
            "disclosure",
            "reference_image",
            "reference_verification",
            "cases",
            "models",
            "top_models",
        }
        or panel["schema"] != PANEL_SCHEMA
    ):
        raise MapRefused("disclosed_panel_schema_required")
    disclosure = panel["disclosure"]
    if (
        type(disclosure) is not dict
        or set(disclosure) != {"kind", "evidence", "source_sha256"}
        or disclosure["kind"] not in ("PUBLIC", "RELEASED")
    ):
        raise MapRefused("public_or_released_only")
    if (
        not isinstance(disclosure["evidence"], str)
        or not disclosure["evidence"].strip()
    ):
        raise MapRefused("disclosure_evidence_required")
    source_digest = disclosure["source_sha256"]
    if (
        not isinstance(source_digest, str)
        or len(source_digest) != 64
        or any(c not in "0123456789abcdef" for c in source_digest)
    ):
        raise MapRefused("source_digest_required")
    verification = panel["reference_verification"]
    if not isinstance(panel["reference_image"], str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", panel["reference_image"]
    ):
        raise MapRefused("reference_image_digest_required")
    if not isinstance(verification, dict) or set(verification) != {
        "family",
        "criteria_digest",
        "image_digest",
        "evidence",
    }:
        raise MapRefused("reference_verification_unavailable")
    if verification["image_digest"] != panel["reference_image"] or not (
        isinstance(verification["evidence"], str) and verification["evidence"].strip()
    ):
        raise MapRefused("reference_verification_binding")
    try:
        acceptance = load_acceptance(
            verification["family"],
            panel["reference_image"],
            verification["criteria_digest"],
        )
    except AcceptanceRefused as error:
        raise MapRefused("reference_verification_" + str(error)) from error

    spec = copy.deepcopy(spec)
    if set(spec) != {"axes", "bands", "marginalized", "outputs", "near_limit"}:
        raise MapRefused("map_spec_schema")
    if len(spec["axes"]) != 2:
        raise MapRefused("two_axes_required")
    axes = spec["axes"] + [spec["bands"]]
    for axis in axes:
        if set(axis) != {"name", "edges"} or not isinstance(axis["name"], str):
            raise MapRefused("axis_schema")
        axis["edges"] = _edges(axis["edges"])
    names = [a["name"] for a in axes] + spec["marginalized"]
    if len(set(names)) != len(names):
        raise MapRefused("duplicate_axis")
    outputs = spec["outputs"]
    if not isinstance(outputs, dict) or not outputs:
        raise MapRefused("outputs_required")
    for description in outputs.values():
        if (
            set(description) != {"length", "unit"}
            or type(description["length"]) is not int
            or description["length"] < 1
            or not isinstance(description["unit"], str)
            or not description["unit"]
        ):
            raise MapRefused("output_description")
    near = spec["near_limit"]
    if not isinstance(near, list) or not near:
        raise MapRefused("near_limit_required")
    for condition in near:
        if (
            set(condition) != {"output", "statistic", "operator", "value"}
            or condition["output"] not in outputs
            or condition["statistic"] not in ("max", "abs_min")
            or condition["operator"] not in ("le", "ge")
        ):
            raise MapRefused("near_limit_condition")
        _number(condition["value"])

    cases, models, top = panel["cases"], panel["models"], panel["top_models"]
    if (
        not isinstance(cases, list)
        or not cases
        or not isinstance(models, dict)
        or not models
    ):
        raise MapRefused("cases_and_models_required")
    if (
        not isinstance(top, list)
        or len(top) < 2
        or len(set(top)) != len(top)
        or not set(top) <= set(models)
    ):
        raise MapRefused("two_distinct_top_models_required")
    ids = [c.get("id") for c in cases]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise MapRefused("unique_case_ids_required")
    for name, predictions in models.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(predictions, dict)
            or set(predictions) != set(ids)
        ):
            raise MapRefused("model_case_alignment")
    nx, ny, nb = [len(a["edges"]) - 1 for a in axes]
    groups = {(b, y, x): [] for b in range(nb) for y in range(ny) for x in range(nx)}
    for case in cases:
        if (
            set(case) != {"id", "inputs", "reference"}
            or set(case["inputs"]) != set(names)
            or set(case["reference"]) != set(outputs)
        ):
            raise MapRefused("case_projection_schema")
        for value in case["inputs"].values():
            _number(value)
        x, y, b = [_bin(case["inputs"][a["name"]], a["edges"]) for a in axes]
        refs = {
            k: _vector(case["reference"][k], v["length"]) for k, v in outputs.items()
        }
        predictions = {}
        for name in models:
            raw = models[name][case["id"]]
            if type(raw) is not dict or set(raw) != set(outputs):
                raise MapRefused("prediction_output_schema")
            predictions[name] = {
                k: _vector(raw[k], v["length"]) for k, v in outputs.items()
            }
        important = False
        for condition in near:
            values = refs[condition["output"]]
            statistic = (
                max(values)
                if condition["statistic"] == "max"
                else min(abs(v) for v in values)
            )
            important |= (
                statistic <= condition["value"]
                if condition["operator"] == "le"
                else statistic >= condition["value"]
            )
        spread = {}
        for output, desc in outputs.items():
            deviations = []
            for i in range(desc["length"]):
                values = [predictions[m][output][i] for m in top]
                mean = math.fsum(v / len(values) for v in values)
                deviations.append(_rms([v - mean for v in values]))
            spread[output] = _rms(deviations)
        errors = {
            m: {
                k: _rms([a - r for a, r in zip(predictions[m][k], refs[k])])
                for k in outputs
            }
            for m in models
        }
        groups[b, y, x].append((important, spread, errors))
    result = {}
    verification = acceptance
    for model in models:
        cells = []
        for (b, y, x), rows in groups.items():
            cells.append(
                {
                    "band": b,
                    "y": y,
                    "x": x,
                    "count": len(rows),
                    "status": "OBSERVED" if rows else "NO_DATA",
                    "near_limit_count": sum(r[0] for r in rows),
                    "error": {
                        k: _summary([r[2][model][k] for r in rows]) for k in outputs
                    },
                    "disagreement": {
                        k: _summary([r[1][k] for r in rows]) for k in outputs
                    },
                }
            )
        result[model] = {
            "schema": MAP_SCHEMA,
            "maturity": "DEVELOPMENT",
            "model": model,
            "spec": spec,
            "top_models": list(top),
            "source": copy.deepcopy(disclosure),
            "reference_verification": verification,
            "cells": cells,
            "basis": {
                "cases": len(cases),
                "models": len(models),
                "top_models": len(top),
            },
            "methods": {
                "error": "per-case RMS in native units; cell median and linear p90",
                "disagreement": "RMS population standard deviation across named top models; cell median and linear p90",
                "marginalization": "empirical pooling of all disclosed cases; no population weights",
            },
            "scored_case_selection": "FORBIDDEN",
        }
    return result


def render_svg(document):
    """One SVG per model, all outputs/layers and all input bands."""
    spec = document["spec"]
    nx, ny = [len(a["edges"]) - 1 for a in spec["axes"]]
    nb = len(spec["bands"]["edges"]) - 1
    cell = 28
    pw, ph = nx * cell + 80, ny * cell + 125
    layers = [("error", "median"), ("error", "p90"), ("disagreement", "median")]
    outputs = list(spec["outputs"])
    width, height = nb * pw + 30, len(outputs) * len(layers) * ph + 95
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<title>{escape(document["model"])} DEVELOPMENT trust map</title>',
        '<g font-family="sans-serif" font-size="11" fill="#17212b">',
        f'<text x="15" y="22">{escape(document["model"])} | DEVELOPMENT | {document["basis"]["cases"]} disclosed cases</text>',
        '<text x="15" y="42">Gray = no data. Orange outline = observed near-limit reference cells.</text>',
        f'<text x="15" y="58">Empirically pooled axes: {escape(", ".join(spec["marginalized"]))}</text>',
    ]
    for oi, output in enumerate(outputs):
        for li, (layer, statistic) in enumerate(layers):
            row = oi * len(layers) + li
            values = [
                c[layer][output][statistic] for c in document["cells"] if c["count"]
            ]
            vmax = max(values, default=0)
            unit = spec["outputs"][output]["unit"]
            heading = f"{output}: {layer} {statistic} ({unit})"
            svg.append(f'<text x="15" y="{85 + row * ph}">{escape(heading)}</text>')
            for band in range(nb):
                ox, oy = 45 + band * pw, 120 + row * ph
                low, high = spec["bands"]["edges"][band : band + 2]
                label = f'{spec["bands"]["name"]} {low:g}-{high:g}'
                svg.append(f'<text x="{ox - 30}" y="{oy - 12}">{escape(label)}</text>')
                for c in document["cells"]:
                    if c["band"] != band:
                        continue
                    value = c[layer][output][statistic]
                    intensity = 0 if not vmax or value is None else value / vmax
                    color = (
                        "#e6e8eb"
                        if value is None
                        else f"rgb({int(235 - 200 * intensity)},{int(245 - 125 * intensity)},245)"
                    )
                    px, py = ox + c["x"] * cell, oy + (ny - 1 - c["y"]) * cell
                    stroke = "#d97706" if c["near_limit_count"] else "white"
                    title = f'n={c["count"]}; near limit={c["near_limit_count"]}; {layer}={value}; {unit}'
                    svg.append(
                        f'<rect x="{px}" y="{py}" width="{cell}" height="{cell}" fill="{color}" stroke="{stroke}" stroke-width="2"><title>{escape(title)}</title></rect>'
                    )
                xedge, yedge = [a["edges"] for a in spec["axes"]]
                svg.extend(
                    [
                        f'<text x="{ox}" y="{oy + ny * cell + 18}">{escape(spec["axes"][0]["name"])} {xedge[0]:g} to {xedge[-1]:g}</text>',
                        f'<text x="{ox}" y="{oy + ny * cell + 34}">{escape(spec["axes"][1]["name"])} {yedge[0]:g} to {yedge[-1]:g} (up)</text>',
                        f'<text x="{ox}" y="{oy + ny * cell + 50}">color range 0 to {vmax:.4g} {escape(unit)}</text>',
                    ]
                )
    svg.append("</g></svg>")
    return "\n".join(svg) + "\n"


def write_maps(maps, directory):
    """Deterministic safe filenames; no model label can escape the output folder."""
    from pathlib import Path

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, document in sorted(maps.items()):
        stem = "model-" + hashlib.sha256(name.encode()).hexdigest()[:16]
        target = directory / (stem + ".json")
        target.write_text(
            json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        (directory / (stem + ".svg")).write_text(render_svg(document), encoding="utf-8")
        paths.append(str(target))
    return paths
