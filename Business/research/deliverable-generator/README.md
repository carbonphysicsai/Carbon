# DELIVERABLE-GENERATOR-01 — development evidence automation

**Implemented:** a pure Python command reads registered committed public files, fills #956's automatable-now sections, keeps manual/later sections as gaps, retains adverse findings and renders a standards index. It writes Markdown, the filled JSON record, an unchanged copy of the framework schema, and a fact/source manifest. Every output is **DEVELOPMENT SAMPLE**, **UNESTABLISHED**, with a null qualification record. This tool has no evaluator, solver, customer acceptance or qualification authority.

The source manifest is [public-sources.json](public-sources.json). Supported source selections: `battery-fastcharge-ageing-development-v1`, `motor`, `cooling-cell`, and `f02`. These are dossier aliases, not runtime Challenge registration. The reader/renderer is Challenge-neutral; additional Challenges need a reviewed public source map and extraction adapter. Unsupported IDs refuse before evidence access. No filesystem scan, official pool, raw reference cases, protected tuning record, private ledger, physical solver or network client is used. See the [new-adapter source/gap guide](../../../docs/development/challenge_pipeline/deliverable-adapters/README.md) for pinned samples and their limitations.

## Run from committed Git

After framework #956 is available locally, run at the repository root:

```text
python -m scripts.dev.customer_deliverable battery-fastcharge-ageing-development-v1 --ref HEAD --standard nasa-std-7009b --output-dir Business/research/deliverable-generator-output/battery
```

`HEAD` resolves to an exact commit before reading. `git ls-tree`/`cat-file` read only registered regular blobs, with Git replacement objects disabled; uncommitted file changes and replacement refs cannot alter the evidence attributed to that commit. To examine a historical evidence snapshot with a later framework, add `--framework-ref <exact-commit>`. The output directory must be fresh; existing outputs and symlinked destinations are refused. The command copies the exact framework schema, rather than redefining or widening it.

Choose `--standard asme-vv10` for the second profile. **This is a topic rendering with HUMAN_INPUT clause IDs**, following #956's explicit licensed-review gap. NASA rendering indexes verified requirement anchors, separately lists the five capability and six results factors from Appendix E, and adds an Appendix A record-location subset. Formal capability/results levels, applicability and sufficiency remain HUMAN_INPUT. The source manifest stores that profile index alongside the common fact store. Neither profile is a standards compliance certificate.

## Offline committed-public export

On this host the shared checkout predates the evidence and its Git metadata is read-only. The committed battery example was therefore generated from a public export obtained with the authorized GitHub file connector, not from modified workspace reports. [The generation manifest](examples/battery-nasa/generation-manifest.json) records each original revision, Git blob, public-file SHA-256, fact locator and source URL. All exported bytes matched the connector's reported blob identity before generation.

```text
python -m scripts.dev.customer_deliverable battery-fastcharge-ageing-development-v1 --public-export <public-export-directory> --standard nasa-std-7009b --output-dir <fresh-directory>
```

An export contains `receipt.json` and `<source-id>.txt` payloads for the registered sources. Receipt shape: `schema: PUBLIC_SOURCE_EXPORT_V1`, fixed repository, exact `evidence_revision` and `framework_revision`, and `files[id]` with registered `path`, `revision`, `git_blob`, `sha256`. Payload names are fixed by registered IDs, not receipt-controlled paths. Revisions cannot be overridden on this route. Missing optional evidence creates a gap; altered bytes, role/revision mismatch or absent framework files refuse rendering.

**Trust limit:** receipt/blob equality authenticates exported bytes relative to the supplied receipt; membership in the named commit is the trusted exporter's assertion. The output states that limit. For direct Git, membership is checked against committed objects. Neither mode demonstrates physical validity or independence of scientific evidence. Exporting protected data is outside this interface; the manifest lists only known public documentation/aggregate records. Local scratch exports are excluded from the PR.

## What gets filled

- **D08:** source/runtime-evidence provenance as recorded public-file identities, digests and source references. Actual product artifact, deployment parity and qualification remain gaps.
- **D11:** immutable source ledger, recorded public review states, scoped outcome/rebuild facts and audit warnings. Buyer rights, independence assessment and acceptance remain gaps.
- **D01–D07, D09–D10:** preserve the fixed template section with **GAP** and HUMAN_INPUT. The tool does not select intended use, P/Q/w, physical limits, reference credibility, uncertainty or fallback thresholds.
- **Adverse annex:** extract public EV4 false-feasible counts/H1 outcome and in-band/out-of-band violations, EV5 adversarial verdict/counterexamples/findings/sign-error rate, and the Q1 audit's historical missing v3 measures. Extraction is bounded to numeric/enum anchors, never wholesale publication of raw records. Missing or ambiguous anchors create visible gaps. Historical records cannot prove that a later score rule fixes their panel.

The source policy also reads the common packet, worked battery design-packet example, readiness gate, Attacker specification, decision contract and Q1 mapping. Those are indexed as **specifications**, not treated as passed measurements. Broad evidence completeness and private confirmation remain unassessed. The initial regex adapters intentionally fail closed when source formats change; the gap needs a prospective adapter update, not a guessed interpretation.

## Evidence and tests

[Battery NASA example](examples/battery-nasa/sample.md): evidence snapshot `915225242146be67e6de098d4a08324cc63dc684`; framework `b0244360dbe49d534b0346779e1cebe5b21de085`. The real public-source run also tested ASME rendering in scratch. It preserved the recorded failures and missing v3 evidence, copied the framework schema byte-for-byte and left all manual sections GAP. The structured record and fact manifest carry citations; no new scientific number was chosen. Count triplets reproduce source points, not confidence bounds.

The focused suite is synthetic and executes no physics:

```text
./scripts/dev/canonical.sh python -m unittest discover -s tests/cpu -p test_customer_deliverable_generator.py -v
```

Tests cover changed-source extraction, adverse/missing/ambiguous evidence, manual gaps, source version/role and byte checks, unsupported inputs before reads, public-field projection, standards gaps, schema copy, determinism, committed-Git versus workspace reads, and existing-output refusal. Native tests use an owned workspace temporary parent because the Windows sandbox's default temporary directory denies cleanup. That environment failure is not recorded as a passing test; the subsequent workspace-temp run passed. The attempted canonical wrapper refused at its repository-root guard on this Windows host. A separate check found Docker's daemon unavailable. Native output is diagnostic, not canonical acceptance; GitHub CI runs the focused module as part of the repository CPU suite.

## Limits and next work

This is a development renderer, not the later neutral EV/receipt/Attacker join promised by the framework. It does not authenticate an offline exporter, certify full JSON Schema semantics, quantify physical uncertainty, review professional competence, determine standard applicability, inspect private confirmation, or create a Product Battery/Qualification Record. The record is constructed in the closed framework shape; full independent schema validation remains additional review work.

Next adapters should consume registered safe machine outputs with stable measurement/requirement IDs and evidence-role/mask semantics. Add approved buyer projections and source completeness controls before external use. Extend ASME clause mappings only after authorized licensed review. [Working contract](WORKING_CONTRACT.md) records the authority, plan, validation and maturity ceiling. Adoption and qualification remain the owner's decisions; delivery stops at PR Head.

## PRD-01 — Carbon Model Package development sections

The same command now renders five additional views: **physics contract and
law-check report**, **model card**, **trust map**, **solver code verification
(MMS)**, and **decision evidence**. They index the same D01–D11 record; the
unchanged PROPOSAL_V1 schema and the four output filenames remain intact.
Detailed normalized fields, their sources/locators, denominators, outcomes and
reasons live in `generation-manifest.json` under `package_evidence`. The source
policy's content digest is also recorded. A manual D-section can have PARTIAL
factual coverage while its acceptance/judgment stays HUMAN_INPUT.

Current main public sources provide battery and motor particle/field MMS
machine records, the separate owner acceptance decision, f02's original MMS
and separate time-only diagnostic, and f02/motor/cooling draft contract
definitions. The earlier machine verdict is copied unchanged; the acceptance
link is a distinct observation. The f02 t_end=0.5 time orders remain beside the
t_end=0.375 rerun. A verification plan is not a measured MMS result, and EV5
rebuild agreement never fills this section. None establishes physical validity,
full application/reference adequacy or product qualification.

PLT-01 law-check outputs, a complete product Model Card, measured maps and
current job-shaped VERIFY-R/equal-budget output are not present in the registered
public source snapshot used by the v2 examples. Those fields are GAP with their
individual reasons. Draft output availability is definition metadata, not a
measurement. No sample calls a solver, imports a prediction bank, searches for
private files or fills the gaps with synthetic values. The examples were
generated battery first, then f02, motor and cooling-cell; prior examples retain
their original source revisions and bytes.

### Optional reviewed public export transport

`package_sources` explicitly registers the optional
`docs/development/product-evidence/<family>/package-projection.json` blob for
each supported family. This is a **generator-owned transport**, not a new
PLT-01, Model Card or scientific evaluator API. Upstream producers must publish
a reviewed public aggregate projection before it can be consumed. No arbitrary
filesystem path, scan or hidden-material export is accepted.

The closed header is `schema: carbon.customer-deliverable.public-package-projection.v1`,
`mode: DEVELOPMENT_SAMPLE`, exact dossier `challenge`, `disclosure` with
`kind: PUBLIC|RELEASED` and an HTTPS evidence location, and `identity` with
SHA-256 `model_artifact_hash`, `reference_image_digest`, `physics_contract_digest`.
Its five payload keys are `law_checks`, `model_card`, `trust_map`, `verify_r`,
`equal_budget`, each nullable. The image must match an available image-bound
MMS result. A law join additionally checks the exact draft contract bytes and
the per-law calibration image. Identity/disclosure assertions are not independent
attestation or evidence that the exam/reference is scientifically qualified.

- `law_checks`: `producer: PLT-01`, a `measurement_version` token and `laws`.
  Each result has a draft-bound `id`, positive `sample_count`, `violation_rate`,
  nullable `residual_median`, `unit`, typed `outcome`, Boolean `adopted`, and
  `calibration_image_digest`. A draft can supply diagnostics only; a projection's
  adoption flag cannot make it a registered gate. Missing law/residual fields
  remain GAP; uncalibrated/incompatible results are refused.
- `model_card`: optional fixed metrics `accuracy_overall`, `accuracy_near_limits`,
  `robustness`, `extrapolation`, `uncertainty_calibration`, `speedup_equal_accuracy`,
  `inference_latency`, `training_cost`. Each supplied metric has `value`, `unit`,
  `sample_count`, `statistic`, `measurement_version`, `outcome`. Null/unmeasured
  values remain GAP; FAILED_REFERENCE/FAILED_INFRA retain their classification.
  All floors/acceptance are null / HUMAN_INPUT, independent of the source verdict.
- `trust_map`: the native `carbon.trust-map.v2` DEVELOPMENT aggregate from
  `carbon.trust_map`, with PUBLIC/RELEASED provenance and matching accepted
  verification/image fields. Copy error/disagreement median/p90, units and cell
  counts; NO_DATA is GAP. Current schema has no law or interval layers. A map
  never substitutes for solver verification of Assistant-selected picks.
- `verify_r`: the standalone native `carbon.design-search.verify-aware-result.v1`
  aggregate, never per-question rows. Bounded service regret remains dimensionless;
  an incomplete offered set has no regret default. The native aggregate omits
  k, budget and inference timings; these remain explicit gaps until a matched
  public rule/cost receipt is added prospectively.
- `equal_budget`: native `carbon.design-search.equal-budget-report.v1` aggregates
  only, with the matching family and MEASURED cost basis. Copy the three arms'
  conditional verified value/regret, feasible-pick fraction, registered budget,
  complete paired value delta and valid cluster-bootstrap interval. Unresolved
  panels, assumed costs or incomplete pairs cannot manufacture a measurement.
  Replay is not a measured live Assistant search; selected-pick false feasibility
  still requires PB-INV/ADV evidence.

These shapes are exercised with **synthetic test-only fixtures**; there is no
claim of real positive card/map/decision measurements from their test pass.
All five adapters refuse malformed/nonfinite/identity-mismatched fields with
non-echoing GAP reasons and retain independently readable adverse records.
No numerical threshold, physical validation, qualification, standards compliance,
security audit, legal/export clearance, LIVE or commercial acceptance is issued.

[PRD-01 samples](examples/v2/README.md) and the [working contract](WORKING_CONTRACT.md)
record source scope and remaining proof. Reviewer route: Carbon Validator and
Data Collection for reference/data joins. The Product queue stops at the green
exact-head PR Head handoff; Guard and Assistant implementation are later items.

## PRD-04 — credibility matrix and risk-informed planning

The existing four outputs now include a credibility annex in Markdown and
`generation-manifest.json` under `credibility_evidence`, schema
`carbon.customer-deliverable.credibility-evidence.v1`. The common PROPOSAL_V1
record and schema remain unchanged. Earlier generated examples retain their
original bytes and source revisions; fresh examples live under `examples/v3/`.

The matrix uses stable `DEVREQ.*` development evidence-obligation IDs. These are
not customer acceptance criteria or normative standard requirement IDs. Each
normalized package observation retains its basis, coverage, value, units,
denominator, measurement version when supplied, exact source revision/blob,
locator, source outcome and adverse-finding links. A failed measured observation
can be EVIDENCED. Source PASS never issues requirement acceptance: every
requirement outcome is NOT_ASSESSED, with null/HUMAN_INPUT criterion and authority.
Historical observations have no current product-artifact binding; MMS and draft
definitions stay source-scoped. Only a matching public projection declares
candidate/contract/reference identities, and its assertions are not attestation.

The plan links all eleven D-section evidence goals to available facts, gaps,
next proof and responsible owner roles. Model influence, decision consequence,
required credibility, risk-combination rule and accepted applicability remain
HUMAN_INPUT unless an explicit public declaration supplies the copyable fields.
The planning relationship is model influence × decision consequence. The tool
does not invent a numeric scale, multiply ordinal labels or select risk/credibility
thresholds. Even a declared credibility goal cannot issue a qualification.

Two additional CLI profiles reuse the same frozen framework crosswalk:

- `--standard asme-vv40`: V&V 40-2018 topic mapping; clause IDs and licensed review
  remain HUMAN_INPUT. The medical-device standard's risk-informed idea is used
  as a planning crosswalk; applicability to another industry is not presumed.
- `--standard dod-vva`: MIL-STD-3022 Change 1 template anchors and DoDI 5000.61
  (2024) contents-only anchors. Six questions show indexed evidence and customer
  actions for use, criteria, referent, adverse results, configuration and acceptance.
  Program tailoring, independent assessment, rights, physical evidence and the
  designated authority's accreditation decision remain HUMAN_INPUT.

NASA keeps its separate capability and results factors and verified anchor
subset. Every profile explicitly sets `clause_complete: false`; these outputs
are crosswalks, never standards-compliance or accreditation determinations.
The manifest's `mapping_status` distinguishes verified NASA anchor subsets,
ASME topic-only mappings and MIL template/DoDI contents-only anchors; its
`acceptance_authority` stays HUMAN_INPUT.
The ASME scope is described by the [publisher's overview](https://www.asme.org/topics-resources/content/bioengineering-blog-an-emerging-regulatory-framework-for-medical-device-simulation).
NASA anchors come from [7009B](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf)
and the committed framework. Full current DoDI retrieval still returned HTTP
403 during this ticket; contents anchors cannot establish substantive compliance.

### Optional public risk/context declaration

P8 registers only `docs/development/product-evidence/<family>/credibility-context.json`
for the four existing families. There is no arbitrary input path or file scan.
The closed record requires:

```text
schema: carbon.customer-deliverable.credibility-context.v1
mode: DEVELOPMENT_SAMPLE
challenge: exact dossier alias
disclosure: {kind: PUBLIC|RELEASED, evidence: HTTPS location}
identity: {model_artifact_hash, reference_image_digest, physics_contract_digest}
context_of_use: {id: registered token, version: registered token}
model_influence: {value: token or null, authority_ref: SHA-256 or null}
decision_consequence: {value: token or null, authority_ref: SHA-256 or null}
required_credibility: {value: token or null, authority_ref: SHA-256 or null}
```

Identities must equal the accepted package projection's declared identities,
and the contract digest must match the registered committed draft's bytes.
Each supplied value requires its recorded authority reference; unknowns use
null/null. Values are copied declarations, not authenticated owner approval or
computed risk ratings. Missing, malformed, private, wrong-family or mismatched
records produce a non-echoing P8 gap while other evidence and failures survive.
No real risk declaration is invented for the samples; positive cases exist only
as explicitly synthetic tests.

PRD-01b's wording is applied prospectively: f02 decision rows say CONDITIONAL,
t_end 0.375, in MMS test-design scope, beside both original and supplemental
observations. Norms/absolute errors say manufactured-solution error; convergence
orders keep observed-order units. Code verification does not establish physical
validity, full reference adequacy or the real battery comparison's acceptance.

## 2026-10-13 evidence-honesty presentation repair

See the [five-surface audit](../customer-deliverable/EVIDENCE_HONESTY_2026-10-13.md)
and OWNER-PLATING-REFERENCE-01. New battery renderings identify the
`battery-plating-ref-v2` transition and the unresolved near-onset label hold
before required mesh-160 evidence/current-use acceptance. They make no current
near-limit accuracy, calibration, feasible-pick or speed claim from old rows.
Refinement, failure/retry and fallback costs are required for a current workflow
comparison; historical wall_s is not complete v2 cost or CPU core-seconds.

MMS acceptance conditions are explicitly labelled registered test-design
conditions, not application acceptance. Declared use/domain/observable coverage
and risk/authority references remain host assertions. Stretch-set rows describe
recorded error in the declared domain, without asserting physical validity.
The crosswalk retains NOT_ASSESSED requirement acceptance and historical outcomes.

No reference adapter, version default, schema/data join, gate or capability is
added. Existing generated examples and EV4/EV5/score-proof files/hashes remain
unchanged. Corrections are prospective wording/additive notes, never re-scoring.
