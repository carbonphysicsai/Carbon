# Image-bound code verification — Data Collection handoff

CODE-VERIFICATION-MMS-01, DEVELOPMENT. **No reference solver was run in this
ticket.** Tests of the checker and symbolic expressions are synthetic arithmetic
evidence, not measured solver accuracy. #1019 owns the stage-exit policy; this
package supplies implementation/specification, not another policy or package.

Code verification tests whether the implementation solves its stated equations.
It does not establish physical adequacy, applicable solution convergence,
conservation, buyer-tool Tier-2 agreement or qualification. Readiness item 3
requires all three distinct evidence types. Re-run after **every image rebuild
or re-pin**, including #1030's rebuilt Elmer. Historical results keep old pins.

## Execution order and coverage

| Order | Solver/package basis | Native test now | Remaining native integration / feature gaps |
| --- | --- | --- | --- |
| 1 f02 | #1030 Elmer 26.2.1, source lock; rebuilt image `sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675` | **KEEP** `scripts/dev/reference_packages/elmer/mms_heat.py` from #1030 | Need actual rebuilt-image result, spatial/time plateau check; heterogeneous stack/Robin interfaces and peak/energy observers remain separate feature proofs |
| 2 motor | main `scripts/dev/motor/reference/Dockerfile`: GetDP 3.5.0, Gmsh 4.15.2, source checksums | `scripts/dev/code_verification/getdp_mms.py`, actual motor Form1P discretisation | Native execution UNMEASURED; nonlinear B-H, remanence, skew reconstruction and signed torque/cogging observers are **not** verified by this linear field test |
| 3 battery | main battery-overlay.lock.json, PyBaMM 26.8.0.0 on pinned base plus hash-locked overlay | `scripts/dev/code_verification/pybamm_submodels.py`: spherical FV/IDAKLU particle and lumped heat | Native execution UNMEASURED; full DFN, SEI/plating and session-start-SOC observers need independent sub-model/assembly checks |
| 4 f13 | #1030 same Elmer build, HelmholtzSolve, quadratic tetrahedra, 60-mm port stubs | `elmer_helmholtz.py`: native phase-rotated complex MMS on linear hexes, reusing the heat mesh writer | Native execution UNMEASURED. **Quadratic-tetra interior-field adapter remains pending**. Port closure ≤0.02% is conservation, not MMS. Matched impedance/port power needs its separate analytic proof |
| 5 CFD | f17 package-specs.json proposes OpenCFD v2506; cooling cell v2512 is a different package; SU2 not selected | `openfoam_periodic.py`: native prescribed-velocity scalarTransportFoam periodic analytic solution | Native execution UNMEASURED, accepted image pin pending. **Flow/pressure and forced-scalar feature adapters remain pending**; no transfer from cooling or substitution with SU2 |
| 6 optics | package-specs.json proposes Meep 1.32.0; no accepted image | `meep_mode.py`: native FDTD vacuum Bloch frequency ladder with Harminv | Native execution UNMEASURED, accepted image pin pending. **Dielectric slab, subpixel and target-overlap adapters remain pending**; MPB alone is not FDTD verification |
| 7 f08 | #1030 CalculiX 2.23, source lock | `calculix_modes.py`: native C3D20R axial-rod frequency ladder; reuse #1030's exact oscillator damping proof | Native execution UNMEASURED. **3D manufactured body-force/interior-field adapter remains pending**; axial modes do not verify bending, full damping implementation or warpage process history |

Seven basic native routes are now prepared (including the reused heat worker),
but **none is solver-tested by this ticket**, and they do not cover every
application feature. Missing feature adapters and pins remain named work, not
fabricated PASSes. Data Collection runs the workers in the specified order as
their packages become available, retaining native failures as reference findings.
The source-based API/deck tests below are not a promise that native APIs were
executed. No new build
or solver launch is authorized by this document. No money, training, hidden
cases, AX42 access, EV5, sealed journal 14 or live contract changes.

## Manufactured/analytic tests and proposed ladders

Every quantity below is a **dimensionless code-verification fixture**, not a
customer population or physical production tolerance. The expected orders are
mathematical predictions for the specified discretisation and smooth fields.
Recommended pass bands are **HUMAN_INPUT**, requiring science's adoption before
reference-stage exit. They do not override application-specific convergence.

Let `S = sin(pi x) sin(pi y) sin(pi z)` on the unit cube, and
`s = sin(pi x) sin(pi y)` on the unit square.

**Elmer heat (reuse #1030).** `rho=cp=k=1`, `T=1+S cos(2 pi t)`;
`f=S(3 pi² cos(2 pi t)-2 pi sin(2 pi t))`. Dirichlet `T=1` on faces;
initial `T=1+S`. Hex808 and BDF2. Space `N=8/16/32`, `dt=1/512`, observer
`t=0.5`; expected L2/Linf order 2, recommendation `[1.7,2.3]`. Time
`dt=1/8,1/16,1/32` at N16, compare same-node fields to `dt=1/256`, expected
2 with the same band. **Important:** verify temporal error is below spatial
error and vice versa. A same-mesh fine-time subtraction isolates temporal error
but is not an exact solution. #1030's nodal RMS/Linf may superconverge; retain
element-interior volume-weighted L2 as a separate check, not silently replace
its old observer. Changing the test/pins requires a new spec/result identity.
The source convention follows the [Elmer model manual](https://www.nic.funet.fi/index/elmer/doc/ElmerModelsManual.pdf).

**GetDP motor.** `a=(0,0,s)`, unit reluctivity; `Jz=2 pi² s`;
`B=(pi sin(pi x) cos(pi y), -pi cos(pi x) sin(pi y), 0)`. Zero `a` on the
entire square boundary. Motor's BF_PerpendicularEdge/Form1P with first-order
triangles and three-point quadrature. Requested `h=1/8,1/16,1/32` (retain actual
mesh statistics too). A L2 order 2 recommendation `[1.7,2.3]`; B L2 order 1
recommendation `[0.7,1.3]`. The worker integrates native triangle fields at
three interior quadrature points; a nodal-only exact coincidence cannot pass.
KEEP the [GetDP formulation](https://getdp.info/doc/texinfo/getdp.html#Magnetostatics),
not a scalar Poisson formulation substituted for motor's discrete space.

**PyBaMM spherical particle.** Unit radius/diffusivity, `c=exp(-t)(1+r²+r⁴)`;
`f=-exp(-t)(7+21r²+r⁴)`. Initial polynomial; derivative BC zero at r0 and
`6 exp(-t)` at r1. Spherical FV N20/40/80, IDAKLU rtol1e-10/atol1e-12,
t0.2. Shell-volume-weighted L2 and Linf, expected spatial order 2,
recommendation `[1.7,2.3]`. Retain concentration integral and boundary/source
mass balance separately. Solver-error floor needs a tighter-tolerance witness,
not an invented second-order temporal claim. **Lumped heat:** `theta'=1-theta`,
theta0=0, exact `1-exp(-t)`; t1, rtol1e-4/1e-6/1e-8. Adaptive IDAKLU does
not imply an order from output sampling intervals. Report error/tolerance
ladder; finest absolute error recommendation≤1e-6 and monotone improvement are
HUMAN_INPUT. Official PyBaMM 26.8 [FV documentation](https://docs.pybamm.org/en/pybamm-v26.8.0.0/source/examples/notebooks/spatial_methods/finite-volumes.html)
supports the domain/discretisation interface, not an earned test result.

**Elmer acoustics.** `p=S`, real pressure; unit rho/c, omega1, zero damping.
For `-lap(p)-p=q`, `q=(3 pi²-1)S`. Zero real/imaginary pressure on all faces.
Inject native `Pressure Source 1`, zero Source2; confirm sign/normalization from
the pinned release before native execution. Quadratic-tetra mesh h1/4,1/8,1/16;
volume L2 expected3, gradient L2 expected2; recommendations `[2.6,3.4]` and
`[1.7,2.3]`. Never use nodal error order as a substitute. Add a nonzero-imaginary
phase-rotated copy and an exact straight-duct plane wave with matched impedance:
port incident/reflected/transmitted power checks are separate from bulk MMS.
Boundary/source keywords are documented in the [Elmer acoustics chapter](https://www.nic.funet.fi/index/elmer/doc/ElmerModelsManual.pdf).

The delivered **basic** worker instead uses #1030's linear Hex808 cube at
N8/16/32 and `(1+0.5i)S`, with both native sources and both pressure components.
Nodal RMS/Linf expected order2, recommendation `[1.7,2.3]`; its imaginary-field
errors are retained independently. This is deliberately **not** the proposed
quadratic-tetra volume/gradient test above, and cannot discharge that feature gap.

**OpenFOAM flow/scalar.** Unit U=(1,0), diffusivity1, `c=1+exp(-t)s`;
`f=exp(-t)((2 pi²-1)s+pi cos(pi x) sin(pi y))`. c1 boundary, initial1+s,
square mesh16/32/64, dt1/1024 at t0.1; linear diffusion/advection on an orthogonal
mesh predicts L2 order2, recommendation `[1.7,2.3]`. Fixed boundary c=1 is
correct only because s vanishes on every face. In a second **flow** fixture use
fully developed Poiseuille `u=(4y(1-y),0)`, unit viscosity/rho,
`dp/dx=-8`, no-slip walls, exact inlet/outlet velocity/pressure. Compare U/p and
integrated flux at the same refinement ladder. A scalar-only run cannot verify
the flow solver. Scalar source injection must match the packaged fvOptions/
fvModels interface; [upstream v2506 solver source](https://api.openfoam.com/2506/dir_c1a1d77e2de9f0a909b0abf393e236fa.html)
is the API basis. Unstructured upwind/high-Pe/nonorthogonal behavior is not
qualified by this smooth orthogonal fixture. SU2 remains an unselected option.

The runnable scalar-only first step avoids a release-dependent source plugin:
`c=1+0.2 exp(-4 pi² D t) sin(2 pi (x-Ut))`, U1, D0.01, periodic unit interval,
transversely constant with zero-flux walls. N16/32/64, backward-time scheme,
central advection/diffusion, dt1/8192, t0.125. Expected spatial order2,
recommendation `[1.7,2.3]`, with a required finer-time witness if the final order
approaches a temporal plateau. It tests advective phase and diffusion, not just
a constant field. Velocity is prescribed: this **does not verify flow**. The
forced-scalar and Poiseuille adapters above remain separate, unimplemented gaps.

**Meep analytic modes.** Use a uniform dielectric slab waveguide with an exact
TE even-mode root `h tan(h d/2)=q`, `h²=n_core² omega²/c²-beta²`,
`q²=beta²-n_clad² omega²/c²`. Recommended fixtures ncore2, nclad1,
unit wavelength, d0.25; retain the root bracket and residual, not a fitted beta.
Resolution20/40/80 pixels per unit; compare effective index, mode-field overlap
and phase accumulation between two monitors. Subpixel averaging on and off are
**separate** registrations. Expected roughly second-order smooth-interface
convergence with averaging; recommendation `[1.6,2.4]` only after an asymptotic
ladder is demonstrated. Raw pixel staircasing may be first order and must not
be forced into that band. Meep's [subpixel documentation](https://meep.readthedocs.io/en/latest/Subpixel_Smoothing/)
and [mode-source guide](https://meep.readthedocs.io/en/latest/Python_Tutorials/Eigenmode_Source/)
support this approach. MPB's eigenmode result alone does not verify the FDTD
propagator or f06's finite-width 3D target-overlap observer. A coarse test has no
51–107 GiB fine-witness memory requirement; no full f06 run is authorized.

The runnable first step is a vacuum 1D Bloch cell of length1, k0.2 cycles/unit,
whose exact frequency is0.2 in Meep units. N20/40/80, the native FDTD propagator
and a post-source Harminv frequency estimate; expected dispersion order2,
recommendation `[1.7,2.3]`. Fit error≤1e-8 is a **sampling recommendation**, not
physical agreement; unresolved or multiple modes refuse export. Sampling200
time units must be extended prospectively if fit error dominates the finest
grid's dispersion. No dielectric interface exists in this first step, so it
cannot verify subpixel averaging or the slab/overlap contract above.

**CalculiX elasticity.** Unit cube, lambda=mu=1 (E2.5, nu0.25),
`u=(S,0,0)`, zero face displacement. Body force `-div(sigma)`:
`fx=5 pi² S`, `fy=-2 pi² cos(pi x) cos(pi y) sin(pi z)`,
`fz=-2 pi² cos(pi x) sin(pi y) cos(pi z)`. Density1. Quadratic solids
N4/8/16; displacement-volume L2 expected3, stress L2 expected2; recommended
bands `[2.6,3.4]`/`[1.7,2.3]`. Register the exact body-force integration, not
nodal forces guessed to match the answer. Add an exact affine thermal-expansion
patch and rod modal-frequency ladder. An exact affine patch alone has zero
error and cannot demonstrate order. [CalculiX 2.23 capabilities](https://www.dhondt.de/ov_calcu.htm)
include thermal/frequency analyses; those capabilities are not empirical
verification. Warpage cure, viscoelasticity, solder formation and full history
remain separate missing physics, not covered by this f08 test.

The runnable rod first step uses C3D20R, unit L/E/rho, nu0, transverse
displacements constrained, fixed ux at x0 and free x1; N4/8/16. Exact axial
frequencies `(2m+1)/4`, m0/1/2. Quadratic FE predicts eigenfrequency order4;
recommendation `[3.5,4.5]`, pending an asymptotic ladder and print-precision
floor check. It does not substitute for the 3D body-force MMS above. KEEP
#1030's independent oscillator proof for exact damping, normalization and
harmonic sign convention. Additional bending/thermal/warpage features remain
explicitly unverified.

## Commands, identity and retained outputs

These are **Data Collection execution instructions**, not actions taken here.
Use immutable current image ID, CPU only, one process/thread, network disabled,
fresh owned work directory, bound wall/memory/resource limits, retain commands,
logs, exit codes, actual mesh statistics, raw fields and image inspection.
Never prune a shared Docker engine. Inspect image availability before running.

Elmer: after #1030 merges, use its existing launcher `python3
scripts/dev/reference_packages/elmer/mms_heat.py IMAGE NEW_WORK RESULT.json`.
That launcher invokes headless CPU Elmer inside the pinned image. It currently
reports a recommended band; science adoption is still required. No copied old
PASS after rebuild. GetDP and PyBaMM workers below run **inside their images**:

```sh
python3 scripts/dev/code_verification/getdp_mms.py --work /work/new-mms \
  --output /work/motor-fields.json --image-digest sha256:ACTUAL --spec-digest sha256:ACTUAL
python3 scripts/dev/code_verification/pybamm_submodels.py \
  --output /work/battery-fields.json --image-digest sha256:ACTUAL --spec-digest sha256:ACTUAL
python3 scripts/dev/code_verification/elmer_helmholtz.py --work /work/new-acoustic \
  --output /work/acoustic-fields.json --image-digest sha256:ACTUAL --spec-digest sha256:ACTUAL
python3 scripts/dev/code_verification/openfoam_periodic.py --work /work/new-scalar \
  --output /work/scalar-fields.json --image-digest sha256:ACTUAL --spec-digest sha256:ACTUAL
python3 scripts/dev/code_verification/meep_mode.py \
  --output /work/optics-fields.json --image-digest sha256:ACTUAL --spec-digest sha256:ACTUAL
python3 scripts/dev/code_verification/calculix_modes.py --work /work/new-rod \
  --output /work/rod-fields.json --image-digest sha256:ACTUAL --spec-digest sha256:ACTUAL
python3 scripts/dev/code_verification/common.py FIELDS.json CRITERIA.json \
  --expected-image sha256:ACTUAL
```

Replace the illustrative ACTUAL labels from real artifact/image inspection;
never hand-pick identities. Host image+overlay lock is battery's complete
identity: the base digest alone doesn't bind PyBaMM. Workers report supplied
image labels; **operator's retained execution receipt**, not that label alone,
establishes which image actually ran. No worker launches Docker or changes the
package. The checker uses only standard Python and runs in all CPU images.

`python3 scripts/dev/code_verification/criteria.py KIND` prints recommended
criteria with hashes **computed from the actual checked-out specs.json and
worker bytes**. Feed its spec_digest to the worker, retain the JSON, and compare
the returned export using common.py. It always prints HUMAN_INPUT: no command
silently adopts a band. The reused heat worker has its own v1 output contract;
criteria.py refuses to pretend it has the new field-export format. Retain its
native spatial/time evidence and accepted criteria in the readiness summary.

`derive.py` derives sources/BCs symbolically using optional SymPy1.14.0 already in
uv.lock; it does not run a physical solver or become a production dependency.
Common checker input: closed `carbon.code-verification.fields.v1`, public scope,
kind/family/image/spec/adapter digest, ordered rows `{h,t,points,values,weights}`,
one retained raw-output hash per rung. Recompute volume-weighted errors against
the exact field; >=3 strictly refined rungs; nonzero positive finite errors.
Zero errors mean **order not demonstrated**, not infinite order/PASS.

Criteria JSON binds kind/family/spec_digest/adapter_digest, literal `h` ladder,
observer `t`, recommended/adopted `order_band`, status HUMAN_INPUT or
ACCEPTED_DEVELOPMENT. With unadopted bands an agreeing result still exits3 and
states HUMAN_INPUT. Invalid/missing/repinned evidence exits2; adopted finite
criteria outside band are a REFERENCE_FINDING, never candidate failure.
The common checker covers scalar fields and registered scalar modal-frequency
lists; supplementary vector, imaginary-field and thermal-ODE diagnostics still
need their science-accepted checks. No assertion that checking ux alone verifies
elasticity. Raw-output digests bind retained files but are not recomputed by the
checker: the operator must retain them and verify their hashes, the image-run
receipt and complete fields. A forged caller label is not a trusted execution.

Readiness handoff: retain results plus exact adopted criteria and operator-run
receipt; the item3 public summary binds all sources and has kind
code_verification/family/image and measured order metrics. Convergence and
conservation must still be supplied separately, on the current family/image.
No feature with a pending adapter or unadopted criterion earns stage exit.
