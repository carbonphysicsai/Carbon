# POWER-PLANNING-01: conditional design-question power tables

**DEVELOPMENT sensitivity analysis, not an adopted question law, settled-panel
power result, solver-cost receipt or spending grant.** The 3,840 aggregate
cells in [tables.v1.csv](tables.v1.csv) are reproduced by:

```sh
python3 scripts/dev/design_search_power_planning.py \
  docs/development/challenge_pipeline/power-planning/assumptions.v1.json \
  docs/development/challenge_pipeline/power-planning/tables.v1.csv
```

The [assumption manifest](assumptions.v1.json) has SHA256
`8e151812f7d5c9e2f1e0978069cefd2dcadfefc4585e4d6f799aa9333584022d`.
The output contains aggregate scenario statistics only: no producer case IDs,
winners, reference values, seeds or private bank material. Its deterministic
seed is a synthetic Monte Carlo replay seed, not an exam or bank seed.

## Basis and model

The question-law inputs are [battery v3 #919](../question-laws/battery-v3-round2.json)
(merged head `891a77bc29aacfb53a60451d19279e88459827df`),
[motor #922](../question-laws/motor-round2.json)
(`cfc306b9b9160a87d3f9d62dcf69ece995b1cbad`) and
[f02 #927](../question-laws/f02-round2.json)
(`c91ffbdfd9e5b033492f0d4f52b6166e59d23fef`). Battery's public
development export has 25 unresolved complete-map questions and five bands
with 80/42/147/147/77 nominal action rows. Motor's public export has 20
unresolved questions and 44 geometry/skew candidates. f02 has 24 physical
contexts, nine historical actions and a proposed 16-action seed menu, not a
settled question export. These are **shapes**, never empirical control effects.

For each hypothetical bank inventory, a sequential window samples k distinct
questions. Every draw consumes one unit of the **underlying solved bank's**
exposure E, even when its requirement/question ID differs. A bank's repeated
questions contribute one sign-test cluster across all windows. The simulation
samples which independent banks are encountered (500 deterministic replicates)
and, conditional on that count, evaluates the same one-sided exact sign test
as `design_search.power` at explicit working alpha=0.05. The assumed effect
size is the probability that one independent bank favours the good model over
the specified control. Target 0.8 is a working analysis input. The simulation
does not fit a relation between buyer-unit severity and this probability.
Both are declared assumptions. It models neither P/Q frequencies nor a
qualification decision; P, diagnostic Q and value weights w remain distinct.

Each control uses four assumed severities, in every controlled quantity's
buyer unit. **Edge optimist** shifts a just-infeasible margin across a limit;
**over-cautious** rejects a just-feasible margin; **localized sign error**
flips a margin within the declared boundary width; **path-aware** behaves
accurately on the search path but shifts off-path margins. The manifest lists
all quantities. For scale, battery s1–s4 charging-temperature widths are
0.2/0.5/1/2 °C and plating widths are 0.2/0.5/1/2 mV; motor holding-torque
widths are 0.1/0.2/0.4/0.8 N·m; f02 peak-temperature widths are
0.25/0.5/1/2 °C and energy widths 25/50/100/200 J. The assumed positive-bank
probabilities at s1–s4 are edge .58/.68/.78/.88, caution .54/.63/.74/.84,
sign .52/.60/.70/.80 and path .56/.66/.77/.87. These are **ASSUMPTIONS**,
not calibrated control response rates or measured effects.

## Conditional curves at proposed k

The full CSV varies k, E, independent solved-bank count, windows and all four
severities. This excerpt uses five sequential windows and a deliberately
optimistic inventory of independent solved banks; it shows s1/s2/s3/s4
detection probabilities. Monte Carlo standard error for these rows is at most
0.003, but **structural and effect-size uncertainty is much larger**.

| Challenge; B questions; k; E; independent banks (all planning assumptions unless noted) | Control | s1 | s2 | s3 | s4 |
| --- | --- | ---: | ---: | ---: | ---: |
| Battery v3; 25 observed unresolved questions; 8; 5; 24 | Edge | .128 | .419 | .798 | .984 |
| same | Caution | .067 | .249 | .655 | .942 |
| same | Sign | .047 | .170 | .497 | .857 |
| same | Path | .094 | .346 | .765 | .977 |
| Motor; proposed B=120; 12; owner class E=10; 32 | Edge | .163 | .540 | .904 | .998 |
| same | Caution | .080 | .326 | .788 | .985 |
| same | Sign | .054 | .220 | .629 | .942 |
| same | Path | .117 | .451 | .880 | .996 |
| f02; proposed B=160; 8; proposed E=5; 32 | Edge | .141 | .467 | .847 | .992 |
| same | Caution | .072 | .279 | .713 | .965 |
| same | Sign | .050 | .189 | .550 | .898 |
| same | Path | .103 | .387 | .817 | .988 |

At the moderate s3 assumptions, **none** of these k/E inventories separates
all four controls at 0.8. Raising battery k from 8 to 12 with the same B=25,
E=5 and 24 independent banks moves sign-error detection only from .497 to
.570; motor k=12→16 at 32 banks moves it .629→.678; f02 k=8→12 at 32 banks
moves it .550→.634. More questions from correlated truth cannot substitute
for independent banks. At one shared solved bank, the exact sign test never
reaches alpha .05 even at E=10; when k exceeds the shared bank's remaining E,
the window is also exposure-infeasible. A new requirement ID does not reset E.

## k, E, B and startup recommendation

**Retain k=8 battery, k=12 motor and k=8 f02 as prospective planning rows,
not powered selections.** For a strong-control (s4) feasibility study, compare
battery E=5 with 24 independent panels, motor's existing development class
E=10 with 32, and f02's proposed E=5 with 32 over five windows. Those rows
cross 0.8 only under the stated effect assumptions. Battery E=5 is a new
planning hypothesis, **HUMAN_INPUT**, not copied from an export into policy.
There is **no evidence-supported k/E adoption recommendation** until settled
control outcomes and independent bank identities replace these assumptions.

| Challenge | Question inventory B | Illustrative independent physical panels | Startup € for those panels | Cost status |
| --- | ---: | ---: | ---: | --- |
| Battery v3 | 25 current unresolved questions; adopted B absent | 24 | UNMEASURED | Complete five-band, 30-cycle programme bill and refinement manifest absent. Historical battery timings describe different jobs. |
| Motor | 120 prospective complete questions (10×k) | 32 | €13,888.64–€38,088.32 bare-node **scenario** | 32 × #922's €434.02 conservative holding to €1,190.26 full-role/refined 44-action panel. These are different scope scenarios, not a confidence interval or quote. |
| f02 | 160 prospective complete questions (20×k) | 32 | €561.28–€841.60 bare-node **scenario** | 32 × #927's €17.54–€26.30 proposed 24×16 transient panel at serial 2–3 CPU-min and €1.37/node-h. Excludes overhead, refinement and witnesses. |

B is a question-case count. The physical-panel count is a separate assumption,
and neither B nor k proves independent sign-test evidence. The cost products
assume each independent cluster requires one full physical panel; sharing
reduces cost and also reduces independence. Measured CCX63 throughput,
billable hours, tax, failures and all Challenge-specific setup remain absent.
These scenarios grant no rental or spend and do not establish the €100 startup
target. Test Lead owns the power target and severity choice; the owner owns
question-law, exposure and bank-cost adoption. Data Collection must supply
digest-bound settled verdicts, independent bank lineage and measured complete
panel costs before a real power and cost recommendation can be made.
