# OpenFOAM v2506 reference package (f17)

Decision: `.agent/decisions/2026-10-15-F17-OPENFOAM-PACKAGE-01.md`. The package is
the vendor image `opencfd/openfoam-default:2506` pinned by its linux/amd64
manifest digest (`image.lock.json`); nothing is built.

| File | Purpose |
| --- | --- |
| `image.lock.json` | index/manifest/config digests and the run reference |
| `pull.sh` | pull by digest and check the in-image build id (`_615aae61-20250627`) |
| `smoke.sh WORK` | cavity (icoFoam) and pitzDaily (scalarTransportFoam) under runner isolation |
| `foam_run.py CASE 'CMD'` | one measured container launch (wall, cgroup CPU-s, memory peak) |
| `f17_geometry.py` | frozen groove convention, validity checks, conforming floor-sheet STL |
| `f17_deck.py` | mesh (blockMesh + snappyHexMesh), flow (simpleFoam) and scalar (scalarTransportFoam) decks; `Allrun` = one container command per case |
| `f17_foam.py` | independent numpy reader for polyMesh and field files |
| `f17_extract.py` | host-side observers: outlet M, Δp, residence, balances, bounds, convergence |
| `f17_controls.py` | Poiseuille series, independent split-tracer marching reference |
| `f17_proof.py` | runs the feature/control proof and writes `f17-feature-proof.json` |
| `f17_freeze.py` | freezes the triage manifest and the bank (operator seed) |

Run notes: the image entrypoint starts in `$HOME`, so every command `cd`s into
its case; `Allrun` sources `etc/bashrc` itself if the entrypoint is overridden.
Science and numerical values: `.agent/decisions/2026-10-15-F17-SCIENCE-VALUES-01.md`.
