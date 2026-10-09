# Source evidence, applicability and numeric provenance

Research date: 2026-10-09. Sources below are primary customer, standards, supplier, author-paper or solver-author material. A named organisation here is an evidence origin, not a Carbon customer. Source IDs are local citations, not Challenge identifiers.

Every numerical fact is either **SOURCED** in its exact context or **ASSUMPTION** in the panel manifest. For each sourced scalar below, low = base = high = the reported value. For a reported temperature-dependent interval, its endpoints are observations under the listed conditions, not independently sampled manufacturing bounds. No unsupported scientific value receives an assumed production limit.

## Buyer workflow and architecture

**S1 — Amkor, Nathan Whitchurch, “Thermal Simulation of DSMBGA & Coupled Thermal-Mechanical Simulation of Large Body HDFO,” Case study 2 and author biography.** [Customer-origin article](https://amkor.com/blog/thermal-simulation-of-dsmbga-coupled-thermal-mechanical-simulation-of-large-body-hdfo/).

The author is a senior staff engineer supporting packaging and mechanical simulation. The case maps an Icepak temperature field into Workbench Mechanical, evaluates deformation/stress and feeds deformed geometry into thermal analysis to study TIM variation. Its HDFO body is **SOURCED 63 × 63 mm**; the illustration contains an ASIC and **SOURCED six HBM modules**. These are one published architecture, not this Challenge's bounds. The article does not publish allowable stress, maximum permissible warpage, a buyer runtime or a process-history distribution.

**S2 — ASE, Package Design, e-Stress Simulator.** [Customer-origin service description](https://ase.aseglobal.com/package-design/).

Customers enter package dimensions and conditions; the service uses ANSYS to provide package stress and warpage. It independently corroborates a package-design decision workflow. It supplies no rights-cleared deck, applicable acceptance limits, demonstrated repetition count or stress/warpage latency. Its separate thermal service timing cannot be transferred to this mechanical job.

**S3 — TSMC, Integrated Turnkey modeling.** [Foundry modeling description](https://www.tsmc.com/english/dedicatedFoundry/services/apm_integrated_turnkey/integratedTurnkey_modeling).

Package modeling supports product requirements and chip-package interaction for advanced packaging. Material/process characterisation and thermal/mechanical test vehicles support model accuracy. This reinforces the need for matched materials and witnesses; it does not provide a generic AI-package acceptance contract.

## Conditional warpage and temperature evidence

**S4 — JEITA ED-7306, March 2007, §§3.1, 3.4–3.5, 5.1–5.2, 6 Table 1 and explanatory §3.2.** [Official standard PDF](https://home.jeita.or.jp/tsc/std-pdf/ED-7306_E.pdf); [official catalogue](https://www.jeita.or.jp/cgi-bin/standard/list.cgi?cateid=5&subcateid=40).

Table 1 was visually checked on printed page 7, PDF page 9. All entries below are **SOURCED**, in mm:

| Ball pitch | Ball-height condition | Maximum absolute package warpage |
| --- | --- | --- |
| 0.4 | 0.20 | 0.10 |
| 0.5 | 0.25 | 0.11 |
| 0.65 | 0.33 | 0.14 |
| 0.8 | 0.35 | 0.17 |
| 0.8 | 0.40 | 0.17 |
| 1.0 | 0.50 | 0.22 |
| 1.27 | 0.60 | 0.25 |

The limit concerns external BGA/FBGA assembly under the standard's assumptions. Stackable packages are expressly outside its scope. Warpage is peak-to-valley relative to a least-squares plane over the substrate terminal zone; sign follows diagonal profiles. The standard references **SOURCED 220°C** for Sn-3.0Ag-0.5Cu melting/solidification measurement; peak follows the package supplier's maximum. Its measurement profile need not reproduce production. The catalogue lists this edition; current customer applicability remains `HUMAN_INPUT`. Do not transfer these limits to internal microbumps or a stackable research vehicle.

**S5 — Henkel, LOCTITE ECCOBOND UF 9000AE TDS, November 2024, page 1 and page 2 disclaimer.** [Supplier TDS](https://datasheets.tdx.henkel.com/LOCTITE-ECCOBOND-UF-9000AE-en_GL.pdf).

| Quantity | SOURCED value and condition |
| --- | --- |
| Cured CTE | 23 ppm/°C below Tg; 85 ppm/°C above Tg |
| Tg | 111°C by DMA; 112°C by TMA |
| DMA storage modulus | 13,500 N/mm² at 25°C; 136 N/mm² at 250°C |
| Reflow capability | 260°C, Pb-free low-k applications |
| Cure guideline | 15 min ramp to 100°C, 90 min hold; 15 min ramp to 165°C, 2 h hold |

This is a plausible material anchor for large-die flip-chip/Cu-pillar underfill, not an approved material choice. The supplier explicitly describes reference data rather than product specifications and allows application-specific cure changes. Storage modulus is not automatically static elastic modulus; no full time-dependent law, cure-shrinkage law, allowable package stress or operating junction limit follows. The profile does not establish a stress-free reference temperature.

**S6 — Henkel, “Advanced Packaging Underfills: AI and HPC Enablers,” property comparison.** [Supplier technical white paper](https://dm.henkel-dam.com/is/content/henkel/Whitepaper_Semi_AdvancedPackaging_Underfills_AI_HPC_Enablers).

The comparison reports UF 9000AE toughness **SOURCED K1c = 3.0 MPa√m**. This is a fracture parameter, not a stress allowance. A stress criterion additionally needs flaw geometry, loading mode, temperature, interfaces, calibration and an approved safety policy. The TDS CTE above Tg differs from the white-paper comparison; this packet uses the TDS observation and does not blend sources into a new constitutive curve.

## Research geometry and strongest low-cost approaches

**S7 — Cheng, Tai and Liu (2021), “Theoretical and Experimental Investigation of Warpage Evolution of Flip Chip Package on Packaging during Fabrication,” §§2, 4 and Tables 5–6.** [Open author paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC8432544/), DOI 10.3390/ma14174816.

The FCPoP research vehicle has a **SOURCED 9.36 × 8.76 mm** chip, **70 µm** chip thickness, **100 µm** embedded-trace substrate and **90 µm** interposer. Its pillar geometry is **40 × 70 × 58 µm**. Its characterised coreless substrate's in-plane modulus changes from **27,279 MPa at 25°C** to **19,991 MPa at 260°C**, with corresponding CTE **12.6 to 22.4 ppm/°C**. These values belong together in that vehicle's temperature-dependent, orthotropic description; they are not allowed geometry/material ranges for Amkor's architecture. The paper uses trace homogenisation and process-aware FE; curing and inelastic history matter. This stackable vehicle cannot inherit S4's assembly limits.

**S8 — Tsai, Wang and Liu (2021), “Thermally-Induced Deformations and Warpages of Flip-Chip and 2.5D IC Packages Measured by Strain Gauges,” Materials 14(13), 3723.** [Publisher article](https://www.mdpi.com/1996-1944/14/13/3723), DOI 10.3390/ma14133723.

The published abstract describes beam-based prediction checked against measurements and FE. It supports a serious analytical baseline and calibration control. The full publisher retrieval was restricted during this research; no unverified material-table values are adopted.

**S9 — Lim, Ubando and Gonzaga (2024), “Optimizing warpage and die stress in semiconductor packaging through a systematic analysis of underfill properties using finite element method and response surface methodology,” Results in Engineering 24, 103556.** [Publisher abstract](https://www.sciencedirect.com/science/article/pii/S2590123024017997), DOI 10.1016/j.rineng.2024.103556.

The abstract describes three-dimensional FE with underfill-property/thickness variation and response-surface optimisation of warpage and die stress. This is direct evidence that a fitted FE response surface is a relevant incumbent. Full publisher retrieval was restricted; no reported optimum becomes an acceptance limit. This is an author study, not evidence of a buying customer or the accuracy of a response surface on D016.

Cached FE is included because repeated admissible cases can reuse the buyer's own outputs. Neither S1 nor S2 discloses its internal cache implementation. We do not claim that either company uses a particular caching algorithm.

## Open reference route and cost anchor

**S10 — CalculiX authors, release and capabilities.** [Release site](https://www.dhondt.de/), [capability overview](https://www.dhondt.de/ov_calcu.htm), [author licence statement](https://www.calculix.de/), [author repository](https://github.com/Dhondtguido/CalculiX).

**SOURCED release 2.23** is available as source; the authors state GPL version 2 or later. The capability overview includes 3D thermo-mechanical analyses, temperature-dependent materials, creep/plasticity, thermal analyses and structural outputs. Source availability supports a CPU container build route. It does not prove an exact frozen image, correct material implementation or adequacy for D016.

**S11 — CalculiX 2.23 manual, *NODE PRINT, *EL PRINT, creep and *STATIC/*VISCO.** [Official manual](https://www.dhondt.de/ccx_2.23.pdf).

The print contracts expose displacements/temperature and integration-point stress/strain with coordinates; output measures depend on the material formulation. FRD nodal stress is extrapolated/averaged, so it cannot substitute for the selected integration-point quantity. Creep is not active in a static step; the relevant time-dependent route must use a supported procedure. Native material capabilities do not establish calibrated cure viscoelasticity. Those constraints inform the proposed adapter; no implementation was run.

**S12 — Hetzner, price adjustment effective 15 June 2026, Cloud servers, Germany/Finland.** [Official price table](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/).

CCX63 new hourly price excluding IPv4 and VAT is **SOURCED €1.3678/hour**. The owner-requested rounded **€1.37/node-hour** is used for arithmetic. US and Singapore tables differ. This is a compute anchor only; tax, idle time, storage, independent witness access and authoring costs must be checked for the actual purchaser.

## Unresolved acceptance and population inputs

| Input | Required source/owner | Fail-closed behaviour |
| --- | --- | --- |
| Current external-assembly warpage criterion and internal-joint limits | Buyer packaging owner; signed package/supplier specification with applicable edition, pitch, standoff, board and zone | No feasible-design label |
| Die/low-k/interface stress, strain, fracture or fatigue allowance | Buyer reliability owner with region, stress measure, temperature/time/flaw basis and safety policy | No stress-feasibility or reliability claim |
| Reflow maximum, ramps, dwell, thermal gradients and service junction limit | Package supplier and buyer thermal/process owners | No temperature-feasibility or full-history grade |
| Approved materials, property curves, residual state and uncertainty | Material supplier/customer characterisation and science owner | No adequate full-history reference |
| Dimensions, tolerances, independent variants and process strata | Rights-cleared customer drawings and process records | No adopted P or deployment-frequency claim |
| Buyer-tool deck, field export rights and agreement tolerances | Customer simulation owner and science owner | No earned Tier 2 credibility |
| Rights to redistribute supplier/test data or derived training data | Rights owner | No public research-bank release |

All entries are `HUMAN_INPUT`. Literature geometry, properties and limits are evidence anchors; none closes these customer-specific inputs by itself.
