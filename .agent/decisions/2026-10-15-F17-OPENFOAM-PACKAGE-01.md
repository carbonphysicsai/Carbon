## 2026-10-15 — F17-OPENFOAM-PACKAGE-01: f17 runs the upstream OpenCFD v2506 image, pinned by digest

**Authority.** Engineering choice within the solver-readiness program (lead
brief 2026-10-15; the owner authorized the package downloads in that session).
It closes the open choice in `solver-package-specs/f17-openfoam.md` §1
(source build vs upstream image). It grants no qualification, Tier claim, LIVE
status, reward or spend.

**Decision.** The f17 reference package is the upstream OpenCFD image
`docker.io/opencfd/openfoam-default:2506`, pinned by digest, with no Carbon
layer:

- index digest `sha256:1578f5ded8bcbc68aa6a98dedd0693c3990bbab3bd6f1c01984e911c681f4e63`
- linux/amd64 manifest `sha256:020e00e512c3e0f50dd9904137bb64bdfe4b55b1fae6b9d6a566e4895d2d6e4a` (the run reference)
- config `sha256:5cef45e8d6aaaf58cb5fe4accaef11228c13dff292722143b9f61a4b3fc68d9c`
- in-image `META-INFO`: `api=2506`, `patch=0`, `build=_615aae61-20250627`, which is
  the spec's upstream commit `615aae61d7e95e110ca842ca105c799d10f59178`;
  platform `linux64GccDPInt32Opt` (double precision, 32-bit labels).

Lock, pull/verify, smoke and run helper: `scripts/dev/reference_packages/openfoam/`.
Evidence: `docs/development/evidence/reference-packages-01/openfoam.json`.

**Reasons.** The image is the vendor's own v2506 build of exactly the pinned
commit, so a source build would add a toolchain and ThirdParty pin set (CGAL,
SCOTCH, MPI) without changing the solver. A registry digest is portable to the
bulk machine without `docker save/load`, and the cooling Challenge already
pins `opencfd/openfoam-default` by digest (v2512, `carbon/cold_plate/openfoam.py`).
No extra tool is needed inside the container: decks, the groove STL and every
observer are produced and read by host Python (numpy only), so no thin
Dockerfile was written.

**Two run facts the runner must respect.** The image entrypoint
`/openfoam/run` starts the shell in `$HOME`, so case commands begin with an
explicit `cd`; each f17 `Allrun` does `cd "$(dirname "$0")"` and sources
`etc/bashrc` itself when the entrypoint is overridden.

**Alternatives rejected.** Source build from the v2506 archive (more pins, same
binary behaviour, slower); cooling's v2512 image (different release, spec pins
v2506); Foundation OpenFOAM 13 (different fork, spec rejects it).

**Reversibility.** A later source build can replace the lock; every f17 deck
binds the run reference in its flow cache key, so a repin invalidates cached
flows and requires fresh verification.

**HUMAN_INPUT left.** None for the package. Licence: GPL-3.0-or-later.
