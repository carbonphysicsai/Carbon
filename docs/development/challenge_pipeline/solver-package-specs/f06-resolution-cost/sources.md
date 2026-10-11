# f06 source and applicability ledger

Primary sources consulted 2026-10-09/10. No paper supplies our task's measured
C1 or a proof of all 45-row decision preservation. Summaries are deliberately
limited; equations/table values in the analysis are our labelled inferences.

| Source | Evidence used | Applicability and limit |
| --- | --- | --- |
| [Farjadpour et al., Optics Letters 31 (2006), DOI 10.1364/OL.31.002972](https://opg.optica.org/ol/abstract.cfm?uri=ol-31-20-2972) | Proper anisotropic interface averaging improves convergence; corners complicate the smooth-interface result | Method credibility, not f06 error/rank certification |
| [Meep subpixel method](https://meep.readthedocs.io/en/latest/Subpixel_Smoothing/) | Built-in geometry averaging, tensor storage and integration-accuracy controls | Freeze exact release/config; arbitrary epsilon blurring or material-function sampling is not equivalent |
| [Meep FAQ](https://meep.readthedocs.io/en/latest/FAQ/) | Quantity-specific convergence and real-field 96-byte baseline | Bare lower bound, not allocated RSS; no universal coarsest grid |
| [Wan, Gaylord and Bakir (2018), Applied Optics 57:5079, Appendix A](https://congshanwan.github.io/files/Wan_2018_GARC.pdf) | Meep 3D grid 19–35 pixels/µm; 20 pixels/µm sensitivity work | Different grating-assisted cylindrical interlayer cavity. Supports a candidate ladder, not our silicon fibre rank, etch or reflection error |
| [Lee et al. (2016), JOSK 20:291, DOI 10.3807/JOSK.2016.20.2.291, §II](https://oak.go.kr/central/journallist/journaldetail.do?article_seq=20707) | Silicon/70-nm-etch fibre-coupler study using Lumerical 20/10 nm directional spacing | Not a Meep isotropic 3D convergence comparison; no transfer of experimental agreement |
| [Meep release v1.32.0](https://github.com/NanoComp/meep/releases/tag/v1.32.0) | Existing package's version proposal | Source commit and recipe are not an accepted built image |
| [Hetzner general-purpose cloud](https://www.hetzner.com/cloud/general-purpose/) | CCX63 advertised 48 vCPU, 192 GB | Availability, tax-inclusive quote, throughput and usable RAM are not established; €1.37/h is the existing analysis assumption |

Repository sources: [packet](../../round1/f06-grating-coupler.md),
[numerical package](../f06-meep.md),
[question-law proposals](../../question-laws/proposals.json),
[cost assumptions](../../value-cost/analysis.md) and
[credibility policy](../../round1/reference-credibility.md). These control
the DEVELOPMENT meaning, not the external sources. Moving documentation URLs
explain the method; DC must bind the pinned release's actual defaults/features
and retain the source/build receipts before a run.
