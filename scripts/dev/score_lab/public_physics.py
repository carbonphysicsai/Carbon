"""Read-only PLT-01 traits for an explicitly public development replay."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from . import public_ev4
from .core import LabRefused, analyze, validate_panel


def _read(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def load_traits(plt_readings, b9_measurements, *, expected_count=142):
    """Keep B15/B16 paired residuals and B9's separate public diagnostic distinct."""
    paired, paired_digest = _read(plt_readings)
    b9, b9_digest = _read(b9_measurements)
    if (
        paired.get("schema") != "carbon.physics-pair-readings.v2"
        or paired.get("scope") != "PUBLIC_DEVELOPMENT"
        or paired.get("complete") is not True
        or b9.get("schema") != "carbon.research.physics-consistency-public.v1"
        or b9.get("maturity") != "DEVELOPMENT_DESCRIPTIVE_NOT_QUALIFIED"
    ):
        raise LabRefused("physics_public_provenance")
    names = paired.get("public_members")
    if (
        not isinstance(names, list)
        or len(names) != expected_count
        or len(set(names)) != len(names)
    ):
        raise LabRefused("physics_public_member_count")
    readings = paired.get("readings") or {}
    b9_entries = b9.get("members", [])
    if not isinstance(b9_entries, list):
        raise LabRefused("physics_public_b9_reading")
    b9_rows = {row.get("member"): row for row in b9_entries}
    if len(b9_rows) != len(b9_entries):
        raise LabRefused("physics_public_b9_duplicate")
    if any(set(readings.get(key, {})) != set(names) for key in ("B15", "B16")):
        raise LabRefused("physics_public_paired_member_coverage")
    traits = {}
    for name in names:
        row = {}
        for key in ("B15", "B16"):
            values = (readings.get(key) or {}).get(name)
            if (
                not isinstance(values, list)
                or not values
                or any(
                    type(x) not in (int, float) or not math.isfinite(x) or x < 0
                    for x in values
                )
            ):
                raise LabRefused("physics_public_paired_reading")
            row[key.lower()] = max(values)
        match = b9_rows.get(name)
        value = (
            match.get("metrics", {}).get("case_maxima", {}).get("below_ambient")
            if match is not None
            else None
        )
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise LabRefused("physics_public_b9_reading")
        row["b9"] = value
        traits[name] = row
    return {
        "status": "PUBLIC_DEVELOPMENT_DIAGNOSTIC",
        "members": traits,
        "source_sha256": {"plt01": paired_digest, "b9": b9_digest},
        "definition": {
            "b15": "maximum paired residual in PLT-01 calibrated readings",
            "b16": "maximum paired residual in PLT-01 calibrated readings",
            "b9": "maximum below-ambient deficit in public physics-consistency measurement",
        },
    }


def apply_traits(panel, trait_record):
    validate_panel(panel)
    provenance = panel.get("provenance") or {}
    if (
        panel["scope"] != "PUBLIC_DEVELOPMENT"
        or panel.get("assumption", {}).get("job") != "battery-EV4-CV-onset-proxy"
        or provenance.get("reference_sha256") != public_ev4.PUBLIC_REFERENCE_SHA256
        or set(provenance.get("bundle_sha256", {}))
        != {m["id"] for m in panel["members"]}
    ):
        raise LabRefused("physics_public_panel_provenance")
    members = []
    missing = []
    for member in panel["members"]:
        name = member["id"]
        traits = trait_record["members"].get(name)
        if traits is None:
            missing.append(name)
        members.append(
            {
                **member,
                "score_metadata": {
                    **member.get("score_metadata", {}),
                    "physics": traits or {"b15": None, "b9": None, "b16": None},
                },
            }
        )
    return {**panel, "members": members}, missing


def replay(panel, trait_record, rule, switches, *, bootstrap, with_physics):
    """Exact registry scorer plus Validator's physics wrapper; no toy proxy."""
    source, missing = apply_traits(panel, trait_record)
    if missing:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "public_trait_member_mismatch",
            "count": len(missing),
        }
    rows = []
    for switch in switches:
        keys = set(switch["limit"]) | set(switch["weight"])
        if keys - {"b15", "b9", "b16"}:
            rows.append(
                {
                    "switch": switch,
                    "status": "INSUFFICIENT_EVIDENCE",
                    "reason": "real_trait_not_measured",
                }
            )
            continue

        def underlying(predictions, references, metadata):
            result = rule(predictions, references, metadata)
            if result is None:
                return {"score": None, "gate": "FAIL"}
            return {
                "score": result["score"],
                "gate": "PASS" if result["admissible"] else "FAIL",
            }

        wrapped = with_physics(underlying)

        def score(predictions, references, metadata, _wrapped=wrapped):
            result = _wrapped(predictions, references, metadata)
            if result["score"] is None:
                return None
            return {
                "score": result["score"],
                "admissible": result["gate"] != "FAIL",
                "tier": result.get("tier", 0),
            }

        score.rule_identity = {**rule.rule_identity, "physics_switch": switch}
        source["score_metadata"] = {
            **source.get("score_metadata", {}),
            "knobs": {"physics": switch},
        }
        result = analyze(source, score, bootstrap=bootstrap)
        rows.append(
            {
                "switch": switch,
                "status": result["status"],
                "tau": result.get("tau"),
                "tau_ci95": result.get("tau_ci95"),
                "reason": result.get("reason"),
                "good_member_gate": "HUMAN_INPUT; no real goodness cutoff selected",
            }
        )
    measured = sum(row["status"] == "MEASURED_DEVELOPMENT" for row in rows)
    return {
        "status": (
            "PUBLIC_DEVELOPMENT_DIAGNOSTIC" if measured else "INSUFFICIENT_EVIDENCE"
        ),
        "trait_members": len(trait_record["members"]),
        "replayed_members": len(source["members"]),
        "measured_switches": measured,
        "trait_sources_sha256": trait_record["source_sha256"],
        "rows": rows,
        "limitation": "retrospective EV4 value only; no shifted or extrapolated reference panel",
    }
