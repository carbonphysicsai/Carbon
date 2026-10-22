"""v6 is the allowlist the step-2 versions serve (Validator, 2026-10-20,
STEP2_BATCH_VERSIONS_20261020): Motor 1.1, Cooling 1.1, F08 1.2, F02 2.1 and
Battery 2.0. Existing versions keep their bytes (v5, and Battery 1.0's graph
path v1) and are never rescored.

Claims: the served v6 bytes are frozen by their sha and v1-v5 stay loadable for
history; the version table serves v6 to exactly the step-2 versions, keeps
every existing version's allowlist, and refuses an unregistered version (no
default); the bundle worker trusts v6 and its history; dot_general precision
HIGHEST stays refused under v6; the caps are unchanged; and the backbones v6
was opened for (neuraloperator UNO, PhysicsNeMo FNO and AFNO, an efficient-KAN
layer) lower and rebuild under v6, matching torch, while v5 refuses each.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret

ROOT = Path(allowlist_module.__file__).parent
V5 = ROOT / "allowlist_v5.json"


def test_the_served_allowlist_is_v6_frozen_by_its_sha():
    raw = allowlist_module.served_bytes()
    assert allowlist_module.SERVED_PATH.name == "allowlist_v6.json"
    assert hashlib.sha256(raw).hexdigest() == allowlist_module.SERVED_SHA256
    assert allowlist_module.load_served().version == "level4-allowlist-v6"
    # History stays loadable by path.
    for n in range(1, 6):
        assert allowlist_module.load(ROOT / f"allowlist_v{n}.json").version == (
            f"level4-allowlist-v{n}"
        )


def test_changed_served_bytes_are_refused(tmp_path, monkeypatch):
    changed = tmp_path / "allowlist_v6.json"
    changed.write_bytes(allowlist_module.SERVED_PATH.read_bytes() + b" ")
    monkeypatch.setattr(allowlist_module, "SERVED_PATH", changed)
    with pytest.raises(ValueError, match="served allowlist bytes differ"):
        allowlist_module.served_bytes()


def test_the_version_table_serves_v6_to_exactly_the_step2_versions():
    from carbon.challenge_kit import served_versions as sv
    from carbon.challenge_kit.synthetic_linear_field_2d import allowlist_v5_bytes

    served, v5 = allowlist_module.served_bytes(), allowlist_v5_bytes()
    assert {key[0] for key in sv.STEP2} == {key[0] for key in sv.EXISTING}
    assert sv.STEP2.isdisjoint(sv.EXISTING) and len(sv.STEP2) == 5
    for challenge_id, version in sv.STEP2:
        assert sv.material_allowlist_bytes(challenge_id, version) == served
        assert sv.graph_allowlist_bytes(challenge_id, version) == served
        assert sv.step_caps(challenge_id, version) is False
    for challenge_id, version in sv.EXISTING:
        assert sv.material_allowlist_bytes(challenge_id, version) == v5
        assert sv.step_caps(challenge_id, version) is True
    # Battery 1.0's direct graph path has always validated against v1.
    assert (
        sv.graph_allowlist_bytes(sv.BATTERY, "1.0")
        == allowlist_module.PATH.read_bytes()
    )
    assert sv.graph_allowlist_bytes(sv.MOTOR, "1.0") == v5


@pytest.mark.parametrize(
    "key",
    # Motor 1.2 and 1.3 are the catalog versions; 1.4 is unregistered.
    [("electric-motor-magnetics", "1.4"), ("chip-cold-plate", ""), ("unknown", "1.0")],
)
def test_an_unregistered_version_is_refused_never_mapped(key):
    from carbon.challenge_kit import served_versions as sv

    for read in (sv.material_allowlist_bytes, sv.graph_allowlist_bytes, sv.step_caps):
        with pytest.raises(sv.UnregisteredVersion):
            read(*key)


def test_existing_materials_keep_their_v5_bytes():
    from carbon.battery import construction_bundle_material
    from carbon.challenge_kit import physical_material
    from carbon.challenge_kit import served_versions as sv
    from carbon.challenge_kit.synthetic_linear_field_2d import allowlist_v5_bytes

    for challenge_id, version in sorted(physical_material.REGISTERED):
        if (challenge_id, version) in sv.EXISTING:
            material = physical_material.bundle_material(challenge_id, version)
            assert material["allowlist_bytes"] == allowlist_v5_bytes(), challenge_id
    battery = construction_bundle_material.bundle_material(
        Path(__file__).resolve().parents[2]
    )
    assert battery["allowlist_bytes"] == allowlist_v5_bytes()


def test_batterys_worker_side_graph_choice_matches_the_version_table():
    from carbon.battery import direct_graph
    from carbon.challenge_kit import served_versions as sv

    battery = sorted(v for c, v in sv.STEP2 | sv.EXISTING | sv.V7 if c == sv.BATTERY)
    assert sorted(direct_graph.GRAPH_ALLOWLISTS) == battery
    for version in battery:
        assert (
            direct_graph.graph_allowlist(version).digest
            == allowlist_module.Allowlist(
                sv.graph_allowlist_bytes(sv.BATTERY, version)
            ).digest
        )
    from carbon.development_session.construction_recipe import RecipeRefused

    with pytest.raises(
        RecipeRefused, match="battery_graph_challenge_version_unregistered"
    ):
        direct_graph.graph_allowlist("1.1")


def test_the_bundle_worker_trusts_v6_and_still_trusts_history():
    from carbon.development_session import bundle_construction_worker as worker

    for raw in (
        allowlist_module.served_bytes(),
        V5.read_bytes(),
        (ROOT / "allowlist_v1.json").read_bytes(),
    ):
        assert worker._trusted_allowlist(raw).version.startswith("level4-allowlist-v")


def test_caps_are_unchanged():
    # OWNER-L4-VALUES-01's caps; the scatter and index expansion-bound refusals
    # are tested in test_level4_torch_scatter_add and _static_gather.
    assert allowlist_module.CAPS == {
        "constant_bytes": 16 * 1024,
        "nodes_executed": 4096,
        "call_depth": 16,
        "document_bytes": 1024**2,
        "largest_intermediate_bytes": 256 * 1024**2,
    }


def test_dot_general_precision_highest_stays_refused_under_served_v6():
    jax = pytest.importorskip("jax")
    from carbon.level4.tooling import through_bprime

    a = jax.numpy.ones((3, 4), jax.numpy.float32)
    b = jax.numpy.ones((4, 2), jax.numpy.float32)
    with pytest.raises(graph.GraphRefused) as refused:
        through_bprime(
            lambda p, q: jax.numpy.dot(p, q, precision=jax.lax.Precision.HIGHEST),
            (a, b),
            role="forward",
            allowlist=allowlist_module.load_served(),
            input_names=["inputs/a", "inputs/b"],
            max_bytes=allowlist_module.CAPS["document_bytes"],
        )
    assert refused.value.code == "parameter_not_default"


# --- the backbones v6 was opened for --------------------------------------------


def _lower_module(module, x, allowlist):
    torch = pytest.importorskip("torch")
    from carbon.level4.tooling import lower_torch

    module = module.eval()
    names = [n for n, _ in module.named_parameters()]
    params = [p.detach() for _, p in module.named_parameters()]
    buffers = dict(module.named_buffers())

    def apply(ps, inputs):
        return torch.func.functional_call(
            module, (dict(zip(names, ps)), buffers), (inputs,)
        )

    _, core = lower_torch.export(apply, params, x)
    doc, _ = lower_torch.lower(core, allowlist=allowlist)
    return doc, params, core


def _served_matches_torch_and_v5_refuses(module, x, *, rtol=2e-4, atol=2e-5):
    import numpy as np

    jax = pytest.importorskip("jax")
    torch = pytest.importorskip("torch")
    from carbon.level4.tooling import lower_torch

    served = allowlist_module.load_served()
    doc, params, core = _lower_module(module, x, served)
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    rebuilt = interpret.rebuild(parsed, served)
    weights = [jax.numpy.asarray(p.numpy()) for p in params]
    got = np.asarray(rebuilt(*weights, jax.numpy.asarray(x.numpy()))[0])
    with torch.no_grad():
        want = module(x)
    if isinstance(want, (tuple, list)):
        want = want[0]
    np.testing.assert_allclose(got, want.numpy(), rtol=rtol, atol=atol)
    with pytest.raises(graph.GraphRefused):
        lower_torch.lower(core, allowlist=allowlist_module.load(V5))


def test_neuraloperator_uno_lowers_under_served_v6():
    torch = pytest.importorskip("torch")
    models = pytest.importorskip("neuralop.models")
    torch.manual_seed(0)
    module = models.UNO(
        in_channels=3,
        out_channels=1,
        hidden_channels=8,
        n_layers=3,
        uno_out_channels=[8, 8, 8],
        uno_n_modes=[[4], [4], [4]],
        uno_scalings=[[1.0], [1.0], [1.0]],
        channel_mlp_skip="linear",
        positional_embedding=None,
    )
    x = torch.randn(2, 3, 16, generator=torch.Generator().manual_seed(1))
    _served_matches_torch_and_v5_refuses(module, x)


def test_physicsnemo_fno_lowers_under_served_v6():
    torch = pytest.importorskip("torch")
    fno = pytest.importorskip("physicsnemo.models.fno")
    torch.manual_seed(0)
    module = fno.FNO(
        in_channels=3,
        out_channels=1,
        decoder_layers=1,
        decoder_layer_size=8,
        dimension=1,
        latent_channels=8,
        num_fno_layers=2,
        num_fno_modes=4,
        padding=4,
    )
    x = torch.randn(2, 3, 16, generator=torch.Generator().manual_seed(2))
    _served_matches_torch_and_v5_refuses(module, x)


def test_physicsnemo_afno_lowers_under_served_v6():
    torch = pytest.importorskip("torch")
    afno = pytest.importorskip("physicsnemo.models.afno")
    torch.manual_seed(0)
    module = afno.AFNO(
        inp_shape=[6, 10],
        in_channels=4,
        out_channels=1,
        patch_size=[2, 2],
        embed_dim=8,
        depth=1,
        num_blocks=2,
    )
    x = torch.randn(2, 4, 6, 10, generator=torch.Generator().manual_seed(3))
    _served_matches_torch_and_v5_refuses(module, x)


def test_an_efficient_kan_layer_lowers_under_served_v6():
    torch = pytest.importorskip("torch")

    class KANLayer(torch.nn.Module):
        """y = W_b silu(x) + W_s B(x), B the order-3 B-spline basis on a
        uniform grid over [-2, 2] (Cox-de Boor), as efficient-KAN."""

        def __init__(self, n_in, n_out, grid=5, order=3):
            super().__init__()
            h = 4.0 / grid
            knots = torch.arange(-order, grid + order + 1, dtype=torch.float32)
            self.register_buffer("knots", knots * h - 2.0)
            self.order = order
            self.base = torch.nn.Linear(n_in, n_out)
            self.spline = torch.nn.Parameter(
                torch.randn(n_out, n_in, grid + order) * 0.1
            )

        def forward(self, x):
            g = self.knots
            u = x.unsqueeze(-1)
            b = ((u >= g[:-1]) & (u < g[1:])).to(x.dtype)
            for k in range(1, self.order + 1):
                b = (u - g[: -(k + 1)]) / (g[k:-1] - g[: -(k + 1)]) * b[..., :-1] + (
                    g[k + 1 :] - u
                ) / (g[k + 1 :] - g[1:-k]) * b[..., 1:]
            spline = torch.einsum("nik,oik->no", b, self.spline)
            return self.base(torch.nn.functional.silu(x)) + spline

    torch.manual_seed(0)
    module = torch.nn.Sequential(KANLayer(4, 8), KANLayer(8, 3))
    x = torch.rand(5, 4, generator=torch.Generator().manual_seed(4)) * 3.0 - 1.5
    _served_matches_torch_and_v5_refuses(module, x)


def test_the_catalog_version_serves_as_a_step2_version():
    from carbon.challenge_kit import served_versions as sv

    assert sv.serves_catalog("electric-motor-magnetics", "1.2")
    assert sv.is_step2("electric-motor-magnetics", "1.2")
    assert not sv.step_caps("electric-motor-magnetics", "1.2")
    assert sv.material_allowlist_bytes(
        "electric-motor-magnetics", "1.2"
    ) == sv.material_allowlist_bytes("electric-motor-magnetics", "1.1")
    for key in sv.STEP2 | sv.EXISTING:
        assert not sv.serves_catalog(*key)
