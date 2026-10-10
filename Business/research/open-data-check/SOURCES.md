# Source register and inspection boundary

**Read 2026-10-10.** Primary sources below support the findings in [ASSESSMENT.md](ASSESSMENT.md). Public access, asset reuse rights and applicability are recorded separately in [inventory.json](inventory.json). Only the identified small public assets were downloaded; none were fitted, simulated or redistributed. Dataset identifiers and hashes are identity records, not physical ranges.

## External sources

| ID | Exact source / inspected part | Asset rights finding / use |
| --- | --- | --- |
| S01 | [GetDP license](https://github.com/getdp-project/getdp/blob/259f4c38ce89c3ad4775aecf515840bd3331b0aa/LICENSE.txt), [geometry](https://github.com/getdp-project/getdp/blob/259f4c38ce89c3ad4775aecf515840bd3331b0aa/tutorials/03-Magnetostatics/electromagnet.geo), [formulation](https://github.com/getdp-project/getdp/blob/259f4c38ce89c3ad4775aecf515840bd3331b0aa/tutorials/03-Magnetostatics/electromagnet.pro), [shared inputs](https://github.com/getdp-project/getdp/blob/259f4c38ce89c3ad4775aecf515840bd3331b0aa/tutorials/03-Magnetostatics/electromagnet_common.pro), [material library](https://github.com/getdp-project/getdp/blob/259f4c38ce89c3ad4775aecf515840bd3331b0aa/templates/Lib_Materials.pro); [official manual](https://getdp.info/doc/texinfo/getdp.html) | Pinned source: GPL-2.0-or-later; open numerical ingredients. Tutorial/library read, not executed. |
| S02 | [COMPUMAG TEAM problem 20 specification](https://www.compumag.org/wp/wp-content/uploads/2018/06/problem20.pdf), geometry, B–H and comparison quantities | Benchmark specification inspected; explicit asset reuse grant not located there. |
| S03 | [FEMM magnetics tutorial](https://www.femm.info/doku/doku.php?id=MagneticsTutorial), winding/circuit and geometry steps | Public air-core example; page-asset rights not confirmed. |
| S04 | [Zhao et al., DT4C temperature/frequency study](https://journals.sagepub.com/doi/10.3233/JAE-180022), primary abstract | Temperature-dependent material research, not a complete cleared input set. Raw assets not verified. |
| S05 | [TRC design dataset, DOI 10.18419/DARUS-3147](https://darus.uni-stuttgart.de/dataset.xhtml?persistentId=doi:10.18419/DARUS-3147), version 1.0; [revision-D PDF asset](https://darus.uni-stuttgart.de/file.xhtml?fileId=148576) | Dataset CC-BY-4.0. PDF downloaded, checksum verified and text inspected; CAD metadata reviewed, CAD not executed. |
| S06 | [KIT tightening-force/friction dataset, DOI 10.35097/yjdmucmycjkbm09g](https://publikationen.bibliothek.kit.edu/1000186977), dataset license and description | CC-BY-NC-ND-4.0 for the data; associated publication rights are separate. |
| S07 | [UNESP BERT dataset README](https://github.com/shm-unesp/DATASET_BOLTEDBEAM), experiment/data-use instructions | Non-commercial/share-alike terms stated; no permission request or restricted download made. |
| S08 | [CalculiX example collection README](https://github.com/calculix/examples/blob/a079253398c05f96b019e8c07ce076e370ddeb75/README.md), [bolt input](https://github.com/calculix/examples/blob/a079253398c05f96b019e8c07ce076e370ddeb75/ccx/test/bolt.inp), [Rubber input](https://github.com/calculix/examples/blob/a079253398c05f96b019e8c07ce076e370ddeb75/materials/Rubber.inp); [solver upstream](https://www.dhondt.de/) | Collection is mixed-origin. No root license found in its inspected tree; do not infer asset permission from the upstream GPL solver. |
| S09 | [Standardized elastomer characterization dataset](https://zenodo.org/records/14983287), [metadata API](https://zenodo.org/api/records/14983287); [associated paper](https://doi.org/10.1002/aisy.202500699), [repository paper copy](https://cris.vub.be/ws/portalfiles/portal/139795529/main.pdf) | Data CC-BY-4.0. Tension/compression archives and headers checked. Paper copy CC-BY-NC; separate asset. |
| S10 | [Biaxial elastomer dataset](https://zenodo.org/records/15187640), [metadata API](https://zenodo.org/api/records/15187640); [associated paper](https://doi.org/10.1016/j.jmps.2025.106339) | Dataset CC-BY-4.0; metadata/context read. Curves and large field archives not downloaded. |
| S11 | [Jing et al., supported O-ring case](https://ms.copernicus.org/articles/17/123/2026/ms-17-123-2026.html), methods, parameter prose and data availability | Paper CC-BY-4.0. Raw-data confidentiality is explicitly stated; not cleared by the paper license. |
| S12 | [Yenigun et al., Materials 15, 8810](https://www.mdpi.com/1996-1944/15/24/8810/pdf), parameter tables, friction method and availability | Paper CC-BY-4.0; publication parameters are not a released raw calibration archive. |
| S13 | [Bosch/Ansys, Cost and Function Optimization Applied to a Proportional Solenoid](https://ansys.synopsys.com/content/dam/resource-center/case-study/cost-function-optimization-applied-proportional-solenoid.pdf), Workflow section | Public case study, downloaded/text-read. Establishes an incumbent metamodel optimization route; not an equal-budget Carbon comparison or reusable calibration pack. |

[CC-BY-4.0 deed](https://creativecommons.org/licenses/by/4.0/) permits sharing/adaptation subject to its terms. [CC-BY-NC-ND-4.0 deed](https://creativecommons.org/licenses/by-nc-nd/4.0/) does not grant commercial use or sharing adapted material. A commercial-company internal use or public miner kit cannot be assumed cleared under NC/ND. Asset-specific rights, attribution, notice and other-rights review remain required.

## Carbon inputs, fixed historical revision

Read at main `65ef88660fe02018c26f54d14655fe7b66354aa8`. These are Carbon specifications/evidence, not independent material experiments.

- R01: [Solenoid first-panel job](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/magnetics-first-panels/solenoid-pole.md).
- R02: [Bolted-joint replacement card](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/value-cost/replacements/bolted-joint.md).
- R03: [Seal-gland replacement card](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/value-cost/replacements/seal-gland.md).
- R04: [Replacement scenarios/cost hypotheses](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/value-cost/replacements/scenarios.json); `cards.<candidate>.startup_eur_scenario`. Costs retained as ASSUMPTION, not recalculated measurements.
- R05: [Cheap-baseline contracts](https://github.com/carbonphysicsai/Carbon/blob/65ef88660fe02018c26f54d14655fe7b66354aa8/docs/development/challenge_pipeline/cheap-baselines/README.md); matched admissibility and lookup/response-map risk.
- R06: [Business Canon](../../Business_Canon.md), read at the same revision; recommendation/commercial authority.
- R07: [Deliverable framework](../deliverable-framework/FRAMEWORK.md), read at the same revision; reference-relative/physical evidence and adverse findings.
- R08: [Portfolio review #995](https://github.com/carbonphysicsai/Carbon/pull/995), historical recommendation only. Current owner direction is [OWNER_DIRECTION.md](OWNER_DIRECTION.md).

## Search limits

The bounded sweep covered open solver tutorials/benchmark decks and licenses, nonlinear solenoid B–H/temperature characterization, bolted-joint assembly/preload/friction datasets, and elastomer raw calibration plus supported O-ring papers. The register includes promising ingredients and rejected near-matches, so the gaps are reviewable. Vendor case studies were used to identify incumbent shortcuts, not to inherit unpublished inputs.

A missing license means permission was not established in the inspected assets; a missing matched input means applicability was not established. Neither means the asset or data cannot exist elsewhere. No private correspondence, gated data acquisition, fitting, solver run or hidden-material inspection was performed.
