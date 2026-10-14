"""PKT-17: miner-visible accounting and omitted architecture fields.

The public task lifecycle, executor, ledger and compiler are real. Only the
sandbox worker is a stand-in: this proves wiring, not host execution or
qualification. Network checks initialize parameters; they train nothing.
"""

import asyncio
import base64
from itertools import pairwise

import pytest
from test_lp_prod_research_tools import sdk_for, workspace

from carbon import research
from carbon.development_session import research_carrier
from carbon.development_session.profile import digest
from carbon.development_session.research_image import ResearchImageIdentity
from carbon.development_session.research_tools import PREFIX, TOOLS_RULE


@pytest.mark.parametrize("rule", [None, TOOLS_RULE], ids=["historical", "v2"])
def test_chunked_export_reads_leave_the_executed_trial_count_unchanged(
    tmp_path, monkeypatch, rule
):
    provider = None if rule is None else {"research_tools": rule}
    sdk, meter, composition = sdk_for(tmp_path, provider=provider)
    executor = composition.executor
    executor.image = ResearchImageIdentity(
        "sha256:" + "a" * 64, "sha256:" + "b" * 64, "sha256:" + "c" * 64
    )
    body = (b"synthetic public export\n" * 700)[:14345]
    calls = []

    def worker(ledger, *, owner, identity, extra_resources, **kwargs):
        # Preserve the carrier's requested charge and the actual ledger.
        # No Docker worker or miner program runs in this test.
        calls.append(extra_resources)
        assert ledger.reserve(
            identity,
            owner=owner,
            phase="research",
            request={"source": kwargs["source"]},
            resources=extra_resources,
        )["dispatch"]
        snapshot = ledger.root / identity / "snapshot"
        snapshot.mkdir(parents=True)
        (snapshot / "export.txt").write_bytes(body)
        result = {"operation": identity, "files": {"export.txt": digest(body)}}
        ledger.finish(
            identity,
            owner=owner,
            state="SUCCEEDED",
            actual=extra_resources,
            result=result,
        )
        return result

    monkeypatch.setattr(research_carrier, "_run", worker)

    def execute(action, arguments, identity):
        request = sdk._request(
            "start_research_task", workspace(action, arguments), identity
        )
        queued = composition.tasks.start_research_task(request).task
        done = composition.tasks.run_queued_task(queued.task_id)
        assert done.state is research.ResearchTaskState.SUCCEEDED
        assert not executor.public_result(done)["official_eligible"]
        return executor.public_result(done)["result"]

    try:
        # This refusal is at the miner door, before a task or charge exists.
        rejected = asyncio.run(
            sdk.call(
                PREFIX + "start_research_task",
                workspace(
                    "read_file", {"name": "missing.txt", "offset": 0, "count": 1}
                ),
                "pkt17-read-refused",
            )
        )
        assert rejected["status"] == "REJECTED_BEFORE_DISPATCH"
        assert meter.status(owner="alice")["used"]["research_trials"] == 0
        assert (
            composition.tasks.started_task(sdk.challenge, "pkt17-read-refused") is None
        )
        ran = execute(
            "run_python",
            {
                "source": "print('fixture only')",
                "files": [],
                "hypothesis": "exercise the charge path",
                "expected_effect": "one research trial and an export",
            },
            "pkt17-charged-control",
        )
        assert calls == [{"research_trials": 1}]
        charged = meter.status(owner="alice")
        assert charged["used"]["research_trials"] == 1
        assert len(charged["operations"]) == 1
        assert charged["operations"][0]["state"] == "SUCCEEDED"
        name = ran["workspace_exports"][0]
        chunks = []
        for index, offset in enumerate(range(0, len(body), 4096)):
            result = execute(
                "read_file",
                {"name": name, "offset": offset, "count": 4096},
                "pkt17-read-chunk-" + str(index),
            )
            chunk = (
                result["content_utf8"].encode("utf-8")
                if result.get("content_utf8") is not None
                else base64.b64decode(result["content_base64"], validate=True)
            )
            assert (result["bytes"], result["offset"], result["digest"]) == (
                len(body),
                offset,
                digest(body),
            )
            assert chunk == body[offset : offset + 4096]
            chunks.append(chunk)
            # Each read actually finished and returned its bytes. It neither
            # starts a worker nor reserves/settles another ledger operation.
            after = meter.status(owner="alice")
            assert after["used"] == charged["used"]
            assert after["operations"] == charged["operations"]
            assert calls == [{"research_trials": 1}]
        assert len(body) == 14345 and len(chunks) == 4
        assert b"".join(chunks) == body
    finally:
        composition.tasks.close()


def strategy(**parameters):
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY_CHALLENGE,
        "backbone": "mlp",
        "parameters": parameters,
    }


@pytest.mark.parametrize(
    "parameters,width,depth",
    [
        ({}, 256, 3),
        ({"width": 64}, 64, 3),
        ({"depth": 1}, 256, 1),
        ({"width": 64, "depth": 1}, 64, 1),
    ],
)
def test_omitted_mlp_fields_resolve_and_build_the_default_network(
    parameters, width, depth
):
    jax = pytest.importorskip("jax")
    from carbon.battery.compile import build_model, compile_recipe

    _, recipe = compile_recipe(strategy(**parameters))
    assert (recipe.settings["width"], recipe.settings["depth"]) == (width, depth)
    assert recipe.supplied & {"width", "depth"} == parameters.keys()
    model = build_model(recipe)
    init, apply = model._network(jax, jax.numpy.float32, 4, 245)
    _, params = init(jax.random.PRNGKey(7))
    sizes = [4] + [width] * depth + [245]
    assert [tuple(w.shape) for w, _ in params] == list(pairwise(sizes))
    assert [tuple(b.shape) for _, b in params] == [(n,) for n in sizes[1:]]
    assert apply(params, jax.numpy.ones((2, 4))).shape == (2, 245)


@pytest.mark.parametrize("parameters", [{}, {"width": 64, "depth": 2}])
def test_level4_network_uses_the_same_staged_graph_despite_catalog_width_and_depth(
    parameters,
):
    jax = pytest.importorskip("jax")
    from test_battery_level4_rebuild import _staged

    from carbon.battery import level4 as battery
    from carbon.battery import level4_worker
    from carbon.battery.compile import compile_recipe

    # Lower and verify a real graph with width 32 and one hidden layer.
    graph_strategy = strategy(width=32, depth=1, steps=16)
    found, workspace_ = _staged(graph_strategy)
    material = battery.material()
    _, native = battery._model(graph_strategy, material.train)
    _, recipe = compile_recipe(strategy(**parameters))
    graph_model = level4_worker.build_in_process(recipe, found, workspace_)
    graph_model.layout = native.layout
    batch = min(recipe.settings["batch_size"], battery.batch(material))
    graph_model.prepared = graph_model._prepare(batch)
    init, apply = graph_model._network(jax, jax.numpy.float32, 4, 245)
    _, params = init(jax.random.PRNGKey(7))
    assert [tuple(p.shape) for p in jax.tree_util.tree_leaves(params)] == [
        (4, 32),
        (32,),
        (32, 245),
        (245,),
    ]
    assert apply(params, jax.numpy.ones((2, 4))).shape == (2, 245)
    assert (recipe.settings["width"], recipe.settings["depth"]) == (
        parameters.get("width", 256),
        parameters.get("depth", 3),
    )
