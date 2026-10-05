"""GRAPHITE-GRANT-PHASE3-COOLING-CPU (OWNER-GRAPHITE-TEST-WAVE-06 §3,
carbonphysicsai/Carbon#595): cooling's CPU-lane Constructor grant.

Claims tested:
- the grant is the owner's, with the approved amounts, and its arithmetic
  holds: 3 × 1.95 + 0.25 = 6.10, all of each run's cost a token share;
- the phase-3 runner binds it to `chip-cold-plate` and to main's committed
  blob (`grant_binding.check_phase3_grant`): another Challenge's grant, a
  tampered copy, a branch-only grant, an unpushed HEAD and a dirty grants
  directory are each refused typed, and a grant on main passes;
- it is tokens-only (`phase3.TOKENS_ONLY_GRANTS`, VALIDATOR-06), so its pod
  money budget is 0: on the real launch path (`experiment.Experiment` over
  `pods.RunPodPods`, RunPod in memory) every paid pod is refused
  `grant_allows_no_pods` before any reservation, and no create request is
  ever sent, while the CPU carrier lane (rate 0) still runs its proposals;
- on the CPU carrier lane (the real `CarrierPods`, its carrier replaced by
  the carrier suite's stand-in) a launch under the grant books exactly
  USD 0, and a non-zero rate reaching the lane is refused, not booked;
- a carrier-lane backend that reports a charge anyway (the 0.30 probe) has
  it booked exactly as reported, gets a typed finding
  (`tokens_only_backend_reported_a_charge`) naming the pod and the amount,
  and stops the session through the existing stop: no further launch, the
  in-flight proposal's retry included;
- `phase3 run --compute runpod` under the grant is refused
  `grant_is_tokens_only_use_the_carrier_lane` through the real CLI before
  any RunPod backend is built, reservation made or request sent;
- battery's phase-3 grants keep working unchanged;
- each guard, disabled, lets the wrong thing through (mutations).

No live run, key, network or spend.
"""

from __future__ import annotations

import copy
import dataclasses
import functools
import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import grant_binding, phase3, pods
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
CPU_ID = "GRAPHITE-GRANT-PHASE3-COOLING-CPU"
CPU_FILE = grant_binding.GRANTS_DIR + "/GRAPHITE-GRANT-PHASE3-COOLING-CPU.json"
#: Battery's phase-3 grants (R3: OWNER-GRAPHITE-PHASE3-R3-01).
BATTERY_IDS = (
    "GRAPHITE-GRANT-PHASE3",
    "GRAPHITE-GRANT-PHASE3-R2",
    "GRAPHITE-GRANT-PHASE3-R3",
)
COOLING = challenge_scoring.scoring_for(COLD_PLATE_CHALLENGE)
BATTERY = challenge_scoring.scoring_for(BATTERY_CHALLENGE)


def _document(name="GRAPHITE-GRANT-PHASE3-COOLING-CPU.json", **changes):
    document = json.loads((GRANTS / name).read_bytes())
    assert "HUMAN_INPUT" not in json.dumps(document)
    return {**document, **changes}


def _grant(name="GRAPHITE-GRANT-PHASE3-COOLING-CPU.json", **changes):
    return SpendingGrant.from_document(_document(name, **changes))


def _refusal(capsys, call):
    with pytest.raises(SystemExit):
        call()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]


# -- the grant ----------------------------------------------------------------------------------
def test_the_cooling_cpu_grant_is_the_owners():
    grant = _grant()
    assert grant.grant_id == CPU_ID
    assert grant.provider == "graphite" and grant.currency == "USD"
    assert grant.account == "Carbon-Account" and grant.granted_by == "owner"
    assert grant.expires_at.isoformat() == "2026-12-31T23:59:59+00:00"
    assert grant.monetary_ceiling == Decimal("6.10")
    assert grant.cleanup_allowance == Decimal("0.25")
    assert grant.worst_case_run_cost == Decimal("1.95")
    assert grant.permitted_runs == 3
    assert grant.max_concurrency == 1
    assert grant.max_runtime_s == 39600
    assert grant.max_submissions == 3


def test_the_registry_binds_it_to_cooling_tokens_only_and_to_main():
    entry = grant_binding.PHASE3_GRANTS[CPU_ID]
    assert entry.challenge == COLD_PLATE_CHALLENGE and entry.grant_file == CPU_FILE
    assert entry.main_blob is True
    assert CPU_ID in phase3.TOKENS_ONLY_GRANTS and grant_binding.tokens_only(_grant())
    assert COLD_PLATE_CHALLENGE in grant_binding.PHASE3_BOUND_CHALLENGES
    # Battery's phase-3 grants: battery's, with pods, no main-blob check.
    for grant_id in BATTERY_IDS:
        battery = grant_binding.PHASE3_GRANTS[grant_id]
        assert (battery.challenge, battery.main_blob) == (BATTERY_CHALLENGE, False)
        assert grant_id not in phase3.TOKENS_ONLY_GRANTS
        assert _grant(Path(battery.grant_file).name).grant_id == grant_id
    assert BATTERY_CHALLENGE not in grant_binding.PHASE3_BOUND_CHALLENGES


def test_the_grant_cites_its_authority():
    readme = (GRANTS / "README.md").read_text()
    section = readme[readme.index("## GRAPHITE-GRANT-PHASE3-COOLING-CPU") :]
    assert "OWNER-GRAPHITE-TEST-WAVE-06 §3" in section
    assert "carbonphysicsai/Carbon#595" in section
    assert "3 × 1.95 + 0.25 = 6.10 ≤ 6.10" in section
    assert "grant_allows_no_pods" in section


def test_the_ceiling_covers_three_runs_and_cleanup():
    grant = _grant()
    total = grant.permitted_runs * grant.worst_case_run_cost + grant.cleanup_allowance
    assert total == grant.monetary_ceiling == Decimal("6.10")
    headroom = grant.monetary_ceiling - grant.cleanup_allowance
    assert headroom // grant.worst_case_run_cost == grant.permitted_runs


def test_the_token_cap_is_the_whole_run_cost():
    """No pod money: the pod allowance is 0 and the run's model calls are
    capped at USD 1.95, the same token share as a GRAPHITE-GRANT-PHASE3 run,
    at the RunPod rate (where every pod is refused) and on the carrier."""
    budget = ex.phase3_budget(_grant(expires_at="2099-01-01T00:00:00Z"), COOLING)
    assert budget.challenge_id == COLD_PLATE_CHALLENGE
    assert budget.tokens_only and not budget.pays_for_pods
    assert budget.pod_allowance_usd == Decimal("0.00")
    assert budget.record()["tokens_only"] is True
    carrier = ex.phase3_budget(
        _grant(expires_at="2099-01-01T00:00:00Z"), COOLING, Decimal(0)
    )
    assert carrier.tokens_only and carrier.pays_for_pods
    assert carrier.token_allowance_usd == Decimal("1.95")
    assert budget.token_allowance_usd == budget.run_cap_usd == Decimal("1.95")
    battery = ex.phase3_budget(_grant("GRAPHITE-GRANT-PHASE3.json"), BATTERY)
    assert budget.token_allowance_usd == battery.token_allowance_usd


def test_validator_06s_tokens_only_list_gives_the_same_budget(monkeypatch):
    """VALIDATOR-06's `phase3.TOKENS_ONLY_GRANTS` is the one list: a grant
    named there gets a pod money budget of 0, whatever this registry says."""
    listed = _grant(
        grant_id="SOME-TOKENS-ONLY-GRANT", expires_at="2099-01-01T00:00:00Z"
    )
    assert not grant_binding.tokens_only(listed)
    monkeypatch.setattr(phase3, "TOKENS_ONLY_GRANTS", frozenset({listed.grant_id}))
    assert grant_binding.tokens_only(listed)
    budget = ex.phase3_budget(listed, COOLING)
    assert budget.tokens_only and budget.token_allowance_usd == Decimal("1.95")


def test_the_provider_runs_its_session_under_the_token_cap(tmp_path):
    from carbon.agent_campaign.graphite.model import ScriptedModel, text

    provider = phase3.Phase3Provider(
        root=tmp_path / "graphite",
        grant=_grant(expires_at="2099-01-01T00:00:00Z"),
        model=ScriptedModel([text("done")]),
        pods=pods.ScriptedPods(),
        scoring=COOLING,
    )
    assert provider.budget.tokens_only and not provider.budget.pays_for_pods
    assert provider.budget.token_allowance_usd == Decimal("1.95")
    assert provider.budget.record()["pod_allowance_usd"] == "0.00"


def test_battery_s_phase3_grants_are_unaffected(tmp_path):
    """The same budget as before (12 pods, USD 2.96 of pods, USD 1.95 of
    tokens), accepted for battery with no git read, and an unregistered
    grant on battery accepted as before."""
    for name in (grant_id + ".json" for grant_id in BATTERY_IDS):
        grant = _grant(name)
        budget = ex.phase3_budget(grant, BATTERY)
        assert budget.max_pods == 12 and not budget.tokens_only
        assert "tokens_only" not in budget.record()
        assert budget.pod_allowance_usd == Decimal("2.96")
        assert budget.token_allowance_usd == Decimal("1.95")
        # `tmp_path` is no repository: a git read would refuse.
        entry = grant_binding.check_phase3_grant(
            GRANTS / name, grant, challenge=BATTERY_CHALLENGE, repository=tmp_path
        )
        assert entry.grant_id == grant.grant_id
    other = _grant("GRAPHITE-GRANT-PHASE3.json", grant_id="SOME-OTHER-GRANT")
    assert not grant_binding.tokens_only(other)
    assert (
        grant_binding.check_phase3_grant(
            GRANTS / "x.json", other, challenge=BATTERY_CHALLENGE, repository=tmp_path
        )
        is None
    )


# -- the binding --------------------------------------------------------------------------------
def test_a_grant_for_another_challenge_is_refused(tmp_path, capsys):
    """Cooling's grant on battery, battery's on cooling: typed, before git."""
    pairs = [
        ("GRAPHITE-GRANT-PHASE3-COOLING-CPU.json", BATTERY_CHALLENGE),
        ("GRAPHITE-GRANT-PHASE3.json", COLD_PLATE_CHALLENGE),
        ("GRAPHITE-GRANT-PHASE3-R2.json", COLD_PLATE_CHALLENGE),
        ("GRAPHITE-GRANT-PHASE3-R3.json", COLD_PLATE_CHALLENGE),
    ]
    for name, challenge in pairs:
        code = _refusal(
            capsys,
            lambda n=name, c=challenge: grant_binding.check_phase3_grant(
                GRANTS / n, _grant(n), challenge=c, repository=tmp_path
            ),
        )
        assert code == "grant_is_for_another_challenge", name
    # Cooling accepts only a grant registered for it: not the phase-4 grant,
    # not an unregistered one.
    for name in ("GRAPHITE-GRANT-PHASE4-COOLING.json", "GRAPHITE-GRANT-PHASE4.json"):
        code = _refusal(
            capsys,
            lambda n=name: grant_binding.check_phase3_grant(
                GRANTS / n, _grant(n), challenge=COLD_PLATE_CHALLENGE
            ),
        )
        assert code == "grant_is_not_a_phase3_grant_for_challenge"


@pytest.mark.parametrize(
    "name, challenge",
    [
        ("GRAPHITE-GRANT-PHASE3-COOLING-CPU.json", BATTERY_CHALLENGE),
        ("GRAPHITE-GRANT-PHASE3-R2.json", COLD_PLATE_CHALLENGE),
    ],
)
def test_the_runner_refuses_a_wrong_pairing_before_anything_opens(
    tmp_path, capsys, name, challenge
):
    root = tmp_path / "root"
    argv = _live_argv(root, challenge, GRANTS / name)
    assert (
        _refusal(capsys, lambda: phase3.main(argv)) == "grant_is_for_another_challenge"
    )
    assert not any(root.iterdir())


def _live_argv(root, challenge, grant):
    """A live `phase3 run` up to the grant: the credentials are named, never
    read, because the grant is checked first."""
    return [
        "run",
        "--root",
        str(root),
        "--challenge",
        challenge,
        "--grant",
        str(grant),
        "--credential-env",
        "ENGY_API_KEY",
        "--runpod-key-env",
        "RUNPOD_API_KEY",
        "--code-ref",
        "0" * 40,
    ]


def _git(cwd, *args):
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True
    )


def _repo(tmp_path, *, on_main=True):
    """A repository with a bare remote. With `on_main`, main carries the
    committed grant; otherwise only a pushed feature branch does."""
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    (repo / "README").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "start")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    if not on_main:
        _git(repo, "checkout", "-q", "-b", "feature")
    grant = repo / CPU_FILE
    grant.parent.mkdir(parents=True)
    grant.write_bytes((REPOSITORY / CPU_FILE).read_bytes())
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "grant")
    branch = "main" if on_main else "feature"
    _git(repo, "push", "-q", "-u", "origin", branch)
    return repo, grant


def _check(path, repo, challenge=COLD_PLATE_CHALLENGE):
    return grant_binding.check_phase3_grant(
        path, phase3.load_grant(path), challenge=challenge, repository=repo
    )


def test_the_grant_on_main_passes_and_every_drift_is_refused(tmp_path, capsys):
    repo, grant = _repo(tmp_path)
    assert _check(grant, repo).grant_id == CPU_ID

    def refusal(path):
        return _refusal(capsys, lambda: _check(path, repo))

    # A tampered copy (ceiling raised), or the edited working tree itself.
    raised = {**json.loads(grant.read_bytes()), "monetary_ceiling": "100.00"}
    copy_ = tmp_path / "raised.json"
    copy_.write_text(json.dumps(raised))
    assert refusal(copy_) == "grant_differs_from_the_committed_phase3_grant"
    clean = tmp_path / "clean.json"
    clean.write_bytes(grant.read_bytes())
    grant.write_text(json.dumps(raised))
    assert refusal(grant) == "grant_differs_from_the_committed_phase3_grant"
    assert refusal(clean) == "grants_directory_has_uncommitted_changes"
    _git(repo, "checkout", "--", CPU_FILE)
    (grant.parent / "NOTE.txt").write_text("untracked")
    assert refusal(clean) == "grants_directory_has_uncommitted_changes"
    (grant.parent / "NOTE.txt").unlink()
    assert _check(clean, repo)
    # An unpushed HEAD, then a HEAD without the grant.
    (repo / "other.txt").write_text("x")
    _git(repo, "add", "other.txt")
    _git(repo, "commit", "-q", "-m", "local only")
    assert refusal(clean) == "grant_commit_not_pushed"
    _git(repo, "rm", "-q", CPU_FILE)
    _git(repo, "commit", "-q", "-m", "no grant")
    assert refusal(clean) == "phase3_grant_not_committed"


def test_a_branch_only_grant_is_refused_until_it_is_on_main(tmp_path, capsys):
    """Committed and pushed on a feature branch only (this pull request's
    state): `main_grant_unavailable`. A branch that edits the grant:
    `grant_differs_from_main`. Once main carries the blob: accepted."""
    repo, grant = _repo(tmp_path, on_main=False)
    assert _refusal(capsys, lambda: _check(grant, repo)) == "main_grant_unavailable"
    _git(repo, "push", "-q", "origin", "feature:main")
    assert _check(grant, repo).grant_id == CPU_ID
    raised = {**json.loads(grant.read_bytes()), "monetary_ceiling": "100.00"}
    grant.write_text(json.dumps(raised))
    _git(repo, "commit", "-q", "-am", "raise the ceiling")
    _git(repo, "push", "-q", "origin", "feature")
    assert _refusal(capsys, lambda: _check(grant, repo)) == "grant_differs_from_main"


# -- no pods: the real launch path --------------------------------------------------------------
class _Ladder:
    def record_failure(self, *args, **kwargs):
        return "failure-1"


def _live_pods(tmp_path, account):
    """`RunPodPods` as `phase3 run` builds it, with RunPod in memory."""
    key = tmp_path / "runpod-key"
    key.write_text(pods.CHECK_KEY + "\n")
    key.chmod(0o600)
    head = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return pods.RunPodPods(
        root=tmp_path / "pods",
        key_file=key,
        code_ref=head,
        repository=REPOSITORY,
        transport=account.transport,
        http=account.http,
        sleep=lambda _seconds: None,
        balance_floor=lambda: Decimal(0),
        scoring=COOLING,
    )


class _Recording:
    """RunPod in memory, recording every request the backend sends."""

    def __init__(self):
        self.account = pods.InMemoryRunPod()
        self.requests = []

    def transport(self, method, url, *, body, headers, timeout):
        self.requests.append((method, url))
        return self.account.transport(
            method, url, body=body, headers=headers, timeout=timeout
        )

    def http(self, url, token, timeout):
        return self.account.http(url, token, timeout)


def _experiment(tmp_path, budget, backend):
    return ex.Experiment(
        root=tmp_path / "experiment",
        run_id="run-cooling-cpu",
        pods=backend,
        budget=budget,
        baseline=COOLING.baseline_strategy(),
        token_committed=lambda: Decimal(0),
        cancelled=lambda: False,
        ladder=_Ladder(),
        emit=lambda event_id, body: None,
        repository=REPOSITORY,
        clock=lambda: 1000.0,
        randomness=lambda n: b"\x03" * n,
        scoring=COOLING,
        construction_level=0,
    )


def _propose(run):
    return run.propose_tool(
        {
            "strategy_json": json.dumps(copy.deepcopy(COOLING.baseline_strategy())),
            "hypothesis": "the baseline recipe again",
            "expected_effect": "refused: this grant funds no pod",
        },
        "identity-1",
    )


def _no_pods_budget():
    return ex.phase3_budget(_grant(expires_at="2099-01-01T00:00:00Z"), COOLING)


def test_every_pod_launch_is_refused_before_any_reservation_or_create(tmp_path):
    recording = _Recording()
    backend = _live_pods(tmp_path, recording)
    sent_at_build = list(recording.requests)
    run = _experiment(tmp_path, _no_pods_budget(), backend)
    _propose(run)
    for pid in ("baseline", run.records()[-1]["proposal_id"]):
        record = run.record(pid)
        assert record["status"] == "REFUSED_BUDGET", record
        assert record["reason_code"] == "grant_allows_no_pods"
    # No reservation, no create, and nothing sent after the backend was built.
    events = [row["event"] for row in run.ledger.rows()]
    assert "pod_reserved" not in events and "pod_launch_requested" not in events
    assert run.ledger.pods() == {}
    assert recording.account.creates == []
    assert recording.requests == sent_at_build
    assert not any(method == "POST" for method, _url in recording.requests)
    assert run.pod_committed() == 0
    # A retry or an ablation is refused the same way.
    assert run._retry_budget(1) == "grant_allows_no_pods"


def test_the_carrier_lane_still_runs_the_grant_s_proposals(tmp_path):
    """On a backend that costs no provider money (the CPU carrier, rate 0),
    the tokens-only grant's baseline and proposal are launched:
    `grant_allows_no_pods` refuses paid pods only (VALIDATOR-06's lane)."""
    budget = ex.phase3_budget(
        _grant(expires_at="2099-01-01T00:00:00Z"), COOLING, Decimal(0)
    )
    # A rate-0 backend that also reports no charge (a reported charge stops
    # the session; see the charge tests below).
    free = pods.ScriptedPods(steps=[pods.Step(rate="0", charge="0")] * 2)
    run = _experiment(tmp_path, budget, free)
    _propose(run)
    for record in run.records():
        assert record.get("reason_code") != "grant_allows_no_pods", record
    events = [row["event"] for row in run.ledger.rows()]
    assert "pod_reserved" in events and len(free.launched) == 2
    assert run._retry_budget(1) is None and run.stopped() is None


def test_mutation_without_the_guard_a_paid_pod_is_reserved(tmp_path, monkeypatch):
    """With `_admit_pod`'s tokens-only guard removed, a RunPod-rate pod under
    the tokens-only grant is reserved against money the grant never gave
    pods."""

    def unguarded(self):
        # `_admit_pod` as it was before the tokens-only guard.
        if self.pods_left() <= 0:
            raise ex.BudgetRefused("session_pod_limit_reached")
        reservation = self.budget.pod_reservation_usd
        committed = self.token_committed() + self.pod_committed()
        if committed + reservation > self.budget.run_cap_usd:
            raise ex.BudgetRefused("run_cap_reached_tokens_plus_pods")
        return reservation

    monkeypatch.setattr(ex.Experiment, "_admit_pod", unguarded)
    run = _experiment(tmp_path, _no_pods_budget(), pods.ScriptedPods())
    _propose(run)
    assert run.record("baseline").get("reason_code") != "grant_allows_no_pods"
    events = [row["event"] for row in run.ledger.rows()]
    assert "pod_reserved" in events


def test_mutation_a_pod_budget_for_this_grant_creates_a_pod(tmp_path):
    """The budget's tokens-only flag is what keeps paid pods away: the same
    budget without it reserves and creates a pod on the real launch path
    (RunPod in memory)."""
    recording = _Recording()
    backend = _live_pods(tmp_path, recording)
    budget = dataclasses.replace(_no_pods_budget(), tokens_only=False)
    run = _experiment(tmp_path, budget, backend)
    _propose(run)
    events = [row["event"] for row in run.ledger.rows()]
    assert "pod_reserved" in events
    assert recording.account.creates


def test_mutation_without_the_tokens_only_entry_the_grant_cannot_run(monkeypatch):
    """Not listed in `phase3.TOKENS_ONLY_GRANTS`, the grant's 1.95 cannot
    cover the phase-3 pod share (2.96): the provider's budget refuses it."""
    monkeypatch.setattr(phase3, "TOKENS_ONLY_GRANTS", frozenset())
    with pytest.raises(ex.BudgetRefused) as refused:
        _no_pods_budget()
    assert refused.value.code == "grant_run_cost_cannot_cover_pods_and_tokens"


def test_mutation_without_the_main_blob_flag_a_branch_only_grant_passes(
    tmp_path, capsys, monkeypatch
):
    repo, grant = _repo(tmp_path, on_main=False)
    assert _refusal(capsys, lambda: _check(grant, repo)) == "main_grant_unavailable"
    entry = grant_binding.PHASE3_GRANTS[CPU_ID]
    monkeypatch.setattr(
        grant_binding,
        "PHASE3_GRANTS",
        {
            **grant_binding.PHASE3_GRANTS,
            CPU_ID: dataclasses.replace(entry, main_blob=False),
        },
    )
    assert _check(grant, repo).grant_id == CPU_ID


def test_mutation_without_the_binding_the_runner_takes_a_wrong_pairing(
    tmp_path, capsys, monkeypatch
):
    """Disable `check_phase3_grant` and cooling's grant on battery gets past
    the grant to the runner's next check."""
    argv = _live_argv(tmp_path / "root", BATTERY_CHALLENGE, REPOSITORY / CPU_FILE)
    assert (
        _refusal(capsys, lambda: phase3.main(argv)) == "grant_is_for_another_challenge"
    )
    monkeypatch.setattr(grant_binding, "check_phase3_grant", lambda *a, **k: None)
    assert _refusal(capsys, lambda: phase3.main(argv)) == (
        "the_real_miner_path_needs_a_miner_profile_and_campaign"
    )


def test_mutation_without_the_bound_challenge_any_grant_runs_cooling(
    tmp_path, monkeypatch
):
    grant = _grant("GRAPHITE-GRANT-PHASE4-COOLING.json")
    path = GRANTS / "GRAPHITE-GRANT-PHASE4-COOLING.json"
    monkeypatch.setattr(grant_binding, "PHASE3_BOUND_CHALLENGES", frozenset())
    assert (
        grant_binding.check_phase3_grant(
            path, grant, challenge=COLD_PLATE_CHALLENGE, repository=tmp_path
        )
        is None
    )


# -- the carrier lane: USD 0 booked, any rate refused -------------------------------------------
def _carrier(tmp_path, rate=None):
    """The real `CarrierPods`, its carrier replaced by the carrier suite's
    stand-in (the carrier's own contract, run in a local subprocess)."""
    from test_graphite_carrier_lane import StandIn, carrier

    runner = StandIn()
    backend = carrier(tmp_path, runner)
    if rate is not None:
        # A paid-pod rate reaching the lane by mistake.
        backend.hourly_usd = rate
    return backend, runner


def _carrier_provider(tmp_path, backend):
    """The budget the live run uses: `Phase3Provider` takes the backend's own
    rate (`hourly_usd`)."""
    from carbon.agent_campaign.graphite.model import ScriptedModel, text

    return phase3.Phase3Provider(
        root=tmp_path / "graphite",
        grant=_grant(expires_at="2099-01-01T00:00:00Z"),
        model=ScriptedModel([text("done")]),
        pods=backend,
        scoring=COOLING,
    )


def _booked(run):
    rows = run.ledger.rows()
    reserved = [
        Decimal(r["reserved_usd"]) for r in rows if r["event"] == "pod_reserved"
    ]
    settled = [Decimal(r["charge_usd"]) for r in rows if r["event"] == "pod_settled"]
    return reserved, settled


def test_a_carrier_launch_under_the_grant_books_exactly_zero(tmp_path):
    backend, runner = _carrier(tmp_path)
    budget = _carrier_provider(tmp_path, backend).budget
    assert budget.tokens_only and budget.pays_for_pods
    assert budget.pod_reservation_usd == 0 and budget.pod_allowance_usd == 0
    assert budget.token_allowance_usd == Decimal("1.95")
    run = _experiment(tmp_path, budget, backend)
    _propose(run)
    assert [r["status"] for r in run.records()] == ["SCORED", "SCORED"]
    reserved, settled = _booked(run)
    assert len(reserved) == len(settled) == len(runner.calls) == 2
    assert all(amount == 0 for amount in reserved + settled)
    assert run.pod_committed() == 0


@pytest.mark.parametrize("rate", [Decimal("0.49"), Decimal("0.000001")])
def test_a_non_zero_rate_on_the_carrier_is_refused_not_booked(tmp_path, rate):
    """However small, a rate reaching the lane under the tokens-only grant is
    refused `grant_allows_no_pods`: no reservation, no carrier run."""
    backend, runner = _carrier(tmp_path, rate)
    budget = _carrier_provider(tmp_path, backend).budget
    assert budget.tokens_only and not budget.pays_for_pods
    run = _experiment(tmp_path, budget, backend)
    _propose(run)
    for record in run.records():
        assert record["status"] == "REFUSED_BUDGET", record
        assert record["reason_code"] == "grant_allows_no_pods"
    assert _booked(run) == ([], [])
    assert runner.calls == [] and run.pod_committed() == 0


def test_a_runpod_rate_budget_on_the_carrier_is_refused(tmp_path):
    """A budget built without the backend's rate (RunPod's) and handed to the
    carrier is refused the same way."""
    backend, runner = _carrier(tmp_path)
    run = _experiment(tmp_path, _no_pods_budget(), backend)
    _propose(run)
    assert run.record("baseline")["reason_code"] == "grant_allows_no_pods"
    assert runner.calls == [] and _booked(run) == ([], [])


def test_mutation_without_the_guard_a_carrier_rate_is_booked(tmp_path, monkeypatch):
    def unguarded(self):
        # `_admit_pod` without the tokens-only guard.
        if self.pods_left() <= 0:
            raise ex.BudgetRefused("session_pod_limit_reached")
        reservation = self.budget.pod_reservation_usd
        committed = self.token_committed() + self.pod_committed()
        if committed + reservation > self.budget.run_cap_usd:
            raise ex.BudgetRefused("run_cap_reached_tokens_plus_pods")
        return reservation

    monkeypatch.setattr(ex.Experiment, "_admit_pod", unguarded)
    backend, runner = _carrier(tmp_path, Decimal("0.49"))
    run = _experiment(tmp_path, _carrier_provider(tmp_path, backend).budget, backend)
    _propose(run)
    reserved, _settled = _booked(run)
    assert reserved and all(amount > 0 for amount in reserved)
    assert runner.calls


# -- `--compute runpod` through the real CLI ----------------------------------------------------
class _NeverBuiltRunPod:
    """`pods.RunPodPods` with RunPod in memory, recording whether the run
    ever built it: a refused run must not."""

    def __init__(self):
        self.recording = _Recording()
        self.built = []

    def __call__(self, **kwargs):
        self.built.append(kwargs)
        return pods.RunPodPods(
            **{
                **kwargs,
                "transport": self.recording.transport,
                "http": self.recording.http,
                "sleep": lambda _seconds: None,
                "balance_floor": lambda: Decimal(0),
            }
        )


def _runpod_cli(tmp_path, monkeypatch):
    """`phase3 run --compute runpod` under the grant committed on main (a
    temporary repository with a bare remote), every other input present."""
    from graphite_phase3_fixtures import snapshot_file

    repo, grant = _repo(tmp_path)
    monkeypatch.setattr(
        grant_binding,
        "check_phase3_grant",
        functools.partial(grant_binding.check_phase3_grant, repository=repo),
    )
    fake = _NeverBuiltRunPod()
    monkeypatch.setattr(pods, "RunPodPods", fake)
    monkeypatch.setenv("ENGY_API_KEY", "fixture-engy")
    monkeypatch.setenv("RUNPOD_API_KEY", "fixture-runpod-key")
    root = tmp_path / "root"
    argv = [
        *_live_argv(root, COLD_PLATE_CHALLENGE, grant),
        "--compute",
        "runpod",
        "--miner-profile",
        "p.json",
        "--miner-campaign",
        "c",
        "--literature-snapshot",
        str(snapshot_file(tmp_path / "lit", count=1, verdicts={1: "CORRECT"})),
    ]
    return argv, fake, root


def test_a_runpod_run_under_the_grant_is_refused_through_the_cli(
    tmp_path, capsys, monkeypatch
):
    argv, fake, root = _runpod_cli(tmp_path, monkeypatch)
    code = _refusal(capsys, lambda: phase3.main(argv))
    assert code == "grant_is_tokens_only_use_the_carrier_lane"
    # Nothing was built, reserved or sent: no RunPod backend, no request, no
    # create, and nothing under the run's root.
    assert fake.built == [] and fake.recording.requests == []
    assert fake.recording.account.creates == []
    assert not any(root.rglob("*"))
    assert "fixture-engy" not in capsys.readouterr().out


def test_mutation_without_the_lane_check_the_runpod_run_goes_on(
    tmp_path, capsys, monkeypatch
):
    """Remove the grant from `TOKENS_ONLY_GRANTS` and the same run passes the
    lane check and goes on to the next one (the code ref)."""
    argv, _fake, _root = _runpod_cli(tmp_path, monkeypatch)
    monkeypatch.setattr(phase3, "TOKENS_ONLY_GRANTS", frozenset())
    code = _refusal(capsys, lambda: phase3.main(argv))
    assert code != "grant_is_tokens_only_use_the_carrier_lane"
    assert code == "code_ref_is_not_this_checkout_head"


# -- a backend that reports a charge anyway: booked, found, stopped -------------------------------
CHARGE = Decimal("0.30")


def _charging_carrier(tmp_path):
    """The real `CarrierPods` (rate 0) whose backend reports USD 0.30 for each
    pod anyway: the probe that found the gap."""
    backend, runner = _carrier(tmp_path)
    backend.charge = lambda handle: CHARGE
    return backend, runner


def _charged_run(tmp_path):
    backend, runner = _charging_carrier(tmp_path)
    run = _experiment(tmp_path, _carrier_provider(tmp_path, backend).budget, backend)
    feedback = _propose(run)
    return run, runner, feedback


def _created(run):
    return [r for r in run.ledger.rows() if r["event"] == "pod_created"]


def test_a_reported_charge_is_booked_truthfully(tmp_path):
    """1. The reported amount is booked as the pod's `pod_settled` row and
    counts against the run: real spend is never hidden or zeroed."""
    run, _runner, _feedback = _charged_run(tmp_path)
    settled = [r for r in run.ledger.rows() if r["event"] == "pod_settled"]
    assert [(r["charge_usd"], r["basis"]) for r in settled] == [
        ("0.30", "provider_reported")
    ]
    assert run.pod_committed() == CHARGE


def test_a_reported_charge_is_a_typed_finding_naming_the_pod_and_amount(tmp_path):
    """2. One finding, typed, with the pod's id and the amount."""
    run, _runner, _feedback = _charged_run(tmp_path)
    [created] = _created(run)
    [finding] = run.findings()
    assert finding["id"].startswith("graphite-tokens-only-backend-reported-a-charge-")
    evidence = finding["evidence"]
    assert evidence["kind"] == "TOKENS_ONLY_BACKEND_REPORTED_A_CHARGE"
    assert evidence["proposal_id"] == "baseline"
    assert evidence["detail"] == {
        "code": "tokens_only_backend_reported_a_charge",
        "intent_id": created["intent_id"],
        "pod_id": created["pod_id"],
        "charge_usd": "0.30",
    }


def test_a_reported_charge_stops_the_session_with_no_further_launch(tmp_path):
    """3. Fail closed through the existing stop: `session-stop.json`, the
    proposal waiting behind the baseline is refused, a later proposal is
    rejected before dispatch, and only the one pod ever ran."""
    run, runner, feedback = _charged_run(tmp_path)
    stop = run.stopped()
    assert stop["status"] == "FAILED_INFRA"
    assert stop["reason_code"] == "tokens_only_backend_reported_a_charge"
    assert stop["proposal_id"] == "baseline" and stop["candidate_charged"] is False
    assert feedback["status"] == ex.SESSION_STOPPED
    later = run.propose_tool(
        {
            "strategy_json": json.dumps(COOLING.baseline_strategy()),
            "hypothesis": "another try",
            "expected_effect": "refused: the session stopped",
        },
        "identity-2",
    )
    assert later["status"] == "REJECTED_BEFORE_DISPATCH"
    assert (
        later["reason_code"] == "session_stopped:tokens_only_backend_reported_a_charge"
    )
    with pytest.raises(ex.BudgetRefused) as refused:
        run._admit_pod()
    assert refused.value.code == "session_stopped:tokens_only_backend_reported_a_charge"
    assert len(runner.calls) == 1 and len(_created(run)) == 1


def _charged_timeout_run(tmp_path):
    """A pod that timed out and reported a charge: the proposal's retry, which
    the timeout rule would launch, must not."""
    from graphite_phase3_fixtures import BASELINE, SCORING, grant
    from test_graphite_pod_timeout import CONFIRMED, timed_out

    from carbon.agent_campaign.graphite.pods import Step, synthetic_outputs

    backend = pods.ScriptedPods(
        steps=[
            timed_out(rate="0", charge="0.30"),
            Step(
                outputs=synthetic_outputs(0.2), timing=CONFIRMED, rate="0", charge="0"
            ),
        ]
    )
    budget = dataclasses.replace(
        ex.phase3_budget(grant(), SCORING, Decimal(0)), tokens_only=True
    )
    run = ex.Experiment(
        root=tmp_path / "experiment",
        run_id="run-charged-timeout",
        pods=backend,
        budget=budget,
        baseline=BASELINE,
        token_committed=lambda: Decimal(0),
        cancelled=lambda: False,
        ladder=_Ladder(),
        emit=lambda event_id, body: None,
        repository=REPOSITORY,
        clock=lambda: 1000.0,
        randomness=lambda n: b"\x02" * n,
        construction_level=0,
        scoring=SCORING,
    )
    record = run.run("baseline", "baseline", BASELINE, why=None)
    return run, backend, record


def test_a_reported_charge_refuses_the_in_flight_retry(tmp_path):
    run, backend, record = _charged_timeout_run(tmp_path)
    assert len(backend.launched) == 1
    assert record["status"] == "FAILED_INFRA"
    assert record["reason_code"] == (
        "worker_timeout_retry_refused:session_stopped:"
        "tokens_only_backend_reported_a_charge"
    )
    assert run.pod_committed() == CHARGE


# -- a mutation per guard ----------------------------------------------------------------------
def test_mutation_zeroing_the_charge_hides_real_spend(tmp_path, monkeypatch):
    """Guard 1. The rejected design: book 0 for a tokens-only budget. The
    ledger then shows nothing while the backend reported USD 0.30."""
    real = ex.Experiment._settle

    def zeroing(self, pid, handle):
        if self.budget.tokens_only:
            self.ledger.append(
                "pod_settled",
                intent_id=handle.intent_id,
                proposal=pid,
                charge_usd="0",
                basis="provider_reported",
            )
            return None
        return real(self, pid, handle)

    monkeypatch.setattr(ex.Experiment, "_settle", zeroing)
    run, _runner, _feedback = _charged_run(tmp_path)
    assert run.pod_committed() == 0 != CHARGE
    assert run.findings() == [] and run.stopped() is None


def test_mutation_without_the_finding_the_charge_goes_unreported(tmp_path, monkeypatch):
    """Guard 2. Stop without the finding: nothing names the pod or amount."""

    def stop_only(self, pid, handle, charge):
        self._stop_session(pid, ex.SimpleNamespace(reason_code=ex.TOKENS_ONLY_CHARGE))

    monkeypatch.setattr(ex.Experiment, "_tokens_only_charge", stop_only)
    run, _runner, _feedback = _charged_run(tmp_path)
    assert run.stopped() is not None and run.findings() == []


def test_mutation_without_the_stop_the_run_keeps_launching(tmp_path, monkeypatch):
    """Guard 3a. No stop: the proposal behind the baseline launches a second
    pod and is charged again."""
    monkeypatch.setattr(ex.Experiment, "_stop_session", lambda self, pid, v: None)
    run, runner, _feedback = _charged_run(tmp_path)
    assert len(runner.calls) == 2 and run.pod_committed() == 2 * CHARGE


def test_mutation_without_the_admission_stop_the_retry_launches(tmp_path, monkeypatch):
    """Guard 3b. `_admit_pod` without its stop check: the in-flight
    proposal's timeout retry launches a second pod after the stop."""
    real = ex.Experiment._admit_pod

    def unstoppable(self):
        stopped = self.stopped
        self.stopped = lambda: None
        try:
            return real(self)
        finally:
            self.stopped = stopped

    monkeypatch.setattr(ex.Experiment, "_admit_pod", unstoppable)
    run, backend, _record = _charged_timeout_run(tmp_path)
    assert run.stopped() is not None and len(backend.launched) == 2
