"""Owner, 2026-10-25: "what the heck is with those high scores" (practice F02 1.296, Cooling
4.37, F08 0.460, Motor 0.187 on the example recipe). The number is a normalised ERROR on the
Challenge's registered scale (lower is better), not a grade; every miner-visible practice line
now says so, with what 0 and 1 mean.
"""

from __future__ import annotations

from pathlib import Path

from carbon.direct_campaign import practice as practice_module
from scripts.dev.miner_launchpad import campaign_view

ROOT = Path(__file__).resolve().parents[2]


def test_the_direct_practice_summary_states_what_its_score_is():
    meaning = practice_module.SCORE_MEANING
    assert "error" in meaning and "lower is better" in meaning
    assert "0 means the model matches the reference exactly" in meaning
    assert "1 means an error as large as that scale" in meaning
    assert "not an exam score" in meaning


def test_the_summary_carries_the_meaning_beside_the_number():
    import numpy as np
    from test_practice_summary_probe_rows import _rows

    from carbon.challenge_kit import physical_material
    from carbon.direct_campaign.spec import SPECS

    challenge, version = "f02", "2.4"
    material = {**physical_material.bundle_material(challenge, version), "version": version}
    spec = SPECS[challenge]
    out = practice_module.summary(
        spec, version, material["interface_document"], np.asarray(_rows(material, spec)), material
    )
    assert out["score_meaning"] == practice_module.SCORE_MEANING
    assert out["aggregate_error"] == out["score"]


def test_the_comparison_and_the_chart_call_it_an_error_not_a_score():
    row = {"index": 1, "score": 4.37, "components": {}}
    shown = campaign_view.comparison([row], None)
    labels = [item["label"] for item in shown["metrics"]]
    assert labels[0] == campaign_view.PRACTICE_ERROR_LABEL
    assert "lower is better" in labels[0] and "0 = exact" in labels[0]
    assert shown["direction"] == "lower_is_better"
    source = (ROOT / "scripts/dev/miner_launchpad/campaign_view.py").read_text("utf-8")
    assert '"Practice score' not in source and '"Practice error by run' in source


def test_the_page_never_shows_a_bare_practice_score_for_a_direct_practice():
    page = (ROOT / "scripts/dev/miner_launchpad/app.js").read_text("utf-8")
    assert 'researchNote(section, "Practice error: " + num(s.score)' in page
    assert "0 = exact, 1 = an error as large as the Challenge's registered scale" in page
    assert 'Descriptive practice score: " + num(s.score)' not in page
    assert "Practice errors, lower is better, 0 = exact" in page


def test_the_miner_guide_explains_the_number():
    text = (ROOT / "docs/MINING.md").read_text("utf-8")
    section = text.split("## 6. Practise, freeze, submit", 1)[1].split("\n## ", 1)[0]
    assert "What the practice number is" in section
    assert "0 means the model matches the reference exactly" in section
    assert "never an exam score" in section
