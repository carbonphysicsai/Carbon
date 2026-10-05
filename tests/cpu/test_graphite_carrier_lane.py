"""Graphite's CPU carrier lane (VALIDATOR-06).

Pins:
- `CarrierPods` implements the experiment's pod protocol: a cooling proposal
  runs the Challenge's own practice program and scores end to end, at no
  provider money (the whole run cap goes to tokens);
- the carrier's failures map to the pod claims (`program`, `timeout`) or to
  infrastructure with no claim, and host timing never confirms a timeout;
- Levels 4-5 are refused before anything is created;
- the live run's `--compute` flag: the carrier needs an image manifest and no
  RunPod key, and a tokens-only grant is refused on RunPod.

The carrier itself is replaced by a stand-in with its contract (the
`research_carrier._run` signature, its snapshot layout and its
`WorkerFailure` codes) that runs the program in a local subprocess: no
Docker, pod, key, network or spend. The real carrier's isolation is the
carrier's own suite's, and this lane needs the dedicated security review.
"""

import json
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import phase3, pod_outcome
from carbon.agent_campaign.graphite.carrier_pods import CarrierLedger, CarrierPods
from carbon.agent_campaign.graphite.pods import PodFailure, PodJob
from carbon.challenge_validator import scoring as cs
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

REPOSITORY = Path(__file__).resolve().parents[2]
COOLING = "chip-cold-plate"
IMAGE = SimpleNamespace(image_id="sha256:" + "c" * 64)


def cooling():
    return cs.scoring_for(COOLING)


class StandIn:
    """The carrier's contract, run in a local subprocess."""

    def __init__(self, fail=None):
        self.fail, self.calls = fail, []

    def __call__(
        self,
        ledger,
        *,
        owner,
        identity,
        source,
        files,
        image,
        seconds,
        provenance,
        extra_resources,
    ):
        self.calls.append(
            {
                "owner": owner,
                "identity": identity,
                "seconds": seconds,
                "provenance": provenance,
            }
        )
        if self.fail is not None:
            raise self.fail
        admission = ledger.reserve(
            identity,
            owner=owner,
            phase="research",
            request={"s": len(source)},
            resources={},
        )
        assert admission["dispatch"]
        operation = ledger.root / "operation-test"
        snapshot = operation / "snapshot"
        snapshot.mkdir(parents=True)
        with tempfile.TemporaryDirectory() as directory:
            work, output = Path(directory) / "work", Path(directory) / "output"
            work.mkdir()
            output.mkdir()
            for name, body in files.items():
                (work / name).write_bytes(body)
            run = subprocess.run(
                [sys.executable, "-I", "-c", source],
                cwd=work,
                capture_output=True,
                timeout=seconds,
                check=False,
            )
            if run.returncode:
                raise WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=run.stderr)
            (operation / "stdout.txt").write_bytes(run.stdout)
            for path in output.iterdir():
                (snapshot / path.name).write_bytes(path.read_bytes())
        result = {"operation": operation.name}
        ledger.finish(
            identity, owner=owner, state="SUCCEEDED", actual={}, result=result
        )
        return result


def carrier(tmp_path, runner):
    tmp_path.chmod(0o700)
    return CarrierPods(
        tmp_path / "carrier", image=IMAGE, repository=REPOSITORY, runner=runner
    )


def _job(scoring, strategy, intent="intent-1", variant=None):
    contract = ex.recorded_contract(scoring)["contract_digest"]
    record, _files, _program = scoring.built_record(strategy, contract, 0, REPOSITORY)
    return PodJob(
        intent_id=intent,
        strategy=strategy,
        contract_digest=contract,
        seed=0,
        expected={"files": record["staged"], "program": record["program"]},
        minutes=30,
        seconds=600,
        development_variant=variant,
    )


def test_a_cooling_job_runs_its_own_program_in_the_carrier(tmp_path):
    runner = StandIn()
    pods = carrier(tmp_path, runner)
    scoring = cooling()
    job = _job(scoring, scoring.baseline_strategy())
    handle = pods.launch(job, tmp_path / "private")
    assert pods.wait(handle, deadline=1e12, cancelled=lambda: False) == "done"
    files = pods.fetch(handle)
    assert {"built.json", "predictions.json", "DONE.json"} <= set(files)
    assert "failure.json" not in files
    assert json.loads(files["built.json"])["program"] == job.expected["program"]
    _rows, summary = ex.frozen_rule(REPOSITORY, scoring).score(
        json.loads(files["predictions.json"])
    )
    assert summary["n_scored"] > 0
    assert runner.calls == [
        {
            "owner": "graphite-carrier",
            "identity": "intent-1",
            "seconds": 600,
            "provenance": "GRAPHITE_CARRIER_PRACTICE",
        }
    ]
    assert pods.charge(handle) == Decimal(0) and pods.terminate(handle) is True
    assert pods.recover("intent-1", tmp_path) is None
    assert set(pods.listing(handle)) == set(files)
    described = pods.describe()
    assert described["backend"] == "c03-carrier" and described["host"] == "operator"
    assert described["image"] not in pod_outcome.SEPARATED_IMAGES


@pytest.mark.parametrize(
    ("failure", "outcome", "stage"),
    [
        (
            WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"Traceback"),
            "failed",
            "program",
        ),
        (WorkerFailure(WorkerCode.DEADLINE), "failed", "timeout"),
        (WorkerFailure(WorkerCode.UNAVAILABLE), "infra", None),
        (WorkerFailure(WorkerCode.CLEANUP), "infra", None),
        (ValueError("research operation ambiguous"), "infra", None),
    ],
)
def test_carrier_failures_map_to_pod_claims_or_infrastructure(
    tmp_path, failure, outcome, stage
):
    pods = carrier(tmp_path, StandIn(fail=failure))
    scoring = cooling()
    handle = pods.launch(_job(scoring, scoring.baseline_strategy()), tmp_path)
    assert pods.wait(handle, deadline=1e12, cancelled=lambda: False) == outcome
    files = pods.fetch(handle)
    claim = (
        json.loads(files["failure.json"])["stage"] if "failure.json" in files else None
    )
    assert claim == stage
    assert "predictions.json" not in files


def _deadline_stop(tmp_path, elapsed):
    clock = iter([100.0, 100.0 + elapsed])
    pods = CarrierPods(
        tmp_path / "carrier",
        image=IMAGE,
        repository=REPOSITORY,
        runner=StandIn(fail=WorkerFailure(WorkerCode.DEADLINE)),
        clock=lambda: next(clock),
    )
    scoring = cooling()
    handle = pods.launch(_job(scoring, scoring.baseline_strategy()), tmp_path)
    pods.wait(handle, deadline=1e12, cancelled=lambda: False)
    return pods, handle


def _typed(pods, handle, attempt):
    return pod_outcome.classify(
        claim="timeout",
        admissible=None,
        timing=pods.timing(handle),
        work_seconds=pods.effective_work_seconds(600),
        attempt=attempt,
        level=0,
        policy=pod_outcome.load_policy(),
    )


def test_a_carrier_deadline_stop_raises_no_forgery_signal(tmp_path):
    # The carrier stops the program at 600 - 45 s from the run's start, so
    # the host sees at least that long: confirmed against the lane's declared
    # deadline, never contradicted, and the pods' rule applies.
    pods, handle = _deadline_stop(tmp_path, 560.0)
    assert pods.effective_work_seconds(600) == 555
    assert pods.describe()["program_deadline_margin_s"] == 45
    assert pod_outcome.timeout_check(pods.timing(handle), 555) == "confirmed"
    first, second = _typed(pods, handle, 0), _typed(pods, handle, 1)
    assert not first.signal and first.retry and first.status == pod_outcome.FAILED_INFRA
    assert not second.signal
    assert second.status == pod_outcome.CANDIDATE_RESOURCE_EXCEEDED
    # Read against the contract's 600 s instead, the same stop would look
    # forged: the reason the lane declares its deadline.
    assert pod_outcome.timeout_check(pods.timing(handle), 600) == "contradicted"


def test_a_deadline_claim_the_host_contradicts_is_a_signal(tmp_path):
    pods, handle = _deadline_stop(tmp_path / "short", 100.0)
    verdict = _typed(pods, handle, 0)
    assert verdict.signal and verdict.status == pod_outcome.FAILED_INFRA


def test_the_margin_is_the_carriers_own():
    import inspect

    from carbon.agent_campaign.graphite import carrier_pods
    from carbon.development_session import research_carrier

    source = inspect.getsource(research_carrier._run_locked)
    assert f"seconds - {carrier_pods.SETUP_MARGIN_S} - " in source


def test_a_cancelled_run_never_starts_the_carrier(tmp_path):
    runner = StandIn()
    pods = carrier(tmp_path, runner)
    scoring = cooling()
    handle = pods.launch(_job(scoring, scoring.baseline_strategy()), tmp_path)
    assert pods.wait(handle, deadline=1e12, cancelled=lambda: True) == "cancelled"
    assert runner.calls == []


def test_levels_4_and_5_are_refused_before_anything_is_created(tmp_path, monkeypatch):
    from carbon.reconstruction import development_variants

    runner = StandIn()
    pods = carrier(tmp_path, runner)
    scoring = cooling()
    for level, allowed in ((3, True), (4, False), (5, False)):
        monkeypatch.setattr(
            development_variants,
            "registered",
            lambda digest, level=level: SimpleNamespace(level=level),
        )
        job = _job(scoring, scoring.baseline_strategy(), intent=f"v{level}")
        job = PodJob(**{**job.__dict__, "development_variant": "sha256:" + "d" * 64})
        if allowed:
            pods.launch(job, tmp_path)
        else:
            with pytest.raises(PodFailure) as refused:
                pods.launch(job, tmp_path)
            assert refused.value.executed is False
            assert "carrier_level_refused" in str(refused.value.detail)
    assert runner.calls == []


def test_the_carrier_lane_gives_the_whole_run_cap_to_tokens():
    from graphite_phase3_fixtures import grant

    granted = grant()
    pods = ex.phase3_budget(granted, cooling())
    carrier_budget = ex.phase3_budget(granted, cooling(), Decimal(0))
    assert pods.pod_allowance_usd > 0
    assert carrier_budget.pod_allowance_usd == 0
    assert carrier_budget.token_allowance_usd == granted.worst_case_run_cost
    assert carrier_budget.max_pods == pods.max_pods


def test_a_cooling_proposal_scores_end_to_end_on_the_carrier(tmp_path):
    from graphite_phase3_fixtures import grant

    scoring = cooling()
    pods = carrier(tmp_path, StandIn())
    budget = ex.phase3_budget(grant(), scoring, pods.hourly_usd)

    class Ladder:
        def record_failure(self, *args, **kwargs):
            return "failure-1"

    run = ex.Experiment(
        root=tmp_path / "experiment",
        run_id="run-carrier",
        pods=pods,
        budget=budget,
        baseline=scoring.baseline_strategy(),
        token_committed=lambda: Decimal(0),
        cancelled=lambda: False,
        ladder=Ladder(),
        emit=lambda event_id, body: None,
        repository=REPOSITORY,
        clock=lambda: 1000.0,
        randomness=lambda n: b"\x03" * n,
        scoring=scoring,
        construction_level=0,
    )
    variant = scoring.fixture_variant_strategy()
    record = run.run("p-carrier", "proposal", variant, why={"hypothesis": "h"})
    assert record["status"] == "SCORED", record
    assert run.record("baseline")["status"] == "SCORED"


def _args(**changes):
    values = {
        "compute": "runpod",
        "level": 0,
        "image_manifest": None,
        "runpod_key_file": "/k",
        "runpod_key_env": None,
    }
    return SimpleNamespace(**{**values, **changes})


def test_the_compute_flag_selects_and_checks_the_lane(monkeypatch):
    assert "GRAPHITE-GRANT-PHASE3-COOLING-CPU" in phase3.TOKENS_ONLY_GRANTS
    granted = SimpleNamespace(grant_id="GRAPHITE-GRANT-TEST")
    assert phase3.compute_lane(_args(), granted) == "runpod"
    carrier_args = _args(
        compute="carrier", image_manifest="/m.json", runpod_key_file=None
    )
    assert phase3.compute_lane(carrier_args, granted) == "carrier"

    def refused(args, code):
        with pytest.raises(phase3.RunnerRefused):
            phase3.compute_lane(args, granted)

    refused(_args(compute="carrier", image_manifest=None), "required: --image-manifest")
    refused(_args(compute="carrier", image_manifest="/m.json", level=4), "levels")
    refused(_args(compute="gpu-cloud"), "unknown")
    monkeypatch.setattr(
        phase3, "TOKENS_ONLY_GRANTS", frozenset({"GRAPHITE-GRANT-TEST"})
    )
    refused(_args(), "tokens only")
    assert phase3.compute_lane(carrier_args, granted) == "carrier"


def test_the_live_run_needs_no_runpod_key_on_the_carrier(capsys):
    argv = [
        "run",
        "--root",
        "/tmp/x",
        "--challenge",
        COOLING,
        "--compute",
        "carrier",
        "--grant",
        "g",
        "--credential-env",
        "ENGY_API_KEY",
        "--code-ref",
        "0" * 40,
    ]
    with pytest.raises(SystemExit):
        phase3.main(argv)
    refusal = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert refusal["reason_code"] == "required: --image-manifest"


def test_the_carrier_ledger_dispatches_once(tmp_path):
    tmp_path.chmod(0o700)
    ledger = CarrierLedger(tmp_path / "ledger")
    request = {"owner": "o", "phase": "p", "request": {"a": 1}, "resources": {}}
    assert ledger.reserve("i", **request) == {"dispatch": True, "state": "RESERVED"}
    again = ledger.reserve("i", **request)
    assert again["dispatch"] is False and again["state"] == "RESERVED"
    with pytest.raises(ValueError, match="reused"):
        ledger.reserve("i", **{**request, "request": {"a": 2}})
    ledger.finish("i", owner="o", state="SUCCEEDED", actual={}, result={"r": 1})
    ledger.finish("i", owner="o", state="SUCCEEDED", actual={}, result={"r": 1})
    with pytest.raises(ValueError, match="terminal conflict"):
        ledger.finish("i", owner="o", state="SUCCEEDED", actual={}, result={"r": 2})
    assert ledger.reserve("i", **request)["result"] == {"r": 1}
    loose = tmp_path / "loose"
    loose.mkdir(mode=0o755)
    loose.chmod(0o755)
    with pytest.raises(PodFailure, match="owner_only"):
        CarrierLedger(loose)
