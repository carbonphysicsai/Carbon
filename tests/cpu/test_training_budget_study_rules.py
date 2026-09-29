"""The training budget study's decision rules are frozen by digest
(OWNER-TRAINING-BUDGET-STUDY-01): the SHA-256 recorded in .agent/DECISIONS.md
must be the digest of the rules file as it stands."""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "docs/development/training_budget_study/DECISION_RULES.md"
DECISIONS = ROOT / ".agent/DECISIONS.md"


def _recorded_digests():
    text = DECISIONS.read_text()
    entry = text.split("OWNER-TRAINING-BUDGET-STUDY-01", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"\b[0-9a-f]{64}\b", entry))


def test_the_frozen_rules_match_the_digest_the_owner_decision_records():
    recorded = _recorded_digests()
    assert len(recorded) == 1
    assert hashlib.sha256(RULES.read_bytes()).hexdigest() in recorded


def test_an_edited_rule_would_no_longer_match():
    # Specimen: changing one character of one rule gives a digest the decision
    # does not record, so the check above can fail.
    edited = RULES.read_bytes().replace(
        b"twice the largest", b"three times the largest"
    )
    assert edited != RULES.read_bytes()
    assert hashlib.sha256(edited).hexdigest() not in _recorded_digests()
