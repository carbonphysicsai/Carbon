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

## Verified public pair calibration

Data Collection supplied 800 OK public records: 100 bases and 700 physical
pairs, with each law's own step. The 0.01 smoothness moves cover all four
input axes. The published source contract remains historical; current
existing pair-law semantics are checked against its hash-bound bytes.

| Binding | SHA-256 |
| --- | --- |
| MANIFEST.json | 7d4529df11998aadb6c16f6d87fcccde64fe24009aed1089f6959c8f1e31785b |
| Simulator image | 2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940 |
| Repository overlay lock | 6267e033b30728b200d9e0c2aa6b55a9117cd67e03c6f89c9a17294d12e594ee |
| plan.json | 83d7ddce8a7e260fe2e0f19968b045abf15b522fa7d2df61b7fb0d3567ac6fdf |
| jobs.json | eebb8066d60af75fc3cf0f71e65885688da35da16c99313e7f846ccdf1c98308 |
| records.jsonl | 7670d5fbb524e6c31a0a04749b53dcb86b9c16cb791b67bfe3673681481b4474 |
| Source contract at ddb63227d | fd2d92811ba2fe2f1f5c9ce6d296a943694530a9df306c7ff1ce271edc246cb2 |

Canonical verification checks these bindings, the generator and solve-command
bytes, every record's exact JSONL-line SHA, every record's solver provenance,
complete job/record coverage, pair geometry/step and the committed MMS
acceptance link. A mismatch is refused. No model residual replaces a
reference residual. The acceptance is code discretisation verification;
reference adequacy, real-cell validity and gate adoption are separate.

B15 is screened first. B15/B16 reuse the same c1/c2 0.05-step pairs and inspect
0, 30, 60 and 90 seconds only. The 120-second switch is excluded. This gives
200 verified readings each, both with exactly zero reference residual.
B5a's reference maximum residual is 0.9835582801131864 degC; B6's is
0.0014502727396130816 V. B5b/B7/B8 have zero reference residual on these
pairs. B10 has 400 readings, with a maximum 143.36326175450458 in the
proposal's raw output-change/input-step convention (not a registered
physical tolerance). These measurements establish diagnostic calibration;
all gate states, quantiles, margins and allowed rates remain UNRESOLVED or
HUMAN_INPUT pending owner registration.

## Pinned B9 parameter reading

`physics-parameters.json` comes from the retained
`scripts/dev/battery/physics_parameters.py`, run inside the accepted simulator
image with the verified overlay, read-only source/root and no network. It
reads parameters without solving. Both OKane2022 electrode OCP entropic
coefficients are zero, giving a zero reversible-heat cooling bound. It also
records nominal capacity 5 Ah, maximum protocol current 10 A, heat-transfer
coefficient 10 W/m2/K, cooling area 0.00531 m2 and effective heat capacity
42.77529812749004 J/K at both ambient bounds, all read or derived from the
pinned parameter set and reference specification.

B9 stays diagnostic. Its accuracy term and proof for other signed heat
terms stay HUMAN_INPUT. Zero entropic coefficients do not establish a
universal real-cell temperature floor. B16 is a model-card metric only;
B1-B3 reference `carbon.battery.exam.GATES` as consistency evidence.
**Gates never substitute for verified decisions.**

Example (on public copies inside the canonical checkout):

```bash
python -m scripts.dev.battery.physics_screen \
  --ev4 public-inputs/ev4 --run5 public-inputs/run5 \
  --attack public-inputs/attack --dev-results public-inputs/dev-results.json \
  --pairs 100 --calibration-panel public-inputs/calibration \
  --pair-readings public-inputs/calibrated-readings.json \
  --out public-inputs/screen-pairs
```

Only aggregate screen evidence is committed. Raw/public pair-reading caches
stay outside the repository and bind the contract/checker/adapter, public
plan, manifest, member identities, builder source and requested count. The pre-RES-06 cache
is refused; missing or partial model readings stay UNRESOLVED.
The roster is frozen to the original public bundles, five controls and
decision file. Later score-proof screen additions (including always-abstain)
cannot silently widen this registry-v9 comparison.
Generate readings first with `--pair-cache-only` and the same public input
arguments, then run the screen with `--pair-readings`. The cache producer
reads one prediction bundle at a time to determine decided membership, and
releases compiled model programs after each member; it does not retain the
historical full-panel curves during rebuilds. Per-member public checkpoint
lines allow an interrupted run to resume under exactly matching identities.
An incomplete cache is refused by the screen, even if labelled complete.
The initial combined run exited under shared WSL memory exhaustion before
a complete cache existed; it is infrastructure failure, not a model verdict.
The handoff's `recipes.py` log(0) warning is traced to
`model_from_bytes` calling `features(np.zeros((1, 4)), ...)` to determine
feature width. It is a zero-input construction sentinel, not a calibration
probe. All public plan inputs are checked against the positive input box;
the pinned recipe modules are unchanged.
Fixture/canonical tests validate engineering boundaries only. The inherited
329-test baseline and resumed 38-test baseline passed with science-jax/chain
dependencies; the expanded focused checker/screen/validity suite has 64
passing tests. Exact final checks remain in the PR and
untracked queue report. Hub maintenance is retired; no Hub outputs are changed.
