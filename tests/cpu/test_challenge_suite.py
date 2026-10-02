"""Test suite v1 of the Challenge Roadmap (§03): its registry, its pin and its
coverage runner."""

from __future__ import annotations

import copy
import json
import re

import pytest

from carbon.challenge_pipeline import suite
from carbon.challenge_readiness import admission

REPOSITORY = suite.REPOSITORY


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
    for vector in s["track_a"]:
        assert vector["checks"].get("generic") or vector["checks"].get("battery")
        assert vector["gaps"], vector["id"]


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
    for vector in s["track_a"]:
        for group in vector["checks"].values():
            for node in group:
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


def test_a_malformed_suite_is_refused(tmp_path):
    s = json.loads(suite.SUITE.read_text())
    for change in (
        lambda d: d["track_a"].pop(),
        lambda d: d["track_a"][0]["checks"].update(elsewhere=[]),
        lambda d: d["severity"]["levels"].pop("low"),
    ):
        bad = copy.deepcopy(s)
        change(bad)
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            suite.load_suite(path)


def test_the_runner_reports_pass_finding_candidate_and_not_run(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
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
        vector["checks"] = {"generic": [], "battery": []}
    s["track_a"][0]["checks"]["battery"] = [
        "tests/test_fake.py::test_holds",
        "tests/test_fake.py::test_param",
    ]
    s["track_a"][1]["checks"]["battery"] = [
        "tests/test_fake.py::test_holds",
        "tests/test_fake.py::test_breaks",
    ]
    s["track_a"][2]["checks"]["battery"] = ["tests/test_fake.py::test_skips"]
    s["track_a"][3]["checks"]["battery"] = ["tests/test_fake.py::test_missing"]
    s["track_a"][4]["checks"]["sandbox"] = ["tests/test_fake.py::test_holds"]
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(s))
    report = suite.run("battery", suite_path=path, repository=tmp_path)
    status = {v["id"]: v["status"] for v in report["vectors"]}
    assert status["A1"] == "PASS"
    assert status["A2"] == "FINDING_CANDIDATE"
    assert status["A3"] == "NOT_RUN" and status["A4"] == "NOT_RUN"
    assert status["A5"] == "NOT_RUN"  # its only check is a sandbox check, not asked for
    # test_breaks is cited by A2, so nothing uncited failed here.
    assert report["uncited_failures"] == []
    assert report["suite_digest"] == suite.digest(path)
    assert report["claims"] == {"security_acceptance": False, "graded": False}
    assert set(report["environment"]["missing_groups"]) <= set(
        s["environments"]["battery"]
    )
    with_sandbox = suite.run(
        "battery", sandbox=True, suite_path=path, repository=tmp_path
    )
    assert {v["id"]: v["status"] for v in with_sandbox["vectors"]}["A5"] == "PASS"
