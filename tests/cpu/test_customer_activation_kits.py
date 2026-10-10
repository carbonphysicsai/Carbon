"""Document coverage/claim checks; no physical or commercial qualification."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs/development/challenge_pipeline/activation-kits"
KITS = ("warpage", "solenoid-pole", "bolted-joint", "seal-gland")


def test_shared_intake_covers_all_984_inputs_with_tests_and_holds():
    doc = (DIR / "README.md").read_text(encoding="utf-8")
    rows = [line for line in doc.splitlines() if re.match(r"\| I\d\d ", line)]
    assert len(rows) == 17
    assert [re.search(r"I\d\d", row).group() for row in rows] == [
        f"I{i:02d}" for i in range(1, 18)
    ]
    assert all(
        "HOLD" in row and "D0" in row and len(row.split("|")) == 6 for row in rows
    )
    assert "not a code" in doc and "0eda2780f9cc645a353b25dbd0a3ca07c2b354be" in doc
    for phrase in ("NOT_QUOTABLE", "null/null/null", "unbounded", "HUMAN_INPUT"):
        assert phrase in doc


def test_each_full_job_extends_shared_contract_without_invented_readiness():
    for name in KITS:
        doc = (DIR / f"{name}.md").read_text(encoding="utf-8")
        assert "HOLD_CUSTOMER_INPUT" in doc
        assert "README.md" in doc
        assert "## Exact customer files and readiness tests" in doc
        assert "## Carbon work, next gate and output" in doc
        assert "## Conditional cost" in doc
        assert "Tier 2" in doc and "NOT_DEMONSTRATED" in doc
        assert "null/null/null / NOT_QUOTABLE" in doc
        assert "ASSUMPTION EUR" in doc or "**ASSUMPTION**" in doc
        rows = [line for line in doc.splitlines() if re.match(r"\| [WSBG]\d\d,", line)]
        assert len(rows) == 6
        assert all(len(row.split("|")) == 6 for row in rows)


def test_scope_and_current_gaps_preserved():
    expected = {
        "warpage": ("full 3D", "cure", "formation", "Tier 2"),
        "solenoid-pole": ("non-PM", "B–H(T)", "I²R", "moving-gap"),
        "bolted-joint": ("faying friction", "pretension", "eccentric", "slip"),
        "seal-gland": ("compressibility", "multiaxial", "history", "leakage"),
    }
    for name, phrases in expected.items():
        doc = (DIR / f"{name}.md").read_text(encoding="utf-8")
        assert all(phrase in doc for phrase in phrases)


def test_local_source_links_resolve():
    for path in DIR.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" not in target:
                assert (path.parent / target.split("#")[0]).is_file(), (path, target)


def test_timeline_arithmetic_is_preparation_only():
    doc = (DIR / "README.md").read_text(encoding="utf-8")
    assert [
        sum(values) for values in zip((4, 8, 16), (8, 24, 64), (4, 12, 32), (2, 6, 16))
    ] == [18, 50, 128]
    assert [
        sum(values) for values in zip((1, 2, 3), (2, 5, 10), (1, 3, 5), (1, 2, 3))
    ] == [5, 12, 21]
    assert "Reference implementation, solves" in doc and "**not included**" in doc
