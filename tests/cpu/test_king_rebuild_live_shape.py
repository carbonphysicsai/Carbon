"""King rebuild (route (b)) on the LIVE shape: regression tests for the independent audit
(reports/KING_REBUILD_AUDIT_20261105.md, items 1, 2, 4, 6, 8) and Validator-2's 13:05 conditions (1), (2), (4), (6), (8).

Each test names its audit item and FAILS on main 57272aec for that item; the TE's fix makes it pass. They run the REAL
code: the research-task provider's own `set_rebuild_seed` / `_derived_rebuild` / `start_research_task` guard and bound
(no stub of either), the real `_derived_build`, `king_parent_moved` / `_parents`, and `recontend.plan` on a real pool
store with a real route-(b) link. Only what sits outside the claim is stood in: the adapter's plumbing around the
provider, the origin task's request record, and the build/retention past admission (the provider's `_retain_source`
raises `_Admitted` where the real one would retain the admitted bytes).

NOT covered here (named for the TE): item 3 (a pre-pack origin rebind falling through to retained_king_source), item 5
(repeat(king) resolving through the king_rebuild.v1 link on a DETHRONED), item 7 (the krb_ row's construction binding =
the rebuilt task's), and condition (9)'s end-to-end plain + graph king through seed 0 -> krb_ -> link -> koth_contention
with a restart: they need an old-construction-binding admission fixture and a live receiver state.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

# the fixtures (graph_case, no_workspace, door) are used by name as test arguments
from test_crown_graph_rebuild import (
    HOST,
    _Admitted,
    _provider,
    graph_case,  # noqa: F401
    no_workspace,  # noqa: F401
)
from test_king_rebuild import (
    _link,
    _rebuild_row,
    door,  # noqa: F401
)

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator import recontend
from carbon.challenge_validator.interface import digest
from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.lifecycle import ResearchTaskProviderError

ORIGIN = "rtsk_" + "e" * 64
MINER = "5" + "M" * 47


def _adapter(recipe, envelope, host):
    """The adapter plumbing `_derived_build` reads, around the REAL host provider: the origin task's owner and request
    record, and the host-owned request (the provider's own request for this recipe)."""
    host_provider, host_request = host
    host_provider.evaluation_pack_digest = "sha256:" + "9" * 64
    origin_provider = SimpleNamespace(
        _requests={ORIGIN: SimpleNamespace(recipe=recipe.to_dict())},
        _source_envelope=lambda origin, rec: envelope,
    )
    return SimpleNamespace(
        owner=lambda origin: MINER if origin == ORIGIN else None,
        _provider=lambda owner: origin_provider if owner == MINER else host_provider,
        _request=lambda owner, rec, **kw: host_request,
        _ended_on_infra=lambda *a: False,
        _measure_query=False,
    )


# --- audit #1 / condition (1): a graph king rebuilds at the OFFICIAL seed 0 -------------------------------------------


def test_audit_1_the_kings_seed_zero_task_is_marked_not_seeded_and_a_retry_proves_its_seed(
    graph_case, no_workspace, tmp_path  # noqa: F811
):
    """TE's head keeps `set_rebuild_seed` refusing 0: research_tasks.py is in the served source identity
    (`lean_recipe._SOURCE_PATHS`), so a change there would move every door's contract and strand every king again. The
    king's seed-0 task takes the provider's normal seed and `rebind_origin`'s validator mark instead.
    """
    recipe, envelope, _ = graph_case
    provider, request = _provider(HOST, recipe, seeded=False, tmp_path=tmp_path)
    task = provider._task_id(request).value
    with pytest.raises(ValueError, match="rebuild seed invalid"):
        provider.set_rebuild_seed(
            task, 0
        )  # unchanged: the official seed is never a derived one
    adapter = _adapter(recipe, envelope, (provider, request))
    with pytest.raises(_Admitted):
        retention._derived_build(
            adapter,
            ORIGIN,
            retention.KING_REBUILD_SEED,
            rebuild="king",
            host_owner=HOST,
        )
    assert task in provider._origin_rebinds and task not in provider._task_seeds
    assert provider._seed_for(task) == 0 and provider._derived_rebuild(request)
    # a retry of an existing task proves its seed and is never admitted again
    provider._views[task] = SimpleNamespace(state=None)
    with pytest.raises(retention.RetentionUnavailable, match="rebuild_seed_changed"):
        retention._derived_build(adapter, ORIGIN, 4242, rebuild="king", host_owner=HOST)


def test_audit_1_a_graph_kings_rebuild_at_seed_zero_is_admitted_with_his_retained_source(
    graph_case, no_workspace, tmp_path  # noqa: F811
):
    recipe, envelope, _ = graph_case
    host = _provider(HOST, recipe, seeded=False, tmp_path=tmp_path)
    adapter = _adapter(recipe, envelope, host)
    # the real _derived_build, the real provider guard: the admission reaches retention (_Admitted), never
    # REQUEST_TYPE_INVALID (graph_source on a task the provider does not count as derived) nor "rebuild seed invalid"
    with pytest.raises(_Admitted):
        retention._derived_build(
            adapter,
            ORIGIN,
            retention.KING_REBUILD_SEED,
            rebuild="king-rebuild",
            host_owner=HOST,
        )
    assert host[0].retained == [envelope]
    assert retention.KING_REBUILD_SEED == 0


# --- audit #2 / condition (2): a capability gap becomes KING_REBUILD_GAP --------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE,
        ResearchServiceErrorCode.REFERENCE_NOT_FOUND,
    ],
)
def test_audit_2b_an_admission_capability_refusal_is_the_rebuild_gap(
    graph_case, no_workspace, tmp_path, code  # noqa: F811
):
    recipe, envelope, _ = graph_case
    host = _provider(HOST, recipe, tmp_path=tmp_path)  # seeded: isolates #2 from #1

    def refused():
        raise ResearchTaskProviderError(code)

    host[0]._verify_images = (
        refused  # where the provider's admission refuses an unserved capability
    )
    with pytest.raises(retention.RetentionUnavailable) as gap:
        retention._derived_build(
            _adapter(recipe, envelope, host),
            ORIGIN,
            4242,
            rebuild="king-rebuild",
            host_owner=HOST,
        )
    assert (
        gap.value.code == retention.KING_REBUILD_GAP
    )  # main: the provider error escapes untyped


def test_audit_2b_another_admission_refusal_is_typed_rebuild_admission(
    graph_case, no_workspace, tmp_path  # noqa: F811
):
    recipe, envelope, _ = graph_case
    host = _provider(HOST, recipe, tmp_path=tmp_path)

    def refused():
        raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)

    host[0]._verify_images = refused
    with pytest.raises(retention.RetentionUnavailable) as typed:
        retention._derived_build(
            _adapter(recipe, envelope, host),
            ORIGIN,
            4242,
            rebuild="king-rebuild",
            host_owner=HOST,
        )
    assert typed.value.code.startswith("rebuild_admission_")


def _moved_fixture(monkeypatch, provider_for):
    """`king_parent_moved` on a BUNDLE king: his retained image.json names parent "old"; the origin lookup and the
    bundle ref parse are stood in (they are not the claim); `_parents` / `_construction_parent` run for real.
    """
    from carbon.development_session import library_bundles

    recipe = SimpleNamespace(
        to_dict=lambda: {"source": {"kind": "bundle", "bundle_ref": {"x": 1}}}
    )
    files = {"image.json": json.dumps({"parent_image_id": "old"}).encode()}
    monkeypatch.setattr(
        retention,
        "_regrade_origin",
        lambda *a, **k: (None, ORIGIN, MINER, None, files, recipe),
    )
    monkeypatch.setattr(retention, "_regrade_incumbent", lambda store: None)
    monkeypatch.setattr(retention, "_owner_directory", lambda d, name: d)
    monkeypatch.setattr(
        library_bundles.LibraryBundleRef, "from_dict", staticmethod(lambda d: d)
    )
    return SimpleNamespace(_provider=provider_for)


def test_audit_2a_an_unserved_current_parent_counts_as_moved(monkeypatch, tmp_path):
    from carbon.development_session.gpu_practice import DirectParentRefused

    def for_bundle(bundle):
        raise DirectParentRefused("parent not served")

    served = SimpleNamespace(
        construction_parents=SimpleNamespace(for_bundle=for_bundle)
    )
    adapter = _moved_fixture(monkeypatch, lambda owner: served)
    # main: RetentionUnavailable("regrade_construction_parent_unavailable"), retried every epoch: route (b) never starts
    assert (
        retention.king_parent_moved(
            adapter,
            None,
            "sha256:" + "1" * 64,
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )
        is True
    )


# --- audit #6 / condition (6): a deregistered king hotkey cannot block every tick -------------------------------------


def test_audit_6_the_parents_are_read_through_the_host_owner_not_the_kings_hotkey(
    monkeypatch, tmp_path
):
    from carbon.challenge_validator.crown_average import HOST_OWNER

    seen = []
    served = SimpleNamespace(construction_parent=SimpleNamespace(image_id="new"))

    def provider_for(owner):
        seen.append(owner)
        if owner != HOST_OWNER:
            raise RuntimeError(
                "king hotkey not registered"
            )  # the live receiver's Unavailable for a gone hotkey
        return served

    adapter = _moved_fixture(monkeypatch, provider_for)
    assert (
        retention.king_parent_moved(
            adapter,
            None,
            "sha256:" + "1" * 64,
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )
        is True
    )
    assert seen == [HOST_OWNER]  # main: _provider(<king hotkey>) -> raises every tick


# --- audit #8 / condition (8): the provider's task-view cap is a typed refusal, not an escape --------------------------


def test_audit_8_the_task_view_bound_is_caught_and_typed(
    graph_case,  # noqa: F811
    no_workspace,  # noqa: F811
    tmp_path,
):
    recipe, envelope, _ = graph_case
    host = _provider(HOST, recipe, tmp_path=tmp_path)
    for n in range(256):  # the host owner's never-pruned views (one per re-measure)
        host[0]._views["rtsk_" + f"{n:064x}"] = object()
    with pytest.raises(retention.RetentionUnavailable) as bound:
        retention._derived_build(
            _adapter(recipe, envelope, host),
            ORIGIN,
            4242,
            rebuild="king-rebuild",
            host_owner=HOST,
        )
    assert (
        "bound" in bound.value.code
    )  # main: ResearchTaskProviderError(BOUND_EXCEEDED) escapes untyped


# --- audit #4 / condition (4): after route (b) the king's derived row is HIS on recontend's restart plan ---------------


def _challenger_row(store, sid, key, exam, root):
    """A challenger's bound private evaluation as the pool store files it, and its regrade provenance (recontend reads
    the origin entry through it)."""
    entry = digest(["bank entry", sid])
    body = {
        "submission_id": sid,
        "evaluation_key": key,
        "evidence": {
            "evaluation_pack_digest": exam,
            "entry_id": entry,
            "source_receipt_sha256": "sha256:" + "7" * 64,
        },
    }
    with store.transaction() as db:
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?)",
            (
                digest(["op", sid, key]),
                "private_evaluation.v1",
                "BOUND_DEVELOPMENT_ONLY",
                json.dumps(body),
            ),
        )
    directory = root / "auto-grade" / "artifacts" / (sid + ".evaluation")
    directory.mkdir(mode=0o700, parents=True)
    (directory / "regrade-provenance.json").write_text(
        json.dumps(
            {
                "entry_id": entry,
                "origin_entry_id": digest(["origin entry", sid]),
                "origin_task_id": sid,
            }
        )
    )


def test_audit_4_recontend_counts_the_kings_rebuilt_row_as_his(
    door,  # noqa: F811
    tmp_path,
):
    root = tmp_path / "state"
    for name in ("artifacts", "entries"):
        (root / "auto-grade" / name).mkdir(parents=True, mode=0o700)
    exam = door.args["score_pack"]["pack_digest"]
    door.store.set_incumbent("king", "historical fixture")
    before, after = "rtsk_" + "1" * 64, "rtsk_" + "2" * 64
    _challenger_row(
        door.store, before, door.key, exam, root
    )  # graded BEFORE the king's rebuild on this key
    derived, king = _rebuild_row(
        door
    )  # route (b): the king's grade on the challengers' key, under krb_
    _link(door, derived, king)
    _challenger_row(
        door.store, after, door.key, exam, root
    )  # graded AFTER it: met the king live
    planned = recontend.plan(root, door.store.path, exam)
    filed = {i["submission_id"]: i for i in planned["file"]}
    # main: the krb_ row is not the king's, so BOTH are filed again on a restart, PENDING_CONTENTION for a regrade that
    # route (b) already did
    assert after not in filed and after not in planned["skipped"]
    assert filed[before]["state"] == "PAUSED"
