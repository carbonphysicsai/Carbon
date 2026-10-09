# CHALLENGE-WARPAGE-PACKET-01 — owner brief and working contract

D016 has a source-confirmed engineering workflow, but it is **not a dispatch-ready customer acceptance packet**. The proposed decision is to choose an underfill and solder-stack geometry for a complete three-dimensional package over its full thermal history. Public sources establish the job and conditional measurements; they do not supply this package's complete stress, temperature or manufacturing acceptance contract.

Amkor publishes a coupled package simulation workflow under a named packaging/mechanical simulation engineer; ASE independently offers customer-input package stress and warpage simulation. These are evidence of an existing buyer role and workflow, not Carbon customers, purchasing commitments or measured willingness to pay. See the [source ledger](source-evidence.md).

The [common-format packet](PACKAGE_WARPAGE_DESIGN_PACKET.md) retains the original full 3D job. It keeps cure, residual stress, solder state changes and calibrated inelastic effects as adequacy requirements where the chosen package needs them. A cheap thermoelastic control cannot silently replace that job.

| Owner decision | Evidence and consequence |
| --- | --- |
| Is package warpage worth advancing? | Credible buyer workflow and AI/HPC context; engineering value remains unmeasured against laminate theory, cached FE and fitted response surfaces. |
| What limits are supported? | JEITA provides conditional external BGA/FBGA warpage limits. Supplier data provides underfill properties and reflow capability. Applicable package limits, especially stress/strain and junction temperature, remain `HUMAN_INPUT`. |
| What costs would start it? | First diagnostic panel: **ASSUMPTION €19.16 / €27.09 / €56.14** low/base/high. Original bank: **ASSUMPTION €23.91 / €46.06 / €127.30**. These are prospective compute estimates, not quotes or authorisation. |
| How attractive is it? | Original #928 value-to-cost index: **ASSUMPTION 0.865 / 453.804 / 41,902.447**, excitement **ASSUMPTION 3.333 / 4.333 / 5.000**. The index assumes a served cohort and gross engineer-time savings; the demonstrated benefit floor is zero. This packet does not establish superiority over any current Challenge or #921 replacement. |
| What is the next gate? | Freeze a rights-cleared customer geometry, process history, applicable limits, material laws and independent witness route before any computation. Then an owner may approve the priced panel. |

The [panel manifest](feasibility-panel.json) contains counts, arithmetic and unresolved inputs. All estimates use low/base/high scenarios. A sourced point has a degenerate low/base/high range equal to that point; this supplies provenance, not a statistical confidence interval. No scientific threshold, population law or runtime configuration is adopted here.

**Bounded delivery contract.** Research and specification only; one PR to PR Head, no adoption or merge. All authored changes are additions in this directory. No solver, paid compute, protected material, hidden evaluation or existing Challenge file is touched. Authority first read at `26324def0cda2e7211f3639087c8be461ae46180` and unchanged at publication base `f227a55a88cfe736171bb64f602a81eb1777c9ba`; source D016: [#928](https://github.com/carbonphysicsai/Carbon/pull/928) at `f6e5eea975fc19bf84aa65dc6e3093624c000860`. The original input is a scored card and flagship analysis, not an existing ten-section dossier.

**Authority and reuse.** Reuse the [common packet](../../COMMON_DESIGN_PACKET_V1.md), [value/cost framework](../../value-cost/README.md), [cheap-baseline contract](../../cheap-baselines/README.md), reference credibility policy and constitutional P/Q/w separation. Current main retires the Development Hub; its frozen map is not edited or regenerated. No queue, runtime identity or readiness state changes.

**Verification and maturity.** Native read-only checks validate JSON arithmetic, ten packet sections, evidence links, path scope and text formatting. These are documentation diagnostics. Clean PR CI supplies canonical repository checks; neither kind establishes physical adequacy. Maturity is `RESEARCH_SPECIFICATION_DRAFT`; reference credibility is `NOT_DEMONSTRATED`. The final exact-head CI result and handoff are recorded in the PR conversation, without an evidence-only commit.
