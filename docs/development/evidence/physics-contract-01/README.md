# PHYSICS-CONTRACT-01 — public EV4 DEVELOPMENT diagnostics

PLT-01 / Carbon Validator review. No gate, tolerance, score change or scientific
qualification is adopted. Quantile, margin, permitted violation rate and
scientific validity remain HUMAN_INPUT. No live/validator integration exists.

`physics-screen-single.json` and `.md` retain the canonical public screen:
142 members, 65 descriptive good-value members, 13 registered bad members,
1,588 public reference cases. Good-value means decision loss at or below the
benign reconstructed panel median; it does not mean physically qualified.
Source hashes bind the public prediction-bundle manifest, decision results,
roles, reference file and registry v9. Historical role prefixes in the already
published scoring-reference file do not make this a new protected exam.

At the reference maximum with zero margin and zero permitted violation rate:

| Law | Good-value members rejected | Bad members caught |
| --- | --- | --- |
| B1 | 1/65 | 0/13 |
| B2 | 0/65 | 0/13 |
| B3 | 0/65 | 0/13 |
| B4 | 1/65 | 0/13 |
| B9 | 63/65 | 12/13 |

B2/B3's earlier 2/13 catches occur at a p99/zero-rate setting that also rejects
the reference. At reference-passing settings they catch none. The earlier
claim that they are clean gates is therefore unsupported by this screen.
B1/B4 can remove their false rejection by a
diagnostic margin but still catch none. The JSON/Markdown give every diagnostic
rate/margin row and before/after tau for registry-v9 A, ARP and ENV/ARP. Rates
and margins in these tables are unregistered diagnostic candidates.

## B9: distinguish the causes

**Model discrepancy:** independently computing `ambient - min(raw curve)`
against paired raw reference curves, without the checker or tolerance, gives
103,220 member-case comparisons. 63/65 good-value members exceed the reference
floor by more than 0.1 degC somewhere; 27 exceed it by more than 1 degC. The
largest deficit is 5.581574752342583 degC. The references' largest deficit is
8.526512829121202e-14 degC. These tails cannot be explained by floating-point
calibration. They are genuine model violations of this reference-relative
temperature-floor proposal, despite good decision value on this panel.

**Calibration artefact:** zero-margin p99 is below the largest reference
residual and rejects about 1.01% of reference cases for B9. Its reported 13/13
catch is therefore not a reference-passing gate. At the reference maximum the
catch is 12/13, with the same 63/65 good-member rejection. Every row reports
reference violation rate so this cannot be mistaken for a clean gate.

**Formulation limit:** B9 is a proposal for this specified DFN reference and
input box, not a universal claim that batteries cannot undergo entropic
cooling. The pinned reference's public OCV implementation explicitly documents
zero OKane2022 entropic coefficients; its measured curves support the floor
here. MMS acceptance verifies code discretisation, not real-cell validity or
the undeclared DFN envelope. Carbon Validator and the owner retain law and
scientific interpretation/adoption authority.

The exact per-member order-statistic screen also corrects the handoff's blanket
"no tolerance separates" statement: at nonzero diagnostic rate allowances,
there are zero-good-rejection rows that catch one bad member. Their numbers
and tau are recorded, with no recommendation or adoption implied. At zero
allowed rate, admitting every good member requires 5.58 degC and catches none.
The pooled residual p99 is only about 0.0000009 degC because the large errors
are rare: 571/103,220 paired readings exceed 0.1 degC. A pooled p99 therefore
hides substantial per-model tail failures.

## Pair calibration pending

The owner's public directory is
`/home/carbon/shared/evidence/physics-calibration-01/`. Data Collection's plan
is now present: 100 base points, 800 jobs and seven partner moves, with each
law's own step. The 0.01 smoothness moves cover all four input axes. Its complete
MANIFEST.json is expected around 20:30 UTC on 2026-10-12.

The loader verifies the image, repository overlay lock, plan, jobs and each
reference-record SHA. It supports the actual JSONL/plan format and refuses
wrong axes/steps, changed other inputs, missing records and reference failures.
Member inference can use the same public plan, avoiding a reference/model
sampling mismatch at the input-box headroom. No solver runs for member probes.
B5a/B5b/B6/B7/B8/B10 remain UNRESOLVED until verified calibration exists.

Example (on public copies inside the canonical checkout):

```bash
python -m scripts.dev.battery.physics_screen \
  --ev4 public-inputs/ev4 --run5 public-inputs/run5 \
  --attack public-inputs/attack --dev-results public-inputs/dev-results.json \
  --pairs 100 --calibration-panel public-inputs/calibration \
  --out public-inputs/screen-pairs
```

Only aggregate screen evidence is committed. Raw/public pair-reading caches
stay outside the repository and bind the contract/checker and public plan.
Fixture/canonical tests validate engineering boundaries only. The inherited
329-test baseline passed with science-jax/chain dependencies; the focused
checker/screen/validity tests passed. Exact final checks remain in the PR and
untracked queue report. Hub maintenance is retired; no Hub outputs are changed.
