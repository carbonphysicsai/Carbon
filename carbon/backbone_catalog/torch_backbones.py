"""Each catalog entry as a fresh, untrained torch module on a Challenge's shape.

The module maps a (cases, n_in) float tensor to (cases, points). The adapters
are the ones Carbon's B0 probe ran on Motor (`entries.ADAPTERS`). Nothing is
downloaded or pretrained; the libraries are the pinned ones, checked first.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .entries import LIBRARIES, CatalogRefused, entry, resolve


@dataclass(frozen=True)
class Shape:
    """A Challenge's interface as the catalog sees it: `n_in` scaled inputs
    to `points` outputs, which a 2-D-only backbone reads as `grid_2d`."""

    n_in: int
    points: int
    grid_2d: tuple

    def __post_init__(self):
        rows, cols = self.grid_2d
        if self.n_in < 1 or self.points < 2 or rows * cols != self.points:
            raise ValueError(
                "a catalog shape needs inputs and a grid holding every point"
            )


def pinned(library):
    """Refuse unless the installed library is exactly the pinned version."""
    from importlib.metadata import PackageNotFoundError, version

    want = LIBRARIES[library][1]
    try:
        have = version(library)
    except PackageNotFoundError:
        have = None
    if have != want:
        raise CatalogRefused(
            "catalog_library_not_pinned",
            f"{library} {want} is required; this image has {have or 'none'}",
        )


class OnGrid(torch.nn.Module):
    """(n, k) -> (n, k + 1, points) [or (n, k + 2, rows, cols)] -> backbone -> (n, points)."""

    def __init__(self, backbone, shape, two_d=False):
        super().__init__()
        self.backbone, self.two_d, self.shape = backbone, two_d, shape
        if two_d:
            rows, cols = shape.grid_2d
            yy, xx = torch.meshgrid(
                torch.linspace(0.0, 1.0, rows),
                torch.linspace(0.0, 1.0, cols),
                indexing="ij",
            )
            self.register_buffer("coords", torch.stack([yy, xx]).unsqueeze(0))
        else:
            self.register_buffer(
                "coords",
                torch.linspace(0.0, 1.0, shape.points).view(1, 1, shape.points),
            )

    def forward(self, x):
        n, k = x.shape
        x = x.to(self.coords.dtype)
        if self.two_d:
            feats = x.view(n, k, 1, 1).expand(n, k, *self.shape.grid_2d)
            grid = torch.cat([feats, self.coords.expand(n, -1, -1, -1)], dim=1)
        else:
            feats = x.view(n, k, 1).expand(n, k, self.shape.points)
            grid = torch.cat([feats, self.coords.expand(n, -1, -1)], dim=1)
        out = self.backbone(grid)
        if isinstance(out, (tuple, list)):
            out = out[0]
        return out.reshape(n, -1)[:, : self.shape.points]


class _Flat(torch.nn.Module):
    def __init__(self, inner):
        super().__init__()
        self.inner = inner

    def forward(self, x):
        return self.inner(x)


class _UQNOSolution(torch.nn.Module):
    def __init__(self, uqno):
        super().__init__()
        self.uqno = uqno

    def forward(self, x):
        return self.uqno.base_model(x)


class _GINOOnPoints(torch.nn.Module):
    LATENT = 16

    def __init__(self, shape, s):
        super().__init__()
        import neuralop.models as m

        c = shape.n_in + 1
        self.shape = shape
        self.gino = m.GINO(
            in_channels=c,
            out_channels=1,
            gno_coord_dim=1,
            in_gno_radius=s["radius"],
            out_gno_radius=s["radius"],
            fno_n_modes=(s["fno_n_modes"],),
            fno_hidden_channels=s["fno_hidden_channels"],
            fno_n_layers=s["fno_n_layers"],
            fno_in_channels=c,
            gno_embed_channels=16,
            in_gno_channel_mlp_hidden_layers=[32, 32],
            out_gno_channel_mlp_hidden_layers=[32, 32],
            gno_use_open3d=False,
            gno_use_torch_scatter=False,
        )
        self.register_buffer(
            "points", torch.linspace(0.0, 1.0, shape.points).view(1, shape.points, 1)
        )
        self.register_buffer(
            "latent", torch.linspace(0.0, 1.0, self.LATENT).view(1, self.LATENT, 1)
        )

    def forward(self, x):
        n, k = x.shape
        p = self.shape.points
        x = x.to(self.points.dtype)
        feats = torch.cat(
            [x.view(n, 1, k).expand(n, p, k), self.points.expand(n, -1, -1)], dim=-1
        )
        return self.gino(self.points, self.latent, self.points, x=feats).reshape(n, p)


def _check_modes(shape, s, name):
    limit = shape.points // 2
    if name in s and s[name] > limit:
        raise CatalogRefused(
            "catalog_settings_inconsistent",
            f"{name} is at most {limit} on this Challenge's {shape.points}-point grid",
        )


def build(catalog_id, settings, shape):
    """`catalog_id` with `settings` (checked by `entries.resolve`) on `shape`,
    as a fresh module. Raises `CatalogRefused`."""
    chosen = entry(catalog_id)
    s = resolve(catalog_id, settings)
    pinned(chosen.library)
    c, c2 = shape.n_in + 1, shape.n_in + 2
    for name in ("n_modes", "num_fno_modes"):
        _check_modes(shape, s, name)
    if catalog_id.startswith("neuralop."):
        import neuralop.models as m
    if catalog_id == "neuralop.FNO":
        return OnGrid(
            m.FNO(
                n_modes=(s["n_modes"],),
                hidden_channels=s["hidden_channels"],
                in_channels=c,
                out_channels=1,
                n_layers=s["n_layers"],
            ),
            shape,
        )
    if catalog_id == "neuralop.TFNO":
        return OnGrid(
            m.TFNO(
                n_modes=(s["n_modes"],),
                hidden_channels=s["hidden_channels"],
                in_channels=c,
                out_channels=1,
                n_layers=s["n_layers"],
                factorization=s["factorization"],
                rank=s["rank"],
            ),
            shape,
        )
    if catalog_id == "neuralop.UNO":
        layers = s["n_layers"]
        return OnGrid(
            m.UNO(
                in_channels=c,
                out_channels=1,
                hidden_channels=s["hidden_channels"],
                n_layers=layers,
                uno_out_channels=[s["hidden_channels"]] * layers,
                uno_n_modes=[[s["n_modes"]]] * layers,
                uno_scalings=[[1.0]] * layers,
                channel_mlp_skip="linear",
                positional_embedding=None,
            ),
            shape,
        )
    if catalog_id == "neuralop.CODANO":
        rows, cols = shape.grid_2d
        layers, heads = s["n_layers"], s["n_heads"]
        modes = [max(1, rows // 2), max(1, cols // 2 - 1)]
        return OnGrid(
            m.CODANO(
                output_variable_codimension=1,
                hidden_variable_codimension=s["hidden_variable_codimension"],
                lifting_channels=s["lifting_channels"],
                use_positional_encoding=False,
                n_layers=layers,
                n_heads=[heads] * layers,
                n_modes=[modes] * layers,
                per_layer_scaling_factors=[[1.0, 1.0]] * layers,
                attention_scaling_factors=[1.0] * layers,
            ),
            shape,
            two_d=True,
        )
    if catalog_id == "neuralop.UQNO":

        def fno():
            return m.FNO(
                n_modes=(s["n_modes"],),
                hidden_channels=s["hidden_channels"],
                in_channels=c,
                out_channels=1,
                n_layers=s["n_layers"],
            )

        return OnGrid(
            _UQNOSolution(m.UQNO(base_model=fno(), residual_model=fno())), shape
        )
    if catalog_id == "neuralop.GINO":
        return _GINOOnPoints(shape, s)
    if catalog_id == "physicsnemo.FNO":
        from physicsnemo.models.fno import FNO

        return OnGrid(
            FNO(
                in_channels=c,
                out_channels=1,
                decoder_layers=1,
                decoder_layer_size=s["decoder_layer_size"],
                dimension=1,
                latent_channels=s["latent_channels"],
                num_fno_layers=s["num_fno_layers"],
                num_fno_modes=s["num_fno_modes"],
                padding=s["padding"],
            ),
            shape,
        )
    if catalog_id == "physicsnemo.AFNO":
        from physicsnemo.models.afno import AFNO

        rows, cols = shape.grid_2d
        if rows % 2 or cols % 2:
            raise CatalogRefused(
                "catalog_settings_inconsistent",
                "AFNO's 2 x 2 patches need an even grid",
            )
        return OnGrid(
            AFNO(
                inp_shape=[rows, cols],
                in_channels=c2,
                out_channels=1,
                patch_size=[2, 2],
                embed_dim=s["embed_dim"],
                depth=s["depth"],
                num_blocks=s["num_blocks"],
            ),
            shape,
            two_d=True,
        )
    if catalog_id == "physicsnemo.FullyConnected":
        from physicsnemo.models.mlp import FullyConnected

        return _Flat(
            FullyConnected(
                in_features=shape.n_in,
                layer_size=s["layer_size"],
                out_features=shape.points,
                num_layers=s["num_layers"],
                activation_fn=s["activation_fn"],
            )
        )
    raise CatalogRefused("catalog_entry_unknown", f"{catalog_id!r} has no builder")
