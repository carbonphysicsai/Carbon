"""Test suite v1 of the Challenge Roadmap (§03): its registry, its pin, the
per-challenge suite maps and the coverage runner; and Graphite's
per-pipeline-stage permission ledger. Landed from CHALLENGE-PROTOCOL-03 under
OWNER-GRAPHITE-ATTACKER-01 (slice AT-A)."""

from __future__ import annotations

import copy
import json
import re

import pytest

from carbon.agent_campaign.attack.adapter import TRACK_A_CHECKS
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.challenge_pipeline import graphite_ledger, suite
from carbon.challenge_readiness import admission

REPOSITORY = suite.REPOSITORY
BATTERY = "battery-fastcharge-ageing-development-v1"


def _maps():
    return sorted(p.stem for p in suite.MAPS.glob("*.json"))


def test_the_suite_registers_the_roadmaps_vectors_and_studies():
    s = suite.load_suite()
    assert s["status"] == "DRAFT" and s["severity"]["status"] == "DRAFT"
    assert [v["name"] for v in s["track_a"]] == [
        "Admission",
        "Execution isolation",
        "Protected-data separation",
        "Resource enforcement",
        "Clean reconstruction",
        "Artifact integrity",
        "Evidence integrity",
        "Adaptive exposure",
    ]
    assert [b["id"] for b in s["track_b"]] == ["B1", "B2", "B3", "B4"]
    battery = suite.load_map(BATTERY)
    for vector in s["track_a"]:
        own = battery["track_a"][vector["id"]]
        assert vector["checks"].get("generic") or own["checks"], vector["id"]
        assert vector["gaps"] or own["gaps"], vector["id"]


def test_the_shared_suite_names_no_challenge_and_every_map_fits_it():
    text = suite.SUITE.read_text().lower()
    assert "battery" not in text and "cold plate" not in text
    assert suite.GROUPS == ("generic", "sandbox")
    assert BATTERY in _maps()
    for challenge in _maps():
        suite_map = suite.load_map(challenge)
        assert suite_map["challenge"] == challenge
        assert suite_map["environment_groups"], challenge


def test_every_vector_states_its_place_on_the_ladder():
    s = suite.load_suite()
    code = {v["id"]: v["ladder"]["participant_code_from_level"] for v in s["track_a"]}
    assert code == {
        "A1": 4, "A2": 4, "A3": None, "A4": 4,
        "A5": None, "A6": None, "A7": None, "A8": None,
    }  # fmt: skip
    assert all(v["ladder"]["applies_from_level"] == 0 for v in s["track_a"])
    assert "NOT_RUN" in s["ladder"]["rule"]


def test_every_admission_check_is_mapped_to_the_suite():
    s = suite.load_suite()
    a = {c for v in s["track_a"] for c in v["admission_checks"]}
    b = {c for v in s["track_b"] for c in v["admission_checks"]}
    assert a == admission.CHECKS["construction_integrity"]
    assert b <= admission.CHECKS["engineering_value"]
    # Untouched confirmation is the frozen run itself, and customer evidence is
    # outside the in-house pipeline; every other engineering-value check maps.
    assert admission.CHECKS["engineering_value"] - b == {
        "untouched_confirmation",
        "customer_evidence_and_limits",
    }


def test_every_cited_check_exists():
    s = suite.load_suite()
    nodes = [n for v in s["track_a"] for group in v["checks"].values() for n in group]
    for challenge in _maps():
        for entry in suite.load_map(challenge)["track_a"].values():
            nodes += entry["checks"] + entry["sandbox"]
    for node in nodes:
        path, name = node.split("::")
        text = (REPOSITORY / path).read_text()
        assert re.search(rf"^def {name}\(", text, re.MULTILINE), node


def test_the_pin_moves_with_the_suite(tmp_path):
    s = json.loads(suite.SUITE.read_text())
    assert suite.digest() == suite.digest(suite.SUITE)
    s["severity"]["levels"]["low"] += " Changed."
    other = tmp_path / "suite.json"
    other.write_text(json.dumps(s))
    assert suite.digest(other) != suite.digest()


def test_a_malformed_suite_or_map_is_refused(tmp_path):
    s = json.loads(suite.SUITE.read_text())
    for change in (
        lambda d: d["track_a"].pop(),
        lambda d: d["track_a"][0]["checks"].update(elsewhere=[]),
        # A challenge's own checks never go into the shared suite.
        lambda d: d["track_a"][0]["checks"].update(battery=[]),
        lambda d: d["track_a"][0].pop("ladder"),
        lambda d: d["severity"]["levels"].pop("low"),
    ):
        bad = copy.deepcopy(s)
        change(bad)
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            suite.load_suite(path)
    battery = json.loads((suite.MAPS / f"{BATTERY}.json").read_text())
    maps = tmp_path / "maps"
    maps.mkdir()
    for change in (
        lambda d: d["track_a"].pop("A8"),
        lambda d: d.update(suite_version="suite-v0"),
        lambda d: d.update(challenge="someone-else"),
        lambda d: d["track_b"].pop("B4"),
    ):
        bad = copy.deepcopy(battery)
        change(bad)
        (maps / f"{BATTERY}.json").write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            suite.load_map(BATTERY, maps)
    with pytest.raises(ValueError, match="no suite map"):
        suite.load_map("synthetic-heat-v1", maps)


def _synthetic(tmp_path, level):
    """A second challenge, not battery: its own map and pipeline record."""
    tests = tmp_path / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_fake.py").write_text(
        "import pytest\n"
        "def test_holds():\n    assert True\n"
        "def test_breaks():\n    assert False\n"
        "def test_skips():\n    pytest.skip('needs a container')\n"
        "@pytest.mark.parametrize('n', [1, 2])\n"
        "def test_param(n):\n    assert n\n"
    )
    s = json.loads(suite.SUITE.read_text())
    for vector in s["track_a"]:
        vector["checks"] = {"generic": []}
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(s))
    entry = {"checks": [], "sandbox": [], "gaps": []}
    track_a = {f"A{i}": copy.deepcopy(entry) for i in range(1, 9)}
    track_a["A1"]["checks"] = [
        "tests/test_fake.py::test_holds",
        "tests/test_fake.py::test_param",
    ]
    track_a["A2"]["checks"] = [
        "tests/test_fake.py::test_holds",
        "tests/test_fake.py::test_breaks",
    ]
    track_a["A3"]["checks"] = ["tests/test_fake.py::test_skips"]
    track_a["A4"]["checks"] = ["tests/test_fake.py::test_missing"]
    track_a["A5"]["sandbox"] = ["tests/test_fake.py::test_holds"]
    maps = tmp_path / "maps"
    maps.mkdir(exist_ok=True)
    (maps / "synthetic-heat-v1.json").write_text(
        json.dumps(
            {
                "schema": "carbon.challenge-pipeline.suite-map.v1",
                "suite_version": s["suite_version"],
                "challenge": "synthetic-heat-v1",
                "family": "f03",
                "environment_groups": ["science-jax"],
                "track_a": track_a,
                "track_b": {b["id"]: {} for b in s["track_b"]},
                "exam": {},
            }
        )
    )
    records = tmp_path / "records"
    records.mkdir(exist_ok=True)
    (records / "f03.json").write_text(
        json.dumps({"construction": {"challenge": "synthetic-heat-v1", "level": level}})
    )
    return {"suite_path": suite_path, "maps": maps, "records": records}


def test_the_runner_reports_pass_finding_candidate_and_not_run(tmp_path):
    paths = _synthetic(tmp_path, level=0)
    report = suite.run("synthetic-heat-v1", repository=tmp_path, **paths)
    status = {v["id"]: v["status"] for v in report["vectors"]}
    assert status["A1"] == "PASS"
    assert status["A2"] == "FINDING_CANDIDATE"
    assert status["A3"] == "NOT_RUN" and status["A4"] == "NOT_RUN"
    assert status["A5"] == "NOT_RUN"  # its only check is a sandbox check, not asked for
    # test_breaks is cited by A2, so nothing uncited failed here.
    assert report["uncited_failures"] == []
    assert report["suite_digest"] == suite.digest(paths["suite_path"])
    assert report["map_digest"] == suite.map_digest("synthetic-heat-v1", paths["maps"])
    assert report["claims"] == {"security_acceptance": False, "graded": False}
    assert set(report["environment"]["missing_groups"]) <= {"science-jax"}
    with_sandbox = suite.run(
        "synthetic-heat-v1", sandbox=True, repository=tmp_path, **paths
    )
    assert {v["id"]: v["status"] for v in with_sandbox["vectors"]}["A5"] == "PASS"


def test_a_frozen_run_records_the_attack_knowledge_store_it_used(tmp_path):
    """The suite version pins the attack-knowledge store: the run's record
    carries the store digest from the pin it was given (`ReadOnlyView.
    suite_pin()`), None without one, and a malformed pin is refused."""
    paths = _synthetic(tmp_path, level=0)
    store = "sha256:" + "ab" * 32
    pin = {
        "schema": suite.ATTACK_KNOWLEDGE_PIN_SCHEMA,
        "attack_knowledge_digest": store,
    }
    report = suite.run(
        "synthetic-heat-v1", repository=tmp_path, attack_knowledge=pin, **paths
    )
    assert report["schema"] == suite.RUN_SCHEMA
    assert report["attack_knowledge_digest"] == store
    assert (
        suite.run("synthetic-heat-v1", repository=tmp_path, **paths)[
            "attack_knowledge_digest"
        ]
        is None
    )
    for bad in ({**pin, "schema": "x"}, {**pin, "attack_knowledge_digest": "x"}, {}):
        with pytest.raises(ValueError, match="attack_knowledge_pin_malformed"):
            suite.run(
                "synthetic-heat-v1", repository=tmp_path, attack_knowledge=bad, **paths
            )


def test_participant_code_is_not_run_below_its_level(tmp_path):
    at_zero = suite.run(
        "synthetic-heat-v1", repository=tmp_path, **_synthetic(tmp_path, level=0)
    )
    code = {v["id"]: v["participant_code"] for v in at_zero["vectors"]}
    assert at_zero["construction_level"] == 0
    assert {k: c["status"] for k, c in code.items() if c} == {
        "A1": "NOT_RUN",
        "A2": "NOT_RUN",
        "A4": "NOT_RUN",
    }
    assert code["A3"] is None
    at_four = suite.run(
        "synthetic-heat-v1", repository=tmp_path, **_synthetic(tmp_path, level=4)
    )
    assert {
        v["id"]: v["participant_code"]["status"]
        for v in at_four["vectors"]
        if v["participant_code"]
    } == {
        "A1": "IN_SCOPE",
        "A2": "IN_SCOPE",
        "A4": "IN_SCOPE",
    }


def test_the_committed_coverage_report_is_for_this_suite_and_map():
    """The pin: change the suite or battery's map and the report must be re-run."""
    report = json.loads(
        (
            REPOSITORY
            / "docs/development/challenge_pipeline/SUITE_V1_BATTERY_COVERAGE.json"
        ).read_text()
    )
    assert report["suite_digest"] == suite.digest()
    assert report["challenge"] == BATTERY
    assert report["map_digest"] == suite.map_digest(BATTERY)
    assert report["construction_level"] == 0
    assert report["environment"]["missing_groups"] == []
    assert report["uncited_failures"] == []
    code = {v["id"]: v["participant_code"] for v in report["vectors"]}
    assert all(c["status"] == "NOT_RUN" for c in code.values() if c)
    # Its provenance is recorded: the commit and environment it ran in, and the
    # attack-knowledge store it was frozen under (None: it used none). It was
    # run on main through the canonical runner (OWNER-GRAPHITE-TEST-WAVE-02).
    assert report["schema"] == suite.RUN_SCHEMA
    assert "attack_knowledge_digest" in report
    assert re.fullmatch(r"[0-9a-f]{40}", report["commit"])
    assert report["environment"]["canonical"] == (
        "ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64"
    )
    assert report["claims"] == {"security_acceptance": False, "graded": False}


def test_every_attack_engine_check_meets_the_suites_vectors():
    """The engine's families name one of the eight checks; each check is
    exercised by at least one suite vector, A1 to A8."""
    by_check = suite.vectors_by_check()
    assert tuple(sorted(by_check)) == tuple(sorted(TRACK_A_CHECKS))
    assert by_check["baseline_and_permission_ablation"] == ["A1"]
    assert by_check["construction_evaluation_isolation"] == ["A2", "A3"]
    assert by_check["artifact_and_dependency_attacks"] == ["A1", "A6"]
    assert all(v in suite.VECTORS for vs in by_check.values() for v in vs)


def test_a_vector_without_admission_checks_maps_nothing(tmp_path):
    """load_suite accepts a vector with no `admission_checks` key when the
    others cover the eight; vectors_by_check reads it the same way."""
    s = json.loads(suite.SUITE.read_text())
    vectors = s["track_a"]
    spare = next(
        v
        for v in vectors
        if set(v["admission_checks"])
        <= {c for o in vectors if o is not v for c in o["admission_checks"]}
    )
    del spare["admission_checks"]
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(s))
    loaded = suite.load_suite(path)
    by_check = suite.vectors_by_check(loaded)
    assert set(by_check) == set(TRACK_A_CHECKS)
    assert spare["id"] not in {v for vs in by_check.values() for v in vs}


def test_a_suite_that_drops_an_admission_check_is_refused(tmp_path):
    s = json.loads(suite.SUITE.read_text())
    s["track_a"][7]["admission_checks"] = []  # A8 carried adaptive feedback alone
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(s))
    with pytest.raises(ValueError, match="eight admission checks"):
        suite.load_suite(path)


# -- Graphite's per-pipeline-stage permission ledger ---------------------------


def test_the_ledger_names_pipeline_stages_and_graphites_roles():
    ledger = graphite_ledger.load_ledger()
    assert tuple(ledger["pipeline_stages"]) == graphite_ledger.PIPELINE_STAGES
    # Renamed from `stages`: a research session's stage is another thing.
    assert "stages" not in ledger
    roles = {r for row in ledger["pipeline_stages"].values() for r in row["roles"]}
    assert roles <= {r.value for r in RoleName}
    assert (REPOSITORY / ledger["protocol"]).is_file()
    assert graphite_ledger.graphite_may("test_iterate", RoleName.ATTACKER)
    assert graphite_ledger.graphite_may("test_iterate", "attacker")
    assert not graphite_ledger.graphite_may("design", RoleName.ATTACKER)
    assert not any(
        graphite_ledger.graphite_may("frozen_run", role) for role in RoleName
    )
    assert not graphite_ledger.graphite_may("no_such_stage", RoleName.WRITER)


def test_a_malformed_ledger_is_refused(tmp_path):
    good = json.loads(graphite_ledger.LEDGER.read_text())
    for change, match in (
        (
            lambda d: d.update(schema="carbon.challenge-pipeline.graphite-ledger.v1"),
            "schema",
        ),
        (lambda d: d.update(stages=d.pop("pipeline_stages")), "pipeline stages"),
        (lambda d: d["pipeline_stages"].pop("rank"), "pipeline stages"),
        (
            lambda d: d["pipeline_stages"]["frozen_run"]["roles"].append("attacker"),
            "frozen run",
        ),
        (
            lambda d: d["pipeline_stages"]["design"].update(roles="planner"),
            "lists its roles",
        ),
    ):
        bad = copy.deepcopy(good)
        change(bad)
        path = tmp_path / "ledger.json"
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match=match):
            graphite_ledger.load_ledger(path)
