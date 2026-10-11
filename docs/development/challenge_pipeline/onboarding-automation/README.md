# Offline onboarding automation

Owner workload ONBOARDING-AUTOMATION-01..04. These are deterministic local
drafting tools, not scientific approvals, runtime registrations or runners.
They do not read hidden banks, call solvers/providers, or spend money.

## Packet (01)

`python -m carbon.challenge_pipeline.onboarding --root . packet --brief brief.json`

The closed JSON input has `schema: carbon.onboarding.brief.v1`, `challenge`
(a planning token), and four strings: `buyer`, `decision`, `physics`, `solver`.
Optional `fields` supplies named ten-section fields, each with `value` and
`sources`. An unsourced value is a HUMAN_INPUT recommendation. A sourced value
must be an exact excerpt in a pinned public repository file: sources have
`path`, `sha256`, `excerpt`. Extraction proves bytes, not relevance/approval.
It cannot turn a role-play customer into observed demand. Remaining prompts
name the decision owner and behavior held closed.

`--format json` retains the structured draft. `--compare <real-packet-path>`
returns a unified text diff, source coverage, section coverage and missing
fields. This is explicitly not semantic equivalence. Stdout only; the tool
does not overwrite canonical packets. Input bound is 2 MB; source references
are explicit repository-relative public documentation, never host discovery.

Tests regenerate battery v3 and motor v2 from a genuinely short brief: ten
sections result, but all detailed laws/limits/pins remain missing. That is the
intended first draft, not a claim to recreate months of evidence from four
sentences. Human source extraction can progressively enrich it.

## Motor first, timing basis

Use the mock precision-joint integrator, selecting a geometry/holding/peak
command; magnetostatics; Gmsh/GetDP. Keep 6/12 N m and safety/ripple/cogging
requirements in the real packet, not inferred generator defaults. Battery
v3 chooses a five-band charge/cooling map using PyBaMM DFN/OKane2022.
The historical battery records contain dates, not drafting person-hours.
Human time saved against battery is therefore **UNKNOWN** until a matched
effort baseline is supplied. Machine drafting time is measured separately;
missing source verification and review work is not counted as saved.

Hub is retired. Existing packets and frozen results remain unchanged.

## Question law (02)

`python -m carbon.challenge_pipeline.onboarding --root . law --brief motor-brief.json --law-source docs/development/challenge_pipeline/question-laws/motor-round2.json --panel <explicit-development-export.json>`

The panel is optional: without it, diversity is UNKNOWN, not zero or a pass.
Use only non-hidden DEVELOPMENT exports. KEEP `producer_panels.adapt_export`
for family/identity/seal/reference validation and `diversity_report` for
aggregate expected winners, feasible/none-feasible mix, close-call/refinement
rates and exposure shortages. No raw cases, winners, curves or task seeds are
emitted. P is not inferred from Q. This does not adopt a panel law or qualify
the panel reference. Indexed battery tasks remain complete maps.

`--law-source` is an optional, pinned-by-content crosswalk from the existing
#919/#922/#927 proposal shapes. Their recommendations, caveats and missing
values are retained as proposals, never approvals. k, E, B, action support and
startup costs need owner/measurement decisions. B counts questions, not solves:
shared physical cases and refinements must be priced independently. CPU-hours
are not rented node-hours without measured throughput. TWO-band T2(a) requires
five distinct designs on **each** side; drafting does not measure it.

## Panel specification (03)

`python -m carbon.challenge_pipeline.onboarding --root . panel --brief motor-brief.json --seed <proposed-panel-seed.json> --reuse <non-hidden-reuse-index.json>`

From a brief alone it emits the needed boundary/value-check measures and
missing registration, not invented geometry. A numeric seed uses
`carbon.onboarding.panel-seed.v1`: challenge; design rows (`id`, `coordinates`);
stratum rows (`id`, `inputs`); rung rows (`id`, `settings`); pins (`solver`,
`environment`, `materials`, `observer`, `geometry_grammar`); optional per-rung
`cost_cpu_seconds` entries (`seconds`, `basis`). These are **proposed** inputs,
not geometry acceptance or registered scientific truth. A source-derived seed
must preserve all causal inputs/units and exact version pins. The Cartesian
manifest is capped at 10,000 and deduplicated by physical identity, not names.

Reuse rows have `identity`, `state` (COMPLETED/SCHEDULED), `receipt`. Both
completed and scheduled work are checked, but matches are recommendations for
DC to verify against retained evidence, not proof from a string. Missing pins
yield UNKNOWN identities, never reusable truth. Changed observers, materials,
conditions or rung settings stop matching. CPU is reported with and without
acceptance of reuse; billing is UNKNOWN without throughput/quote. Failure,
frontier, witness and retained-verification overheads are listed, not buried.

#934 and #965 provide the same discipline: explicit registration and full
identity/rung reuse, both-side TWO-band boundaries, no guaranteed 5+5 yield,
and no automatic run grant. Motor's full coordinate/curve re-export is still
missing, so the motor-first panel output is a registration gap report, not a
request to repeat its existing feasibility panel blindly.

## Read-only status (04)

`python -m carbon.challenge_pipeline.onboarding --root . status --challenge motor`

`--format json` gives the exact checked-file hashes, counts, missing fields,
stage definitions and owners. Reads #970's merged stage map and explicit
artifact bindings, not a hand-maintained duplicate status board. Default
bindings cover all eight and runtime aliases. For a new Challenge, supply
`--bindings <public-repository-file>` with the same path-only shape; without
bindings it reports unknown, not nonexistent work. It never scans hidden banks
or hosts, launches readiness tests, calls GitHub, or reads keys.

The current repository does not have machine-verifiable acceptance receipts
for every #970 exit. Therefore the command reports **observed artifact stages**
and **unverified exits**, not an invented single authoritative stage. It names
each remaining exit and its owner. Ten packet sections are documentation
coverage, not source adequacy; VERIFIED in #970 verifies a definition, not the
Challenge. Readiness history is checked against its retained report/digest,
item counts and recorded SHA; a historical snapshot never makes today's
Challenge green. No file's existence, no empty read and no green fixture can
earn the seven-part S10 TESTED exit.

### Motor application

01 produces the ten-section starting packet; 02 maps the existing 12-question
motor proposal without approving it; 03 identifies the registration/reuse
inputs still needed; 04 reads the real law's full-buyer HOLD, NOT_DEMONSTRATED
boundary status and AWAITING_REEXPORT. Its old 41-item readiness snapshot has
5 FAIL, 25 NOT_BUILT, 6 PASS and 5 REVIEW_REQUIRED **at its old SHA**, not current
acceptance. The next measurements belong to Data Collection; the pending
geometry/full signed torque-and-cogging export remains the comparator trigger.

Historical battery drafting effort is UNKNOWN. Measured milliseconds are
machine drafting/gap-report work only; source research, numerical evidence,
reserved decisions and review time remain required. No quantified human time
savings is claimed. This is onboarding automation implementation/testing, not
a tested motor Challenge or permission to rent its bank.

## Automatic milestone history (ONBOARDING-TIMELINE-01)

Status now includes `artifact_timeline`: first path commit and first main
integration, both pinned; missing/shallow/rename ambiguity and all unverified
stage exits remain explicit. `--main-ref` uses a local ref only. The same
timeline feeds #975's PROCESS field; a [battery reconstruction](../onboarding-timeline/README.md)
separates pre-existing reference code and successive packet/law versions.
Calendar milestones are not person-hours or stage duration. No speed target
or claimed labor savings is introduced.

## Remaining-brief applications

[Eight retained runs and reviewed next-action order](../onboarding-runs/README.md)
apply all four tools to the six remaining portfolio briefs and two conditional
replacement candidates. These preserve source excerpts and missing numeric
registrations; a generated draft or observed artefact does not pass a stage.
