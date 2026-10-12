"""QUIZ-EXTEND-01: the Q3 extension of a selected, sealed quiz.

Every root is synthetic and every solve scripted (the tuning quiz tests'
harness): draw, solve, refine, select and seal the quiz, then the extension;
predict both with one rebuild; score VERIFY-R on both. No container,
network or spend.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    backend,  # noqa: F401 - fixture
    make,
    refs,  # noqa: F401 - fixture
)
from test_challenge_validator_tuning import _stand_in_work, config_for
from test_challenge_validator_tuning_quiz import (
    _drawn,
    assert_owner_only,
    minimal_deployment,
    panel_file,
    rebuilds,  # noqa: F401 - fixture
    refused,
    scripted_solve,
    small,  # noqa: F401 - fixture
)

from carbon.battery import quiz_stratum as qs
from carbon.battery import seeds
from carbon.battery.value import quiz as qz
from carbon.challenge_validator import tuning
from carbon.challenge_validator.interface import BATTERY_TUNING_ROLE

EXT_K = 4


@pytest.fixture
def ext_small(monkeypatch):
    monkeypatch.setattr(qs, "Q3_EXT_K", EXT_K)


def _quiz(tmp_path, config):
    """The selected quiz (no refine points: the plain scripted lattice)."""
    work, _draws, _ = _drawn(tmp_path, config)
    tuning.quiz_select(work, panel_file(tmp_path), backend=object())
    return work


def _extended(tmp_path, config, quiz, infeasible_first=0):
    ext = tmp_path / "quiz-ext"
    tuning.quiz_ext_jobs(config, ext, quiz)
    draws = tuning._read_private(ext / "draws.json")
    infeasible = {tuple(s["condition"]) for s in draws["q3"][:infeasible_first]}
    scripted_solve(ext, infeasible)
    return ext, draws


@pytest.mark.usefixtures("small", "ext_small", "rebuilds")
def test_the_extension_draws_are_its_own_and_away_from_every_quiz_draw(tmp_path):
    config, _root = minimal_deployment(tmp_path / "hidden")
    quiz = _quiz(tmp_path, config)
    ext, draws = _extended(tmp_path, config, quiz)
    base_draws = tuning._read_private(quiz / "draws.json")
    base = tuning.load_quiz(quiz)
    assert draws["extension_of"] == qs.digest(base) and draws["q2"] == []
    assert len(draws["q3"]) == qs.q3_ext_draws(1) == EXT_K + qs.Q3_EXTRA
    assert all(s["scenario_id"].startswith("q3x-") for s in draws["q3"])
    taken = [tuple(s["condition"]) for s in base_draws["q3"]]
    for s in draws["q3"]:
        assert not qs.is_protected(s["condition"], taken)
    base_ids = set(qs.inputs(base))
    jobs = json.loads((ext / "jobs.json").read_text())["jobs"]
    assert len(jobs) == len(draws["q3"]) * 117
    assert not {j["case_id"] for j in jobs} & base_ids
    # Deterministic: a rerun draws the same.
    tuning.quiz_ext_jobs(config, ext, quiz)
    assert tuning._read_private(ext / "draws.json") == draws
    assert_owner_only(ext)


@pytest.mark.usefixtures("small", "ext_small", "rebuilds")
def test_the_extension_selects_its_own_k_and_names_the_next_round(tmp_path):
    config, _root = minimal_deployment(tmp_path / "hidden")
    quiz = _quiz(tmp_path, config)
    # Five of round 1's eight conditions infeasible: only 3 of the 4 needed.
    ext, _draws = _extended(tmp_path, config, quiz, infeasible_first=5)
    refused(
        lambda: tuning.quiz_ext_select(ext, quiz), "tuning_quiz_needs_more_q3:--round 2"
    )
    tuning.quiz_ext_jobs(config, ext, quiz, round_=2)
    scripted_solve(ext)
    tuning.quiz_refine(ext)  # no refine points in the plain lattice
    result = tuning.quiz_ext_select(ext, quiz)
    assert result["q3_scenarios"] == EXT_K
    assert result["redraws"]["q3_infeasible"] == 5
    document = tuning.load_quiz(ext)
    assert document["role"] == BATTERY_TUNING_ROLE + tuning.QUIZ_EXT_ROLE_SUFFIX
    assert document["q2"] == [] and len(document["q3"]) == EXT_K
    # Fixed once selected; the quiz itself is untouched.
    refused(lambda: tuning.quiz_ext_select(ext, quiz), "tuning_quiz_already_selected")
    refused(
        lambda: tuning.quiz_ext_jobs(config, ext, quiz), "tuning_quiz_already_selected"
    )
    assert len(tuning.load_quiz(quiz)["q3"]) == qz.Q3_K


@pytest.mark.usefixtures("small", "ext_small", "rebuilds")
def test_an_extension_of_another_quiz_or_of_an_extension_is_refused(tmp_path):
    config, _root = minimal_deployment(tmp_path / "hidden")
    quiz = _quiz(tmp_path, config)
    ext, _draws = _extended(tmp_path, config, quiz)
    other = tmp_path / "other-quiz"
    other.mkdir(mode=0o700)
    document = dict(tuning.load_quiz(quiz))
    document["redraws"] = {**document["redraws"], "q3_infeasible": 9}
    tuning._write_private(other / "quiz.json", document)
    refused(lambda: tuning.quiz_ext_select(ext, other), "tuning_quiz_ext_base_mismatch")
    refused(lambda: tuning.quiz_ext_select(quiz, quiz), "tuning_quiz_already_selected")
    plain = tmp_path / "plain"
    tuning.quiz_jobs(config, plain)
    scripted_solve(plain)
    refused(
        lambda: tuning.quiz_ext_select(plain, quiz), "tuning_quiz_ext_not_an_extension"
    )
    tuning.quiz_ext_select(ext, quiz)
    refused(
        lambda: tuning.quiz_ext_jobs(config, tmp_path / "ext-of-ext", ext),
        "tuning_quiz_ext_of_an_extension",
    )


@pytest.mark.usefixtures("small", "ext_small")
def test_predict_serves_quiz_and_extension_with_one_rebuild_and_verify_r_scores_both(
    tmp_path,
    rebuilds,  # noqa: F811
    refs,  # noqa: F811
):
    from scripts.dev.battery import verify_r_quiz

    config, _root = minimal_deployment(tmp_path / "hidden")
    quiz = _quiz(tmp_path, config)
    ext, _draws = _extended(tmp_path, config, quiz)
    tuning.quiz_ext_select(ext, quiz)
    work, _batch = _stand_in_work(tmp_path, refs)
    panel = panel_file(tmp_path, ("member-a", "member-b"))
    rebuilds.clear()
    assert tuning.predict(work, panel, quiz=quiz, backend=object())["rebuilt"] == 2
    rebuilds.clear()
    assert (
        tuning.predict(work, panel, quiz=quiz, quiz_ext=ext, backend=object())[
            "rebuilt"
        ]
        == 2
    )
    ext_ids = frozenset(qs.inputs(tuning.load_quiz(ext)))
    # Only the extension's inputs were still missing: one rebuild each.
    assert [inputs for _, inputs in rebuilds] == [ext_ids] * 2
    held = tuning._read_private(work / "quiz-ext-predictions" / "member-a.json")
    assert held["quiz_digest"] == qs.digest(tuning.load_quiz(ext))
    assert set(held["predictions"]) == ext_ids
    refused(
        lambda: tuning.predict(work, panel, quiz=quiz, quiz_ext=quiz, backend=object()),
        "tuning_quiz_ext_not_an_extension",
    )
    base_only = verify_r_quiz.legs(work, quiz)
    both = verify_r_quiz.legs(work, quiz, ext)
    assert base_only["diagnostics"]["v3"]["questions"] == qz.Q3_K
    assert both["diagnostics"]["v3"]["questions"] == qz.Q3_K + EXT_K
    assert both["quiz_ext_digest"] == qs.digest(tuning.load_quiz(ext))
    assert set(both["legs"]["v3"]) >= {"member-a", "member-b"}
    assert "reliability" in both["diagnostics"]["v3"]
    assert both["diagnostics"]["v3"]["budget_stopped"] == 0
    assert_owner_only(work, ext)


@pytest.mark.usefixtures("small", "ext_small", "rebuilds")
def test_the_extension_seals_under_its_own_role(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    deployment_dir = tmp_path / "deployment"
    deployment_dir.mkdir()
    make(deployment_dir, refs, backend)
    config = config_for(deployment_dir)
    quiz = _quiz(tmp_path, config)
    sealed_quiz = tuning.quiz_seal(config, quiz)
    ext, _draws = _extended(tmp_path, config, quiz)
    tuning.quiz_ext_select(ext, quiz)
    result = tuning.quiz_ext_seal(config, ext, quiz)
    journal = seeds.SeedJournal(deployment_dir / "journal.jsonl")
    entry = journal.public()[-1]
    assert entry["kind"] == "quiz"
    assert entry["role"] == BATTERY_TUNING_ROLE + tuning.QUIZ_EXT_ROLE_SUFFIX
    assert entry["digest"] == result["digest"] == qs.digest(tuning.load_quiz(ext))
    assert entry["q2_cases"] == 0 and entry["q3_scenarios"] == EXT_K
    assert result["journal_sequence"] > sealed_quiz["journal_sequence"]
    # Idempotent, and the quiz's own seal still stands.
    assert tuning.quiz_ext_seal(config, ext, quiz) == result
    assert tuning.quiz_seal(config, quiz) == sealed_quiz
    text = (deployment_dir / "journal.jsonl").read_text()
    for s in tuning.load_quiz(ext)["q3"]:
        assert s["scenario_id"] not in text
    # A forged extension is refused.
    forged = dict(tuning.load_quiz(ext))
    forged["q3"] = [{**forged["q3"][0], "condition": [0.0, 0.5]}] + forged["q3"][1:]
    (ext / "quiz.json").unlink()
    tuning._write_private(ext / "quiz.json", forged)
    refused(
        lambda: tuning.quiz_ext_seal(config, ext, quiz),
        "tuning_quiz_not_from_this_root",
    )
