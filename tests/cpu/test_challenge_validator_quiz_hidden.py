"""The near-limit quiz inside every hidden batch (VALIDATOR-19 slice Q, part 2).

The producer seals each screening batch with its private quiz, committed by
digest and shipped inside the signed package; import-only validators verify
and keep it, and report the quiz's measures operator-only after scoring.
The quiz gates nothing: the miner outcome and the score are byte-identical
with and without it.

Synthetic roots, scripted truth solves (`tuning_quiz.truth`), a scripted
panel backend and `DirectBackend`: no container, network, chain or spend.
Not a security audit (AGENTS.md §13).
"""

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import refs  # noqa: F401 - fixture
from test_challenge_validator_acceptance import real_package
from test_challenge_validator_answer_key import battery_validator
from test_challenge_validator_rotation import EVERY
from test_challenge_validator_tuning_quiz import PANEL, truth
from test_graphite_hidden_score import knn

from carbon.battery import quiz_stratum as qs
from carbon.battery import worker
from carbon.battery.challenge import INPUTS
from carbon.battery.value import quiz as qz
from carbon.battery.worker import WorkerFailure
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import battery_quiz, tuning
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.battery_quiz import BatteryQuizSource

SIZE = 12


@pytest.fixture
def small(monkeypatch):
    """Registered sizes scaled down, so a whole quiz runs in a test."""
    monkeypatch.setattr(qz, "Q2_POOL", 20)
    monkeypatch.setattr(qz, "Q2_N", 8)
    monkeypatch.setattr(qz, "Q3_K", 3)


class PanelBackend:
    """The registered panel, scripted: each member predicts the scripted
    truth with its own plating bias. Counts rebuilds and inferences."""

    def __init__(self):
        self.identity = {"backend": "SCRIPTED_PANEL", "validator_path": False}
        self.rebuilt, self.inferred = [], []

    def reconstruct(self, identity, recipe, seed):
        member = identity.removeprefix(f"quiz-panel-v{qz.PANEL_VERSION}-")
        self.rebuilt.append(member)
        return member.encode(), {}

    def infer(self, identity, state, inputs):
        member = state.decode()
        self.inferred.append(member)
        bias = -0.006 + 0.012 * PANEL.index(member) / (len(PANEL) - 1)
        predictions = {}
        for case_id, x in inputs.items():
            outputs = truth({"case_id": case_id, **x}, ())
            outputs["plating_margin_v"] += bias
            predictions[case_id] = outputs
        return predictions


class Truth:
    """The truth container's contract, scripted and resumable: every job in
    `/work/jobs.json` gets a closed-form terminal record. With `short`, the
    first round's first five Q3 conditions plate at every candidate."""

    def __init__(self, short=False):
        self.short = short
        self.infeasible = set()

    def __call__(self, command, check):
        mount = next(a for a in command if a.endswith(":/work:rw"))
        work = Path(mount.removesuffix(":/work:rw"))
        draws = work / pr.Producer.QUIZ_DRAWS
        if self.short and draws.exists():
            value = json.loads(draws.read_text())
            if value["round"] == 1:
                self.infeasible.update(
                    tuple(c["condition"]) for c in value["draws"]["q3"][:5]
                )
        jobs = json.loads((work / "jobs.json").read_text())["jobs"]
        path = work / "records.jsonl"
        done = {json.loads(line)["case_id"] for line in path.read_text().splitlines()}
        with path.open("a") as out:
            for job in jobs:
                if job["case_id"] in done:
                    continue
                record = {
                    "case_id": job["case_id"],
                    "inputs": {k: job[k] for k in INPUTS},
                    "status": "OK",
                    "outputs": truth(job, self.infeasible),
                }
                out.write(json.dumps(record) + "\n")

        class Done:
            returncode = 0

        return Done()


def panel_file(directory):
    path = directory / "panel.json"
    path.write_text(
        json.dumps(
            {
                "schema": tuning.PANEL_SCHEMA,
                "members": [
                    {"member": m, "kind": "RECONSTRUCTED", "strategy": knn(), "seed": 0}
                    for m in PANEL
                ],
            }
        )
    )
    return path


def quiz_producer(tmp_path, *, short=False):
    source = BatteryQuizSource(
        battery_validator(tmp_path / "producer-state"),
        overlay=tmp_path / "overlay",
        runner=Truth(short),
        panel_backend=PanelBackend(),
    )
    key = ak.ProducerKey.create(tmp_path / "producer.key")
    producer = pr.Producer(
        tmp_path / "producer",
        [source],
        signing_key=key,
        quiz={"panel": str(panel_file(tmp_path))},
    )
    real_draw = producer.draw
    producer.draw = lambda c, role, *, kind, size=None: real_draw(
        c, role, kind=kind, size=SIZE
    )
    return producer, source, key


def sealed(producer, source, role):
    drawn = producer.draw(source.challenge_id, role, kind="screening")
    producer.solve(source.challenge_id, drawn["fingerprint"])
    return drawn, producer.seal(source.challenge_id, drawn["fingerprint"])


def package_of(producer, source, fingerprint, slot):
    producer.schedule(source.challenge_id, fingerprint, slot, block=0)
    result = producer.publish(source.challenge_id, fingerprint)
    directory = producer.directory / "outbox" / source.challenge_id
    return json.loads((directory / result["file"]).read_text())


# -- the producer ---------------------------------------------------------------------------


def test_the_producer_seals_a_screening_batch_with_its_quiz(tmp_path, small):
    producer, source, key = quiz_producer(tmp_path)
    drawn, commitment = sealed(producer, source, "pscreen-Q01")
    assert drawn["quiz_jobs"] == qz.Q2_POOL * 4 + (qz.Q3_K + 4) * len(qz.q3_candidates())
    work = producer._work(source.challenge_id, drawn["fingerprint"])
    quiz = producer._quiz(source.challenge_id, drawn["fingerprint"])
    document = quiz["document"]
    assert document["role"] == "pscreen-Q01"
    assert (len(document["q2"]), len(document["q3"])) == (qz.Q2_N, qz.Q3_K)
    assert document["panel_version"] == qz.PANEL_VERSION
    assert commitment["quiz_panel_version"] == qz.PANEL_VERSION
    assert commitment["quiz_digest"] == qs.digest(document)
    assert {k: commitment[k] for k in ("quiz_digest", "quiz_references_digest")} == (
        pr.quiz_digests(quiz)
    )
    # Q2 is chosen from the panel's predictions only, as the tuning set's.
    drawn_q2 = {
        c["case_id"]: c
        for c in json.loads((work / "quiz-draws.json").read_text())["draws"]["q2"]
    }
    assert {c["case_id"] for c in document["q2"]} <= set(drawn_q2)
    assert set(quiz["references"]) == set(qs.inputs(document))
    # The quiz is committed to the producer's seed journal before any use.
    journal = source.adapter.target.journal
    entry = journal.public()[-1]
    assert (entry["kind"], entry["role"], entry["digest"]) == (
        "quiz",
        "pscreen-Q01",
        qs.digest(document),
    )
    # Its quiz cases never enter the batch's own references.
    stored = source.adapter.target.store.references([drawn["fingerprint"]])
    assert not set(stored) & set(qs.inputs(document))
    # The public record names no quiz case or scenario.
    public = (producer.directory / "journal.jsonl").read_text() + json.dumps(commitment)
    for case_id in qs.inputs(document):
        assert case_id not in public
    for scenario in document["q3"]:
        assert scenario["scenario_id"] not in public
    # The package carries it beside the batch.
    value = package_of(producer, source, drawn["fingerprint"], 1)
    signed, payload = ak.verify(value, key.public_key)
    assert payload["quiz"] == quiz
    assert set(payload) == {"document", "references", "reconstruction_salt", "quiz"}
    assert signed["quiz_digest"] == commitment["quiz_digest"]
    # The panel is rebuilt once per version, then cached on the producer host.
    backend = source.panel_backend
    assert sorted(backend.rebuilt) == sorted(PANEL)
    sealed(producer, source, "pscreen-Q02")
    assert sorted(backend.rebuilt) == sorted(PANEL)
    assert len(backend.inferred) == 2 * len(PANEL)
    for path in producer.directory.rglob("*"):
        assert path.stat().st_mode & 0o077 == 0, path


def test_finalists_and_unconfigured_producers_carry_no_quiz(tmp_path, small):
    producer, source, _key = quiz_producer(tmp_path)
    drawn = producer.draw(source.challenge_id, "pfinal-S9", kind="finalist")
    assert "quiz_jobs" not in drawn
    producer.solve(source.challenge_id, drawn["fingerprint"])
    commitment = producer.seal(source.challenge_id, drawn["fingerprint"])
    assert not set(pr.QUIZ_COMMITMENT_FIELDS) & set(commitment)
    with pytest.raises(pr.ProducerRefused) as refused:
        source.quiz_draw(drawn["fingerprint"], 1)
    assert refused.value.code == "producer_quiz_kind_refused"
    plain = pr.Producer(tmp_path / "plain", [source])
    drawn = plain.draw(source.challenge_id, "pscreen-P", kind="screening", size=SIZE)
    assert set(drawn) == {"fingerprint", "jobs"}
    for bad in ({"panel": ""}, {"panel": "x", "margin": 1}, "x"):
        with pytest.raises(pr.ProducerRefused):
            pr.Producer(tmp_path / "bad", [source], quiz=bad)


def test_infeasible_q3_scenarios_take_another_round_on_the_next_tick(tmp_path, small):
    producer, source, key = quiz_producer(tmp_path, short=True)
    challenge = source.challenge_id
    first = producer.tick(100)[challenge]
    # The batch's references are complete, but Q3 has too few feasible
    # scenarios: the round advances and the slot is left unfilled.
    assert (first["filled"], first["unfilled"]) == ([], [1])
    rounds = [e for e in producer.journal.entries() if e["event"] == "quiz_round"]
    assert [(e["round"]) for e in rounds] == [2]
    assert "inputs" not in json.dumps(rounds)
    again = producer.tick(101)[challenge]
    assert again["filled"] == [1]
    unfilled = [e for e in producer.journal.entries() if e["event"] == "slot_unfilled"]
    assert [(e["slot"], e["kind"]) for e in unfilled] == [(1, "screening")]
    [path] = [
        p
        for p in (producer.directory / "outbox" / challenge).glob("*.json")
        if ak.verify(json.loads(p.read_text()), key.public_key)[0]["kind"]
        == "screening"
    ]
    _commitment, payload = ak.verify(json.loads(path.read_text()), key.public_key)
    document = payload["quiz"]["document"]
    assert document["redraws"]["q3_infeasible"] == 5
    assert len(document["q3"]) == qz.Q3_K
    infeasible = source.runner.infeasible
    assert not any(tuple(s["condition"]) in infeasible for s in document["q3"])
    for scenario in document["q3"]:
        assert not qs.is_protected(
            scenario["condition"], qs.protected_conditions(REPOSITORY)
        )


def test_a_changed_quiz_is_never_published(tmp_path, small):
    producer, source, _key = quiz_producer(tmp_path)
    drawn, _commitment = sealed(producer, source, "pscreen-T")
    path = producer._work(source.challenge_id, drawn["fingerprint"]) / "quiz.json"
    quiz = json.loads(path.read_text())
    quiz["document"]["q2"] = quiz["document"]["q2"][1:]
    path.unlink()
    pr._write_once(path, quiz)
    producer.schedule(source.challenge_id, drawn["fingerprint"], 1, block=0)
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.publish(source.challenge_id, drawn["fingerprint"])
    assert refused.value.code == "producer_commitment_changed"


# -- the validator's import -----------------------------------------------------------------


@pytest.fixture
def shipped(tmp_path, small):
    producer, source, key = quiz_producer(tmp_path)
    drawn, _commitment = sealed(producer, source, "pscreen-I")
    value = package_of(producer, source, drawn["fingerprint"], 1)
    return {"value": value, "key": key}


def test_a_validator_imports_and_keeps_the_quiz(tmp_path, shipped):
    commitment, payload = ak.verify(shipped["value"], shipped["key"].public_key)
    adapter = battery_validator(tmp_path / "validator", import_only=True)
    adapter.import_answer_key(commitment, payload)
    held = adapter.target.store.quiz(commitment["fingerprint"])
    assert held["document"] == payload["quiz"]["document"]
    assert held["quiz_digest"] == commitment["quiz_digest"]
    assert held["panel_version"] == commitment["quiz_panel_version"]
    assert adapter.holds_answer_key(commitment)
    # Importing again is idempotent; the quiz never joins the batch's cases.
    adapter.import_answer_key(commitment, payload)
    row = adapter.target.store.batch(commitment["fingerprint"])
    assert not {c["case_id"] for c in row["document"]["cases"]} & set(
        qs.inputs(held["document"])
    )


def _resign(shipped, change):
    value = json.loads(json.dumps(shipped["value"]))
    commitment, payload = value["manifest"]["commitment"], value["payload"]
    change(commitment, payload)
    return ak.verify(
        ak.package(shipped["key"], commitment, payload), shipped["key"].public_key
    )


def _first_ref(_c, p):
    case = min(p["quiz"]["references"])
    p["quiz"]["references"][case]["status"] = "REFERENCE_TIMEOUT"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (_first_ref, "answer_key_quiz_mismatch"),
        (lambda c, p: p["quiz"]["document"]["q2"].pop(), "answer_key_quiz_mismatch"),
        (lambda c, p: c.update(quiz_digest="sha256:" + "0" * 64), "answer_key_quiz_mismatch"),
        (lambda c, p: c.update(quiz_panel_version=2), "answer_key_quiz_mismatch"),
        (lambda c, p: p.pop("quiz"), "answer_key_quiz_mismatch"),
        (lambda c, p: c.pop("quiz_digest"), "answer_key_quiz_mismatch"),
        (lambda c, p: p["quiz"]["document"].pop("redraws"), "answer_key_quiz_malformed"),
        (lambda c, p: p["quiz"]["references"].popitem(), "answer_key_quiz_mismatch"),
    ],
)  # fmt: skip
def test_a_tampered_quiz_is_refused_at_import(tmp_path, shipped, change, code):
    """Correctly signed, but not the committed quiz: nothing is imported."""
    commitment, payload = _resign(shipped, change)
    adapter = battery_validator(tmp_path / "validator", import_only=True)
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        adapter.import_answer_key(commitment, payload)
    assert refused.value.code == code
    assert adapter.target.store.batches() == []


# -- the operator-only quiz report ----------------------------------------------------------


def synthetic_quiz(role):
    """A small quiz over two scenarios and four Q2 cases, with references."""
    contract = qs.contract(REPOSITORY)
    q2 = [
        {
            "case_id": f"{role}-quiz-{i}",
            "inputs": {"c1": 1.0, "c2": 0.5, "t_amb_c": 20.0, "soc0": soc0},
        }
        for i, soc0 in enumerate((0.1, 0.15, 0.2, 0.25))
    ]
    q3 = []
    for i, condition in enumerate(([12.5, 0.21], [33.25, 0.4])):
        entry = {"scenario_id": f"q3-{role}-{i}", "condition": condition}
        q3.append({**entry, "grid": qz.q3_grid(contract, qs.scenario(entry))})
    document = qs.document(role, 1, q2, q3, {"q3_infeasible": 0, "q3_protected": 0})
    references = {
        case_id: {
            "case_id": case_id,
            "status": "OK",
            "inputs": x,
            "outputs": truth({"case_id": case_id, **x}, ()),
        }
        for case_id, x in qs.inputs(document).items()
    }
    return {"document": document, "references": references}


def quiz_package(key, identities, refs, role, slot, *, quiz):  # noqa: F811
    value = real_package(key, identities, refs, role, slot)
    if not quiz:
        return value
    commitment, payload = ak.verify(value, key.public_key)
    added = synthetic_quiz(role)
    commitment = {
        **commitment,
        **pr.quiz_digests(added),
        "quiz_panel_version": added["document"]["panel_version"],
    }
    return ak.package(key, commitment, {**payload, "quiz": added})


class QuizInferFails(worker.DirectBackend):
    def infer(self, identity, state, inputs):
        if identity.startswith("quiz-"):
            raise WorkerFailure("injected", candidate=False)
        return super().infer(identity, state, inputs)


def test_the_quiz_is_reported_operator_only_and_changes_no_score(
    tmp_path,
    refs,  # noqa: F811
):
    from carbon.agent_campaign.graphite import hidden_score
    from carbon.agent_campaign.graphite.hidden_score import HiddenPool
    from carbon.battery.pool_store import canonical

    key = ak.ProducerKey.create(tmp_path / "producer.key")
    names = ("quiz-a", "quiz-b", "plain", "quiz-fails")
    validators = {}
    for name in names:
        adapter = battery_validator(tmp_path / name, import_only=True)
        adapter.target.allow_published_cases = True
        validators[name] = adapter
    identities = validators["plain"].identities()
    roles = [(f"pscreen-B0{slot - 1}", slot) for slot in (1, 2, 3)]
    packages = {
        quiz: [
            quiz_package(key, identities, refs, role, slot, quiz=quiz)
            for role, slot in roles
        ]
        for quiz in (True, False)
    }
    for name, adapter in validators.items():
        values = packages[name != "plain"]
        if name == "quiz-b":
            values = values[::-1]  # another import order
        for value in values:
            adapter.import_answer_key(*ak.verify(value, key.public_key))
        adapter.target.store.open_pool()
    validators["quiz-fails"].target.backend = QuizInferFails(REPOSITORY)
    block = 3 * EVERY + 5
    results = {
        name: HiddenPool(adapter.target, run_id="quiz", clock=lambda: block).submit(
            "proposal", knn(7)
        )
        for name, adapter in validators.items()
    }
    views = {name: canonical(view) for name, (view, _record) in results.items()}
    records = {name: record for name, (_view, record) in results.items()}
    # The miner outcome and the score are byte-identical with and without a
    # quiz, and whatever the quiz's own inference did.
    assert len(set(views.values())) == 1
    assert "quiz" not in views["quiz-a"]
    sid = records["plain"]["submission_id"]
    scores = {
        name: canonical(adapter.target.store.score(sid))
        for name, adapter in validators.items()
    }
    assert len(set(scores.values())) == 1
    assert (
        len({canonical(r["aggregate"]) for r in records.values()}) == 1
        and records["plain"]["aggregate"]["score"] is not None
    )
    for adapter in validators.values():
        assert adapter.target.store.submission(sid)["state"] == "SCORED"
    # The operator record carries the quiz; two validators measure it alike.
    assert records["plain"]["quiz"] is None
    quiz = records["quiz-a"]["quiz"]
    assert quiz == records["quiz-b"]["quiz"]
    assert quiz["state"] == "MEASURED" and quiz["gates"] == "NONE"
    assert set(quiz["batches"]) == set(records["quiz-a"]["active_batches"])
    for batch in quiz["batches"].values():
        assert set(batch) == {"quiz_digest", "panel_version", "q2", "q3"}
        assert set(batch["q2"]) == {"false_feasible", "plating_fa", "false_infeasible"}
        assert len(batch["q3"]["outcomes"]) == 2
    assert set(quiz["pooled"]["q3"]) >= {"false_feasible", "regret", "over_caution"}
    full = validators["quiz-a"].score_record(sid)
    assert full["quiz"] == quiz
    # Quiz cases never enter the accuracy rows or the scored predictions.
    quiz_ids = {
        c
        for f in records["quiz-a"]["active_batches"]
        for c in qs.inputs(validators["quiz-a"].target.store.quiz(f)["document"])
    }
    assert not {r["case_id"] for r in full["cases"]} & quiz_ids
    assert not set(full["predictions"]) & quiz_ids
    assert set(validators["quiz-a"].target.store.predictions(sid, quiz_ids)) == set()
    # A quiz inference failure is the quiz's own FAILED_INFRA.
    failed = records["quiz-fails"]["quiz"]
    assert (failed["state"], failed["code"]) == ("FAILED_INFRA", "injected")
    # Without installed measures the daemon measures nothing; the operator's
    # `battery_quiz report` retries the failure, with the same measures.
    target = validators["quiz-fails"].target
    target.backend = worker.DirectBackend(REPOSITORY)
    target.quiz_measures = None
    assert target.quiz_report(sid) is None
    assert battery_quiz.report(target) == {"scored": 1, "states": {"MEASURED": 1}}
    assert target.store.quiz_report(sid) == quiz
    # The run report's quiz table (`report()["quiz"]`), per pool version and
    # descriptive only. Called directly: `report` itself fails on main for
    # any primary record (`_variant_ranking` is handed the device-class map).
    table = hidden_score._quiz_table(
        [{**records["quiz-a"], "proposal_id": "p1", "kind": "proposal"}]
    )
    assert table["gates"] == "NONE" and table["descriptive_only"]
    [row] = table["by_pool_version"][str(records["quiz-a"]["pool_version"])]
    assert row["state"] == "MEASURED" and row["panel_versions"] == [1]
    assert row["q2"] == quiz["pooled"]["q2"]
    assert hidden_score._quiz_table([records["plain"]])["by_pool_version"] == {}
