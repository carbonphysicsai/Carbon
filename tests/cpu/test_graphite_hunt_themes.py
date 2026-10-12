"""Hunt themes (GRAPHITE-L5-HUNT-01): opt-in advice that widens nothing and changes no old brief."""

from __future__ import annotations

import graphite_phase3_fixtures as p3f
import pytest

from carbon.agent_campaign.graphite import hunt_themes, phase3
from carbon.agent_campaign.graphite import tools as toolbox


def graphite_provider(tmp_path):
    return p3f.provider(tmp_path, [], p3f.ScriptedPods())


def brief(graphite, **kw):
    return phase3.session_brief(
        checkout_commit="1" * 40,
        budget=graphite.budget,
        literature=graphite.literature,
        **kw,
    )


def test_every_registered_theme_is_neutral_and_passes_the_protected_check():
    for theme_id, entry in hunt_themes.THEMES.items():
        for level in entry["levels"]:
            block = hunt_themes.theme_block(theme_id, level)
            assert not toolbox.protected({"hunt_theme": block}), theme_id
            assert block["schema"] == hunt_themes.THEME_SCHEMA
            assert "WISH" in block["report_requirement"]
            assert "advice only" in block["effect"]


def test_the_physics_themes_cover_the_levels_the_owner_named():
    assert hunt_themes.THEMES["physics-law-losses"]["levels"] == (1, 2)
    assert hunt_themes.THEMES["physics-structure"]["levels"] == (3, 4)
    assert "open" in hunt_themes.THEMES


def test_an_unknown_theme_or_a_level_it_does_not_name_is_refused():
    with pytest.raises(hunt_themes.UnknownTheme, match="unregistered"):
        hunt_themes.theme_block("nonsense", 1)
    with pytest.raises(hunt_themes.UnknownTheme, match="not_for_this_level"):
        hunt_themes.theme_block("physics-law-losses", 3)
    with pytest.raises(hunt_themes.UnknownTheme):
        hunt_themes.theme_block(None, 1)


def test_a_brief_without_a_theme_is_exactly_as_before(tmp_path):
    graphite = graphite_provider(tmp_path)
    plain = brief(graphite)
    assert "hunt_theme" not in plain.initial_observation
    assert brief(graphite, hunt_theme=None).initial_observation == (
        plain.initial_observation
    )


def test_a_themed_brief_adds_the_block_and_the_text_and_nothing_else(
    tmp_path, monkeypatch
):
    monkeypatch.setitem(
        hunt_themes.THEMES, "t0", {"levels": (0,), "text": "Theme: test."}
    )
    graphite = graphite_provider(tmp_path)
    plain = brief(graphite).initial_observation
    themed = brief(graphite, hunt_theme="t0").initial_observation
    assert themed["hunt_theme"]["id"] == "t0" and themed["hunt_theme"]["level"] == 0
    assert themed["instructions"].startswith(plain["instructions"])
    assert "Theme: test." in themed["instructions"]
    assert hunt_themes.REPORT_REQUIREMENT in themed["instructions"]
    rest = {k: v for k, v in themed.items() if k not in ("hunt_theme", "instructions")}
    assert rest == {k: v for k, v in plain.items() if k != "instructions"}


def test_a_theme_for_another_level_is_refused_when_the_brief_is_built(tmp_path):
    graphite = graphite_provider(tmp_path)
    with pytest.raises(hunt_themes.UnknownTheme):
        brief(graphite, hunt_theme="physics-law-losses")  # level 0


def test_the_run_command_takes_only_registered_themes():
    with pytest.raises(SystemExit):
        phase3.main(
            [
                "run",
                "--root",
                "/nonexistent",
                "--challenge",
                "battery-fastcharge-ageing-development-v1",
                "--theme",
                "bogus",
            ]
        )
