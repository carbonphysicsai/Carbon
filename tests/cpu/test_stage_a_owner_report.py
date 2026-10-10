"""Synthetic-only stage-end owner summary inputs."""

import hashlib
import json

import pytest

from scripts.dev.battery import stage_a_owner_report as owner


def _sha(letter):
    return "sha256:" + letter * 64


def _inputs(tmp_path):
    refusals = {
        "schema": owner.REFUSALS_SCHEMA,
        "scope": owner.SCOPE,
        "source_sha256": _sha("a"),
        "complete": True,
        "levels_covered": [0, 1, 2],
        "records": [
            {
                "capability_id": "method.neural",
                "level": 2,
                "refusal_code": "not_rebuildable",
            },
            {
                "capability_id": "method.neural",
                "level": 2,
                "refusal_code": "not_rebuildable",
            },
            {
                "capability_id": "data.pool",
                "level": 1,
                "refusal_code": "not_registered",
            },
        ],
    }
    grant_id = "GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR"
    grant_body = (owner.GRANTS / (grant_id + ".json")).read_bytes()
    spend = {
        "schema": owner.SPEND_SCHEMA,
        "scope": owner.SCOPE,
        "grants": [
            {
                "grant_id": grant_id,
                "grant_sha256": "sha256:" + hashlib.sha256(grant_body).hexdigest(),
                "observed_spend_usd": "12.00",
                "source_sha256": _sha("b"),
                "state": "SETTLED",
            }
        ],
    }
    rpath = tmp_path / "refusals.json"
    spath = tmp_path / "spend.json"
    rpath.write_text(json.dumps(refusals), encoding="utf-8")
    spath.write_text(json.dumps(spend), encoding="utf-8")
    return rpath, spath, refusals, spend


def _alignment():
    metrics = {"tau_b": 0.3, "rho": 0.4}
    band = {"tau_b": {"low": 0.1, "high": 0.5, "defined_draws": 9}}
    return {
        "input_sha256": _sha("c"),
        "cohorts": [
            {
                "cohort": {"level": 1, "pool_version": 1, "device_class": "toy-cpu"},
                "planned_members": 3,
                "status": "MEASURED",
                "v2": {
                    "alignment": metrics,
                    "divergent_members": ["toy"],
                    "bootstrap_95_descriptive": band,
                },
                "v3": {
                    "alignment": {"tau_b": 0.8, "rho": 0.9},
                    "term_alignment": {
                        "accuracy_a": metrics,
                        "q3_q": metrics,
                        "g_feas_lower_better": {"tau_b": None, "rho": None},
                    },
                    "divergent_members": [],
                    "bootstrap_95_descriptive": band,
                },
                "practice_vs_exam": {
                    "rank_association": metrics,
                    "rank_association_status": "COMPARABLE",
                    "per_recipe": [
                        {"mean_practice_score": 0.1, "mean_exam_score": 0.2}
                    ],
                },
                "unmeasured_members": [],
            }
        ],
    }


def test_report_uses_alignment_and_ranks_refusals(tmp_path, monkeypatch):
    rpath, spath, _, _ = _inputs(tmp_path)
    monkeypatch.setattr(
        owner.stage_a_alignment, "analyze", lambda *_args, **_kwargs: _alignment()
    )
    report = owner.build(
        tmp_path / "synthetic-alignment.json", rpath, spath, draws=10, seed=3
    )
    ranked = report["refusals"]["ranked_level5_investigation_candidates"]
    assert ranked[0] == {
        "capability_id": "method.neural",
        "level": 2,
        "refusal_code": "not_rebuildable",
        "count": 2,
    }
    assert report["spend"]["grants"][0]["cap_usd"] == "74.67"
    page = owner.render(report)
    assert "0.300/0.400" in page and "0.800/0.900" in page
    assert "12.00" in page and "method.neural" in page
    assert "No score-rule change or Level 5 approval" in page
    assert "practice median 0.100" in page and "exam median 0.200" in page
    assert "[0.100, 0.500]" in page


def test_unknown_refusal_fields_and_tampered_grant_refused(tmp_path):
    rpath, spath, refusals, spend = _inputs(tmp_path)
    refusals["records"][0]["recipe"] = "must-not-leak"
    rpath.write_text(json.dumps(refusals), encoding="utf-8")
    with pytest.raises(owner.Refused, match="refusal_record_shape"):
        owner._refusals(rpath)
    spend["grants"][0]["grant_sha256"] = _sha("0")
    spath.write_text(json.dumps(spend), encoding="utf-8")
    with pytest.raises(owner.Refused, match="grant_digest_mismatch"):
        owner._spend(spath)


def test_unresolved_spend_is_not_zero_and_overrun_is_reported(tmp_path):
    _, spath, _, spend = _inputs(tmp_path)
    row = spend["grants"][0]
    row.update(state="UNRESOLVED", observed_spend_usd=None)
    spath.write_text(json.dumps(spend), encoding="utf-8")
    assert owner._spend(spath)["grants"][0]["observed_spend_usd"] is None
    row.update(state="SETTLED", observed_spend_usd="80.00")
    spath.write_text(json.dumps(spend), encoding="utf-8")
    assert owner._spend(spath)["grants"][0]["over_cap"]
