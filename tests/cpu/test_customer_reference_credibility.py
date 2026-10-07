"""Static buyer-target consistency, never solver agreement or qualification."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKETS = ROOT / "docs/development/challenge_pipeline/round1"
CASES = (
    ("motor-precision-joint.md", "Tier 2", "Ansys Maxwell", "Gmsh/GetDP", "N·m"),
    ("cooling-accelerator-manifold.md", "Tier 2", "Ansys Fluent", "OpenFOAM", "°C"),
    ("battery-ev-fast-charge.md", "Tier 3", "COMSOL", "PyBaMM", "mV"),
    ("f02-burst-thermal.md", "Tier 2", "Ansys Icepak", "Elmer", "°C"),
    ("f06-grating-coupler.md", "Tier 2", "Ansys Lumerical", "Meep", "nm"),
    ("f08-resonance-structure.md", "Tier 2", "Ansys Mechanical", "CalculiX", "Hz"),
    ("f13-compressor-silencer.md", "Tier 2", "COMSOL", "Elmer", "dB"),
    ("f17-passive-micromixer.md", "Tier 2", "COMSOL", "OpenFOAM", "M difference"),
)
PRIMARY_DOMAINS = {
    "www.ansys.com",
    "ansyshelp.ansys.com",
    "optics.ansys.com",
    "doc.comsol.com",
    "www.nafems.org",
    "zenodo.org",
}


def normalized(text: str) -> str:
    return " ".join(text.replace("**", "").split())


def subsection(filename: str) -> tuple[str, str]:
    body = (PACKETS / filename).read_text(encoding="utf-8")
    title = "### Reference credibility target"
    assert body.count(title) == 1
    reference_start = body.index("## 5. Reference policy")
    start = body.index(title)
    output_start = body.index("## 6. Output and measurement contract")
    assert reference_start < start < output_start
    assert re.findall(r"^## (\d+)\. ", body, re.MULTILINE) == [
        str(i) for i in range(1, 11)
    ]
    return body[start:output_start], normalized(body[start:output_start])


@pytest.mark.parametrize("filename,tier,buyer,reference,unit", CASES)
def test_all_eight_targets_have_explicit_unearned_evidence_and_units(
    filename: str, tier: str, buyer: str, reference: str, unit: str
) -> None:
    _, text = subsection(filename)
    for label in (
        "Buyer tool:",
        "Carbon reference:",
        "Target tier:",
        "Benchmark cases:",
        "Acceptance tolerance: HUMAN_INPUT",
        "Credibility evidence: NOT_DEMONSTRATED",
        "Claim boundary:",
    ):
        assert label in text, (filename, label)
    assert f"Target tier: {tier}" in text
    assert buyer in text and reference in text and unit in text
    assert "not the same tool" in text
    assert "Tier 1" in text and "Tier 3" in text
    assert "matches the reference simulator" in text
    assert "matches reality" in text
    assert "reference-credibility.md" in text
    assert "≤" in text
    assert re.search(r"recommend(?:ed)?", text, re.IGNORECASE)


@pytest.mark.parametrize("filename", [row[0] for row in CASES])
def test_benchmarks_have_named_primary_sources_and_valid_local_companion(
    filename: str,
) -> None:
    raw, _ = subsection(filename)
    sources = []
    for label, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", raw):
        if target.startswith("https://"):
            assert label.strip()
            assert urlparse(target).netloc in PRIMARY_DOMAINS, target
            sources.append(target)
        else:
            assert (PACKETS / target.split("#", 1)[0]).is_file(), target
    assert sources, filename


def test_companion_keeps_targets_separate_from_claims_gates_and_execution() -> None:
    text = normalized((PACKETS / "reference-credibility.md").read_text("utf-8"))
    for required in (
        "Tier 1",
        "Tier 2",
        "Tier 3",
        "Acceptance tolerance: HUMAN_INPUT",
        "NOT_DEMONSTRATED",
        "not approved acceptance limits",
        "near-zero",
        "UNRESOLVED",
        "unless Tier 3 is met",
        "no benchmark or lab comparison was run",
        "no licences",
        "Protected EVAL/STRESS",
        "sealed journal sequence 14",
    ):
        assert required.lower() in text.lower(), required
    index = (PACKETS / "README.md").read_text("utf-8")
    assert "[shared credibility contract](reference-credibility.md)" in index


def test_battery_experiment_and_cooling_cell_boundaries_are_not_erased() -> None:
    _, battery = subsection("battery-ev-fast-charge.md")
    for required in (
        "Tier 3 before EV-use",
        "parameter identification from held-out validation",
        "do not alone cover",
        "independently accepted measurement",
        "no experimental plating tolerance is fabricated",
    ):
        assert required.lower() in battery.lower()
    _, cooling = subsection("cooling-accelerator-manifold.md")
    for required in (
        "cell-level",
        "ignore the full cold plate",
        "Ongoing hidden truth stays cell-level",
        "does not satisfy",
        "not an allowance for unmeasured manifold error",
    ):
        assert required in cooling
