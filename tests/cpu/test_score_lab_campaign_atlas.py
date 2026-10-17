"""Synthetic atlas refuses incomplete or mixed shard evidence."""

import copy
import gzip
import json

import pytest

from scripts.dev.score_lab import campaign_atlas
from scripts.dev.score_lab.legacy_cli import main
from scripts.dev.score_lab.core import LabRefused


def _shard(index, tau):
    scopes = ("in_range", "shifted", "extrapolated", "neighbourhood_blend")
    return {
        "schema": campaign_atlas.SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "plan_sha256": "toy-plan",
        "candidates_sha256": "toy-candidates",
        "component_spec_sha256": None,
        "count": 2,
        "shard": index,
        "shards": 2,
        "rows": [
            {
                "index": index,
                "config_sha256": f"toy-{index}",
                "axes": {
                    "problem.space": "small-grid" if index == 0 else "continuous",
                    "neighbourhood.size": 0.1 + index * 0.1,
                },
                "rows": [
                    {
                        "candidate": "toy-rule",
                        "switch_index": 0,
                        "tau": {scope: tau for scope in scopes},
                        "top1_regret": {scope: 0.2 + index for scope in scopes},
                        "gamer_top_half": {scope: index == 1 for scope in scopes},
                        "good_wrongly_excluded": index,
                    }
                ],
            }
        ],
    }


def test_complete_shards_report_worst_case_without_selecting_a_rule():
    first, second = _shard(0, 0.8), _shard(1, -0.4)
    result = campaign_atlas.aggregate([second, first])
    assert result["profiles"] == 2
    assert result["selection"] is None
    assert result["sobol_indices"] is None
    row = result["candidate_switch_summaries"][0]
    assert row["scope_stats"]["neighbourhood_blend"]["median_tau"] == pytest.approx(0.2)
    assert row["scope_stats"]["neighbourhood_blend"]["worst_tenth_tau"] == -0.4
    assert row["gamer_top_half_profiles"] == 1
    assert row["good_wrongly_excluded_total"] == 1
    assert row["axis_associations"]["neighbourhood.size"][
        "high_minus_low"
    ] == pytest.approx(-1.2)
    assert row["axis_associations"]["problem.space"]["median_tau_by_value"] == {
        '"continuous"': -0.4,
        '"small-grid"': 0.8,
    }


def test_duplicate_missing_or_mixed_shards_refuse():
    first, second = _shard(0, 0.8), _shard(1, -0.4)
    with pytest.raises(LabRefused, match="atlas_duplicate_index"):
        campaign_atlas.aggregate([first, first])
    with pytest.raises(LabRefused, match="atlas_incomplete"):
        campaign_atlas.aggregate([first])
    mixed = copy.deepcopy(second)
    mixed["plan_sha256"] = "other-plan"
    with pytest.raises(LabRefused, match="atlas_identity"):
        campaign_atlas.aggregate([first, mixed])


def test_cli_accepts_gzip_synthetic_shards(tmp_path):
    paths = []
    for index, tau in ((0, 0.8), (1, -0.4)):
        path = tmp_path / f"shard-{index}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(_shard(index, tau), handle)
        paths.append(path)
    output = tmp_path / "atlas.json"
    assert (
        main(
            [
                "campaign-atlas",
                "--result",
                str(paths[0]),
                "--result",
                str(paths[1]),
                "--out",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["profiles"] == 2
