"""The backbone catalog's table: ids, pinned libraries and bounded settings.

Pure data. Each entry names the library and exact version Carbon runs it
from, the adapter that fits it to a Challenge's interface, and every setting
a miner may choose, each with a closed range and a default.

**Defaults** are architectures from scratch, never tuned values (Validator,
2026-10-20): the library's own default wherever it has one that fits the
Challenge's grid; otherwise the value Carbon's untuned B0 probe used, sized
to the grid (`basis` says which). Tuned settings found by Carbon's batches
stay private.

**Bounds** are engineering bounds (memory, the grid's Nyquist limit, the
library's own constraints), not quality claims. The training step count has
no fixed cap: the rebuild's wall time is the only training limit
(OWNER-REBUILD-TIME-LIMIT-01).

`resolve` is the one door: an id and settings in, the complete settings out,
or `CatalogRefused` with a typed code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SCHEMA = "carbon.backbone-catalog.v1"

#: Refusal codes (each sent to the Validator for its GAP/REFUSED class).
REFUSAL_CODES = (
    "catalog_entry_unknown",
    "catalog_setting_unknown",
    "catalog_setting_invalid",
    "catalog_settings_inconsistent",
    "catalog_library_not_pinned",
)

ADAPTERS = {
    "grid1d": "the case's inputs broadcast over the output grid plus the grid "
    "coordinate: a 1-D function with inputs + 1 channels",
    "grid2d": "the output points as a 2-D grid, the inputs broadcast over it "
    "plus both coordinates: inputs + 2 channels",
    "flat": "the inputs mapped directly to the output points",
    "point_cloud": "the output points as a 1-D point cloud, used as both the "
    "input geometry and the output queries, with a latent grid between",
}

LIBRARIES = {
    "neuraloperator": ("neuralop", "2.0.0"),
    "nvidia-physicsnemo": ("physicsnemo", "2.2.0"),
}


class CatalogRefused(ValueError):
    """A catalog selection refused before anything is built or charged."""

    def __init__(self, code, detail):
        if code not in REFUSAL_CODES:
            raise ValueError("unregistered catalog refusal code")
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Setting:
    name: str
    kind: str  # "uint", "float" or "choice"
    low: object = None
    high: object = None  # None: no fixed cap (the steps count only)
    default: object = None
    choices: tuple = ()
    basis: str = "library default"
    meaning: str = ""

    def check(self, value):
        if self.kind == "choice":
            if value not in self.choices:
                raise CatalogRefused(
                    "catalog_setting_invalid",
                    f"{self.name} is one of {', '.join(map(str, self.choices))}",
                )
            return value
        if self.kind == "uint":
            ok = type(value) is int and value >= self.low
        else:
            ok = (
                type(value) in (int, float)
                and math.isfinite(value)
                and value >= self.low
            )
        ok = ok and (self.high is None or value <= self.high)
        if not ok:
            top = "no fixed cap" if self.high is None else str(self.high)
            unit = "a whole number" if self.kind == "uint" else "a number"
            raise CatalogRefused(
                "catalog_setting_invalid",
                f"{self.name} must be {unit} from {self.low} to {top}",
            )
        return float(value) if self.kind == "float" else value

    def document(self):
        out = {"kind": self.kind, "default": self.default, "basis": self.basis}
        if self.kind == "choice":
            out["choices"] = list(self.choices)
        else:
            out["bounds"] = [self.low, self.high]
        if self.meaning:
            out["meaning"] = self.meaning
        return out


@dataclass(frozen=True)
class Entry:
    catalog_id: str
    library: str
    adapter: str
    summary: str
    settings: tuple
    note: str = ""

    def document(self):
        module, version = LIBRARIES[self.library]
        out = {
            "library": {
                "distribution": self.library,
                "module": module,
                "version": version,
            },
            "adapter": self.adapter,
            "summary": self.summary,
            "settings": {s.name: s.document() for s in self.settings + TRAINING},
        }
        if self.note:
            out["note"] = self.note
        return out


GRID = "B0 probe value, sized to the grid (the library requires a value or its default does not fit)"

#: Carbon's training loop's settings, shared by every entry.
TRAINING = (
    Setting(
        "steps",
        "uint",
        1,
        None,
        1000,
        basis="Carbon loop default",
        meaning="full-batch Adam updates; the rebuild wall time is the only limit",
    ),
    Setting(
        "learning_rate",
        "float",
        1e-6,
        0.1,
        1e-3,
        basis="Adam's default",
        meaning="Adam learning rate",
    ),
)


def _modes(default, high=30, name="n_modes", meaning="Fourier modes kept"):
    return Setting(
        name,
        "uint",
        1,
        high,
        default,
        basis=GRID,
        meaning=meaning + " (at most half the grid)",
    )


ENTRIES = (
    Entry(
        "neuralop.FNO",
        "neuraloperator",
        "grid1d",
        "Fourier neural operator (neuraloperator)",
        (
            _modes(16),
            Setting(
                "hidden_channels",
                "uint",
                4,
                256,
                32,
                basis=GRID,
                meaning="channel width",
            ),
            Setting("n_layers", "uint", 1, 8, 4),
        ),
    ),
    Entry(
        "neuralop.TFNO",
        "neuraloperator",
        "grid1d",
        "Tensorized FNO: factorized spectral weights (neuraloperator)",
        (
            _modes(16),
            Setting(
                "hidden_channels",
                "uint",
                4,
                256,
                32,
                basis=GRID,
                meaning="channel width",
            ),
            Setting("n_layers", "uint", 1, 8, 4),
            Setting(
                "factorization",
                "choice",
                default="tucker",
                choices=("tucker", "cp", "tt"),
                basis="TFNO's default",
            ),
            Setting(
                "rank",
                "float",
                0.01,
                1.0,
                0.42,
                basis=GRID,
                meaning="fraction of the full rank kept",
            ),
        ),
    ),
    Entry(
        "neuralop.UNO",
        "neuraloperator",
        "grid1d",
        "U-shaped neural operator (neuraloperator)",
        (
            Setting(
                "hidden_channels",
                "uint",
                4,
                256,
                32,
                basis=GRID,
                meaning="channel width of every U-NO layer",
            ),
            Setting("n_layers", "uint", 1, 8, 3, basis=GRID),
            _modes(8, meaning="Fourier modes kept per layer"),
        ),
    ),
    Entry(
        "neuralop.CODANO",
        "neuraloperator",
        "grid2d",
        "Codomain attention neural operator: each input is one variable (neuraloperator)",
        (
            Setting("n_layers", "uint", 1, 4, 2, basis=GRID),
            Setting("hidden_variable_codimension", "uint", 1, 64, 8, basis=GRID),
            Setting("lifting_channels", "uint", 4, 128, 16, basis=GRID),
            Setting(
                "n_heads",
                "uint",
                1,
                4,
                2,
                basis=GRID,
                meaning="attention heads in every layer",
            ),
        ),
        note="2-D only: it sees the output points as a 2-D grid; modes are fixed to fit the grid.",
    ),
    Entry(
        "neuralop.UQNO",
        "neuraloperator",
        "grid1d",
        "UQNO's solution operator: its base FNO (neuraloperator)",
        (
            _modes(16),
            Setting(
                "hidden_channels",
                "uint",
                4,
                256,
                16,
                basis=GRID,
                meaning="channel width",
            ),
            Setting("n_layers", "uint", 1, 8, 2, basis=GRID),
        ),
        note="Trains UQNO's stage 1 (the solution). The residual uncertainty stage is not trained, so no uncertainty ball is produced.",
    ),
    Entry(
        "neuralop.GINO",
        "neuraloperator",
        "point_cloud",
        "Geometry-informed neural operator: GNO in, FNO latent, GNO out (neuraloperator)",
        (
            Setting(
                "radius",
                "float",
                0.01,
                0.5,
                0.1,
                basis=GRID,
                meaning="neighbour radius on the unit point cloud",
            ),
            _modes(
                8,
                high=8,
                name="fno_n_modes",
                meaning="latent FNO modes (latent grid of 16)",
            ),
            Setting("fno_hidden_channels", "uint", 4, 256, 32, basis=GRID),
            Setting("fno_n_layers", "uint", 1, 8, 2, basis=GRID),
        ),
        note="Neighbour search in plain torch (no open3d or torch_scatter).",
    ),
    Entry(
        "physicsnemo.FNO",
        "nvidia-physicsnemo",
        "grid1d",
        "Fourier neural operator (PhysicsNeMo)",
        (
            Setting("latent_channels", "uint", 4, 256, 32),
            Setting("num_fno_layers", "uint", 1, 8, 4),
            _modes(16, name="num_fno_modes"),
            Setting("padding", "uint", 0, 32, 8),
            Setting("decoder_layer_size", "uint", 4, 256, 32),
        ),
    ),
    Entry(
        "physicsnemo.AFNO",
        "nvidia-physicsnemo",
        "grid2d",
        "Adaptive Fourier neural operator (PhysicsNeMo)",
        (
            Setting(
                "embed_dim",
                "uint",
                4,
                256,
                32,
                basis=GRID,
                meaning="token width; a multiple of num_blocks",
            ),
            Setting("depth", "uint", 1, 8, 2, basis=GRID),
            Setting("num_blocks", "uint", 1, 16, 4, basis=GRID),
        ),
        note="2-D only, on 2 x 2 patches of the output grid.",
    ),
    Entry(
        "physicsnemo.FullyConnected",
        "nvidia-physicsnemo",
        "flat",
        "Fully connected network (PhysicsNeMo)",
        (
            Setting("layer_size", "uint", 4, 1024, 512),
            Setting("num_layers", "uint", 1, 12, 6),
            Setting(
                "activation_fn",
                "choice",
                default="silu",
                choices=("silu", "gelu", "tanh", "relu"),
            ),
        ),
    ),
)

#: Backbones tested and not wrappable today, with why (documented limits).
LIMITS = {
    "neuralop.LocalNO": "needs torch-harmonics, incompatible with the pinned torch and neuraloperator",
    "neuralop.SFNO": "needs torch-harmonics, incompatible with the pinned torch and neuraloperator",
    "physicsnemo.MeshGraphNet": "needs torch_geometric, which has no wheel for the pinned torch",
}

_BY_ID = {entry.catalog_id: entry for entry in ENTRIES}


def entry(catalog_id):
    try:
        return _BY_ID[catalog_id]
    except (KeyError, TypeError):
        raise CatalogRefused(
            "catalog_entry_unknown",
            f"{catalog_id!r} is not in the catalog"
            + (f" ({LIMITS[catalog_id]})" if catalog_id in LIMITS else ""),
        ) from None


def resolve(catalog_id, settings):
    """The complete settings for `catalog_id`: the chosen ones checked, the
    rest at their defaults. Raises `CatalogRefused`."""
    chosen = entry(catalog_id)
    if type(settings) is not dict:
        raise CatalogRefused("catalog_setting_invalid", "settings are an object")
    known = {s.name: s for s in chosen.settings + TRAINING}
    for name in settings:
        if name not in known:
            raise CatalogRefused(
                "catalog_setting_unknown",
                f"{catalog_id} has no setting {name!r}; it has {', '.join(sorted(known))}",
            )
    out = {
        name: (s.check(settings[name]) if name in settings else s.default)
        for name, s in known.items()
    }
    if catalog_id == "physicsnemo.AFNO" and out["embed_dim"] % out["num_blocks"]:
        raise CatalogRefused(
            "catalog_settings_inconsistent",
            "embed_dim must be a multiple of num_blocks",
        )
    return out


def document(catalog_ids=None):
    """The catalog as served: every entry (or the named ones), its settings
    and the documented limits."""
    ids = [e.catalog_id for e in ENTRIES] if catalog_ids is None else list(catalog_ids)
    return {
        "schema": SCHEMA,
        "entries": {i: entry(i).document() for i in ids},
        "adapters": dict(ADAPTERS),
        "limits": dict(LIMITS),
        "defaults": "architectures from scratch; library defaults where they fit, else an untuned value sized to the grid",
    }
