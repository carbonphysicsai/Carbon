"""PRACTICE-SAFETY-01 B4: the committed practice decision set keeps its
distance from every EV condition and is reproduced by its committed rule."""

import json

from scripts.dev.battery import practice_decision_set as pds


def _committed():
    return json.loads((pds.ROOT / pds.EVIDENCE / "conditions.json").read_text())


def test_the_set_is_reproduced_by_the_committed_rule():
    assert pds.select()["conditions"] == _committed()["conditions"]


def test_every_condition_keeps_its_distance_and_stays_in_the_box():
    conditions = _committed()["conditions"]
    assert [c["kind"] for c in conditions].count("representative") == 4
    assert [c["kind"] for c in conditions].count("near_limit") == 2
    prior = pds.excluded()
    points = [(c["t_amb_c"], c["soc0"]) for c in conditions]
    for i, point in enumerate(points):
        assert pds.BOX["t_amb_c"][0] <= point[0] <= pds.BOX["t_amb_c"][1]
        assert pds.BOX["soc0"][0] <= point[1] <= pds.BOX["soc0"][1]
        assert not pds.refused(point, prior + points[:i] + points[i + 1 :])


def test_refusal_needs_both_distances():
    assert pds.refused((10.0, 0.20), [(11.0, 0.21)])
    assert not pds.refused((10.0, 0.20), [(13.0, 0.21)])
    assert not pds.refused((10.0, 0.20), [(11.0, 0.30)])


def test_the_jobs_are_each_condition_at_ev4_s_grid():
    jobs = pds.jobs(_committed())["jobs"]
    assert len(jobs) == 6 * 35 and len({j["case_id"] for j in jobs}) == 210


def _committed_v2():
    return json.loads((pds.ROOT / pds.EVIDENCE_V2 / "conditions.json").read_text())


def test_v2_is_reproduced_and_clears_the_wider_list():
    """Test Lead ruling 2026-10-06: EV5's protected grids count as EV5."""
    document = _committed_v2()
    assert pds.select_v2()["conditions"] == document["conditions"]
    conditions = document["conditions"]
    assert [c["kind"] for c in conditions].count("representative") == 4
    assert [c["kind"] for c in conditions].count("near_limit") == 2
    prior = pds.excluded_v2()
    points = [(c["t_amb_c"], c["soc0"]) for c in conditions]
    for i, point in enumerate(points):
        assert not pds.refused(point, prior + points[:i] + points[i + 1 :])
    replaced = {c["replaces"] for c in conditions if "replaces" in c}
    assert replaced == {"P-T23.9-S0.244", "P-T34.4-S0.238"}
