"""The crown's averaging rebuilds build at a validator-chosen seed through the ordinary task provider.

Claims: a task with no seed builds at the official seed 0, exactly as before; a validator-derived task builds at its
host-private seed, which is kept with the task so a restart never builds it at 0; the seed map has no way in from a
request (the request shape is closed and carries no seed field); a seed is write-once, set before the task starts,
never 0 and a positive int32; and no public view of a task shows the seed."""

from __future__ import annotations

import dataclasses

import pytest
from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.development_session import bundle_construction_worker
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

SEED = 1234567891


@pytest.fixture
def builds(monkeypatch):
    """Record the seed every construction call is made with; the call returns nothing the provider accepts as success."""
    seen = []

    def claimed(*args, **kwargs):
        seen.append(kwargs["seed"])
        return {"claimed": "success"}

    monkeypatch.setattr(
        bundle_construction_worker, "reconstruct_and_infer_public", claimed
    )
    return seen


def test_a_task_without_a_seed_builds_at_the_official_seed_zero(
    tmp_path, monkeypatch, builds
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        tasks.run_queued_task(started.task.task_id)
        assert builds == [0]
        assert tasks._seed_for(started.task.task_id.value) == 0
        assert tasks._task_seeds == {}
    finally:
        tasks.close()


def test_a_derived_task_builds_at_its_seed_and_keeps_it_across_a_restart(
    tmp_path, monkeypatch, builds
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    task_value = tasks._task_id(request).value
    tasks.set_rebuild_seed(task_value, SEED)
    started = tasks.start_research_task(request)
    tasks.close()
    reopened = provider()
    try:
        # the queued task is still a derived one after the restart: never rebuilt at 0
        assert reopened._seed_for(task_value) == SEED
        reopened.run_queued_task(started.task.task_id)
        assert builds == [SEED]
    finally:
        reopened.close()


def test_the_seed_is_never_in_a_public_view_of_the_task(tmp_path, monkeypatch, builds):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        tasks.set_rebuild_seed(tasks._task_id(request).value, SEED)
        started = tasks.start_research_task(request)
        view = tasks.run_queued_task(started.task.task_id)
        for document in (started.task, view, request):
            assert str(SEED).encode() not in research.canonical_bytes(document)
    finally:
        tasks.close()


@pytest.mark.parametrize("seed", [0, -1, 2**31 - 1, 2**31, True, "5", 1.5, None])
def test_an_invalid_seed_is_refused(tmp_path, monkeypatch, seed):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        with pytest.raises(ValueError, match="rebuild seed invalid"):
            tasks.set_rebuild_seed(tasks._task_id(request).value, seed)
        assert tasks._task_seeds == {}
    finally:
        tasks.close()


def test_a_seed_is_write_once_and_must_precede_the_task(tmp_path, monkeypatch, builds):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        value = tasks._task_id(request).value
        tasks.set_rebuild_seed(value, SEED)
        tasks.set_rebuild_seed(value, SEED)  # the same seed again is harmless
        with pytest.raises(ValueError, match="already set"):
            tasks.set_rebuild_seed(value, SEED + 1)
        tasks.start_research_task(request)
        with pytest.raises(ValueError, match="before the task starts"):
            tasks.set_rebuild_seed(value, SEED)
    finally:
        tasks.close()


def test_a_task_that_already_started_cannot_be_given_a_seed(
    tmp_path, monkeypatch, builds
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        with pytest.raises(ValueError, match="before the task starts"):
            tasks.set_rebuild_seed(started.task.task_id.value, SEED)
        tasks.run_queued_task(started.task.task_id)
        assert builds == [0]  # still the official seed
    finally:
        tasks.close()


def test_the_request_shape_is_closed_and_carries_no_seed(tmp_path, monkeypatch):
    request, _provider, _ = _fixture(tmp_path, monkeypatch)
    names = {
        field.name for field in dataclasses.fields(research.DirectStartTaskRequestV3)
    }
    assert not [name for name in names if "seed" in name.lower()]
    fields = {name: getattr(request, name) for name in names}
    for extra in ("seed", "rebuild_seed", "random_seed", "derived_seed"):
        with pytest.raises(TypeError):
            research.DirectStartTaskRequestV3(**fields, **{extra: 7})


def test_the_three_build_sites_take_their_seed_from_the_provider_only():
    import ast
    from pathlib import Path

    source = Path(research_module_path()).read_text(encoding="utf-8")
    tree = ast.parse(source)
    seeds = [
        ast.unparse(keyword.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "seed"
    ]
    assert seeds and set(seeds) == {"self._seed_for(task_id.value)"}
    assert len(seeds) == 3


def research_module_path():
    import inspect

    from carbon.development_session import research_tasks

    return inspect.getsourcefile(research_tasks)


def test_the_provider_class_is_the_one_under_test():
    assert DirectDevelopmentTasksV3.set_rebuild_seed is not None


# --- route (b): a king's rebuild at the OFFICIAL seed through the real provider (Deploy 5 Nov 12:41) ---------------


def _adapter(request, provider):
    """The adapter surface `_derived_build` uses, over the REAL provider: every request is the fixture's."""
    from types import SimpleNamespace

    return SimpleNamespace(
        _provider=lambda owner: provider,
        _request=lambda owner, recipe, **identity: request,
        _ended_on_infra=lambda owner, task_id, provider_: False,
        _measure_query=False,
        discovery=SimpleNamespace(
            info=SimpleNamespace(challenge_key=request.challenge_key)
        ),
    )


def _build(request, provider, seed):
    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.development_session.construction_recipe import ConstructionRecipe

    try:
        return retention._derived_build(
            _adapter(request, provider),
            "rtsk_" + "a" * 64,
            seed,
            rebuild="KING_REBUILD",
            host_owner="host",
            recipe=ConstructionRecipe.from_dict(request.recipe),
        )
    except retention.RetentionUnavailable as ended:
        return str(
            ended
        )  # the stand-in build claims a success the provider does not accept


def test_a_kings_rebuild_at_the_official_seed_reaches_the_build_at_seed_zero(
    tmp_path, monkeypatch, builds
):
    from carbon.challenge_validator import lean_recipe_retention as retention

    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        ended = _build(request, tasks, retention.KING_REBUILD_SEED)
        assert builds == [
            0
        ]  # through admission and the queue INTO the build, at the official seed
        value = tasks._task_id(request).value
        assert (
            tasks._task_seeds == {} and tasks._seed_for(value) == 0
        )  # no derived seed: the normal path
        assert (
            value in tasks._origin_rebinds
        )  # the validator mark that lets it carry a king's retained source
        assert tasks._derived_rebuild(request)
        # a retry finds the same task at the same seed and builds nothing again
        assert _build(request, tasks, retention.KING_REBUILD_SEED) == ended
        assert builds == [0]
    finally:
        tasks.close()


def test_a_kings_rebuild_retried_after_a_restart_is_never_admitted_again(
    tmp_path, monkeypatch, builds
):
    from carbon.challenge_validator import lean_recipe_retention as retention

    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    ended = _build(request, tasks, retention.KING_REBUILD_SEED)
    tasks.close()
    reopened = provider()  # the in-memory mark is gone; the task and its seed 0 are not
    try:
        assert reopened._origin_rebinds == set()
        assert _build(request, reopened, retention.KING_REBUILD_SEED) == ended
        assert builds == [0]
    finally:
        reopened.close()


def test_a_retry_proves_the_seed_either_way(tmp_path, monkeypatch, builds):
    from carbon.challenge_validator import lean_recipe_retention as retention

    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        _build(
            request, tasks, SEED
        )  # a crown-average rebuild: the derived seed, as before
        assert builds == [SEED]
        assert (
            _build(request, tasks, retention.KING_REBUILD_SEED)
            == "rebuild_seed_changed"
        )
    finally:
        tasks.close()
    request, provider, _ = _fixture(tmp_path / "second", monkeypatch)
    tasks = provider()
    try:
        _build(request, tasks, retention.KING_REBUILD_SEED)
        assert _build(request, tasks, SEED) == "rebuild_seed_changed"
    finally:
        tasks.close()
