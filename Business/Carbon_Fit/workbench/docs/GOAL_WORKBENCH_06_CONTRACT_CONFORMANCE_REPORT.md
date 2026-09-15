# GOAL-WORKBENCH-06 contract/conformance report

## Outcome

Status: `CONTRACT_READY_SOURCE_DECISION_PENDING`.

Contract/schema/test preparation is complete for the exact public Burgers/Dynamics profile. Source-owner semantic, issuer/scope verification, and fixture acceptance are pending. The production consumer/dispatcher is not implemented. The v0.6 application, workspace schemas, standalone HTML, active Wave selection, source runtime, C-05 bytes, CPES, scientific/rights state, and launch boundaries are unchanged.

Baseline inspected: GOAL-WORKBENCH-05A merge `e5aafc522ca40db12f1897bcc0beacdedb44d823`, accepted head `36cb25b6d6d010aaf4378eaece99cebb63ca630a`, acceptance run `34918769638`. Current authority records named the separate C-EA1-D4 private-alpha workstream at preparation; this delivery does not edit it.

## Implemented

- Four closed versioned schemas for request, response, profile, and detached receipt.
- Exact sealed design snapshot and canonical/raw digest binding.
- Source-derived C-AUTH1 authoring output generated through the existing fixed bridge on public synthetic inputs.
- Exact retained C-05 fixture referenced in place and replayed through its accepted reader; no duplicate or numerical rerun.
- Field-level provenance, trust table, cumulative-review interpretation, all-false authority ceiling, 18 compact conformance vectors, and digest manifest.
- One detached Node validator that writes only to a specified new directory after complete validation.
- Non-authoritative Markdown preview and owner decision packet.
- Regression proof that the current v0.6 generic importer rejects the candidate format without mutation.

The source-derived example establishes technical Dynamics authoring and one historical fixed-case C-05 relationship. It leaves scientific applicability, intended-use suitability, qualified limits/floors, uncertainty, population adequacy, rights, protected use, scoring, and launch unresolved.

## Reproduction and execution boundaries

The retained authoring artifact was generated with:

```sh
env PYTHONPATH=. python3 Business/Carbon_Fit/workbench/tools/authoring_bridge.py \
  Business/Carbon_Fit/workbench/source_assessment/v1/source/authoring_request.json \
  Business/Carbon_Fit/workbench/source_assessment/v1/source/authoring_bridge_output
```

An initial invocation without repository `PYTHONPATH` failed with `ModuleNotFoundError: carbon`; the declared supported repository route above succeeded and is retained as command provenance. No solver, reference calculation, measurement campaign, worker, training, network, or account action ran.

The contract and detached output reproduce with the commands in `GOAL_WORKBENCH_06_SOURCE_ASSESSMENT_CONTRACT.md`. `source_assessment/v1/example_output/validation_receipt.json` records zero solver/training/network/account actions. `source_assessment/v1/manifest.json` is the authoritative digest/byte inventory; `example_output/output_manifest.json` covers generated receipt and preview bytes.

## Requirement-to-test summary

| Requirement | Evidence |
|---|---|
| Exact request/content/source association | `test_source_assessment.cjs`: positive path, wrong identity/snapshot/case/query/source tests |
| Capability is not applicability/qualification | technical/unqualified and authority-ceiling tests |
| Consumer-derived origin | fixture-origin receipt and forged provenance tests |
| Partial/stale/conflicting/superseding behavior | partial reason, stale association, replay/conflict/reconciliation tests |
| Fixed-case C-05 cannot become fresh/campaign evidence | strict reader replay and execution-laundering test |
| Unsupported physics/rights stay explicit | unsupported/blocker preview tests |
| Parser, display, and atomic output boundary | duplicate/key/number/depth, escaping, no-output-on-failure tests |
| Production app stays closed | direct v0.6 `importResponse` rejection with before/after equality |
| GOAL-WORKBENCH-05A integrity remains | inherited `test_state_integrity.cjs` F1–F7 suite |

Local results on macOS arm64:

- `node --test` across engine, workflow, routing, state-integrity, C-05, and source-assessment suites: 183 passed, 0 failed, 0 skipped. The source-assessment file contributes 24 focused tests.
- Pinned pytest 9.1.1 over the bridge and C-AUTH1 source contract: 24 passed, 0 failed, 0 skipped.
- Focused Decision Console validation after routing the owner packet: 111 decisions, 111 unique IDs, passed.
- Standalone v0.6 HTML SHA-256 remained `19a8cc52f2c8dd55d4549a4cb581c39e94aa3293803f7ec0193dc3858daf3404` and contains no candidate schema string.
- Browser automation was not rerun because no application source or generated HTML changed. No new browser/runtime coverage is claimed.

Failure history remains visible: the first focused Python test attempt used a primary runtime without pytest; a second `uv run --frozen` attempt correctly rejected this arm64 macOS host against the repository's Linux x86_64 lock environment; an offline pinned `uvx` attempt initially lacked `PYTHONPATH`. The corrected pinned `uvx` command with `PYTHONPATH=.` produced the 24-pass result. Early source-assessment test development caught four harness expectation/import-order issues and then one message-pattern mismatch; all were repaired before the 183-pass combined run. None was a source-runtime or production-application defect.

Test counts are reported by suite and do not represent science/security percentages. Exact classifier, required CI, tested head, PR, and merge are recorded in the final delivery closeout once known.

## Owner packet status and next action

GOAL-WORKBENCH-06A found that comment [`5674263522`](https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5674263522) contained only a local-path token and was therefore `DELIVERY_MALFORMED_CONTENT_NOT_DELIVERED`. It remains historical evidence. The complete notification was posted once as [`5675346832`](https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5675346832), immediately read back, and verified byte-for-byte at `sha256:04952e91e9fda00b36e85ac8862cb601bb9992c124546eec9b7fb56e2c63d72c`. Current status is `DELIVERED_VERIFIED_UNACKNOWLEDGED`; no source-owner acknowledgment, acceptance, funding, or selection is inferred. See `GOAL_WORKBENCH_06A_DELIVERY_INTEGRITY_REPORT.md` and `source_assessment/delivery/v1/`.

The one authorized post-delivery issue check found no eligible exact owner response. The exact next action remains for `WAVE-C/C-AUTH1` to answer the three packet questions: field semantics, permitted issuer/scope verification, and fixture/source mapping. No GOAL-WORKBENCH-07 draft was generated.

Restart event: an actual source-owner response accepts or names exact changes for contract/profile v1.0 and supplies/accepts the required verifier/trust/public-fixture inputs. Until then, the later production consumer remains unselected and unavailable.
