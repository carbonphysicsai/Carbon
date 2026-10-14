"""S3 plus PLT-30 integration; synthetic images, no worker/GPU execution."""

import copy
import json

import pytest
from composition_check_fixtures import accepted_fixture_checks
from test_battery_gpu_practice import gpu_image, practice
from test_battery_torch_gpu_practice_route import torch_image
from test_battery_validator_daemon import submission

from carbon.development_ladder import required_checks
from carbon.development_session import battery_gpu as gpu
from carbon.development_session import construction_level as cl
from carbon.development_session import research_carrier
from carbon.reconstruction import development_composition as dc
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

__all__ = ["accepted_fixture_checks"]


def bind_composition(callback, monkeypatch):
    callback.level = cl.with_target(
        cl.resolve_composition(BATTERY_CHALLENGE),
        "http://127.0.0.1:9/carbon/v1/battery/intake",
    )
    monkeypatch.setattr(
        cl,
        "READ_TARGET",
        lambda *_args: {
            "served_contracts": [
                {
                    "level": None,
                    "kind": "composition",
                    "variant": callback.level["variant"],
                    "digest": callback.level["digest"],
                }
            ]
        },
    )


@pytest.mark.parametrize(
    "backend,widened", [("jax", False), ("jax", True), ("pytorch", False)]
)
def test_composition_checks_original_before_staging_base_on_selected_gpu_worker(
    tmp_path, monkeypatch, accepted_fixture_checks, backend, widened
):
    image = torch_image() if backend == "pytorch" else gpu_image()
    callback = practice(tmp_path, gpu_image_=image, seen=[])
    bind_composition(callback, monkeypatch)
    callback._seed = lambda _identity: 0
    requested = submission(
        "hk",
        "mlp",
        backend=backend,
        width=8,
        depth=1,
        steps=24,
        optimizer_family="muon" if widened else "adam",
    ).strategy
    if widened:
        requested["parameters"]["muon_spectral"] = True
    original = copy.deepcopy(requested)
    compiled = []
    actual_cli = cl.RUN

    def compile_original(request):
        compiled.append(copy.deepcopy(request))
        return actual_cli(request)

    monkeypatch.setattr(cl, "RUN", compile_original)
    asked = []

    def capture(_ledger, **kwargs):
        asked.append(kwargs)
        raise RuntimeError("captured-before-worker")

    callback.runner = capture
    with pytest.raises(RuntimeError, match="captured-before-worker"):
        callback("fixture", requested)
    assert requested == original
    assert len(compiled) == len(asked) == 1
    assert compiled[0]["strategy"] == original
    assert compiled[0]["composition_digest"] == callback.level["digest"]
    assert asked[0]["image"] is image
    assert asked[0]["accelerator"] == research_carrier.MINER_GPU
    assert asked[0]["source"] == (
        gpu.TORCH_GPU_PROGRAM if backend == "pytorch" else gpu.GPU_PROGRAM
    )
    staged = json.loads(asked[0]["files"]["recipe.json"])
    assert staged["settings"]["backend"] == backend
    assert "muon_spectral" not in staged["settings"]
    label = cl.practice_label(callback.level, callback._construction_compile)
    assert label["widened_trained"] is False
    assert label["level"] == (2 if widened else 0)


@pytest.mark.parametrize("backend", ["jax", "pytorch"])
def test_composition_default_unknown_health_never_reaches_either_worker(
    tmp_path, monkeypatch, backend
):
    image = torch_image() if backend == "pytorch" else gpu_image()
    callback = practice(tmp_path, gpu_image_=image, seen=[])
    bind_composition(callback, monkeypatch)
    callback.runner = lambda *_args, **_kwargs: pytest.fail(
        "unknown check reached worker"
    )
    requested = submission(
        "hk", "mlp", width=8, depth=1, steps=24, optimizer_family="muon"
    ).strategy
    requested["parameters"]["muon_spectral"] = True
    with pytest.raises(cl.LevelRefused, match="construction_checks_unavailable"):
        callback("fixture", requested)


def test_graph_v4_explicit_arm_does_not_move_the_composition_v1_subject(
    accepted_fixture_checks,
):
    composition = dc.load(BATTERY_CHALLENGE)
    graph = next(part for part in composition.variants if part.level == 4)
    assert composition.version == "battery-construction-v1"
    assert graph == dv.variant(BATTERY_CHALLENGE, 4)
    assert graph.version == "battery-l4-graph-v3"
    prospective = dv.variant(BATTERY_CHALLENGE, 4, arm="inert_fields")
    assert (
        prospective.version == "battery-l4-graph-v4"
        and prospective.digest != graph.digest
    )
    requested = submission("hk", "mlp", width=8, depth=1, steps=24).strategy
    requested["parameters"]["composition_graphs"] = "sha256:" + "a" * 64
    binding = required_checks.check(requested, composition)
    assert binding["arms"]["graph"]["variant_digest"] == graph.digest
    historical = dc.compile(requested, composition, check_budget=False)
    assert (
        historical.reconstruction["hybrid.composition_graphs"]["submission"]
        == requested["parameters"]["composition_graphs"]
    )
    with pytest.raises(dv.VariantRefused, match="level4_field_inert:width"):
        dv.compile_development(requested, prospective, check_budget=False)
