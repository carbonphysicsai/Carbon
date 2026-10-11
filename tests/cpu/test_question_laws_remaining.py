"""Static laws/generator parity, not reference adequacy or power evidence."""

import hashlib
import json
import re
from pathlib import Path

from carbon.challenge_pipeline.onboarding import law, packet

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs/development/challenge_pipeline/question-laws/remaining"
DATA = json.loads((DIR / "laws.json").read_text(encoding="utf-8"))


def test_exact_merged_generator_output_is_retained():
    saved = json.loads((DIR / "generator-output.json").read_text(encoding="utf-8"))
    for family in ("f13", "f17"):
        brief = packet.read_json(DIR / f"{family}-brief.json")
        generated = law.generate(packet.generate(brief, ROOT))
        assert generated == saved[family]
        assert generated["diversity"] is None
        assert generated["panel_basis"] is None


def test_laws_are_unregistered_no_runs_and_two_sided_two_bands():
    assert DATA["maturity"] == "SPECIFIED" and DATA["registered"] is None
    assert not DATA["runtime_adoption"]
    assert DATA["solver_runs"] == DATA["spend"] == 0
    near = DATA["two_band_rule"]
    assert near["near_refinement_bands"] == 2
    assert near["minimum_distinct_feasible"] == near["minimum_distinct_infeasible"] == 5
    assert near["both_sides_near"] and near["band_widths_registered"] is None
    assert "NO_REDRAW" in DATA["none_feasible"]
    assert not DATA["exposure"]["threshold_variation_renews_E"]
    assert all(DATA["exposure"][key] is None for key in ("B", "n", "E"))
    for family in DATA["families"]:
        for key in ("P", "Q", "w", "action_set", "k"):
            assert family[key]["registered"] is None
            assert family[key]["status"] == "HUMAN_INPUT"
        assert family["diversity"]["expected_distinct_winners_P"] is None
        assert family["diversity"]["expected_distinct_winners_Q"] is None


def test_primary_intervals_do_not_relax_packet_anchors():
    for family in DATA["families"]:
        assert (
            hashlib.sha256((ROOT / family["packet"]).read_bytes()).hexdigest()
            == family["packet_sha256"]
        )
        for axis in family["axes"]:
            low, high = axis["primary_continuous"]
            assert low <= high and axis["registered"] is None
            if axis["op"] == ">=":
                assert low >= axis["packet_anchor"]
            else:
                assert high <= axis["packet_anchor"]
            assert len(axis["audit_grid"]) == 3


def test_physical_work_not_questions_or_launches_as_truth_units():
    f13, f17 = DATA["families"]
    assert f13["cost"]["legacy_separate_frequency_launches"] == 16 * 201
    assert f17["cost"]["legacy_geometry_condition_pairs"] == 45 * 9
    assert f17["cost"]["legacy_no_reuse_process_launches"] == 45 * 9 * 2
    assert (
        f17["cost"]["conditional_flow_reuse_launches_before_controls"]
        == 45 * 3 + 45 * 9
    )
    assert all(f["cost"]["startup_eur"] is None for f in DATA["families"])
    assert f13["cost"]["single_process_per_curve_is_not_free_frequency_work"]
    assert f17["cost"]["reuse_is_not_earned"]


def test_local_document_links_resolve():
    for path in DIR.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" not in target:
                assert (path.parent / target.split("#")[0]).is_file(), (path, target)
