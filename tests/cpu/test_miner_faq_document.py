"""Source-link and explicit-availability checks; not a privacy/security audit."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAQ = ROOT / "docs/development/MINER_FAQ.md"


def test_local_claim_sources_exist():
    text = FAQ.read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)]+)\)", text)
    local = [
        target.split("#")[0] for target in targets if not target.startswith("https:")
    ]
    assert len(local) >= 12
    for target in local:
        assert (FAQ.parent / target).is_file(), target


def test_pending_tools_and_reserved_policy_are_not_promised():
    text = FAQ.read_text(encoding="utf-8")
    assert "HUMAN_INPUT" in text and "opt-in mechanism is not decided" in text
    assert "Pending [PR #918]" in text and "not on" in text
    assert "do **not** yet have equivalent miner-runnable" in text
    assert "no mainnet emissions or reward entitlement" in text
    assert "testnet winner weights" in text


def test_current_install_guide_links_the_faq():
    guide = (FAQ.parent / "MINER_LAUNCHPAD_HANDOFF.md").read_text(encoding="utf-8")
    assert "[plain-language miner FAQ](MINER_FAQ.md)" in guide
