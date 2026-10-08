"""The quiz's panel argument (a real-run finding on the AX42, 2026-10-07):
`quiz-select --panel` takes the operator's full panel, the same file `predict`
takes, and filters it to the registered disagreement panel. Passing the
registry is refused with its own code. The runbook documents the working
invocation."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from carbon.battery import quiz_stratum as qs
from carbon.challenge_validator import tuning

REPOSITORY = Path(__file__).resolve().parents[2]
REGISTRY = "docs/development/evidence/battery-quiz-designs/disagreement-panel-v1.json"


def operator_panel(tmp_path, names, extra=("not-in-the-registry",)):
    members = [
        {"member": name, "kind": "recipe", "strategy": {"name": name}, "seed": 1}
        for name in [*names, *extra]
    ]
    path = tmp_path / "panel.json"
    path.write_text(json.dumps({"schema": tuning.PANEL_SCHEMA, "members": members}))
    return path


def test_the_full_operator_panel_is_filtered_to_the_registered_members(tmp_path):
    registered = qs.registered_panel(REPOSITORY)
    members = tuning.quiz_panel_members(
        operator_panel(tmp_path, registered), REPOSITORY
    )
    assert sorted(m["member"] for m in members) == sorted(registered)


def test_an_exact_subset_still_works(tmp_path):
    registered = qs.registered_panel(REPOSITORY)
    path = operator_panel(tmp_path, registered, extra=())
    assert len(tuning.quiz_panel_members(path, REPOSITORY)) == len(registered)


def test_the_registry_itself_is_refused_with_its_own_code():
    with pytest.raises(tuning.TuningRefused) as refused:
        tuning.quiz_panel_members(REPOSITORY / REGISTRY, REPOSITORY)
    assert str(refused.value) == "tuning_quiz_panel_is_the_registry"


def test_a_missing_registered_member_is_named(tmp_path):
    registered = sorted(qs.registered_panel(REPOSITORY))
    path = operator_panel(tmp_path, registered[1:])
    with pytest.raises(tuning.TuningRefused) as refused:
        tuning.quiz_panel_members(path, REPOSITORY)
    assert str(refused.value) == "tuning_quiz_panel_missing:" + registered[0]


def test_the_runbook_documents_the_operator_panel():
    text = (
        REPOSITORY / "docs/development/graphite/HIDDEN_POOL_AND_TUNING_RUNBOOK.md"
    ).read_text()
    [line] = [l for l in text.splitlines() if "tuning quiz-select" in l]
    panel = re.search(r"--panel (\S+)", line).group(1)
    assert panel.endswith("/panel.json") and "disagreement-panel" not in panel
