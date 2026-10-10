# DELIVERABLE-GENERATOR-01 — development evidence automation

**Implemented:** a pure Python command reads registered committed public files, fills #956's automatable-now sections, keeps manual/later sections as gaps, retains adverse findings and renders a standards index. It writes Markdown, the filled JSON record, an unchanged copy of the framework schema, and a fact/source manifest. Every output is **DEVELOPMENT SAMPLE**, **UNESTABLISHED**, with a null qualification record. This tool has no evaluator, solver, customer acceptance or qualification authority.

The source manifest is [public-sources.json](public-sources.json). Initial supported Challenge: `battery-fastcharge-ageing-development-v1`. The reader/renderer is Challenge-neutral; additional Challenges need a reviewed public source map and extraction adapter. Unsupported IDs refuse before evidence access. No filesystem scan, official pool, raw reference cases, protected tuning record, private ledger, physical solver or network client is used.

## Run from committed Git

After framework #956 is available locally, run at the repository root:

```text
python -m scripts.dev.customer_deliverable battery-fastcharge-ageing-development-v1 --ref HEAD --standard nasa-std-7009b --output-dir Business/research/deliverable-generator-output/battery
```

`HEAD` resolves to an exact commit before reading. `git ls-tree`/`cat-file` read only registered regular blobs; uncommitted file changes cannot alter evidence. To examine a historical evidence snapshot with a later framework, add `--framework-ref <exact-commit>`. The output directory must be fresh; existing outputs and symlinked destinations are refused. The command copies the exact framework schema, rather than redefining or widening it.

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
