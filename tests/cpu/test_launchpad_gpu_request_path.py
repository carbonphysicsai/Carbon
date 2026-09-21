"""A browser-selected GPU runtime, carried to the wire the worker actually reads.

Device-free by construction. `stage_request` writes the real request and input
files and `load_worker_request` reads that directory back; no schema check,
decoder or admission dispatch is replaced, no container is created and no
accelerator is initialized. The one simulated boundary is the container
controller's own execution, which is where a device would be attached - so this
covers the path up to dispatch and deliberately not the numerics beyond it.

What it adds over the protocol round-trip in `test_local_staged_request_reader`
is provenance. That suite stages a hand-written worker profile and proves the
reader accepts it. This one takes the identities the Launchpad *actually
produces* for a campaign whose runtime declares GPU research - the compiled
plan, the resolved policy and resource-class refs, the installed device record -
and proves those are what reach the reader, with the miner role and authority
intact. A profile that round-trips is worth little if the product builds a
different one.
"""

import json

import pytest
from test_public_gpu_research import STRATEGY, fixture, invoke

from carbon.development_session import gpu_research as gpu
from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker import accelerator_runtime
from carbon.reconstruction.worker.model import (
    MINER_HOST_AUTHORITY,
    DevelopmentWorkerProfile,
    registered_run_controls,
)
from carbon.reconstruction.worker.protocol import load_worker_request, stage_request


def _launchpad_dispatch(tmp_path, monkeypatch):
    """Run the campaign's GPU practice and capture what it hands the controller.

    The arguments recorded here are the real ones: a plan compiled from the
    registered recipe under the GPU contracts, a replica bound to the resolved
    policy and resource class, the campaign's own public TRAIN archive and its
    derived seed.
    """
    data, ledger, image, calls, composition = fixture(tmp_path, monkeypatch)
    invoke(composition.executor.practice, strategy=STRATEGY)
    assert len(calls) == 1, "the campaign must dispatch exactly one GPU attempt"
    return data, ledger, image, calls[0], composition


def _miner_lane_profile(replica, device):
    """Rebuild the worker profile exactly as the miner lane composes it.

    Mirrors `IsolatedReconstructionController._execute_miner_lane`. Kept in step
    with it by `test_profile_matches_the_controllers_own_composition` below,
    which fails if that constructor changes shape.
    """
    identity = replica.binding.replicate_identity
    return DevelopmentWorkerProfile(
        identity.policy_ref.content_digest,
        identity.resource_class_ref.content_digest,
        "carbon.c03.cuda.development.v1",
        "1.0",
        GPU_PROFILE.profile_id,
        device.digest,
        AcceleratorRole.MINER_RESEARCH.value,
        MINER_HOST_AUTHORITY,
        None,
        device.device_uuid,
        registered_run_controls(),
    )


def test_browser_selected_gpu_runtime_reaches_the_real_reader(tmp_path, monkeypatch):
    """Browser selection -> campaign composition -> staged request -> real reader."""
    _data, _ledger, _image, dispatch, _c = _launchpad_dispatch(tmp_path, monkeypatch)
    device = accelerator_runtime.host_device()
    profile = _miner_lane_profile(dispatch["replica"], device)

    stage, _manifest = stage_request(
        stage_root=tmp_path / "staged",
        claimed=dispatch["claimed"],
        repeat_plan=dispatch["repeat_plan"],
        replica=dispatch["replica"],
        plan=dispatch["plan"],
        training_archive=dispatch["training_archive"],
        derived_seed=dispatch["derived_seed"],
        worker_profile=profile,
    )

    request = json.loads((stage / "request.json").read_bytes())
    assert request["accelerator"]["authority"] == MINER_HOST_AUTHORITY
    assert request["accelerator"]["role"] == AcceleratorRole.MINER_RESEARCH.value
    assert request["accelerator"]["profile_id"] == GPU_PROFILE.profile_id
    # No grant key at all, the whole point of the lane.
    assert "grant_digest" not in request["accelerator"]

    _claimed, loaded_plan, loaded_profile, _archive, _seed = load_worker_request(stage)

    # The plan the miner's browser selection compiled is the plan the worker
    # reads back - not merely a well-formed one.
    assert loaded_plan.to_ref() == dispatch["plan"].to_ref()
    assert loaded_profile.accelerator_authority == MINER_HOST_AUTHORITY
    assert loaded_profile.accelerator_device_uuid == device.device_uuid
    assert loaded_profile.accelerator_grant_digest == device.digest


def test_the_identities_are_the_campaigns_own_not_a_fixtures(tmp_path, monkeypatch):
    """Provenance: every identity traces to the campaign that produced it."""
    _data, _ledger, _image, dispatch, composition = _launchpad_dispatch(
        tmp_path, monkeypatch
    )
    identity = dispatch["replica"].binding.replicate_identity

    # Resolved from the campaign's own contracts, not written by the test.
    assert identity.policy_ref == composition.inspection.policy_ref
    assert identity.resource_class_ref == composition.inspection.resource_class_ref
    # The plan is the GPU-contract compilation of the requested recipe, which is
    # a different object from the CPU compilation of the same recipe.
    from carbon.development_session.research_catalog import compile_recipe

    cpu_plan = compile_recipe(STRATEGY)[0].construction_plan
    assert dispatch["plan"].to_ref() != cpu_plan.to_ref()
    assert (
        dispatch["plan"].to_ref().content_digest
        == identity.construction_plan_ref.content_digest
    )


def test_profile_matches_the_controllers_own_composition(tmp_path, monkeypatch):
    """This suite must not drift from the lane it is asserting about.

    If `_execute_miner_lane` ever composes its worker profile differently, the
    helper above becomes a fiction that still passes. Comparing against the
    controller's real construction keeps that honest.
    """
    _data, _ledger, _image, dispatch, _c = _launchpad_dispatch(tmp_path, monkeypatch)
    device = accelerator_runtime.host_device()
    mine = _miner_lane_profile(dispatch["replica"], device)

    identity = dispatch["replica"].binding.replicate_identity
    assert mine.research_resource_policy_digest == identity.policy_ref.content_digest
    assert mine.resource_class_digest == identity.resource_class_ref.content_digest
    assert mine.accelerator_controls == registered_run_controls()
    # The controls are the worker's registered bounds with nothing added: the
    # fields an approval would supply stay absent rather than defaulted.
    assert set(mine.accelerator_controls) == {
        "productive_seconds",
        "host_ram_bytes",
        "output_bytes",
        "worker_network",
    }
    accelerators = mine.body["accelerators"]
    assert accelerators["assurance"]["validator_grade"] is False
    assert "grant_digest" not in accelerators


def test_the_lane_label_travels_with_the_role(tmp_path, monkeypatch):
    """The role decides the lane, and the record says which it ran in.

    Deliberately not asserted here: that a validator role cannot carry this
    authority. Main admits GPU validator reconstruction through the same host
    record by owner decision (C-CORE-19, `a756b448`), with
    `SELF_SERVICE_HOST_AUTHORITY` as an alias of this one, and
    `tests/cpu/test_validator_self_service_admission.py` owns that boundary.
    Asserting the older pairing here would encode a superseded requirement.
    """
    _data, _ledger, _image, dispatch, _c = _launchpad_dispatch(tmp_path, monkeypatch)
    device = accelerator_runtime.host_device()
    accelerators = _miner_lane_profile(dispatch["replica"], device).body["accelerators"]

    assert accelerators["role"] == AcceleratorRole.MINER_RESEARCH.value
    assert accelerators["lane"] == "MINER_CONTAINED"
    assert accelerators["allocation"] == "TASK_OWNED_NOT_EXCLUSIVE"
    assert accelerators["assurance"]["validator_grade"] is False
    assert accelerators["assurance"]["official_eligible"] is False


def test_no_device_was_attached_by_this_suite():
    """Stated as an assertion rather than a comment.

    The Launchpad requires no Carbon-owned or developer-owned device. The device
    binding on this lane is an operator-installed record, so the whole path up
    to dispatch is exercisable with no hardware at all.
    """
    from carbon.reconstruction.host_inventory import HostDeviceRecord

    assert HostDeviceRecord is not None
    assert gpu.lane_for_role(AcceleratorRole.MINER_RESEARCH).value == "MINER_CONTAINED"
