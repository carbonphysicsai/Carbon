# f13 — diagnose power before buying more truth

**F13-POWER-BALANCE-DIAGNOSIS-01 / DEVELOPMENT / SPECIFIED.** Code/config and
analytic review only: no solver runs, spend, installation or hidden/AX42 data.
[Machine-readable return](f13-power-balance-diagnosis.json). KEEP the
[customer packet](f13-compressor-silencer.md), [strong incumbent](../cheap-baselines/f13.md)
and package ownership. A reference finding never grades a candidate.

## 1. What was actually reviewed

Public acquisition branch at **0f12834226f65cdb317e7407e1e83e68c135801b**:

- [f13_deck.py](https://github.com/carbonphysicsai/Carbon/blob/0f12834226f65cdb317e7407e1e83e68c135801b/scripts/dev/reference_packages/elmer/f13_deck.py),
  Git blob `5a527255fb83202ec67f11a86555bff18763fffc`;
- [feature proof](https://github.com/carbonphysicsai/Carbon/blob/0f12834226f65cdb317e7407e1e83e68c135801b/docs/development/evidence/reference-packages-01/f13-feature-proof.json),
  [grant-host report](https://github.com/carbonphysicsai/Carbon/blob/0f12834226f65cdb317e7407e1e83e68c135801b/docs/development/evidence/reference-packages-01/triage-ccx33/README.md),
  [ledger](https://github.com/carbonphysicsai/Carbon/blob/0f12834226f65cdb317e7407e1e83e68c135801b/docs/development/evidence/reference-packages-01/triage-ccx33/ledger.jsonl),
  [deck manifest](https://github.com/carbonphysicsai/Carbon/blob/0f12834226f65cdb317e7407e1e83e68c135801b/docs/development/evidence/reference-packages-01/triage-decks-manifest.json).

Elmer source target26.2.1; config image
`sha256:8bcd864dd60be0a80be9769c1a95c67db76eca9e718212f63dd0460cf3a08fc6`;
grant-host OCI run manifest
`sha256:fdb4d8385710a833d556d4540dfe1b60a8fb505d8b894203bffa82ff6703133d`.
These are different image identities, not interchangeable digest strings.
Nominal frozen case.sif SHA256
`4cf02f9c24fe89861353ee413efdea97d85d14ba8f11eb5968412e8260020e17`;
deck.json SHA256
`885dc6d87887bb5e3e1cb7c4ac74de3767a3280546286d36b9c279eb90209286`.
The audit consumed tracked reports, not raw nominal fields/ports.dat or a
local reproduction. Exact worst frequency, signed residual, area/column
values and offset mesh convergence remain **NOT_EXAMINED / requested**.
Source/manual agreement is not proof of the installed build or deck hash.

Reported facts (not Codex measurements): straight/coaxial closure <=0.34%;
nominal offset reaches4.7%; large-offset/clearance sweeps are censored.
The feature proof's coaxial h8/h6/h4 parity does **not** qualify the offset
geometry. Do not infer offset mesh independence from that result. Completed
dense curves cost7.6 and81 CPU-min; the >2h tail remains censored. No p95,
full-bank cost or full-band feasible buyer answer is established.

## 2. Setup audit and ranked explanations

The deck uses fused second-order tetrahedra, rigid walls, rho1.2/c343, no
damping/mean flow, port radius25mm, stub length10mm, `Wave Impedance 1=c`,
inlet imaginary source `Wave Flux 2=2kA` and A=sqrt(2*rho*c/S) for1W incident
power. This source normalization is consistent with the plane-wave Robin
condition; the near-unity duct control argues against a universal missing
factor2, rho or RMS conversion. Do not change `c` to `rho*c`: Elmer's Z in
its pressure-gradient condition is speed-like, unlike physical p/u impedance.
The [Elmer Models Manual, Helmholtz §12.2.1/12.3](https://www.nic.funet.fi/index/elmer/doc/ElmerModelsManual.pdf)
defines the boundary equation and source/impedance components; confirm its
implementation in the exact package before an extractor repair is accepted.

Ranked, falsifiable hypotheses:

1. **Proven code asymmetry; explanatory contribution unmeasured.** Inlet
   reflection is |mean(p_in)-A|²*S/(2rho*c). Outlet transmission is the
   *integral* of |p_out|²/(2rho*c), including transverse spatial variance.
   The inlet |p|² integral is saved but unused. Offset geometry can excite
   nonuniform port fields, so these definitions need not close together.
2. **Likely boundary-model error.** A local plane-wave Robin impedance at
   10mm absorbs/reacts incorrectly to evanescent modes. Merely adding missing
   variance can close the artificial Robin problem while leaving physical
   reflected/transmitted plane powers wrong. Below cutoff does not mean
   a field is already plane at a nearby port.
3. **Unquantified product/quadrature and geometry error.** `Pabs2` is formed
   from nodal Pressure1/2 and exported as a field. Interpolating nodal squares
   is not generally squaring the interpolated quadratic pressure at integration
   points. Verify exact boundary quadrature, curved-area and exported-field
   update semantics; do not assume an integral identity survives this shortcut.
   Offset mesh/linear residual checks are missing.
4. **Lower priority bookkeeping/sign error.** `observe()` assumes six
   boundary-int columns in inlet/outlet order, and an ideal pi*r² area, without
   validating actual BC IDs, areas or normals. Verify names, row/frequency
   alignment and source/phasor convention. Scalar count alone is not custody
   or sign validation. Existing scan/separate parity is for coaxial controls,
   not proof that the nominal offset postprocessor is correct.

The [COMSOL Pressure Acoustics port guide](https://doc.comsol.com/6.4/doc/com.comsol.help.aco/aco_ug_pressure.05.028.html)
supports including evanescent modes near a geometry discontinuity. Its
[muffler example](https://doc.comsol.com/6.3/doc/com.comsol.help.models.aco.absorptive_muffler/absorptive_muffler.html)
uses modal powers rather than treating pressure amplitude as transmitted
power. These motivate a check, not an earned Tier2 or a tested fix.

## 3. Cheapest discriminating test: retained integrals, zero new solves

DC can first use the already saved six port integrals at each frequency.
Let S be the verified cross-sectional area, A the real incident amplitude,
Z0=rho*c, I_in/out=integral(p)dS and H_in/out=integral(|p|²)dS. With
mean m=I/S, define:

```
P_inc       = A²*S/(2Z0)                              # verify equals1
P_ref_pw    = |m_in-A|²*S/(2Z0)
P_out_pw    = |m_out|²*S/(2Z0)
V_in/out    = (H_in/out - |I_in/out|²/S)/(2Z0)
P_out_all   = H_out/(2Z0) = P_out_pw + V_out
r_old       = P_inc - P_ref_pw - P_out_all
r_robin     = r_old - V_in
P_ref_all   = (H_in - 2*A*Re(I_in) + A²*S)/(2Z0)
```

Derivation: decompose p=m+q with integral(q)=0. The integral of |p|² is
S|m|²+integral(|q|²). Under the reviewed Robin/source model, the latter
contributes boundary power even when the corresponding physical duct mode
would be evanescent. If V_in explains the **positive signed** r_old and
r_robin is small, this identifies mixed extraction as a major cause.
No such agreement is asserted from the unsigned4.7% summary. Negative
variance beyond quadrature tolerance is an operator/area/product finding;
retain it, never clamp it to0 or normalize powers to sum1.

This calculation diagnoses the current Robin model only. V_in/out are
**not physical propagating acoustic powers** for evanescent fields. Nor is
replacing P_out_all with P_out_pw alone a validated correction. Return both
definitions and exact data identity; do not relabel the old TL as repaired.
If raw saved integrals are unavailable, record DATA_REQUIRED rather than
run new solves. No extractor/solver invocation is included in this ticket.

## 4. Why10mm is suspicious, quantitatively

For a rigid circular duct, cutoff fc=c*mu/(2pi*a), where mu is a root of
J_m'. The [COMSOL cutoff reference](https://doc.comsol.com/6.4/doc/com.comsol.help.aco/aco_ug_pipe.12.18.html)
gives the relevant derivative roots. Analytic values below use mu=1.84118
(lowest nonaxisymmetric) and3.83171 (first nonzero axisymmetric), a=0.025m.
Offset necks can excite the lower nonaxisymmetric pair; ideal coaxial symmetry
suppresses it. Chambers themselves have lower cutoffs, so1D chamber truth is
not justified by plane-wave inlet/outlet support.

At2500Hz, mu1.84118 yields fc~4020Hz and decay alpha~57.7/m. A10mm uniform
lead reduces that mode's amplitude only to~0.56 of its value at the junction,
and squared amplitude to~0.315. A60/100mm computational lead gives~0.0010/
0.000010 squared-amplitude ratios under this isolated-mode calculation.
These are attenuation hypotheses, **not guaranteed residual bounds**:
excitation, modal mixing and termination feedback still need checking.
Coaxial mu3.83171 yields fc~8367Hz and much faster decay; this is consistent
with, but does not prove, the reported coaxial/offset difference.

## 5. Repair routes without weakening the buyer job

**Preferred physical definition:** matched modal radiation (DtN or proven
equivalent) at original port planes, with plane-mode incident source and
propagating-mode power extraction; include converged evanescent modes in
the boundary representation, both orthogonal azimuthal members where relevant.
Independent signed flux 0.5*Re(integral(p*conj(u_n))) checks conservation.
Freeze the time convention and outward normals: with exp(+i*omega*t),
u_n=-(partial_n p)/(i*omega*rho). A naive pointwise c impedance is not a
modal boundary. Existence of an adequate Elmer implementation is **HUMAN_INPUT**
pending acquisition feature proof; do not claim it is packaged.

**Fallback numerical witness:** extend uniform computational leads, test
60 then100mm, and de-embed complex plane-mode phase to the original physical
planes. These are numerical exterior domains, **not longer manufactured
ports**: the physical140mm/300mm package and its original10mm stubs stay
unchanged. Converged infinite matched leads are a prospective reference
interpretation/identity, not permission to silently change sealed truth.
Reject if extension changes TL/picks beyond the registered band. Extra
mesh/factorization cost must be measured; no free speedup is assumed.

Both routes need exact quadratic products/velocity-flux quadrature, BC/area
checks, mesh refinement and reciprocal/no-loss controls. Changing extraction
alone, taking absolute residual, adding damping, narrowing offsets or raising
the1% gate is not an adequate fix. Conditional coaxial f13-v2 remains a
separate owner reframe, not a reference bug workaround.

## 6. Smallest *proposed* new verification, after the zero-solve return

DC first identifies f_star=argmax |r_old| on the complete retained nominal
curve, with a deterministic tie rule and raw return. Do not select a favorable
frequency. Proposed sequential gate (no run/grant approval here):

| Stage | Geometry / setup | New frequency systems |
| --- | --- | ---: |
| A | Same nominal:60 and100mm computational leads at f_star, same resolution | 2 |
| B | Nominal100mm at f_star, local/mesh h4 vs h8; record solver/RSS limits | 1 |
| C | Straight-duct100mm at500 and2500Hz; coaxial control100mm at500 and2500Hz | 4 |

**Seven systems total** if retained baseline supplies the original nominal
f_star; up tofive sequential processes if control pairs each use one scan.
If retained baseline/columns are missing, add exactly one original nominal
system/one process to a separately approved manifest: **eight**, not silently
retry. Meshing/conversion children, censored attempts and repeats are counted
and costed separately. Stop as soon as a stage cannot settle within its frozen
memory/wall/resource cap. This document supplies no host/capacity/spend grant.

A proposed pass requires unchanged1% absolute signed-flux residual
(both excess and deficit, normalized by verified incident power) and the packet's
0.5dB mesh/lead sensitivity checks, with stricter near-decision bounds as
registered by science. Recommend lead-length ΔTL<=0.25dB as HUMAN_INPUT.
Straight duct retains |TL|<=0.25dB; analytic coaxial transfer matrix is a
low-frequency control only, not exact high-chamber-mode truth. If A does not
converge, stop expansion and implement/prove the modal route before volume.

Passing seven points is not a full-curve p10/5dB feasibility result. Next
separately authorized work must cover complete dense/adaptive curves, mesh,
lead/modal refinement and independent non-hidden/retired Tier2 witnesses.
Return interval-weighted p10/minimum, verdict/pick/dB regret and unresolved
coverage near the buyer boundary; three frequencies cannot certify a bank.
Report every process, frequency system, mesh, CPU/wall/RSS/failure and new
reference/deck/extractor identity. Historical sealed results never rescore.

## 7. Recommendation and remaining authority

Ask for retained nominal integrals first. If the variance identity explains
the residual, prioritize proper port treatment, not more training data or
more full-band offset solves under the defective reference. DC owns package
repair and verification; Test Lead/science owns numerical/decision acceptance.
Buyer5dB, physical envelope and conservation stay unchanged. The original
3D buyer job is retained while the reference is repaired; no replacement
decision follows from the present diagnostic hypothesis.

Unresolved: raw signed finding, exact port/area/quadrature identity, modal
feature availability, offset convergence, valid full-band cost/Tier2 receipt
and separately authorized run manifest/caps. All remain fail closed. This
PR tests algebra/specification only and earns **SPECIFIED**, not an adequate
reference, a feasible bank, production claims or physical attenuation.
