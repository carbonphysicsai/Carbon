"""Route (a) (Validator 5 Nov): a SITTING king whose construction parent moved since he was built is regraded on HIS OWN
retained parent, iff the receiver configures that image's identity, the image store answers to that id directly with
exactly that .Id, and the receiver infers on its construction parent; anything else, and any other task, refuses
``regrade_construction_parent_differs`` as before. Every inference step of the regrade uses the chosen image.

All 4 doors' kings failed their automatic regrade with regrade_construction_parent_differs (Deploy 5 Nov 09:3x).
Synthetic identities; no docker, model or solver runs.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_receiver as dr
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.reconstruction.worker.model import WorkerImageIdentity

KING, OTHER = "rtsk_" + "a" * 64, "rtsk_" + "b" * 64
OLD, NEW = "sha256:" + "1" * 64, "sha256:" + "2" * 64


def _identity(image_id):
    # a worker image's id is its config digest (WorkerImageIdentity checks it)
    return WorkerImageIdentity(
        image_id, image_id, *("sha256:" + c * 64 for c in "345678")
    )


@pytest.fixture
def door(monkeypatch):
    """A receiver whose construction parent (and inference image) moved from OLD to NEW; the king was built on OLD."""
    monkeypatch.setattr(
        "carbon.development_session.library_bundles.LibraryBundleRef.from_dict",
        lambda value: value,
    )
    monkeypatch.setattr(
        retention,
        "_construction_parent",
        lambda provider, bundle: provider.construction_parent,
    )
    store = {OLD: OLD}
    monkeypatch.setattr(
        retention, "_docker_image_id", lambda image_id: store.get(image_id)
    )
    retention.install_king_retained_parents([_identity(OLD)])
    yield store
    retention.install_king_retained_parents([])


def _provider(current=NEW, inference=None):
    return SimpleNamespace(
        construction_parent=SimpleNamespace(image_id=current),
        inference_image=_identity(current if inference is None else inference),
    )


RECIPE = SimpleNamespace(
    to_dict=lambda: {"source": {"kind": "bundle", "bundle_ref": {"x": 1}}}
)


def _image(kind="bundle", built_on=OLD):
    key = "image_id" if kind == "graph" else "parent_image_id"
    return {"image.json": json.dumps({key: built_on}).encode()}


def _choose(provider, origin=KING, incumbent=KING, kind="bundle", built_on=OLD):
    return retention._regrade_inference_image(
        kind, _image(kind, built_on), provider, RECIPE, origin, incumbent
    )


def test_the_same_parent_regrades_on_the_receivers_own_image(door):
    provider = _provider(current=OLD)
    assert _choose(provider) is provider.inference_image


def test_a_king_built_on_the_previous_parent_regrades_on_his_own_retained_parent(
    door, capsys
):
    chosen = _choose(_provider())
    assert chosen == _identity(OLD)
    (line,) = [json.loads(x) for x in capsys.readouterr().err.splitlines()]
    assert line["event"] == "king_regrade_on_retained_parent"
    assert (line["incumbent"], line["retained_parent"], line["current_parent"]) == (
        KING,
        OLD,
        NEW,
    )


def test_a_graph_king_regrades_on_his_retained_inference_image(door):
    assert _choose(_provider(), kind="graph") == _identity(OLD)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("missing", "retained_parent_not_in_the_image_store"),
        ("mismatch", "retained_parent_not_in_the_image_store"),
        ("unconfigured", "retained_parent_not_configured"),
        ("separate_inference", "separate_inference_image"),
    ],
)
def test_the_king_fallback_refuses_as_before_unless_every_condition_holds(
    door, capsys, change, reason
):
    provider = _provider()
    if change == "missing":
        door.clear()
    elif change == "mismatch":
        door[OLD] = "sha256:" + "f" * 64  # the store answers with another id
    elif change == "unconfigured":
        retention.install_king_retained_parents([])
    else:
        provider = _provider(inference="sha256:" + "e" * 64)
    with pytest.raises(
        retention.RetentionUnavailable, match="regrade_construction_parent_differs"
    ):
        _choose(provider)
    (line,) = [json.loads(x) for x in capsys.readouterr().err.splitlines()]
    assert (line["event"], line["reason"]) == ("king_regrade_parent_refused", reason)


@pytest.mark.parametrize("incumbent", [KING, None])
def test_any_task_but_the_sitting_king_refuses_with_no_fallback(
    door, capsys, incumbent
):
    with pytest.raises(
        retention.RetentionUnavailable, match="regrade_construction_parent_differs"
    ):
        _choose(_provider(), origin=OTHER, incumbent=incumbent)
    assert capsys.readouterr().err == ""  # not even considered


def test_an_unreadable_retained_image_record_is_its_own_refusal(door):
    with pytest.raises(
        retention.RetentionUnavailable, match="regrade_construction_parent_unavailable"
    ):
        retention._regrade_inference_image(
            "bundle", {"image.json": b"{}"}, _provider(), RECIPE, KING, KING
        )


def test_every_inference_step_of_the_regrade_uses_the_chosen_image():
    provider = SimpleNamespace(inference_image=_identity(NEW))
    assert retention._inference_image_of(provider, None) is provider.inference_image
    plain = retention._Regrade("hk", RECIPE, KING, "sha256:" + "0" * 64)
    assert retention._inference_image_of(provider, plain) is provider.inference_image
    chosen = retention._Regrade(
        "hk", RECIPE, KING, "sha256:" + "0" * 64, inference_image=_identity(OLD)
    )
    assert retention._inference_image_of(provider, chosen) == _identity(OLD)


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


def test_the_configuration_names_valid_distinct_manifests_and_installs_them(tmp_path):
    good = _manifest(tmp_path / "old.json", OLD)
    assert [i.image_id for i in dr._king_retained_parents([good])] == [OLD]
    try:
        dr.install_king_retained_parents({"king_retained_parents": [good]})
        assert retention.KING_RETAINED_PARENTS == {OLD: _identity(OLD)}
        dr.install_king_retained_parents({})
        assert retention.KING_RETAINED_PARENTS == {}
    finally:
        retention.install_king_retained_parents([])
    (tmp_path / "bad.json").write_text("{}")
    twin = _manifest(tmp_path / "twin.json", OLD)
    for bad in (
        [],
        "x",
        [good, good],
        ["relative.json"],
        [str(tmp_path / "bad.json")],
        [good, twin],
    ):
        with pytest.raises(ValueError, match="invalid king_retained_parents"):
            dr._king_retained_parents(bad)
