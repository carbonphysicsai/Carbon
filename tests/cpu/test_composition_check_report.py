"""Private diagnostic transport only; fixture health never grants authority."""

import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from composition_check_fixtures import fixture_source
from test_composition_ladder import BATTERY, strategy

from carbon.development_ladder import required_checks as checks
from carbon.development_session import construction_level as cl
from carbon.development_session import unified_construction as unified
from carbon.reconstruction import development_composition as dc
from carbon.reconstruction import development_level_cli as cli


def request(op="compile"):
    return {
        "op": op,
        "challenge": BATTERY,
        "composition_digest": dc.load(BATTERY).digest,
        "strategy": strategy(),
    }


def unavailable_report():
    value = cli.answer(request())
    assert value["ok"] is False and value["code"] == "construction_checks_unavailable"
    return value


def test_original_unavailable_report_never_compiles_or_reads_graph(monkeypatch):
    monkeypatch.setattr(dc, "compile", lambda *a: pytest.fail("compiler called"))
    value = unavailable_report()
    report = value["required_check_report"]
    assert report["composition_digest"] == dc.load(BATTERY).digest
    assert report["base_contract_digest"] == dc.load(BATTERY).base_contract_digest
    assert report["aggregate_status"] == "UNAVAILABLE"
    assert report["compiler_security_components"] == "NOT_SEPARATELY_MEASURED"
    assert report["development_authorization"] == {
        "decision": "NOT_BOUND",
        "execution": "NOT_DISPATCHED",
    }
    assert report["admission_allowed"] is False
    assert {row["id"] for row in report["checks"]} == {
        "L2:registered-compiler-and-security",
        "L3:registered-compiler-and-security",
    }
    reported = {(row["id"], path) for row in report["checks"] for path in row["paths"]}
    assert reported == {(issue["code"], issue["path"]) for issue in value["issues"]}
    graph = request("level4")
    graph["strategy"]["parameters"]["composition_graphs"] = "sha256:" + "1" * 64
    graph["directory"] = "never-open-this"
    value = cli.answer(graph)
    assert value["code"] == "construction_checks_unavailable"
    assert any(
        row["id"].startswith("L4:") for row in value["required_check_report"]["checks"]
    )


def test_checks_only_report_has_same_refusal_and_no_compilation(monkeypatch):
    monkeypatch.setattr(dc, "compile", lambda *a: pytest.fail("compiler called"))
    assert cli.answer(request("checks")) == unavailable_report()


def test_fixture_fail_is_reported_as_fail_and_still_refused(monkeypatch):
    monkeypatch.setattr(checks, "_source", lambda challenge: fixture_source("FAIL"))
    value = unavailable_report()
    assert value["required_check_report"]["aggregate_status"] == "FAIL"
    assert {r["status"] for r in value["required_check_report"]["checks"]} == {"FAIL"}
    assert value["required_check_report"]["admission_allowed"] is False


def test_positive_fixture_and_base_binding_return_unchanged(monkeypatch):
    composition = dc.load(BATTERY)
    recipe = strategy()
    provider = fixture_source()
    monkeypatch.setattr(checks, "_source", lambda challenge: provider)
    assert checks.check(recipe, composition) == unified.derive(recipe, provider)
    base = strategy()
    for field in ("muon_spectral", "quasi_newton_family", "line_search"):
        base["parameters"].pop(field)
    assert checks.check(base, composition) == unified.derive(base, provider)
    assert "required_check_report" not in cli.answer(
        {**request("checks"), "strategy": base}
    )


@pytest.mark.parametrize(
    "failure", ["provider", "roster", "descriptor", "arm", "derive"]
)
def test_unauthenticated_or_underived_subject_has_no_report(monkeypatch, failure):
    composition = dc.load(BATTERY)
    recipe = strategy()
    if failure == "provider":

        def broken(challenge):
            raise OSError("untrusted private details never echoed")

        monkeypatch.setattr(checks, "_source", broken)
    elif failure == "roster":
        document = fixture_source().document
        document["types"][1]["checks"][0]["id"] = "missing-real-obligation"
        monkeypatch.setattr(
            checks, "_source", lambda challenge: unified.UnifiedContract(document)
        )
    elif failure == "descriptor":
        composition = replace(composition, base_contract_digest="sha256:" + "0" * 64)
    elif failure == "arm":
        derive = unified.derive

        def wrong_arm(recipe, contract):
            binding = derive(recipe, contract)
            binding["arms"]["optimizer_and_data"]["variant_digest"] = (
                "sha256:" + "0" * 64
            )
            return binding

        monkeypatch.setattr(unified, "derive", wrong_arm)
    else:
        recipe["parameters"]["unregistered_private_field"] = 1
    with pytest.raises((checks.ChecksUnavailable, ValueError)) as failed:
        checks.check(recipe, composition)
    assert getattr(failed.value, "required_check_report", None) is None


def test_private_child_report_bound_to_request_and_original_refusal(monkeypatch):
    value = unavailable_report()
    sent = []

    def child(*args, **kwargs):
        sent.append(json.loads(kwargs["input"]))
        return SimpleNamespace(stdout=json.dumps(value))

    monkeypatch.setattr(cl.subprocess, "run", child)
    with pytest.raises(cl.LevelRefused) as failed:
        cl._run(request("checks"))
    assert sent == [request("checks")]
    assert failed.value.code == value["code"] and failed.value.issues == value["issues"]
    assert failed.value.required_check_report == value["required_check_report"]
    assert failed.value.required_check_report is not value["required_check_report"]


@pytest.mark.parametrize(
    "mutation",
    [
        "composition",
        "base",
        "challenge",
        "extra",
        "path",
        "duplicate",
        "status",
        "aggregate",
        "admission",
        "authorization",
        "all_pass",
        "no_subject",
    ],
)
def test_bad_sidecar_discarded_without_changing_primary_refusal(mutation):
    value = copy.deepcopy(unavailable_report())
    report = value["required_check_report"]
    subject = (BATTERY, dc.load(BATTERY).digest)
    if mutation == "composition":
        report["composition_digest"] = "sha256:" + "0" * 64
    elif mutation == "base":
        report["base_contract_digest"] = "sha256:" + "0" * 64
    elif mutation == "challenge":
        report["challenge"] = "other"
    elif mutation == "extra":
        report["private_path"] = "/never-echo"
    elif mutation == "path":
        report["checks"][0]["paths"] = ["/private/key\nvalue"]
    elif mutation == "duplicate":
        report["checks"].append(copy.deepcopy(report["checks"][0]))
    elif mutation == "status":
        report["checks"][0]["status"] = {"PASS": True}
    elif mutation == "aggregate":
        report["aggregate_status"] = "PASS"
    elif mutation == "admission":
        report["admission_allowed"] = 0  # must be false by type, not equality
    elif mutation == "authorization":
        report["development_authorization"][
            "decision"
        ] = "AUTHORIZED_BOUNDED_DEVELOPMENT_TEST"
    elif mutation == "all_pass":
        for row in report["checks"]:
            row["status"] = "PASS"
    else:
        subject = None
    with pytest.raises(cl.LevelRefused) as failed:
        cl.checked(value, expected_report_subject=subject)
    assert failed.value.code == value["code"] and failed.value.issues == value["issues"]
    assert failed.value.required_check_report is None


def test_legacy_client_answer_and_unrelated_refusal_unchanged():
    value = {"ok": True, "variant": "legacy", "variant_digest": "sha256:" + "2" * 64}
    assert cl.checked(value) is value
    refusal = unavailable_report()
    refusal["code"] = "level_strategy_refused"
    with pytest.raises(cl.LevelRefused) as failed:
        cl.checked(refusal, expected_report_subject=(BATTERY, dc.load(BATTERY).digest))
    assert failed.value.code == "level_strategy_refused"
    assert failed.value.required_check_report is None


def test_legacy_unavailable_without_sidecar_preserves_refusal():
    value = unavailable_report()
    del value["required_check_report"]
    with pytest.raises(cl.LevelRefused) as failed:
        cl.checked(value, expected_report_subject=(BATTERY, dc.load(BATTERY).digest))
    assert failed.value.code == value["code"] and failed.value.issues == value["issues"]
    assert failed.value.required_check_report is None


def test_client_metadata_read_failure_discards_report_not_primary_refusal(monkeypatch):
    value = unavailable_report()
    from carbon.reconstruction import capability_registry as registry

    def unreadable(*args):
        raise OSError("private details must not be echoed")

    monkeypatch.setattr(registry, "development_composition_document", unreadable)
    with pytest.raises(cl.LevelRefused) as failed:
        cl.checked(
            value,
            expected_report_subject=(
                BATTERY,
                value["required_check_report"]["composition_digest"],
            ),
        )
    assert failed.value.code == value["code"] and failed.value.issues == value["issues"]
    assert failed.value.required_check_report is None
