"""The divergence report splits conditions by who diverges, prospectively.

Claims: every condition the frozen count saw is classed exactly once (the
classed totals equal each study's committed counts); pairs are classed by
family; a condition takes its worst pair; and the report changes no frozen
outcome.
"""

import json
from pathlib import Path

from carbon.battery.value import divergence as d
from carbon.battery.value import real_divergence as rd

REPOSITORY = Path(__file__).resolve().parents[2]
EVIDENCE = REPOSITORY / "docs/development/evidence"


def test_classed_totals_equal_each_studys_committed_count():
    report = rd.report(REPOSITORY)
    ev4 = report["datasets"]["ev4-2026-10-01"]["rules"]
    for study in ("sr2", "sr3"):
        committed = json.loads((EVIDENCE / rd.CANDIDATES[study]).read_text())["rows"]
        for rule in (d.DECIDING_RULE, report["candidates"][study]["rule"]):
            for split in d.SPLITS:
                assert (
                    sum(ev4[rule]["counts"][split].values())
                    == committed[rule]["divergence"][split]
                ), (study, rule, split)
    sr1 = json.loads((EVIDENCE / rd.CANDIDATES["sr1"]).read_text())
    rule = report["candidates"]["sr1"]["rule"]
    for split in d.SPLITS:
        assert (
            sum(ev4[rule]["counts"][split].values())
            == sr1["ev4"][rule]["divergence"][split]
        )
    assert report["claims"]["frozen_outcomes_changed"] is False


def test_the_deciding_rules_seven_ev4_verification_conditions_split_as_reported():
    """The SR-EV4 README's reading: 2 controls, 4 within-family (3 kNN and
    one MLP), and 1 across families (a DeepONet above 25%-TRAIN MLPs)."""
    rules = rd.report(REPOSITORY)["datasets"]["ev4-2026-10-01"]["rules"]
    counts = rules[d.DECIDING_RULE]["counts"]["verification"]
    assert counts == {"across_families": 1, "within_family": 4, "control": 2}


def _toy():
    names = {
        "control-optimist": ("SYNTHETIC_CONTROL", 0.9, 5.0),
        "mlp_a-s0": ("RECONSTRUCTED", 0.8, 3.0),
        "mlp_b-s0": ("RECONSTRUCTED", 0.5, 1.0),
        "knn-s0": ("RECONSTRUCTED", 0.7, 2.0),
        "deeponet-s0": ("RECONSTRUCTED", 0.6, 0.5),
    }
    members = {
        m: {
            "kind": k,
            "eligible": True,
            "loss_development": loss,
            "loss_verification": loss,
        }
        for m, (k, _, loss) in names.items()
    }
    return {
        "schema": "carbon.engineering-value-results.v1",
        "summary": {"members": members},
        "rule_scores": {m: {d.DECIDING_RULE: s} for m, (_, s, _) in names.items()},
        "seed_variation": {},
    }


def test_pairs_are_classed_by_family_and_a_condition_by_its_worst_pair():
    out = rd.classified(_toy(), d.DECIDING_RULE)
    rows = {r["member"]: r for r in out["conditions"] if r["split"] == "verification"}
    assert rows["control-optimist"]["class"] == "control"
    # mlp_a outranks a better MLP (within) and a better kNN/DeepONet (across).
    assert rows["mlp_a-s0"]["class"] == "across_families"
    assert rows["mlp_a-s0"]["pairs"]["within_family"] == ["mlp_b-s0"]
    assert set(rows["mlp_a-s0"]["pairs"]["across_families"]) == {
        "knn-s0",
        "deeponet-s0",
    }
    assert out["counts"]["verification"] == {
        "across_families": 2,  # mlp_a, and kNN above both better ones
        "within_family": 0,
        "control": 1,
    }
    # Specimen: the best decider never diverges.
    assert "deeponet-s0" not in rows


def test_family_is_the_leading_word_and_controls_are_their_own_class():
    assert rd.family("mlp_t3000_w256_d3_arr_pca16-s0", "RECONSTRUCTED") == "mlp"
    assert rd.family("knn40-s0", "RECONSTRUCTED") == "knn"
    assert rd.family("deeponet_t1500_w512_d3-s0", "RECONSTRUCTED") == "deeponet"
    assert rd.family("control-oracle", "SYNTHETIC_CONTROL") == "control"
