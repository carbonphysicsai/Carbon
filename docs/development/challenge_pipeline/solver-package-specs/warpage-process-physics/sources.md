# Source credibility and calibration applicability

Consulted 2026-10-10. **A** = primary measurement with public quantitative
data/model; **B** = primary implementation or research calibration with
limited/raw-data/transfer gaps; **C** = source-bound assumption or descriptive
lead, insufficient calibration. These grades are our research assessments,
**not earned reference credibility tiers**. Public access is not a blanket
licence to copy data/code. No parameter set is adopted.

| Source | What was located / research grade | Exact limitation |
| --- | --- | --- |
| [Phansalkar et al., MSE B 311 (2025) 117829, NIST-hosted paper](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957563), DOI 10.1016/j.mseb.2024.117829 | **A/B:** equations and Table 2 dual-reaction fit; independent heating rates check cure evolution | Specific underfill; no complete mechanical/shrinkage law. Readable manuscript retains publisher rights; redistribution/fit assets must be checked |
| [Tao et al. (2026), DOI 10.1002/pola.70283, NIST paper](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=962138) | **A:** two-step diffusion-controlled model, Table 1 and public data DOI | Cure/thermal degradation, not mechanical residual-state calibration or buyer formulation; do not interpret degradation testing as a service safety limit |
| [NIST data catalogue, mds2-4162 v1.0](https://www.nist.gov/data-publications/data-predicting-cure-evolution-and-thermal-endurance-highly-filled-epoxy-underfill) | **A:** published spreadsheet identities; `Figure 4 data.xlsx` SHA256 `a2b729e1a98ed5214fae0d96865be399e6fcda0acf779767e6f017df280ee208`; DOI 10.18434/mds2-4162 | Catalogue inspected, workbook not downloaded/validated here. Recover exact files/units/test conditions and reuse rights before fitting; no matched packet material identity |
| [Chowdhury, Auburn dissertation, §§5–6, Tables 5-4–5-7, 6-5](https://etd.auburn.edu/bitstream/handle/10415/7035/Promod%20Chowdhury_PhD%20Dissertation_R8.pdf?isAllowed=y&sequence=2) | **B:** measured relaxation, Prony/WLF tables and FE/experiment comparisons; repository-hosted author work | Specific cured underfill, not cure-dependent full-history data. PDF extraction has sign/exponent risks; figures/tables need independent checked transcription. No blind high-temperature extrapolation or transfer to NIST material |
| [Cheng, Tai and Liu (2021), DOI 10.3390/ma14174816](https://pmc.ncbi.nlm.nih.gov/articles/PMC8432544/) | **B:** process-aware vehicle, temperature-dependent properties, reported EMC chemical shrinkage and measured warpage | Manufacturer input and simplifying assumptions, not a complete open raw-data/deck set. EMC is not underfill; a stress-free cure-temperature assumption is not generic formation truth |
| [Random Voids / LED flip-chip solder study (2020), Table 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC6982262/) | **B:** public SAC305 Anand equation and nine-parameter set, attributed to earlier work | A published borrowed parameter set, not newly measured target-package calibration. Solid viscoplasticity only; no molten phase/joint formation proof |
| [Rojíček, Cienciala and Fusek (2025), DOI 10.1038/s41598-025-89360-y](https://www.nature.com/articles/s41598-025-89360-y) | **A/B:** identifiability analysis with tensile-data validation | Warns against inferring unique physical parameters from a good fit; not proof of microjoint or formation applicability |
| [CalculiX 2.23 author manual](https://www.dhondt.de/ccx_2.23.pdf), [author user-material source interface](https://github.com/Dhondtguido/CalculiX/blob/master/src/umat_user.f) | **B:** existing #947 manual/source obligations; compiled state/material interface is a route | Manual fetch timed out in this follow-up; preserve prior package source evidence, not a newly verified feature. Moving master is not the pinned archive; exact procedure/restart proof still missing |
| [MOOSE versioned GeneralizedMaxwellModel](https://mooseframework.inl.gov/releases/moose/2024-11-11/source/materials/GeneralizedMaxwellModel.html) | **B:** open constitutive update and manager/stress integration documentation | No complete cure/solder/formation law or selected package build; feature documentation is not material calibration |
| [Bleyer, FEniCS viscoelastic numerical tour](https://comet-fenics.readthedocs.io/en/latest/demo/viscoelasticity/linear_viscoelasticity.html) | **B:** open linear-viscoelastic code and analytic controls, stated CC BY-SA 4.0 | Illustrated 2D restricted model; verification anchor only, not our full-3D job or buyer laws |

**Not found:** a single openly reusable, source-complete law/data/deck suite
combining the packet's underfill cure/shrinkage/relaxation, solid/liquid joint
formation, substrate and full residual history. That absence prevents a
buyer-level Tier-2 claim today; it is not evidence that such a suite cannot
be produced. A downloadable table or a good scalar fit is not a qualified
material family. Full 3D and complete history remain mandatory.
