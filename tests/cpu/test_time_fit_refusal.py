"""A practice the campaign's time limit cannot fit is a time-limit refusal,
never FAILED_INFRA (gate2b).

On Motor with a remote GPU, six practices went FAILED_INFRA: the GPU worker's
reservation was refused "worker cannot fit remaining elapsed time", the
practice fell back to the CPU build, and the agent read the result as
"practice backend persistently down". Now, the same for every Challenge:
- a GPU attempt that meets the campaign's own limit (its time, a ceiling) or
  its stop or pause ends the practice with it - no CPU fallback;
- that refusal reaches the agent and the page as a time-limit refusal, with
  what the work needs, what is left, and the next step, in words;
- a direct (bundle or graph) task refused that way is REFUSED
  `time_limit_reached`, never FAILED_INFRA.
"""

from __future__ import annotations

import pytest
from test_gpu_only_entry import JAX_RUNTIME
from test_gpu_per_backend import JAX, entry
from test_research_budget_refusal_typing import (
    OWNER,
    State,
    charging,
    compose,
    product,
    run,
)

from carbon.development_session.gpu_practice import device_build, run_on_device
from carbon.development_session.research_control import (
    CampaignDeadlineReached,
    DispatchStopped,
)
from carbon.development_session.research_ledger import (
    CARBON_SERVICE_CAPACITY,
    MINER_CEILING_REACHED,
    LedgerRefusal,
)
from carbon.development_session.research_tasks import (
    _campaign_limit_code,
    ceiling_correction,
)
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS


def time_refusal(requested=600, used=673, ceiling=1200):
    return LedgerRefusal(
        "worker cannot fit remaining elapsed time",
        code=MINER_CEILING_REACHED,
        dimension="elapsed_seconds",
        basis="miner_launch_budget",
        used=used,
        requested=requested,
        ceiling=ceiling,
    )


class Parents:
    def for_bundle(self, bundle):
        return ("parent", bundle)


class Practice:
    cache_root = "/cache"

    def __init__(self):
        self.gpu_image = JAX
        self.resolved = []

    def parents(self):
        return Parents()

    def _resolve(self, bundle):
        self.resolved.append(bundle)
        if bundle == "cpu":
            return "cpu image"
        raise FileNotFoundError(bundle)


@pytest.mark.parametrize(
    "limit",
    [
        time_refusal(),
        CampaignDeadlineReached("campaign deadline", time_refusal()),
        DispatchStopped(),
    ],
    ids=["time", "deadline", "stop"],
)
def test_a_campaign_limit_in_the_gpu_preparation_never_falls_back(limit):
    def preparation(bundle, parent, expanded):
        raise limit

    practice = Practice()
    with pytest.raises(type(limit)):
        device_build(practice, entry({JAX_RUNTIME}), lambda ref: ref, preparation)
    # The CPU build was never tried.
    assert "cpu" not in practice.resolved


def test_a_campaign_limit_in_the_gpu_build_never_falls_back():
    from carbon.development_session.library_environment_cache import (
        VerifiedLibraryOverlay,
    )

    calls = []

    def run(trial, built, image, parent, device):
        calls.append(device)
        raise time_refusal()

    with pytest.raises(LedgerRefusal):
        run_on_device(
            Practice(),
            "trial-1",
            entry({JAX_RUNTIME}),
            lambda ref: ref,
            lambda *_: object.__new__(VerifiedLibraryOverlay),
            run,
        )
    assert len(calls) == 1 and calls[0] is not None


def test_the_time_refusal_says_needed_and_left_and_the_next_step():
    record = time_refusal().record()
    words = ceiling_correction({**record, "refused_at": "reservation"})
    assert "This needs 600 s" in words
    assert "527 s left of the time limit you set yourself (1200 s, 673 s used)" in words
    assert "not a failure" in words
    assert "budget.elapsed_seconds" in words and "leave more of the time" in words
    # Other ceilings keep their own words.
    other = ceiling_correction(
        {**record, "dimension": "research_trials", "refused_at": "reservation"}
    )
    assert "ceiling you set yourself: research_trials" in other


def test_a_practice_the_time_cannot_fit_completes_typed_through_the_executor(
    tmp_path,
):
    clock = [1000.0]
    ledger = product(tmp_path, clock=lambda: clock[0], elapsed_seconds=1200)
    f, p, e = compose(
        tmp_path, ledger, charging(ledger, {"numerical_milliseconds": 600_000})
    )
    assert run(f, p, 0).state is State.SUCCEEDED  # starts the campaign's clock
    clock[0] += 673
    done = run(f, p, 1)
    # Completed with its typed result, never an infrastructure failure.
    assert done.state is State.SUCCEEDED
    assert done.terminal_receipt.infrastructure_failure_class is None
    result = e.public_result(done)["result"]
    assert result["dimension"] == "elapsed_seconds"
    assert "This needs 600 s" in result["correction"]
    assert "s left of the time limit you set yourself" in result["correction"]
    assert OWNER


def test_a_direct_task_refused_by_the_campaign_limit_is_refused_by_code():
    assert _campaign_limit_code(time_refusal()) == "time_limit_reached"
    assert _campaign_limit_code(
        CampaignDeadlineReached("campaign deadline", time_refusal())
    ) == ("time_limit_reached")
    trials = LedgerRefusal(
        "ceiling",
        code=MINER_CEILING_REACHED,
        dimension="research_trials",
        basis="miner_launch_budget",
    )
    assert _campaign_limit_code(trials) == "miner_ceiling_reached"
    capacity = LedgerRefusal(
        "capacity", code=CARBON_SERVICE_CAPACITY, dimension="research_trials"
    )
    assert _campaign_limit_code(capacity) is None
    assert _campaign_limit_code(ValueError("x")) is None
    assert "budget.elapsed_seconds" in NEXT_ACTIONS["time_limit_reached"]
    assert "not a failure" in NEXT_ACTIONS["time_limit_reached"]
