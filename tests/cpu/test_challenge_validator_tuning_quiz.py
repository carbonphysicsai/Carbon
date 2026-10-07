"""The tuning set's near-limit quiz stratum (VALIDATOR-19 slice Q;
VALIDATOR-17's v2 amendment).

Every root here is synthetic and every solve is scripted: references come
from small closed-form outputs, and panel rebuilds from a stand-in
`member_bundle`. No container, network or spend; no real deployment's sealed
set is read or regenerated.
"""

import json
import os
import stat
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

from carbon.battery import quiz_stratum as qs
from carbon.battery import seeds
from carbon.battery.domain import INPUT_BOUNDS
from carbon.battery.value import experiment
from carbon.battery.value import quiz as qz
from carbon.challenge_validator import confirmation as cf
from carbon.challenge_validator import tuning
from carbon.challenge_validator.interface import (
    BATTERY_TUNING_ROLE,
    BATTERY_TUNING_ROLE_V1,
    RESERVED_SEED_ROLES,
    role_reserved,
)

PIN = seeds.seed_pin("sha256:" + "1" * 64, "sha256:" + "2" * 64)
POINTS = 13
PANEL = qs.registered_panel(REPOSITORY)


@pytest.fixture
def small(monkeypatch):
    """Registered sizes scaled down, so a whole quiz runs in a test."""
    monkeypatch.setattr(qz, "Q2_POOL", 20)
    monkeypatch.setattr(qz, "Q2_N", 8)
    monkeypatch.setattr(qz, "Q3_K", 3)


@pytest.fixture
def rebuilds(monkeypatch):
    """A stand-in rebuild: each member predicts the scripted truth with its
    own plating bias. Records every call."""
    calls = []

    def member_bundle(_backend, member, _strategy, _seed, inputs):
        calls.append((member, frozenset(inputs)))
        index = PANEL.index(member) if member in PANEL else 0
        bias = -0.006 + 0.012 * index / (len(PANEL) - 1)
        predictions = {}
        for case_id, x in inputs.items():
            outputs = truth({"case_id": case_id, **x}, ())
            outputs["plating_margin_v"] += bias
            predictions[case_id] = outputs
        return {"member": member, "predictions": predictions}, None

    monkeypatch.setattr(experiment, "member_bundle", member_bundle)
    return calls


def outputs(time_s, margin, peak):
    step = 3600.0 / (POINTS - 1)
    return {
        "voltage_v": [min(3.5 + 0.7 * i * step / time_s, 4.2) for i in range(POINTS)],
        "temperature_c": [25.0] + [peak] * (POINTS - 1),
        "plating_margin_v": margin,
    }


def q2_margin(x):
    """Spread over [-0.004, 0.016] V: about 60 % within 4 bands."""
    return (x["soc0"] - 0.05) / 0.45 * 0.02 - 0.004


def truth(job, infeasible):
    """The scripted reference. A Q3 grid's c1 >= 1.5 plates; a condition in
    `infeasible` plates at every candidate."""
    if job["case_id"].startswith("ev4:"):
        condition = (job["t_amb_c"], job["soc0"])
        plates = condition in infeasible or job["c1"] >= 1.5
        time_s = 600.0 + 1500.0 / (job["c1"] + job["c2"])
        return outputs(time_s, -0.01 if plates else 0.01, 30.0)
    return outputs(1500.0, q2_margin(job), 30.0)


def scripted_solve(work, infeasible=()):
    """Solve `work/jobs.json` into `work/records.jsonl`, resumably."""
    jobs = json.loads((work / "jobs.json").read_text())["jobs"]
    path = work / "records.jsonl"
    done = {json.loads(line)["case_id"] for line in path.read_text().splitlines()}
    with path.open("a") as out:
        for job in jobs:
            if job["case_id"] in done:
                continue
            record = {
                "case_id": job["case_id"],
                "refined": False,
                "inputs": {k: job[k] for k in ("c1", "c2", "t_amb_c", "soc0")},
                "status": "OK",
                "outputs": truth(job, set(infeasible)),
            }
            out.write(json.dumps(record) + "\n")


def minimal_deployment(directory):
    """A deployment's root, journal and configuration (no validator)."""
    directory.mkdir(mode=0o700)
    root = seeds.PrivateRoot.create(directory / "root.bin")
    seeds.SeedJournal(directory / "journal.jsonl").commit_root(root, PIN)
    return config_for(directory), root


def panel_file(directory, members=PANEL):
    path = directory / "panel.json"
    path.write_text(
        json.dumps(
            {
                "schema": tuning.PANEL_SCHEMA,
                "members": [
                    {"member": m, "kind": "RECONSTRUCTED", "strategy": {}, "seed": 0}
                    for m in members
                ],
            }
        )
    )
    return path


def refused(call, code):
    with pytest.raises(tuning.TuningRefused) as caught:
        call()
    assert str(caught.value) == code, str(caught.value)


def assert_owner_only(*directories):
    for directory in directories:
        for path in [directory, *Path(directory).rglob("*")]:
            if path.name == "lock" or path.suffix in (".lock", ".sqlite3"):
                continue
            mode = os.lstat(path).st_mode
            assert stat.S_ISDIR(mode) or stat.S_ISREG(mode), path
            assert mode & 0o077 == 0, path


# --- the registration -------------------------------------------------------------------


def test_v2_is_registered_reserved_and_v1_stays_reserved():
    sets = cf.load_sets()
    item = sets[BATTERY_TUNING_ROLE]
    assert BATTERY_TUNING_ROLE == "graphite-tuning-v2"
    assert (item.cases, item.hidden_duplicates, item.strata) == (200, 4, ())
    v1 = sets[BATTERY_TUNING_ROLE_V1]
    assert (item.sampling_law, item.subgroups) == (v1.sampling_law, v1.subgroups)
    # Sealed on the hidden host: every prior is an owner-only file, so no
    # sealed role is regenerated there (HIDDEN_HOST_SETUP §6).
    assert item.required_prior_roles == ()
    # graphite-confirmation-v1 was never sealed: no cases, so no prior.
    assert item.required_private_priors == (
        "graphite-hidden-battery-v1-pool",
        "ev5-confirmation",
    )
    assert item.sealable and not item.human_input
    stratum = item.skeleton()["quiz_stratum"]
    assert set(stratum) == {"description", "amendment", "library", "drawn_by"}
    assert "carbon/battery/value/quiz.py" in stratum["library"]
    assert (REPOSITORY / "carbon/battery/value/quiz.py").exists()
    assert "quiz_stratum" not in v1.skeleton()
    for role in (BATTERY_TUNING_ROLE, BATTERY_TUNING_ROLE_V1):
        assert role in RESERVED_SEED_ROLES and role_reserved(role.upper())


def test_a_malformed_quiz_stratum_is_refused():
    document = json.loads((cf.SET_DIR / f"{BATTERY_TUNING_ROLE}.json").read_text())
    del document["quiz_stratum"]["library"]
    with pytest.raises(cf.ConfirmationRefused) as caught:
        cf.ConfirmationSet.from_document(document, cf.digest(document))
    assert caught.value.code == "confirmation_set_malformed:quiz_stratum"


# --- draws ------------------------------------------------------------------------------


def test_draws_are_deterministic_uniform_and_never_a_main_set_draw(tmp_path):
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    other = seeds.PrivateRoot.create(tmp_path / "other.bin")
    role = BATTERY_TUNING_ROLE
    drawn = qs.q2_candidates(root, PIN, role, 40)
    assert drawn == qs.q2_candidates(root, PIN, role, 40)
    assert qs.q2_candidates(root, PIN, role, 10) == drawn[:10]
    assert drawn != qs.q2_candidates(other, PIN, role, 40)
    ids = [c["case_id"] for c in drawn]
    assert len(set(ids)) == len(ids)
    assert all(c.startswith(role + "-") and "q2" not in c for c in ids)
    for case in drawn:
        for name, value in case["inputs"].items():
            low, high = INPUT_BOUNDS[name]
            assert low <= value <= high and round(value, 4) == value
    main = seeds.make_batch(root, PIN, role, 204, 4)
    keys = {tuple(sorted(dict(x).items())) for _c, x in main.cases}
    assert not keys & {tuple(sorted(c["inputs"].items())) for c in drawn}
    assert not set(ids) & {c for c, _x in main.cases}


def test_a_protected_condition_is_refused_and_redrawn(tmp_path):
    points = qs.protected_conditions(REPOSITORY)
    from carbon.battery.value import contract as ev

    for path in (REPOSITORY / qs.CONTRACTS).glob("*.json"):
        document, _ = ev.load(path)
        for scenario in ev.scenarios(document):
            assert {tuple(map(float, c)) for c in scenario["conditions"]} <= set(points)
    # The committed practice decision set (B4) is protected too.
    assert (37.6, 0.344) in points and (5.5, 0.423) in points
    # Within BOTH 2 degC and 0.03 soc0 (B4's own rule, strict).
    one = [(37.6, 0.344)]
    assert qs.is_protected((39.5, 0.373), one)
    assert not qs.is_protected((39.6, 0.344), one)
    assert not qs.is_protected((37.6, 0.374), one)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    context = seeds._context(root, PIN)
    first = [
        seeds.draw_inputs(context, BATTERY_TUNING_ROLE, qs.Q3_BASE + a)
        for a in range(3)
    ]
    blocked = [(x["t_amb_c"], x["soc0"]) for x in first]
    accepted = qs.q3_conditions(root, PIN, BATTERY_TUNING_ROLE, 5, blocked)
    assert accepted[0]["attempt"] >= 3
    assert not any(qs.is_protected(a["condition"], blocked) for a in accepted)
    assert accepted == qs.q3_conditions(root, PIN, BATTERY_TUNING_ROLE, 5, blocked)
    real = qs.q3_conditions(root, PIN, BATTERY_TUNING_ROLE, 12, points)
    assert not any(qs.is_protected(a["condition"], points) for a in real)
    for a in real:
        t, s = a["condition"]
        assert 5.0 <= t <= 40.0 and 0.05 <= s <= 0.5


def test_quiz_jobs_draw_the_agreed_sizes_owner_only(tmp_path):
    config, _root = minimal_deployment(tmp_path / "hidden")
    work = tmp_path / "quiz"
    result = tuning.quiz_jobs(config, work)
    assert result["q2_candidates"] == qz.Q2_POOL * 4 == 1280
    assert result["q3_conditions"] == qz.Q3_K + 4 == 12
    assert result["solve_jobs"] == 1280 + 12 * 35
    jobs = json.loads((work / "jobs.json").read_text())["jobs"]
    assert len({j["case_id"] for j in jobs}) == len(jobs)
    # The output names no case, input or condition.
    text = json.dumps(result)
    assert "inputs" not in text and BATTERY_TUNING_ROLE not in text
    assert_owner_only(work)
    refused(lambda: tuning.quiz_jobs(config, work, 0), "tuning_quiz_round_malformed")
    refused(
        lambda: tuning.quiz_jobs(config, REPOSITORY / "tmp-quiz"),
        "tuning_work_inside_repository",
    )


# --- selection --------------------------------------------------------------------------


def _drawn(tmp_path, config, infeasible_first=0):
    work = tmp_path / "quiz"
    tuning.quiz_jobs(config, work)
    draws = tuning._read_private(work / "draws.json")
    infeasible = {tuple(s["condition"]) for s in draws["q3"][:infeasible_first]}
    scripted_solve(work, infeasible)
    return work, draws, infeasible


def test_the_pool_is_capped_in_draw_order_and_q2_reads_only_the_panel(
    tmp_path, small, rebuilds
):
    config, _root = minimal_deployment(tmp_path / "hidden")
    work, draws, _ = _drawn(tmp_path, config)
    contract = qs.contract(REPOSITORY)
    solved = tuning._records(work)
    band = contract["reference"]["uncertainty"]["bands"]["plating_margin_v"]
    near = [
        c["case_id"]
        for c in draws["q2"]
        if abs(q2_margin(c["inputs"])) <= qz.Q2_POOL_BANDS * band
    ]
    assert len(near) > qz.Q2_POOL
    pool = qs.q2_pool(contract, draws["q2"], solved)
    assert pool == near[: qz.Q2_POOL]
    result = tuning.quiz_select(work, panel_file(tmp_path), backend=object())
    assert (result["q2_pool"], result["q2_cases"]) == (qz.Q2_POOL, qz.Q2_N)
    assert result["panel_version"] == qz.PANEL_VERSION == 1
    # The panel is the registered one, rebuilt once on the Q2 candidates only.
    candidates = frozenset(c["case_id"] for c in draws["q2"])
    assert sorted(m for m, _ in rebuilds) == sorted(PANEL)
    assert all(inputs == candidates for _, inputs in rebuilds)
    cache = work / "panel-v1"
    panel = {m: tuning._read_private(cache / f"{m}.json")["predictions"] for m in PANEL}
    document = tuning._read_private(work / "quiz.json")
    chosen = [c["case_id"] for c in document["q2"]]
    assert chosen == qz.q2_select(contract, pool, panel, n=qz.Q2_N)
    assert set(chosen) <= set(pool)
    # The panel splits most evenly where the truth is closest to the limit.
    inputs = {c["case_id"]: c["inputs"] for c in draws["q2"]}
    worst_chosen = max(abs(q2_margin(inputs[c])) for c in chosen)
    best_left = min(abs(q2_margin(inputs[c])) for c in set(pool) - set(chosen))
    assert worst_chosen <= best_left + 0.012 / (len(PANEL) - 1)
    assert document["schema"] == qs.SCHEMA and document["panel_version"] == 1
    assert document["role"] == BATTERY_TUNING_ROLE
    assert_owner_only(work)
    # A selected quiz is never redrawn or reselected.
    refused(
        lambda: tuning.quiz_select(work, panel_file(tmp_path), backend=object()),
        "tuning_quiz_already_selected",
    )
    refused(lambda: tuning.quiz_jobs(config, work, 2), "tuning_quiz_already_selected")


def test_an_unsolved_candidate_or_an_unregistered_panel_is_refused(
    tmp_path, small, rebuilds
):
    config, _root = minimal_deployment(tmp_path / "hidden")
    work = tmp_path / "quiz"
    tuning.quiz_jobs(config, work)
    refused(
        lambda: tuning.quiz_select(work, panel_file(tmp_path), backend=object()),
        "tuning_quiz_unsolved",
    )
    scripted_solve(work)
    refused(
        lambda: tuning.quiz_select(
            work, panel_file(tmp_path, PANEL[:-1]), backend=object()
        ),
        "tuning_quiz_panel_not_registered",
    )
    assert rebuilds == []


def test_infeasible_scenarios_are_redrawn_and_a_short_round_names_the_next(
    tmp_path, small, rebuilds
):
    config, _root = minimal_deployment(tmp_path / "hidden")
    # Round 1 draws Q3_K + 4 = 7 conditions; 5 are all-infeasible.
    work, draws, infeasible = _drawn(tmp_path, config, infeasible_first=5)
    refused(
        lambda: tuning.quiz_select(work, panel_file(tmp_path), backend=object()),
        "tuning_quiz_needs_more_q3:--round 2",
    )
    assert rebuilds == []  # refused before any panel rebuild
    result = tuning.quiz_jobs(config, work, 2)
    assert result["q3_conditions"] == qz.Q3_K + 8
    again = tuning._read_private(work / "draws.json")
    assert again["q2"] == draws["q2"]  # Q2 is never redrawn
    assert again["q3"][:7] == draws["q3"]
    scripted_solve(work, infeasible)
    result = tuning.quiz_select(work, panel_file(tmp_path), backend=object())
    assert result["q3_scenarios"] == qz.Q3_K
    assert result["redraws"]["q3_infeasible"] == 5
    document = tuning._read_private(work / "quiz.json")
    kept = [s["scenario_id"] for s in document["q3"]]
    assert kept == [s["scenario_id"] for s in again["q3"][5:8]]
    for s in document["q3"]:
        assert len(s["grid"]) == 35
        assert tuple(s["condition"]) not in infeasible
    assert document["redraws"] == result["redraws"]
    assert_owner_only(work)


# --- quiz-seal --------------------------------------------------------------------------


def test_quiz_seal_journals_public_fields_only_and_readers_skip_it(
    tmp_path,
    small,
    rebuilds,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    deployment_dir = tmp_path / "deployment"
    deployment_dir.mkdir()
    target = make(deployment_dir, refs, backend)
    config = config_for(deployment_dir)
    item = cf.confirmation_set(BATTERY_TUNING_ROLE)
    sealed = target.seal_batch(
        BATTERY_TUNING_ROLE, count=item.batch_size, duplicates=item.hidden_duplicates
    )
    work, _draws, _ = _drawn(tmp_path, config)
    tuning.quiz_select(work, panel_file(tmp_path), backend=object())
    document = tuning._read_private(work / "quiz.json")
    result = tuning.quiz_seal(config, work)
    assert result["digest"] == qs.digest(document)
    journal = seeds.SeedJournal(deployment_dir / "journal.jsonl")
    entry = journal.public()[-1]
    assert entry == {
        "schema": seeds.JOURNAL_SCHEMA,
        "sequence": result["journal_sequence"],
        "kind": "quiz",
        "role": BATTERY_TUNING_ROLE,
        "digest": result["digest"],
        "q2_cases": qz.Q2_N,
        "q3_scenarios": qz.Q3_K,
        "panel_version": qz.PANEL_VERSION,
    }
    text = (deployment_dir / "journal.jsonl").read_text()
    for case in document["q2"]:
        assert case["case_id"] not in text
    for scenario in document["q3"]:
        assert scenario["scenario_id"] not in text
    # Idempotent: a rerun returns the same commitment.
    assert tuning.quiz_seal(config, work) == result
    assert len(journal.public()) == result["journal_sequence"] + 1
    # Every existing journal reader skips the new kind.
    assert journal.root_pin(target.root) == target.pin
    assert seeds.verify_reveal(journal.public())["reveals_checked"] == 0
    assert journal.recall(sealed.batch).sequence == sealed.sequence
    commitment = tmp_path / "commitment.json"
    commitment.write_text(
        json.dumps(
            {"fingerprint": sealed.fingerprint, "journal_sequence": sealed.sequence}
        )
    )
    recalled = tuning.jobs(config, commitment, tmp_path / "tuning")
    assert recalled["journal_sequence"] == sealed.sequence
    assert BATTERY_TUNING_ROLE in target.sealed_roles()
    target.prepare_batch("screening-after-quiz", kind="screening")
    # A quiz that is not this root's own draws is refused.
    forged = dict(document)
    forged["q2"] = [
        {**document["q2"][0], "inputs": {**document["q2"][0]["inputs"], "c1": 0.5}}
    ] + document["q2"][1:]
    (work / "quiz.json").unlink()
    tuning._write_private(work / "quiz.json", forged)
    refused(lambda: tuning.quiz_seal(config, work), "tuning_quiz_not_from_this_root")
    assert_owner_only(work)


def test_a_second_quiz_under_one_role_is_refused(tmp_path):
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    document = qs.document(BATTERY_TUNING_ROLE, 1, [], [], {})
    first = qs.seal(journal, document)
    assert qs.seal(journal, document) == first
    with pytest.raises(qs.QuizRefused) as caught:
        qs.seal(journal, {**document, "redraws": {"q3_infeasible": 1}})
    assert caught.value.code == "quiz_role_already_sealed"


# --- predict and score ------------------------------------------------------------------


def _quiz_work(tmp_path):
    """A quiz directory over two scenarios and four Q2 cases, solved."""
    contract = qs.contract(REPOSITORY)
    q2 = [
        {
            "case_id": f"q2-case-{i}",
            "inputs": {"c1": 1.0, "c2": 0.5, "t_amb_c": 20.0, "soc0": soc0},
        }
        for i, soc0 in enumerate((0.1, 0.15, 0.2, 0.25))
    ]
    q3 = []
    for i, condition in enumerate(([12.5, 0.21], [33.25, 0.4])):
        entry = {"scenario_id": f"q3-s{i}", "condition": condition}
        q3.append({**entry, "grid": qz.q3_grid(contract, qs.scenario(entry))})
    document = qs.document(BATTERY_TUNING_ROLE, 1, q2, q3, {"q3_infeasible": 0})
    work = tuning._owner_only_dir(tmp_path / "quiz")
    tuning._write_private(work / "quiz.json", document)
    lines = []
    for case_id, x in qs.inputs(document).items():
        record = {"case_id": case_id, "status": "OK", "inputs": x}
        lines.append(json.dumps({**record, "outputs": truth(record | x, ())}))
    (work / "records.jsonl").write_text("\n".join(lines) + "\n")
    (work / "records.jsonl").chmod(0o600)
    return work, document


def _member(document, shift):
    """Predictions on every quiz input: the truth, plating shifted."""
    predictions = {}
    for case_id, x in qs.inputs(document).items():
        outputs = truth({"case_id": case_id, **x}, ())
        outputs["plating_margin_v"] += shift
        predictions[case_id] = outputs
    return predictions


def test_score_writes_quiz_measures_and_q3_regret(
    tmp_path,
    refs,  # noqa: F811
):
    work, _ = _stand_in_work(tmp_path, refs)
    batch_refs = tuning.references(work)[1]
    quiz, document = _quiz_work(tmp_path)
    digest = qs.digest(document)
    folder = tuning._owner_only_dir(work / "quiz-predictions")
    for member, shift in (("oracle", 0.0), ("optimist", 0.05), ("pessimist", -0.05)):
        tuning._write_private(
            folder / f"{member}.json",
            {
                "member": member,
                "kind": "RECONSTRUCTED",
                "quiz_digest": digest,
                "predictions": _member(document, shift),
            },
        )
    result = tuning.score(work, quiz=quiz)
    assert result["quiz"]["quiz_digest"] == digest
    regret = tuning._read_private(work / "q3-regret.json")
    # The oracle picks the fastest feasible design (no regret); the optimist
    # picks a plating design (false acceptance, cost 10); the pessimist
    # abstains where a design was feasible (missed opportunity, cost 1).
    assert regret["oracle"] == 0.0
    assert regret["optimist"] == 10.0
    assert regret["pessimist"] == 1.0
    assert regret["control-oracle"] == 0.0
    scores = tuning._read_private(work / "quiz-scores.json")
    assert scores["quiz_digest"] == digest and scores["panel_version"] == 1
    oracle, optimist = scores["members"]["oracle"], scores["members"]["optimist"]
    assert oracle["q3"]["false_feasible"] == 0.0
    assert optimist["q3"]["false_feasible"] == 1.0
    assert scores["members"]["pessimist"]["q3"]["over_caution"] == 1.0
    assert [o["kind"] for o in optimist["q3"]["outcomes"]] == [
        "SELECTED_INFEASIBLE"
    ] * 2
    assert set(oracle["q2"]) == {"false_feasible", "plating_fa", "false_infeasible"}
    assert scores["members"]["pessimist"]["q2"]["false_infeasible"] == 1.0
    # Accuracy rows never hold a quiz case.
    quiz_ids = set(qs.inputs(document))
    for path in (work / "rows").glob("*.json"):
        assert not {r["case_id"] for r in tuning._read_private(path)} & quiz_ids
    accuracy = tuning._read_private(work / "scores.json")
    assert accuracy["cases_with_reference"] == len(batch_refs)
    assert_owner_only(work, quiz)
    # Predictions made for another quiz are refused.
    path = folder / "oracle.json"
    stale = {**tuning._read_private(path), "quiz_digest": "sha256:" + "0" * 64}
    path.unlink()
    tuning._write_private(path, stale)
    refused(lambda: tuning.score_quiz(work, quiz), "tuning_quiz_predictions_stale")


def test_predict_keeps_quiz_predictions_apart_with_one_rebuild(
    tmp_path,
    rebuilds,
    refs,  # noqa: F811
):
    work, batch_document = _stand_in_work(tmp_path, refs)
    quiz, document = _quiz_work(tmp_path)
    panel = panel_file(tmp_path, ("member-a", "member-b"))
    assert tuning.predict(work, panel, backend=object()) == {"rebuilt": 2, "failed": 0}
    assert not (work / "quiz-predictions").exists()
    batch_ids = {c["case_id"] for c in batch_document["cases"]}
    quiz_ids = set(qs.inputs(document))
    rebuilds.clear()
    assert tuning.predict(work, panel, quiz=quiz, backend=object())["rebuilt"] == 2
    # Only the quiz's inputs were still missing.
    assert [inputs for _, inputs in rebuilds] == [frozenset(quiz_ids)] * 2
    for member in ("member-a", "member-b"):
        accuracy = tuning._read_private(work / "predictions" / f"{member}.json")
        assert set(accuracy["predictions"]) == batch_ids
        held = tuning._read_private(work / "quiz-predictions" / f"{member}.json")
        assert set(held["predictions"]) == quiz_ids
        assert held["quiz_digest"] == qs.digest(document)
    rebuilds.clear()
    assert tuning.predict(work, panel, quiz=quiz, backend=object())["rebuilt"] == 0
    assert rebuilds == []
    assert_owner_only(work)
    refused(
        lambda: tuning.predict(work, panel, quiz=tmp_path / "none", backend=object()),
        "tuning_quiz_not_selected",
    )


# --- export-prior -----------------------------------------------------------------------


def test_export_prior_writes_a_sealed_sets_inputs_owner_only(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    deployment_dir = tmp_path / "testnet"
    deployment_dir.mkdir()
    target = make(deployment_dir, refs, backend)
    config = config_for(deployment_dir)
    role = "graphite-confirmation-v1"
    item = cf.confirmation_set(role)
    with pytest.raises(cf.ConfirmationRefused) as caught:
        cf.export_prior(role, config=config, out=tmp_path / "early.json")
    assert caught.value.code == "confirmation_prior_not_sealed:" + role
    sealed = target.seal_batch(
        role, count=item.batch_size, duplicates=item.hidden_duplicates
    )
    out = tmp_path / "prior.json"
    result = cf.export_prior(role, config=config, out=out)
    assert (result["role"], result["cases"]) == (role, item.cases)
    assert out.stat().st_mode & 0o077 == 0
    exported = json.loads(out.read_text())["cases"]
    duplicates = dict(sealed.batch.duplicates)
    expected = [dict(x) for c, x in sealed.batch.cases if c not in duplicates]
    assert [case["inputs"] for case in exported] == expected
    assert "inputs" not in json.dumps(result)
    for path, code in (
        (out, "confirmation_private_prior_exists"),
        (REPOSITORY / "tmp-prior.json", "confirmation_private_prior_inside_repository"),
    ):
        with pytest.raises(cf.ConfirmationRefused) as caught:
            cf.export_prior(role, config=config, out=path)
        assert caught.value.code == code


def test_the_quiz_reads_the_same_practice_points_without_the_safety_code():
    """quiz_stratum pins the practice decision set's conditions itself
    instead of importing practice-safety code (the hidden path stays apart
    from practice feedback); the two must name the same points."""
    from pathlib import Path

    from carbon.battery import practice_safety as ps
    from carbon.battery import quiz_stratum as qs

    repository = Path(__file__).resolve().parents[2]
    sums = (repository / ps.DECISION_SET_PATH / "SHA256SUMS").read_text()
    pinned = dict(reversed(line.split()) for line in sums.splitlines())
    assert pinned["conditions.json"] == qs.PRACTICE_CONDITIONS_SHA256
    expected = [
        (float(t), float(s)) for t, s in ps.load_decision_set(repository).conditions
    ]
    assert sorted(qs.practice_conditions(repository)) == sorted(expected)
