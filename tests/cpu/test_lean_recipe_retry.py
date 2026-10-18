"""Adapter retries keep failed originals and validate durable owned lineage.

The existing provider fixture supplies inert image identities. Infrastructure
failure occurs before execution; no test dispatches a model or Docker worker.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator.interface import Admitted, Unavailable
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.development_session.research_tasks import DIRECT_RETRY_KEY_PREFIX


@pytest.fixture
def lane(tmp_path, monkeypatch):
    request, factory, discovery = _fixture(
        tmp_path / "provider", monkeypatch, material=bundle_material_v5()
    )
    providers = [factory()]
    root = tmp_path / "attempts"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    ledger_path = root / "attempts.sqlite3"
    probes = []

    class TrustedDocker:
        def run(self, arguments, *, timeout):
            assert arguments == [
                "ps",
                "-aq",
                "--filter",
                "label=org.carbonphysicsai.overlay-uv-intent",
            ]
            assert timeout == 10
            probes.append(tuple(arguments))
            return SimpleNamespace(stdout=b"")

    monkeypatch.setattr(
        "carbon.reconstruction.worker.docker_runtime.DockerCLI", TrustedDocker
    )

    def adapter(*, measure_query=False):
        return LeanRecipeAdapter(
            discovery,
            lambda owner: providers[0] if owner == "miner" else None,
            AttemptLedger(ledger_path),
            measure_query=measure_query,
        )

    def reopen():
        providers[0].close()
        providers[0] = factory()
        return adapter()

    selected = adapter()
    submission = Admitted(
        "miner",
        {},
        selected.challenge_id,
        selected.challenge_version,
        request.recipe,
        selected.contract_digest,
    )
    value = SimpleNamespace(
        adapter=selected,
        adapter_factory=adapter,
        provider=lambda: providers[0],
        submission=submission,
        reopen=reopen,
        probes=probes,
    )
    try:
        yield value
    finally:
        providers[0].close()


def _fail_before_execution(lane, task_id, monkeypatch):
    def unavailable(_request):
        raise FileNotFoundError("inert fixture image unavailable before execution")

    provider = lane.provider()
    with monkeypatch.context() as patch:
        patch.setattr(provider, "_resolved_image", unavailable)
        failed = provider.run_queued_task(research.ResearchTaskId(task_id))
    assert failed.state is research.DirectTaskStateV3.FAILED_INFRA
    assert failed.terminal_receipt.infrastructure_failure_class is not None
    assert all(
        provider.ledger.operation_state(child, owner="miner") is None
        for child in provider._all_children(failed.task_id)
    )
    return research.canonical_bytes(failed)


def _parent(lane, monkeypatch):
    first = lane.adapter.evaluate(lane.submission)
    return first["task_id"], _fail_before_execution(lane, first["task_id"], monkeypatch)


def test_historical_request_key_is_unchanged_and_retry_parent_is_strict(lane):
    adapter = lane.adapter
    recipe = adapter.validate_strategy(lane.submission.strategy)
    original = adapter._request("miner", recipe)
    identity = hashlib.sha256(
        ("miner\0" + adapter.contract_digest + "\0" + recipe.digest).encode()
    ).hexdigest()
    assert original.idempotency_key == "lean-recipe-" + identity
    parent = "rtsk_" + "a" * 64
    retry = adapter._request("miner", recipe, retry_of=parent)
    assert retry.idempotency_key == DIRECT_RETRY_KEY_PREFIX + parent
    assert research.canonical_bytes(
        replace(retry, idempotency_key=original.idempotency_key)
    ) == research.canonical_bytes(original)
    for invalid in (
        True,
        "rtsk_bad",
        "rtsk_" + "A" * 64,
        "rtsk_" + "a" * 64 + "suffix",
    ):
        with pytest.raises((TypeError, ValueError)):
            adapter._request("miner", recipe, retry_of=invalid)


def test_retry_preserves_parent_and_has_one_durable_child(lane, monkeypatch):
    parent, original = _parent(lane, monkeypatch)
    child = lane.adapter.retry(lane.submission, parent)
    repeated = lane.adapter.retry(lane.submission, parent)
    assert child == repeated
    assert child["state"] == "ADMITTED" and child["task_id"] != parent
    assert child["qualification"] is child["reward"] is False
    assert lane.adapter.owner(child["task_id"]) == "miner"
    assert lane.adapter.outcome(child["task_id"]) == child
    assert lane.adapter.evaluate(lane.submission)["task_id"] == parent
    assert research.canonical_bytes(lane.provider()._views[parent]) == original
    assert len(lane.provider()._requests) == 2
    assert len(lane.provider().queued_tasks()) == 1
    assert len(lane.probes) == 1  # A replay does not re-probe host cleanup.
    assert set(
        lane.adapter.ledger.submitted_outcomes(lane.adapter.contract_digest)
    ) == {parent, child["task_id"]}


def test_retry_status_and_repeated_submission_survive_restart(lane, monkeypatch):
    parent, original = _parent(lane, monkeypatch)
    child = lane.adapter.retry(lane.submission, parent)
    adapter = lane.reopen()
    assert adapter.owner(parent) == adapter.owner(child["task_id"]) == "miner"
    assert adapter.outcome(child["task_id"]) == child
    assert adapter.retry(lane.submission, parent) == child
    assert adapter.evaluate(lane.submission)["task_id"] == parent
    assert research.canonical_bytes(lane.provider()._views[parent]) == original
    assert len(lane.probes) == 1


def test_failed_child_can_have_one_fresh_descendant_without_rewriting_ancestors(
    lane, monkeypatch
):
    parent, original_parent = _parent(lane, monkeypatch)
    child = lane.adapter.retry(lane.submission, parent)
    original_child = _fail_before_execution(lane, child["task_id"], monkeypatch)
    grandchild = lane.adapter.retry(lane.submission, child["task_id"])
    assert len({parent, child["task_id"], grandchild["task_id"]}) == 3
    assert lane.adapter.retry(lane.submission, child["task_id"]) == grandchild
    assert lane.adapter.owner(grandchild["task_id"]) == "miner"
    assert research.canonical_bytes(lane.provider()._views[parent]) == original_parent
    assert (
        research.canonical_bytes(lane.provider()._views[child["task_id"]])
        == original_child
    )


def test_retry_requires_real_failed_parent_and_current_authentic_owner(
    lane, monkeypatch
):
    queued = lane.adapter.evaluate(lane.submission)["task_id"]
    with pytest.raises(Unavailable, match="construction_retry_predecessor_unavailable"):
        lane.adapter.retry(lane.submission, queued)
    _fail_before_execution(lane, queued, monkeypatch)
    with pytest.raises(Unavailable):
        lane.adapter.retry(replace(lane.submission, hotkey="other"), queued)
    with pytest.raises(Unavailable, match="construction_retry_predecessor_invalid"):
        lane.adapter.retry(lane.submission, "rtsk_bad")
    with pytest.raises(Unavailable, match="construction_retry_predecessor_unavailable"):
        lane.adapter.retry(lane.submission, "rtsk_" + "f" * 64)
    assert len(lane.provider()._requests) == 1 and not lane.probes


def test_same_recipe_and_full_admitted_contract_are_required(lane, monkeypatch):
    parent, _ = _parent(lane, monkeypatch)
    changed = {
        **lane.submission.strategy,
        "procedure": {
            **lane.submission.strategy["procedure"],
            "configuration": {"fixture_change": 1},
        },
    }
    with pytest.raises(Unavailable, match="construction_retry_predecessor_unavailable"):
        lane.adapter.retry(replace(lane.submission, strategy=changed), parent)
    with pytest.raises(Unavailable, match="construction_retry_binding_mismatch"):
        lane.adapter.retry(
            replace(lane.submission, contract_digest="sha256:" + "f" * 64), parent
        )
    assert len(lane.provider()._requests) == 1 and not lane.probes


@pytest.mark.parametrize(
    "field",
    [
        "challenge_info_digest",
        "manifest_digest",
        "construction_kit_digest",
        "public_train_digest",
        "practice_inputs_digest",
        "interface_digest",
        "construction_limits_digest",
        "resource_policy_digest",
    ],
)
def test_retained_full_request_tamper_cannot_keep_owner_or_retry(
    lane, monkeypatch, field
):
    parent, _ = _parent(lane, monkeypatch)
    provider = lane.provider()
    provider._requests[parent] = replace(
        provider._requests[parent], **{field: "sha256:" + "f" * 64}
    )
    assert lane.adapter.owner(parent) is None
    with pytest.raises(Unavailable, match="construction_retry_predecessor_unavailable"):
        lane.adapter.retry(lane.submission, parent)
    assert len(provider._requests) == 1 and not lane.probes


def test_retained_retry_requires_an_authentic_failed_ancestor(lane, monkeypatch):
    parent, _ = _parent(lane, monkeypatch)
    child = lane.adapter.retry(lane.submission, parent)
    ledger_owner = lane.adapter.ledger.owned_outcome
    monkeypatch.setattr(
        lane.adapter.ledger,
        "owned_outcome",
        lambda contract, task: (
            "other" if task == parent else ledger_owner(contract, task)
        ),
    )
    assert lane.adapter.owner(child["task_id"]) is None
    with pytest.raises(LookupError, match="unknown_submission"):
        lane.adapter.outcome(child["task_id"])
    assert len(lane.provider()._requests) == 2


@pytest.mark.parametrize("suffix", ["rtsk_bad", "rtsk_" + "f" * 64])
def test_forged_retry_prefix_does_not_establish_lineage(lane, monkeypatch, suffix):
    parent, _ = _parent(lane, monkeypatch)
    child = lane.adapter.retry(lane.submission, parent)
    provider = lane.provider()
    provider._requests[child["task_id"]] = replace(
        provider._requests[child["task_id"]],
        idempotency_key=DIRECT_RETRY_KEY_PREFIX + suffix,
    )
    assert lane.adapter.owner(child["task_id"]) is None
    with pytest.raises(LookupError, match="unknown_submission"):
        lane.adapter.outcome(child["task_id"])


def test_query_measurement_mode_cannot_change_during_retry(lane, monkeypatch):
    parent, _ = _parent(lane, monkeypatch)
    measured = lane.adapter_factory(measure_query=True)
    assert measured.owner(parent) is None
    with pytest.raises(Unavailable, match="construction_retry_predecessor_unavailable"):
        measured.retry(lane.submission, parent)
    assert len(lane.provider()._requests) == 1 and not lane.probes


def test_graph_retry_replay_uses_retained_source_but_fresh_child_checks_workspace(
    lane, monkeypatch
):
    from test_synthetic_graph_adapter import _graph_case

    from carbon.development_session.research_workspace import ResearchWorkspace
    from carbon.level4 import staging, submission
    from carbon.level4.allowlist import Allowlist

    material = lane.adapter.discovery._material
    _, _, old_recipe, raw_manifest, graph_files = _graph_case()
    old_manifest = json.loads(raw_manifest)
    forward = json.loads(graph_files[old_manifest["documents"]["forward"]])
    allowed = Allowlist(material["allowlist_bytes"])
    forward["allowlist"] = allowed.version
    init_spec = json.loads(graph_files[old_manifest["documents"]["init_spec"]])
    init_spec["graph"] = (
        "sha256:" + hashlib.sha256(submission.canonical(forward)).hexdigest()
    )
    manifest, graph_files = submission.build(
        challenge=material["construction_kit"]["id"],
        interface=old_manifest["interface"],
        allowlist=allowed,
        forward=forward,
        init_spec=init_spec,
    )
    recipe = old_recipe.to_dict()
    recipe["challenge"] = material["construction_kit"]
    recipe["source"]["submission_digest"] = submission.digest(manifest)
    admitted = replace(lane.submission, strategy=recipe)
    workspace = ResearchWorkspace(lane.provider().ledger, "miner")
    workspace.put(staging.WORKSPACE_MANIFEST, submission.canonical(manifest))
    for name, body in graph_files.items():
        workspace.put(staging.WORKSPACE_PREFIX + name[7:] + ".json", body)
    parent = lane.adapter.evaluate(admitted)["task_id"]
    original_parent = _fail_before_execution(lane, parent, monkeypatch)
    child = lane.adapter.retry(admitted, parent)
    retained_source = lane.provider()._source_envelope(
        child["task_id"], lane.adapter.validate_strategy(recipe)
    )
    workspace.put(
        staging.WORKSPACE_MANIFEST,
        b"{}",
        expected_digest=workspace.current_digest(staging.WORKSPACE_MANIFEST),
    )
    assert lane.adapter.retry(admitted, parent) == child
    adapter = lane.reopen()
    assert adapter.retry(admitted, parent) == child
    assert adapter.owner(child["task_id"]) == "miner"
    assert (
        lane.provider()._source_envelope(
            child["task_id"], adapter.validate_strategy(recipe)
        )
        == retained_source
    )
    _fail_before_execution(lane, child["task_id"], monkeypatch)
    with pytest.raises(Unavailable, match="construction_recipe_graph_manifest_invalid"):
        adapter.retry(admitted, child["task_id"])
    assert research.canonical_bytes(lane.provider()._views[parent]) == original_parent
    assert len(lane.provider()._requests) == 2 and not lane.probes
