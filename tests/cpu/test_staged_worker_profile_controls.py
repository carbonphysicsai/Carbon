"""The staged request carries its controls, and what the reader rebuilds cannot bound a run.

Two separate properties, and the second is the one that would have been missed.

The reader rebuilds a worker profile from `request.json` to check it against the
digest the writer recorded. Before this, the accelerator block carried no
controls, so a controller that had resolved any rebuilt to a different profile
with a different digest, and **both weaker lanes failed every dispatch**. Adding
the controls to the wire fixes that - and hands the reader a profile that could
answer `effective_deadline_seconds` from bytes it was still verifying.

So the rebuilt profile is narrowed to a type that holds no bound at all. A
sibling type then meets a second problem: admission dispatched on
`type(worker_profile) is DevelopmentWorkerProfile` in three places, and a
sibling falls out of those blocks into the strict check - fail-closed and loud,
but it breaks both weaker lanes and contradicts the documented promise that each
authority reaches exactly one check.
"""

import pytest

from carbon.reconstruction.accelerators import (
    GPU_PROFILE,
    require_local_diagnostic_profile_admission,
    require_miner_lane_profile_admission,
    require_profile_admission,
)
from carbon.reconstruction.model import ReconstructionFailure
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    MINER_HOST_AUTHORITY,
    DevelopmentWorkerProfile,
    RequestDerivedWorkerProfile,
    registered_run_controls,
)

DIGEST = "sha256:" + "a" * 64
PLAN_DIGEST = "sha256:" + "b" * 64
DEVICE = "GPU-31e88d04-75ff-89b2-9160-4b923dd7eb81"


def _profile(authority, *, controls=None):
    """The shape each weaker lane actually stages, not an approximation.

    The device UUID must match the installed-host pattern and the local lane's
    approved plan digest must differ from its approval digest, because the
    profile refuses both otherwise - so a fixture that skipped either would be
    testing a profile the system never produces.
    """
    local = authority == LOCAL_DEVELOPMENT_AUTHORITY
    return DevelopmentWorkerProfile(
        DIGEST,
        DIGEST,
        "carbon.c03.cuda.development.v1",
        "1.0",
        GPU_PROFILE.profile_id,
        DIGEST,
        "VALIDATOR_RECONSTRUCTION" if local else "MINER_RESEARCH",
        authority,
        PLAN_DIGEST if local else None,
        DEVICE,
        controls,
    )


# 1. Asking a request-derived profile for a bound fails.


@pytest.mark.parametrize(
    "bound", ["effective_deadline_seconds", "effective_output_bytes"]
)
def test_a_request_derived_profile_cannot_supply_a_bound(bound: str) -> None:
    """The point of the type. A bound must not come from bytes being verified."""
    rebuilt = RequestDerivedWorkerProfile.of(
        _profile(MINER_HOST_AUTHORITY, controls=registered_run_controls())
    )
    assert not hasattr(rebuilt, bound)
    with pytest.raises(AttributeError):
        getattr(rebuilt, bound)


def test_the_narrowed_profile_retains_no_controls_at_all() -> None:
    """Not merely hidden behind a property - absent from the object."""
    controls = registered_run_controls()
    rebuilt = RequestDerivedWorkerProfile.of(
        _profile(MINER_HOST_AUTHORITY, controls=controls)
    )
    assert not hasattr(rebuilt, "accelerator_controls")
    held = {getattr(rebuilt, name) for name in rebuilt.__slots__}
    assert controls["productive_seconds"] not in held
    assert controls["output_bytes"] not in held


def test_it_still_carries_the_digest_the_comparison_needs() -> None:
    """Narrowing must not cost the reader the check it exists to perform."""
    full = _profile(MINER_HOST_AUTHORITY, controls=registered_run_controls())
    assert RequestDerivedWorkerProfile.of(full).digest == full.digest


# 2. Admission still routes each authority to exactly one check.


@pytest.mark.parametrize(
    ("authority", "expected"),
    [
        (MINER_HOST_AUTHORITY, "require_miner_lane_profile_admission"),
        (LOCAL_DEVELOPMENT_AUTHORITY, "require_local_diagnostic_profile_admission"),
    ],
)
@pytest.mark.parametrize("narrowed", [False, True])
def test_admission_routes_a_staged_profile_to_its_own_check(
    monkeypatch: pytest.MonkeyPatch, authority: str, expected: str, narrowed: bool
) -> None:
    """The assertion that catches the exact-type fall-through.

    A sibling type does not fail the dispatch into a no-op; it falls through to
    the strict check, which the weaker lanes cannot satisfy. Both the controller's
    own profile and the reader's narrowed one must reach the same check.
    """
    reached: list[str] = []
    from carbon.reconstruction import accelerators

    for name in (
        "require_miner_lane_profile_admission",
        "require_local_diagnostic_profile_admission",
        "require_reconstruction_profile_admission",
    ):
        monkeypatch.setattr(
            accelerators, name, lambda *a, _n=name, **k: reached.append(_n)
        )

    worker_profile = _profile(authority, controls=registered_run_controls())
    if narrowed:
        worker_profile = RequestDerivedWorkerProfile.of(worker_profile)
    require_profile_admission(object(), worker_profile=worker_profile)
    assert reached == [expected], f"routed to {reached}, not {expected}"


def test_a_cpu_launch_still_reaches_the_strict_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No worker profile at all is the CPU lane, and it keeps the strict path."""
    reached: list[str] = []
    from carbon.reconstruction import accelerators

    for name in (
        "require_miner_lane_profile_admission",
        "require_local_diagnostic_profile_admission",
        "require_reconstruction_profile_admission",
    ):
        monkeypatch.setattr(
            accelerators, name, lambda *a, _n=name, **k: reached.append(_n)
        )
    require_profile_admission(object(), worker_profile=None)
    assert reached == ["require_reconstruction_profile_admission"]


def test_the_lane_checks_themselves_accept_a_narrowed_profile() -> None:
    """Routing is not enough if the check it routes to refuses the type.

    The same exact-type comparison appeared inside both lane admissions, so
    fixing only the dispatcher would have moved the refusal one frame deeper.
    """
    for authority, check in (
        (MINER_HOST_AUTHORITY, require_miner_lane_profile_admission),
        (LOCAL_DEVELOPMENT_AUTHORITY, require_local_diagnostic_profile_admission),
    ):
        narrowed = RequestDerivedWorkerProfile.of(_profile(authority))
        # `ReconstructionFailure` does not echo, so the code is read from the
        # exception rather than its message. The narrowed profile must get past
        # the worker-profile type gate and fail on the reconstruction profile,
        # which is `object()` here - a different code from the type refusal.
        with pytest.raises(ReconstructionFailure) as caught:
            check(object(), worker_profile=narrowed)
        assert caught.value.code != "reconstruction.accelerator.admission_disabled"

        # The same call with a profile that declares no authority is refused at
        # the gate, which is what makes the assertion above meaningful.
        with pytest.raises(ReconstructionFailure) as refused:
            check(
                object(),
                worker_profile=RequestDerivedWorkerProfile.of(
                    DevelopmentWorkerProfile(DIGEST, DIGEST)
                ),
            )
        assert refused.value.code == "reconstruction.accelerator.admission_disabled"


def test_a_profile_declaring_no_authority_does_not_reach_a_weaker_lane() -> None:
    """Widening the dispatch must not widen who may claim a weaker authority."""
    for check in (
        require_miner_lane_profile_admission,
        require_local_diagnostic_profile_admission,
    ):
        with pytest.raises(ReconstructionFailure):
            check(
                object(),
                worker_profile=RequestDerivedWorkerProfile.of(
                    DevelopmentWorkerProfile(DIGEST, DIGEST)
                ),
            )
        with pytest.raises(ReconstructionFailure):
            check(object(), worker_profile=object())
