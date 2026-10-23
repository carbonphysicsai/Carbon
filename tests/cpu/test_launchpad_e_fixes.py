"""Newcomer fixes (codex-queue/handoff-20261021/EASY_MINER_FIX_LIST_20261023.md)."""

import re
from pathlib import Path

from scripts.dev.miner_launchpad import supervisor

ROOT = Path(__file__).resolve().parents[2]


def test_no_miner_text_says_read_the_code():
    # E9: "Read the code: it names what was refused" was not a step a
    # newcomer could take.
    for entry in (*supervisor.NEXT_ACTIONS.values(), supervisor.FALLBACK_ACTION):
        assert "read the code" not in entry.lower()
    for name in ("app.js", "research_view.js", "index.html"):
        text = (ROOT / "scripts/dev/miner_launchpad" / name).read_text(encoding="utf-8")
        assert not re.search(r"read the code", text, re.IGNORECASE), name


def test_a_code_without_its_own_entry_is_said_in_words():
    words = supervisor.next_action("catalog_setting_unknown_for_example")
    assert words.startswith("Refused: catalog setting unknown for example.")
    assert "your campaign and any frozen candidate are kept" in words
    # A code with its own entry keeps it.
    assert supervisor.next_action("construction_intake_unavailable") == (
        supervisor.NEXT_ACTIONS["construction_intake_unavailable"]
    )


def test_each_implemented_challenge_says_whether_it_can_be_practised():
    # E11: Battery could not practise, yet was offered like the others.
    from scripts.dev.miner_launchpad import capabilities

    state = {"configured": False, "reason": "profile_unset", "next_action": "-"}
    entries = [e for e in capabilities._challenges(state, None) if e.get("implemented")]
    assert entries
    for entry in entries:
        ready = entry["practise"]["ready"]
        assert ready == bool(entry["example_strategy"] or entry["catalog_recipes"])
        if not ready:
            assert entry["practise"]["plain"].startswith("Coming soon")
