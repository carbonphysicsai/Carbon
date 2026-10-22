# Backbone catalog licence manifest

What the catalog ships and under which licence, by component. Written 2026-10-22 for the
Validator's landing condition on the 16 catalog entries (receipt on `claude/catalog-combined`
c017ba4d8). Owner decisions: OWNER-CATALOG-VENDORED-LICENCES-01 (2026-10-20) and
OWNER-CATALOG-LICENCES-02 (2026-10-22). Licences below are read from each component's own
shipped file or package metadata, not from memory. Never published: GPL code (KNO), and nothing
reaching `68bfee956`.

## Vendored source trees (inside each bundle's `source.tar.gz`, licence file kept beside the tree)

| Tree | Licence | Source | Used by |
|---|---|---|---|
| `cno-6e76519` | MIT (ETH Computational and Applied Mathematics Laboratory) | CNO | 13 entries |
| `lno-78c64ef` | MIT (qianyingcao) | LNO | 13 entries |
| `neural-solver-library-db942b7` | MIT (THUML, Tsinghua University) | Neural-Solver-Library | 13 entries |
| `oformer-f1111b3` | MIT (BaratiLab) | OFormer | 13 entries |
| `transolver_plus-d5a23` | MIT (THUML, Tsinghua University) | Transolver++ | 13 entries |
| `Transolver-75e0f67…` | MIT (THUML, Tsinghua University) | Transolver | 3 entries |

## Wheels shipped in bundles (`bundle.json` `wheels`)

| Wheel | Licence (package metadata) | Entries |
|---|---|---|
| `torch_harmonics-0.7.4` | **BSD-3-Clause** (NVIDIA): cleared by name in OWNER-CATALOG-LICENCES-02 | neuralop.SFNO, neuralop.LocalNO |
| `torch_geometric-2.8.1` | MIT | physicsnemo.MeshGraphNet |
| `deepxde-1.15.0` | LGPL-2.1: cleared in -01 | deepxde.DeepONetCartesianProd, thuml.FNO, thuml.F_FNO, thuml.Factformer, thuml.Galerkin_Transformer, thuml.Transolver |
| `joblib-1.5.2` | BSD-3-Clause | the same six |
| `scikit_learn-1.7.2` | BSD-3-Clause | the same six |
| `scikit_optimize-0.10.2` | BSD-3-Clause | the same six |
| `threadpoolctl-3.6.0` | BSD-3-Clause | the same six |
| `pyaml-25.7.0` | WTFPL (public-domain style) | the same six |

**For the Validator:** the four BSD-3 wheels (joblib, scikit_learn, scikit_optimize, threadpoolctl)
and the WTFPL wheel (pyaml) are not named in -01 or -02. They have shipped in the six cleaned
DeepXDE/THUML entries since the clean packets; this manifest names them so the owner's record can
cover them explicitly.

## Libraries supplied by the pinned worker image (not vendored; imported by the entries)

| Library | Licence | Entries |
|---|---|---|
| `neuraloperator` (neuralop) | MIT (read from package metadata, 2.0.0) | neuralop.*, f08.neuralop.*, cooling.neuralop.* |
| `nvidia-physicsnemo` | Apache-2.0 (read from package metadata, 2.2.0) | physicsnemo.*, f08/cooling/f02 FullyConnected |

The versions the image actually carries are pinned by its environment digest; the figures above are
from the test venv and must be re-read from the published image when it is built.

## Variants (an entry that is not the backbone's plain default)

- **`thuml.LSM`** is the upstream instance-norm variant (`task: dynamic`): it uses upstream's own
  instance-norm option, so it differs from the plain default build. Any card or listing text for it must say so.

## Code with no licence

None shipped. WNO (no licence) may ship under OWNER-CATALOG-LICENCES-02 only when listed here by
name and source as "no licence: shipped under owner risk acceptance OWNER-CATALOG-LICENCES-02";
no WNO entry is in the catalog today.
