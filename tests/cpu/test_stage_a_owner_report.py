"""Synthetic-only stage-end owner summary inputs."""

import hashlib
import json

import pytest

from scripts.dev.battery import stage_a_owner_report as owner


def _sha(letter):
    return "sha256:" + letter * 64


def _inputs(tmp_path):
    refusals = [
        {
            "stage": "A",
            "level": 2,
            "role": "Constructor",
            "refusal_code": "not_rebuildable",
            "requested": "method.neural",
            "count": 2,
            "first_seen": "2026-10-10T12:00:00Z",
            "last_seen": "2026-10-10T12:10:00Z",
            "run_id": "toy-run-1",
        },
        {
            "stage": "A",
            "level": 1,
            "role": "Attacker",
            "refusal_code": "not_registered",
            "requested": "data.pool",
            "count": 1,
            "first_seen": "2026-10-10T12:00:00Z",
            "last_seen": "2026-10-10T12:00:00Z",
            "run_id": "toy-run-2",
        },
    ]
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
    rpath = tmp_path / "refused_capabilities.jsonl"
    spath = tmp_path / "spend.json"
    rpath.write_text(
        "\n".join(json.dumps(row) for row in refusals) + "\n", encoding="utf-8"
    )
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
    ranked = report["refusals"]["ranked_requested_investigations"]
    assert ranked[0] == {
        "requested": "method.neural",
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
    assert report["refusals"]["top_by_code"][0]["count"] == 2
    assert report["refusals"]["top_by_level"][0]["level"] == 2


def test_unknown_refusal_fields_and_tampered_grant_refused(tmp_path):
    rpath, spath, refusals, spend = _inputs(tmp_path)
    refusals[0]["recipe"] = "must-not-leak"
    rpath.write_text(
        "\n".join(json.dumps(row) for row in refusals) + "\n", encoding="utf-8"
    )
    with pytest.raises(owner.Refused, match="refusal_record_shape"):
        owner._refusals(rpath)
    spend["grants"][0]["grant_sha256"] = _sha("0")
    spath.write_text(json.dumps(spend), encoding="utf-8")
    with pytest.raises(owner.Refused, match="grant_digest_mismatch"):
        owner._spend(spath)


def test_duplicate_identity_and_bad_timestamp_refused(tmp_path):
    rpath, _, refusals, _ = _inputs(tmp_path)
    rpath.write_text(
        "\n".join(json.dumps(row) for row in refusals + [refusals[0]]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(owner.Refused, match="refusal_duplicate_identity"):
        owner._refusals(rpath)
    refusals[0]["first_seen"] = "2026-10-10T12:00:00-05:00"
    rpath.write_text(
        "\n".join(json.dumps(row) for row in refusals) + "\n", encoding="utf-8"
    )
    with pytest.raises(owner.Refused, match="refusal_timestamp_not_utc"):
        owner._refusals(rpath)


def test_unresolved_spend_is_not_zero_and_overrun_is_reported(tmp_path):
    _, spath, _, spend = _inputs(tmp_path)
    row = spend["grants"][0]
    row.update(state="UNRESOLVED", observed_spend_usd=None)
    spath.write_text(json.dumps(spend), encoding="utf-8")
    assert owner._spend(spath)["grants"][0]["observed_spend_usd"] is None
    row.update(state="SETTLED", observed_spend_usd="80.00")
    spath.write_text(json.dumps(spend), encoding="utf-8")
    assert owner._spend(spath)["grants"][0]["over_cap"]
