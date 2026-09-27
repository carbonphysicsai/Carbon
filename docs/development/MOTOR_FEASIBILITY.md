# Electric motor (#344): small feasibility assessment

**Status.** This is a decision input, not a scope. Per #341, the motor gets a
small feasibility assessment before any dataset.
- Nothing was run and nothing was spent.
- The candidate below is a **proposed development design**, not a ratified
  production population.
- The work stops here until the owner decides.

## 1. Does a bounded candidate exist? Yes, on paper

#344 already bounds one:
- one permanent-magnet topology, with a parameterized 2D cross-section and a
  stated axial length;
- inputs: geometry, material curves, current and phase, rotor angle;
- outputs: the torque-angle curve, mean torque, torque ripple and selected
  flux quantities.

That is a small, well-posed 2D nonlinear magnetostatic problem per rotor
position. Its scale is much smaller than the cold plate's 3D conjugate heat
transfer.

What would make it evaluable as an exam, all **unresolved**:
- **Benchmark.** A published, reproducible motor benchmark (#344's first
  task). None has been selected here.
- **Materials.** Nonlinear B–H curves for steel, and magnet properties, with
  rights to use them. Not identified.
- **Exclusions.** End effects, thermal duty, stress, acoustics and drive
  control. #344 names them; their effect on the output contract is not yet
  written.
- **Ripple resolution.** A coarse rotor-angle grid can hide torque ripple
  (#344). The angle step needed has to be demonstrated, not assumed.

## 2. What reference execution it needs, verified 2026-09-27 on this host

| Tool | Role | Obtainable on this Linux host? | Licence |
|---|---|---|---|
| FEMM | 2D magnetics | **No native Linux build.** `pyfemm` on PyPI drives the Windows application, which confirms #344's warning | as published |
| GetDP | FE solver | Ubuntu apt offers 3.2.0, which needs sudo. Upstream publishes static Linux binaries up to 3.5.0 (listing read at `getdp.info/bin/Linux/`) | GPL |
| Gmsh | geometry and mesh | yes, a `manylinux` wheel on PyPI (4.15.2) | GPLv2+ |
| Elmer | FE solver | not in this host's apt sources; not checked further | GPL |

**Proposed reference path: GetDP with Gmsh.** It is native to Linux, can be
scripted, and is open source. GetDP can compute torque two independent ways,
Maxwell stress and virtual work. That is the kind of consistency check #344
asks for.

Not verified: that a specific GetDP electric-machine model runs here. Doing
that means downloading and executing a new third-party binary on the shared
host, which is the owner's call, as the OpenFOAM image was.

## 3. What it would cost

- **Reference execution runs on the local CPU, so the cost is USD 0.**
  - A 2D nonlinear magnetostatic solve per rotor position is small. This is
    the expected order of magnitude, **not measured**: seconds per position.
  - A rotor-angle sweep of about 100 positions is minutes of CPU per design.
  - No GPU pod is needed for the reference.
- **The real costs are not compute:**
  - a benchmark with published geometry;
  - material data with the right to use it;
  - the scientific review of which outputs are graded.
- A dataset is **not** proposed here.

## 4. Recommendation (decision input)

**Proceed to #344's first concrete task, and only that.** Reproduce one
published motor benchmark with GetDP and Gmsh as a bounded rotor-angle sweep,
and check torque by two formulations. Then stop again.

Before that runs, the owner decides:
1. whether this session may download and run the GetDP 3.5.0 static binary
   (GPL, local only, nothing on the shared Docker daemon);
2. which published benchmark to reproduce, once candidates are listed with
   their data rights.

Launch order is unchanged: battery, then cold plate, then the motor, then the
photonics repair.
