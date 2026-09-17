"""Public practice cannot read or rewrite prospectively committed finals."""

import pytest

from carbon.development_session.research_profile import (
    document,
    freeze_roles,
    public_cases,
)
from carbon.scoring.development import RULE, rule_digest


def test_frozen_roles_are_disjoint_and_replay_does_not_redraw(tmp_path):
    first = freeze_roles(tmp_path)
    assert first == freeze_roles(tmp_path)
    assert [r["count"] for r in first.values()] == [72, 24, 24, 24]
    all_parents = [p for row in first.values() for p in row["parent_signatures"]]
    assert len(all_parents) == len(set(all_parents)) == 144
    assert len(public_cases(tmp_path, "research-train")) == 72
    for role in ("final-epoch-1", "final-epoch-2", "../final-epoch-1"):
        with pytest.raises(ValueError):
            public_cases(tmp_path, role)
    assert document()["objective_math"] == RULE
    assert document()["objective_math_digest"] == rule_digest()


def test_tampered_public_data_and_root_reuse_fail(tmp_path):
    freeze_roles(tmp_path)
    (tmp_path / "research-train-cases.json").write_text("[]")
    with pytest.raises(ValueError, match="identity"):
        public_cases(tmp_path, "research-train")
    root = tmp_path / "role-roots"
    (root / "final-epoch-2.bin").write_bytes((root / "final-epoch-1.bin").read_bytes())
    with pytest.raises(ValueError, match="distinct"):
        freeze_roles(tmp_path)
