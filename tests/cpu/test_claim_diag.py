"""Grade-speed (18 Nov 2026, "use all lanes"): built tasks the claim scan passes over are logged by reason, once per
change; a task's owner and allowance group come from the providers' own keys (never `adapter.owner`, which raises for
a lazy or gated owner); a build requeue refused for good is not asked again in the same process.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

from carbon.challenge_validator import auto_grade, grade_sequencer
from carbon.challenge_validator.direct_receiver import OwnerProviders
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

A, B = ("rtsk_" + c * 64 for c in "ab")


def _grader(lines, *, owners):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)

    def owner(task):
        raise RuntimeError("adapter.owner raised (a lazy or gated owner)")

    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(
            owner=owner, provider_for=SimpleNamespace(hotkey_of=owners.get)
        )
    )
    grader.pending = lambda: [A, B]
    grader._withdrawn_pending = lambda task: False
    grader._copy_decision = lambda task: None
    graded = []
    grader._grade_one = lambda task, *, turn: graded.append(task) or (task, "GRADED")
    return grader, graded


def _claim(grader, claims):
    sequencer = grade_sequencer.Sequencer()
    with sequencer.task() as task:
        taken = []
        try:
            return grader._claim_and_grade(sequencer, task, set(), claims, taken)
        finally:
            for owner in taken:
                claims.release(owner)


def test_the_owner_comes_from_the_providers_keys_and_a_busy_owner_is_logged_once(
    monkeypatch,
):
    from carbon.battery import intake

    lines = []
    monkeypatch.setattr(
        intake, "log", lambda event, **fields: lines.append((event, fields))
    )
    grader, graded = _grader(lines, owners={A: "5Busy", B: "5Free"})
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim("5Busy")
    # adapter.owner raises for both, yet both owners are known from the providers' keys: B is graded
    assert _claim(grader, claims) == (B, "GRADED")
    assert lines == [("grade_claim_passed", {"owner_busy": 1})]
    graded.clear()
    grader.pending = lambda: [A]
    _claim(grader, claims)  # the same pass-over again: no new line
    assert lines == [("grade_claim_passed", {"owner_busy": 1})]


def test_hotkey_of_reads_open_and_lazy_providers_without_opening_one():
    providers = OwnerProviders.__new__(OwnerProviders)
    providers._lock = threading.Lock()
    providers._providers = {"5Open": SimpleNamespace(_views={A: object()})}
    providers._lazy_index = {"dir-b": {B: ("SUCCEEDED", 0)}}
    providers._lazy = {"dir-b": "5Lazy"}
    assert providers.hotkey_of(A) == "5Open"
    assert providers.hotkey_of(SimpleNamespace(value=B)) == "5Lazy"
    assert providers.hotkey_of("rtsk_" + "c" * 64) is None


def test_a_build_requeue_refused_for_good_is_not_asked_again(monkeypatch):
    import carbon.research
    from carbon.research import DirectTaskStateV3

    monkeypatch.setattr(carbon.research, "DirectGetTaskRequestV3", lambda *args: args)

    adapter = LeanRecipeAdapter.__new__(LeanRecipeAdapter)
    adapter.discovery = SimpleNamespace(info=SimpleNamespace(challenge_key="key"))
    reads = []

    def get(request):
        reads.append(1)
        return SimpleNamespace(
            task=SimpleNamespace(state=DirectTaskStateV3.FAILED_INFRA)
        )

    provider = SimpleNamespace(get_research_result=get, _requests={})
    adapter.ledger = SimpleNamespace(requeue_failed_build=lambda *a, **k: "requeuable")
    task_id = SimpleNamespace(value=A)
    adapter._requeue_failed_build(
        "5Owner", task_id, provider
    )  # no retained request: refused for good
    adapter._requeue_failed_build("5Owner", task_id, provider)
    assert reads == [1]


def test_the_steps_owner_lookup_never_opens_a_provider_when_the_ledger_knows_it():
    """Lead (18 Nov 2026): after a restart the incumbent's steps opened 163 lazy owners one at a time (1,556 s) before
    the first claim. Their owner lookup reads the providers' keys and the ledger first; `adapter.owner` only last."""

    def opens(task):
        raise AssertionError("a provider was opened")

    adapter = SimpleNamespace(
        owner=opens,
        contract_digest="sha256:" + "c" * 64,
        provider_for=SimpleNamespace(hotkey_of=lambda task: None),
        ledger=SimpleNamespace(
            owned_outcome=lambda contract, task: "5Ledger" if task == A else None,
            admitted_owner=lambda task: ("contract", "5Earlier") if task == B else None,
        ),
    )
    assert auto_grade.AutoGrader._task_owner(adapter, A) == "5Ledger"
    assert auto_grade.AutoGrader._task_owner(adapter, B) == "5Earlier"


def test_a_requeue_is_asked_at_most_once_per_interval(monkeypatch):
    import carbon.research
    from carbon.challenge_validator import lean_recipe
    from carbon.research import DirectTaskStateV3

    monkeypatch.setattr(carbon.research, "DirectGetTaskRequestV3", lambda *args: args)
    adapter = LeanRecipeAdapter.__new__(LeanRecipeAdapter)
    adapter.discovery = SimpleNamespace(info=SimpleNamespace(challenge_key="key"))
    reads = []

    def get(request):
        reads.append(1)
        return SimpleNamespace(task=SimpleNamespace(state=DirectTaskStateV3.SUCCEEDED))

    provider = SimpleNamespace(get_research_result=get, _requests={})
    task_id = SimpleNamespace(value=B)
    now = [1000.0]
    import time

    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    adapter._requeue_failed_build("5Owner", task_id, provider)
    adapter._requeue_failed_build("5Owner", task_id, provider)  # within the interval: not asked
    now[0] += lean_recipe.REQUEUE_ASK_SECONDS
    adapter._requeue_failed_build("5Owner", task_id, provider)
    assert reads == [1, 1]
