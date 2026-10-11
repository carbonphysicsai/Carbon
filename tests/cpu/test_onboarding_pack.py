"""The Carbon evidence pack is generated, deterministic and makes no business claim.

Pages are measurements read from ledgers. These tests keep them honest: output is
byte-identical on repeated runs, every line cites an artefact or reads UNMEASURED, the
equal-budget screen-then-verify section is always present, the banned claim words appear
only in the standing disclaimer, and no spend or hidden-pool material enters a page.
"""

import importlib.util
import re
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY / "scripts/dev/onboarding/build_pack.py"
PACK = REPOSITORY / "docs/development/challenge_pipeline/onboarding/pack"
CHALLENGES = (
    "battery-fastcharge-ageing-development-v1",
    "electric-motor-magnetics",
    "f02",
)
BANNED = ("traction", "customers", "qualified", "production-ready")


def _pack():
    spec = importlib.util.spec_from_file_location("onboarding_build_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _without_disclaimer(text):
    return "\n".join(
        line for line in text.splitlines() if not line.startswith("> DISCLAIMER:")
    )


def test_the_pack_is_deterministic_and_covers_the_first_three_challenges():
    module = _pack()
    first, second = module.build(CHALLENGES), module.build(CHALLENGES)
    assert first == second
    assert set(first) == {f"{c}.md" for c in CHALLENGES} | {
        "cross_challenge.md",
        "credibility.md",
    }


@pytest.mark.parametrize("which", ["generated", "committed"])
def test_every_line_cites_an_artefact_or_reads_unmeasured(which):
    pages = (
        _pack().build(CHALLENGES)
        if which == "generated"
        else {p.name: p.read_text(encoding="utf-8") for p in PACK.glob("*.md")}
    )
    assert pages
    for name, text in pages.items():
        for line in text.splitlines():
            if line.startswith("- "):
                assert "[source:" in line or "UNMEASURED" in line, (name, line)
        for source in re.findall(r"\[source: ([^\]]+)\]", text):
            if source.startswith("ledger "):
                continue
            assert (REPOSITORY / source).exists(), (name, source)


def test_the_required_equal_budget_section_is_on_every_challenge_page():
    for name, text in _pack().build(CHALLENGES).items():
        if name in {"cross_challenge.md", "credibility.md"}:
            continue
        assert "## Required: equal-budget screen-then-verify" in text, name
        assert "Models never beat the solver on accuracy" in text


def test_every_page_carries_the_disclaimer_and_no_banned_word_elsewhere():
    for name, text in _pack().build(CHALLENGES).items():
        assert text.count("> DISCLAIMER:") == 1, name
        body = _without_disclaimer(text).lower()
        for word in BANNED:
            assert word not in body, (name, word)
        assert " live " not in f" {body} ", name


def test_no_spend_figure_or_hidden_material_on_a_page():
    for name, text in _pack().build(CHALLENGES).items():
        body = _without_disclaimer(text)
        assert not re.search(r"\$\s?\d|USD\s?\d|\d\s?USD", body), name
        for word in ("draw_id", "sealed_batch", "hidden_pool", "api_key"):
            assert word not in body, (name, word)


def test_the_credibility_page_shows_three_layers_per_solver_without_inventing_results():
    page = _pack().build(CHALLENGES)["credibility.md"]
    for solver in ("PyBaMM", "GetDP", "Elmer"):
        assert f"### {solver}" in page
    assert page.count("Code verification (observed order matches theory)") == 3
    assert page.count("Solution verification (refinement, conservation)") == 3
    assert page.count("Validation (benchmarks)") == 3
    for line in page.splitlines():
        if line.startswith(("- Code verification", "- Solution", "- Validation")):
            assert "UNMEASURED" in line, line
