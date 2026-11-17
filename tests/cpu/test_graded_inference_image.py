"""A receiver's configured ``graded_inference_image`` (Lead + Validator 17 Nov).

After a declared door migration moved the worker images, every counted grade refused
``leg_minimum_platform_mismatch``: the sealed pack's leg minimums are pinned to the previous
inference image while the graded worker evidence named the new one. Builds may stay on the new
image; the GRADED graph inference runs on the configured image the pack is pinned to. Absent the
configuration, everything is as before (the mismatch still refuses); a bundle regrade refuses while
it is set. Custody binds a differing inference image to the retained ``inference_image`` role.

Synthetic image identities and the existing counted-graph e2e fixture; no docker, worker, model or
solver runs. No crown, LIVE eligibility or settlement authority is claimed.
"""

# ruff: noqa: F811 (the imported case fixture is received by tests)
from __future__ import annotations

import json

import pytest
import test_graph_pool_counted_e2e as e2e
from test_graph_pool_counted_e2e import TASK, _cap_rows, _grade, _setup
from test_physical_dual_pack_end_to_end import IMAGE as PACK_IMAGE
from test_pool_dual_e2e import case  # noqa: F401
from test_public_bundle_model_custody import _json, _sha

from carbon.challenge_validator import direct_receiver as dr
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session import bundle_construction_worker, paired_inference
from carbon.reconstruction.worker.model import WorkerImageIdentity
from scripts.dev.score_lab import public_unbound_custody as custody

#: the migrated build image (synthetic); the pack's platform image is PACK_IMAGE.
BUILD = _sha(b"synthetic-migrated-build-image")


def _identity(image_id):
    return WorkerImageIdentity(*([image_id] * 8))


@pytest.fixture
def migrated(case, tmp_path, monkeypatch):
    """A graph task built and retained on BUILD (image.json, worker evidence, receiver image), graded
    against a sealed pack whose leg minimums name PACK_IMAGE. Records the image each inference ran on.
    """
    monkeypatch.setattr(e2e, "IMAGE", BUILD)
    fixture = _setup(case, tmp_path, monkeypatch)
    assert json.loads(fixture.artifacts["image.json"])["image_id"] == BUILD
    used = []
    pair, single = (
        paired_inference.infer_frozen_pair,
        bundle_construction_worker._infer_state,
    )

    def pair_on(ledger, **kwargs):
        used.append(("pair", kwargs["inference_image"].image_id))
        result = pair(ledger, **kwargs)
        # the pair names the image it ran on, as the real worker's does
        result.evidence["inference_image_id"] = kwargs["inference_image"].image_id
        return result

    def single_on(ledger, **kwargs):
        used.append(("single", kwargs["inference_image"].image_id))
        return single(ledger, **kwargs)

    monkeypatch.setattr(paired_inference, "infer_frozen_pair", pair_on)
    monkeypatch.setattr(bundle_construction_worker, "_infer_state", single_on)
    store = {PACK_IMAGE: PACK_IMAGE}
    monkeypatch.setattr(
        retention, "_docker_image_id", lambda image_id: store.get(image_id)
    )
    fixture.used, fixture.image_store = used, store
    yield fixture
    retention.install_graded_inference_image(None)


def _regrade_root(fixture):
    (root,) = [
        p
        for p in fixture.base.iterdir()
        if p.is_dir() and p.name != TASK and not p.name.endswith(".evaluation")
    ]
    return root


def test_unconfigured_the_migrated_grade_still_refuses_the_platform_mismatch(
    migrated,
):
    assert retention.GRADED_INFERENCE_IMAGE is None
    result = _grade(migrated, counted=True)
    assert result["private_evaluation_state"] == "UNAVAILABLE", result
    assert "leg_minimum_platform_mismatch" in result["private_evaluation_reason"]
    assert {image for _, image in migrated.used} == {BUILD}
    root = _regrade_root(migrated)
    worker = json.loads((root / "worker-evidence.json").read_bytes())
    assert worker["inference_image_id"] == worker["image_id"] == BUILD
    assert not (root / retention.GRADED_INFERENCE_IMAGE_FILE).exists()
    assert _cap_rows(migrated)[0][2] == "RELEASED"


def test_configured_the_graph_is_graded_on_the_packs_image_and_binds(migrated, capsys):
    retention.install_graded_inference_image(_identity(PACK_IMAGE))
    result = _grade(migrated, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    # every graded inference step ran on the configured image, none on the build's
    assert migrated.used and {image for _, image in migrated.used} == {PACK_IMAGE}
    assert _cap_rows(migrated) == [
        (TASK, "GRADED", "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE", e2e.OWNER, 7)
    ]
    root = _regrade_root(migrated)
    worker = json.loads((root / "worker-evidence.json").read_bytes())
    # the build lineage stays the build's; the inference names the image it ran on
    assert (worker["image_id"], worker["parent_image_id"]) == (BUILD, BUILD)
    assert worker["inference_image_id"] == PACK_IMAGE
    assert json.loads((root / "image.json").read_bytes())["image_id"] == BUILD
    graded = json.loads((root / retention.GRADED_INFERENCE_IMAGE_FILE).read_bytes())
    assert graded["image_id"] == PACK_IMAGE
    roles = json.loads((migrated.base / (root.name + ".roles.json")).read_bytes())[
        "roles"
    ]
    assert roles["inference_image"] == {
        "file": retention.GRADED_INFERENCE_IMAGE_FILE,
        "codec": "json",
    }
    # the dev evidence of the origin is untouched
    origin = json.loads(
        (migrated.retained["artifact_path"] / "worker-evidence.json").read_bytes()
    )
    assert origin["inference_image_id"] == BUILD
    notes = [json.loads(x) for x in capsys.readouterr().err.splitlines() if x]
    assert any(
        n.get("event") == "graded_on_configured_inference_image"
        and n.get("graded_image") == PACK_IMAGE
        for n in notes
    )


def test_configured_image_absent_from_the_image_store_refuses_typed(migrated):
    retention.install_graded_inference_image(_identity(PACK_IMAGE))
    migrated.image_store.clear()
    with pytest.raises(
        retention.RetentionUnavailable,
        match="graded_inference_image_not_in_the_image_store",
    ):
        _grade(migrated, counted=True)
    assert migrated.used == []  # refused before any inference
    assert _cap_rows(migrated)[0][2] == "RELEASED"


def test_a_bundle_regrade_refuses_while_a_graded_image_is_configured():
    retention.install_graded_inference_image(_identity(PACK_IMAGE))
    try:
        with pytest.raises(
            retention.RetentionUnavailable, match="graded_inference_image_graph_only"
        ):
            retention._regrade_inference_image(
                "bundle", {}, object(), object(), TASK, TASK
            )
    finally:
        retention.install_graded_inference_image(None)


def test_the_regrade_worker_evidence_names_the_image_it_inferred_on():
    origin = {"image_id": BUILD, "parent_image_id": BUILD, "inference_image_id": BUILD}
    graded = type(
        "G",
        (),
        {"worker_operation": "operation-" + "1" * 64, "predictions_digest": "d"},
    )
    evidence = json.loads(
        retention._graph_regrade_worker_evidence(
            _json(origin),
            provider=None,
            owner="o",
            identity="i",
            runner=object(),
            graded=graded,
            receipt_raw=b"{}",
            predictions=b"[]",
            timed_result=None,
            timed_raw=None,
            timed_identity="t",
            inference_image_id=PACK_IMAGE,
        )
    )
    assert (evidence["image_id"], evidence["parent_image_id"]) == (BUILD, BUILD)
    assert evidence["inference_image_id"] == PACK_IMAGE


def _manifest(path, image_id):
    identity = _identity(image_id)
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.c03.worker-image.v1",
                **{k: getattr(identity, k) for k in identity.__dataclass_fields__},
            }
        )
    )
    return str(path)


def test_the_configuration_names_one_valid_absolute_manifest(tmp_path):
    good = _manifest(tmp_path / "graded.json", PACK_IMAGE)
    assert dr._graded_inference_image(good) == _identity(PACK_IMAGE)
    try:
        dr.install_graded_inference_image({"graded_inference_image": good})
        assert retention.GRADED_INFERENCE_IMAGE == _identity(PACK_IMAGE)
        dr.install_graded_inference_image({})
        assert retention.GRADED_INFERENCE_IMAGE is None
    finally:
        retention.install_graded_inference_image(None)
    (tmp_path / "bad.json").write_text("{}")
    for bad in (
        "graded.json",
        str(tmp_path / "bad.json"),
        str(tmp_path / "missing.json"),
        [good],
        None,
        "",
    ):
        with pytest.raises(ValueError, match="invalid graded_inference_image"):
            dr._graded_inference_image(bad)
    assert "graded_inference_image" in dr._OPTIONAL_FIELDS


# custody: the graph worker lineage with and without the graded inference image role


def _custody(case, tmp_path, monkeypatch, *, worker=None, graded_image=None):
    """Custody over a graph retained on BUILD (as retention keeps it), then re-prepared with the worker
    evidence changed by ``worker`` and, with ``graded_image``, an ``inference_image`` role naming it.
    """
    monkeypatch.setattr(e2e, "IMAGE", BUILD)
    _material, _recipe, artifacts, evidence = e2e._graph_originals(
        case, json.loads(json.dumps(case["outputs"]))
    )
    base, entries = tmp_path / "artifacts", tmp_path / "entries"
    base.mkdir(mode=0o700)
    entries.mkdir(mode=0o700)
    retention._retain_graph_artifacts(
        artifacts, TASK, artifact_directory=base, entry_directory=entries
    )
    manifest = json.loads((base / (TASK + ".roles.json")).read_bytes())
    evidence.update(worker or {})
    artifacts["worker-evidence.json"] = _json(evidence)
    if graded_image is not None:
        artifacts[retention.GRADED_INFERENCE_IMAGE_FILE] = _json(
            dict.fromkeys(WorkerImageIdentity.__dataclass_fields__, graded_image)
        )
        manifest["roles"]["inference_image"] = {
            "file": retention.GRADED_INFERENCE_IMAGE_FILE,
            "codec": "json",
        }
    manifest["retained_files"] = {n: _sha(b) for n, b in sorted(artifacts.items())}
    root = tmp_path / "again"
    root.mkdir()
    for name, raw in artifacts.items():
        (root / name).write_bytes(raw)
    path = tmp_path / "again.roles.json"
    path.write_bytes(_json(manifest))
    return custody.prepare_custody_v5(root, path), artifacts


def test_custody_accepts_a_differing_inference_image_bound_by_its_role(
    case, tmp_path, monkeypatch
):
    receipt, artifacts = _custody(
        case,
        tmp_path,
        monkeypatch,
        worker={"inference_image_id": PACK_IMAGE},
        graded_image=PACK_IMAGE,
    )
    assert receipt["roles"]["inference_image"]["sha256"] == _sha(
        artifacts[retention.GRADED_INFERENCE_IMAGE_FILE]
    )
    assert receipt["image_digest"] == _sha(artifacts["image.json"])


@pytest.mark.parametrize(
    ("worker", "graded_image", "code"),
    [
        # differs with no role naming it (as before)
        ({"inference_image_id": PACK_IMAGE}, None, "graph_worker_lineage"),
        # the role names another image than the worker ran on
        (
            {"inference_image_id": PACK_IMAGE},
            _sha(b"synthetic-other-image"),
            "graph_worker_lineage",
        ),
        # a role only when it differs from the build
        ({}, BUILD, "graph_graded_inference_image"),
        # the build lineage stays the image role's
        (
            {"image_id": PACK_IMAGE, "inference_image_id": PACK_IMAGE},
            PACK_IMAGE,
            "graph_worker_lineage",
        ),
        (
            {"parent_image_id": PACK_IMAGE, "inference_image_id": PACK_IMAGE},
            PACK_IMAGE,
            "graph_worker_lineage",
        ),
    ],
)
def test_custody_refuses_an_unbound_or_misplaced_inference_image(
    case, tmp_path, monkeypatch, worker, graded_image, code
):
    with pytest.raises(custody.CustodyRefused, match=code):
        _custody(case, tmp_path, monkeypatch, worker=worker, graded_image=graded_image)
