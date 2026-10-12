"""PUBLIC-DEV-DECISIONS-01: the leg/value split of the public development
questions is registered, deterministic and disjoint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SPLIT = (
    Path(__file__).resolve().parents[2]
    / "docs/development/evidence/battery-score-tuning/public-dev-split-v1.json"
)


def side(split, scenario_id):
    h = hashlib.sha256(f"{split['salt']}:question:{scenario_id}".encode()).hexdigest()
    return "LEG" if int(h[:8], 16) / 2**32 < split["leg_share"] else "VALUE"


def test_the_split_is_registered_with_its_parameter():
    split = json.loads(SPLIT.read_text())
    assert split["schema"] == "carbon.battery.public-dev-split.v1"
    assert split["leg_share"] == 0.5 and split["salt"]


def test_every_question_falls_on_exactly_one_side_near_the_share():
    split = json.loads(SPLIT.read_text())
    ids = [f"dev-q-{i}" for i in range(4000)]
    sides = [side(split, i) for i in ids]
    assert sides == [side(split, i) for i in ids]  # deterministic
    assert 0.47 < sides.count("LEG") / len(ids) < 0.53
