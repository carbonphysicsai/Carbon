"""Retained-check fail-closed plumbing; all positives are private test fixtures.

No fixture status is reachable through a request/environment variable, persisted
as authority, or offered as evidence of security acceptance/activation.
"""

import copy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from composition_check_fixtures import (
    accepted_fixture_checks,
    fixture_source,
)
from test_composition_ladder import BATTERY, MINER, strategy, target

from carbon.battery import campaign, intake
from carbon.battery.daemon import (
    AuthenticatedSubmission,
    BatteryValidator,
    DevelopmentCompilerUnavailable,
)
from carbon.battery.worker import WorkerFailure
from carbon.development_ladder import operate
from carbon.development_ladder import required_checks as checks
from carbon.development_session import construction_level as cl
from carbon.development_session.unified_construction import UnifiedContract
from carbon.reconstruction import development_composition as dc
from carbon.reconstruction import development_level_cli as cli


def test_default_unknown_stops_original_fields_before_compile_or_graph_read(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(dc, "compile", lambda *args: calls.append(args))
    composition = dc.load(BATTERY)
    request = {
        "op": "compile",
        "challenge": BATTERY,
        "composition_digest": composition.digest,
        "strategy": strategy(),
    }
    result = cli.answer(request)
    assert result["code"] == "construction_checks_unavailable" and not result["ok"]
    assert {i["path"] for i in result["issues"]} == {
        "/parameters/muon_spectral",
        "/parameters/quasi_newton_family",
        "/parameters/line_search",
    }
    graph = copy.deepcopy(request)
    graph["strategy"]["parameters"]["composition_graphs"] = "sha256:" + "1" * 64
    graph.update(op="level4", directory="never-open-this")
    assert cli.answer(graph)["code"] == "construction_checks_unavailable"
    with pytest.raises(
        DevelopmentCompilerUnavailable, match="construction_checks_unavailable"
    ) as failed:
        operate.compile_variant(strategy(), composition.digest)
    assert isinstance(failed.value, WorkerFailure) and failed.value.candidate is False
    assert calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "empty_types",
        "missing_type",
        "empty_checks",
        "duplicate_check",
        "unknown_check",
        "fields",
        "source",
        "arm",
    ],
)
def test_incomplete_or_changed_authority_cannot_vacuously_pass(monkeypatch, mutation):
    doc = fixture_source().document
    if mutation == "empty_types":
        doc["types"] = []
    elif mutation == "missing_type":
        doc["types"].pop()
    elif mutation == "empty_checks":
        doc["types"][1]["checks"] = []
    elif mutation == "duplicate_check":
        doc["types"][1]["checks"] *= 2
    elif mutation == "unknown_check":
        doc["types"][1]["checks"][0]["id"] = "weaker-check"
    elif mutation == "fields":
        # Well-formed but unbound replacement authority, even for an unused row.
        doc["types"][0]["registration_digest"] = "sha256:" + "0" * 64
    elif mutation == "source":
        doc["version"] = "unregistered-source"
    else:
        doc["types"][1]["arms"][0]["external_allowed"] = not doc["types"][1]["arms"][0][
            "external_allowed"
        ]
    try:
        source = UnifiedContract(doc)
    except ValueError:
        # A malformed provider is infrastructure too, not candidate refusal.
        def source_error(challenge):
            raise ValueError("malformed provider")

        monkeypatch.setattr(checks, "_source", source_error)
    else:
        monkeypatch.setattr(checks, "_source", lambda challenge: source)
    with pytest.raises(checks.ChecksUnavailable):
        checks.check(strategy(), dc.load(BATTERY))


def test_l0_has_no_changed_obligations_but_still_authenticates_all_parts():
    composition = dc.load(BATTERY)
    base = strategy()
    for field in ("muon_spectral", "quasi_newton_family", "line_search"):
        base["parameters"].pop(field)
    assert checks.check(base, composition)["change_set"] == []
    for changed in (
        replace(composition, variants=composition.variants[:-1]),
        replace(composition, base_contract_digest="sha256:" + "0" * 64),
        replace(composition, challenge="other"),
    ):
        with pytest.raises(checks.ChecksUnavailable):
            checks.check(base, changed)


@pytest.mark.parametrize("new_status", ["UNAVAILABLE", "FAIL"])
def test_current_status_rechecked_after_positive_before_submit(
    monkeypatch, tmp_path, accepted_fixture_checks, new_status
):
    found = cl.with_target(cl.resolve_composition(BATTERY), "http://127.0.0.1:9/intake")
    monkeypatch.setattr(
        cl,
        "READ_TARGET",
        lambda *args: {
            "served_contracts": [
                {
                    "kind": "composition",
                    "level": None,
                    "variant": found["variant"],
                    "digest": found["digest"],
                }
            ]
        },
    )
    assert cl.compile_strategy(found, strategy())["ok"]
    monkeypatch.setattr(checks, "_source", lambda challenge: fixture_source(new_status))
    with pytest.raises(cl.LevelRefused, match="construction_checks_unavailable"):
        cl.compile_strategy(found, strategy())

    class NeverSign:
        @property
        def hotkey(self):
            raise AssertionError("signer touched")

    from carbon.battery.remote_submission import IntakeRefusal

    with pytest.raises(IntakeRefusal, match="construction_checks_unavailable"):
        campaign.submit_through_intake(
            found["target_intake"],
            NeverSign(),
            root=tmp_path,
            epoch=0,
            strategy=strategy(),
            contract_digest=found["digest"],
            construction_level=found,
        )
    assert not list(tmp_path.iterdir())


def test_actual_intake_pass_preserves_received_and_continues_peers(
    tmp_path, monkeypatch
):
    instance = target(tmp_path)
    instance.processes_here = False
    submissions = [
        AuthenticatedSubmission(
            MINER, {"sequence": i}, BATTERY, "1.0", strategy(), dc.load(BATTERY).digest
        )
        for i in (1, 2)
    ]
    inbox = intake.Inbox(tmp_path / "inbox.sqlite3")
    for i, submission in enumerate(submissions):
        inbox.receive(str(i), submission, 1)
    seen = []

    def admit(submission):
        seen.append(submission.receipt["sequence"])
        # Real ladder/compiler guard, before any store/commitment use.
        instance.development_compiler(submission.strategy, submission.contract_digest)

    instance.admit = admit
    from carbon.battery import deployment

    monkeypatch.setattr(deployment, "processes_here", lambda target: False)
    result = intake.work_once(inbox, instance)
    assert result["left"] == 2 and result["refused"] == result["admitted"] == 0
    assert len(list(inbox.received())) == 2 and seen == [1, 2]


def test_actual_daemon_process_retries_guard_failure_without_reconstruct(tmp_path):
    instance = target(tmp_path)
    calls = []
    row = {
        "state": "ADMITTED",
        "hotkey": MINER,
        "strategy": strategy(),
        "binding": {
            "attempt": 0,
            "development": {"variant_contract_digest": dc.load(BATTERY).digest},
        },
    }
    instance.store = SimpleNamespace(
        submission=lambda sid: row,
        pool=lambda: {"status": "OPEN"},
        mark=lambda *args: calls.append(args),
    )
    instance._settle = lambda: None
    instance._bump_attempt = lambda *args: calls.append(("bump", *args))
    instance.outcome = lambda sid: {"state": calls[0][1]}
    instance.backend = SimpleNamespace(
        reconstruct=lambda *args: pytest.fail("must not reconstruct")
    )
    assert BatteryValidator.process(instance, "candidate") == {"state": "FAILED_INFRA"}
    assert calls == [
        (
            "candidate",
            "FAILED_INFRA",
            {"code": "construction_checks_unavailable", "attempt": 0},
        ),
        ("bump", "candidate", 1),
    ]


__all__ = ["accepted_fixture_checks"]


def test_real_child_default_unknown_and_unused_base_controls(monkeypatch):
    found = cl.with_target(cl.resolve_composition(BATTERY), "http://127.0.0.1:9/intake")
    monkeypatch.setattr(
        cl,
        "READ_TARGET",
        lambda *args: {
            "served_contracts": [
                {
                    "kind": "composition",
                    "level": None,
                    "variant": found["variant"],
                    "digest": found["digest"],
                }
            ]
        },
    )
    with pytest.raises(
        cl.LevelRefused, match="construction_checks_unavailable"
    ) as failed:
        cl.compile_strategy(found, strategy())
    assert {i["path"] for i in failed.value.issues} == {
        "/parameters/muon_spectral",
        "/parameters/quasi_newton_family",
        "/parameters/line_search",
    }
    base = strategy()
    for name in ("muon_spectral", "quasi_newton_family", "line_search"):
        base["parameters"].pop(name)
    result = cl.compile_strategy(found, base)
    assert result["ok"] and result["derived"]["changes"] == []


def test_equal_numeric_values_do_not_substitute_canonical_source_or_composition(
    monkeypatch,
):
    source = fixture_source()
    document = source.document
    original = document["base_fields"]["steps"]["low"]
    assert type(original) is int
    document["base_fields"]["steps"]["low"] = float(original)
    # Use a numeric field whose schema permits either JSON numeric type.
    document = source.document
    field = next(
        row
        for row in document["base_fields"].values()
        if row["kind"] == "float" and float(row["low"]).is_integer()
    )
    original = field["low"]
    field["low"] = int(original) if float(original).is_integer() else original
    if type(field["low"]) is type(original):
        field["low"] = float(original)
    assert field["low"] == original and type(field["low"]) is not type(original)
    changed = UnifiedContract(document)
    assert changed.document == source.document
    monkeypatch.setattr(checks, "_source", lambda challenge: changed)
    with pytest.raises(checks.ChecksUnavailable):
        checks.check(strategy(), dc.load(BATTERY))
    composition = dc.load(BATTERY)
    changed = replace(
        composition, base_record_sequence=float(composition.base_record_sequence)
    )
    assert changed == composition
    with pytest.raises(checks.ChecksUnavailable):
        checks.check(strategy(), changed)


def test_expected_source_unreadable_is_infrastructure(monkeypatch):
    source = fixture_source()
    monkeypatch.setattr(checks, "_source", lambda challenge: source)

    def unavailable(challenge):
        raise OSError("fixture source changed between reads")

    monkeypatch.setattr(checks, "_expected", unavailable)
    with pytest.raises(checks.ChecksUnavailable):
        checks.check(strategy(), dc.load(BATTERY))


def test_current_check_failure_stops_campaign_commitment_gate(monkeypatch, tmp_path):
    import asyncio

    from carbon.development_session.research_campaign import OperationRefused

    found = cl.resolve_composition(BATTERY)
    manifest = {"construction_level": found}

    class Gate:
        def before_submit(self, *args, **kwargs):
            pytest.fail("commitment gate called")

    with pytest.raises(OperationRefused, match="construction_checks_unavailable"):
        asyncio.run(
            campaign._committed(
                Gate(), tmp_path, 0, {"strategy": strategy()}, manifest, request=True
            )
        )


def test_queued_launchpad_commit_rechecks_before_poster(monkeypatch):
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    host = RunnerAdapter.__new__(RunnerAdapter)
    failures = []

    def refused(admitted):
        raise Rejected("construction_checks_unavailable", 409)

    monkeypatch.setattr(host, "_require_level_served", refused)
    monkeypatch.setattr(host, "_poster", lambda cfg: pytest.fail("poster touched"))
    monkeypatch.setattr(host, "_refused", lambda *args: failures.append(args))
    host._commit_thread(SimpleNamespace(campaign={"id": "fixture"}, profile={}), {})
    assert failures == [("fixture", "construction_checks_unavailable", "commit")]
