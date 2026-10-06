"""Static F1 packet conformance; no Challenge activation or solver execution."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
PACKET_DIR = ROOT / "docs" / "development" / "challenge_pipeline"
TEMPLATE = PACKET_DIR / "COMMON_DESIGN_PACKET_V1.md"
EXAMPLE = PACKET_DIR / "BATTERY_DESIGN_PACKET_WORKED_EXAMPLE.md"

SECTIONS = (
    "Engineering job",
    "Physical system",
    "Population P, Q and w",
    "Case contract",
    "Reference policy",
    "Output and measurement contract",
    "Construction contract",
    "Research kit",
    "Evidence plan",
    "Readiness and claim record",
)


def _sections(path: Path) -> list[tuple[int, str]]:
    return [
        (int(number), title)
        for number, title in re.findall(
            r"^## (\d+)\. ([^\n]+)$", path.read_text(encoding="utf-8"), re.MULTILINE
        )
    ]


def test_common_packet_and_worked_example_have_all_ten_sections_in_order() -> None:
    expected = list(enumerate(SECTIONS, start=1))
    assert _sections(TEMPLATE) == expected
    assert _sections(EXAMPLE) == expected


def test_common_packet_maps_existing_owners_and_keeps_open_values_explicit() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    example = EXAMPLE.read_text(encoding="utf-8")
    for number in range(1, 11):
        assert f"| {number} |" in template
    for owner in ("carbon/authoring/", "carbon/challenge_readiness/", "carbon/reconstruction/"):
        assert owner in template
    assert template.count("`OPEN`") >= 10
    assert example.count("`OPEN`") >= 10
    assert "not an adopted Battery rule" in " ".join(example.split())
    assert "sealed journal sequence 14" in example
