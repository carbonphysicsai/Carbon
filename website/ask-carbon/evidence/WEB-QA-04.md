# WEB-QA-04 reviewed-answer reliability evidence

**Evidence date:** 2026-09-18 (Asia/Makassar) / 2026-09-17 UTC  
**Branch:** `codex/web-qa-04-structured-output-reliability`  
**Status:** implementation and compatibility smoke complete; frozen final
bakeoff waiting for the existing UTC daily request reset  
**Production candidate:** pending frozen evaluation; none selected by this
partial record

This is staging engineering evidence, not production activation, scientific or
security qualification, or a general factuality certificate.

## Core-programme coordination

Issue #209 and open PR #211 were inspected before implementation. A scope note
was posted to issue #209 at comment `5720642402`. WEB-QA-04 does not change
shared scientific execution, reconstruction, capability discovery, profiles,
checkpoints, grants, campaign accounting, artifacts/evidence, or job lifecycle.
The existing Ask Carbon provider ledger remains an application-specific Q&A
cost authority, not a competing scientific scheduler, runner, artifact format,
or campaign ledger.

## Repair

The WEB-QA-03 provider contract asked the model to author both an answer and a
second paraphrased claim map. A lexical checker then compared those two
paraphrases with reviewed passage prose. The frozen run retained many
`unsupported_claim` and `unmapped_answer_claim` failures even when the delivered
answers that passed were source-correct.

The successor uses strict structured output only to select one to three
request-specific reviewed card IDs and either one exact reviewed follow-up or
`null`. The Worker—not the model—renders the selected cards' exact reviewed
passage text, resolves pinned source destinations, renders maturity notes and
issues the continuation. Unknown, duplicate, stale, withdrawn and
non-retrieved selections fail closed. The provider cannot author displayed
factual prose, URLs, citations or maturity claims. Pilot-design guidance keeps
its separate proposal contract.

Knowledge/release identity:

- `ask-carbon-staging-2026-09-18.1`
- answer contract `SERVER_OWNED_REVIEWED_CARD_SELECTION_V1`
- 26 eligible reviewed cards / nine matched pinned sources
- `STAGING_REVIEWED`; public activation remains false

## Private Cloudflare staging

Final deterministic-rendering deployments:

- Luna Worker `ask-carbon-eval-luna`, version
  `1403397f-089d-427e-942b-dc9db5ed3b24`
- Terra Worker `ask-carbon-eval-terra`, version
  `b144e359-febf-41b3-b827-af50990abc81`

Both remain route-less from the production domain, bind the existing
`ask-carbon-budget-authority` Durable Object and retain the existing private
browser Basic-auth path. A separate rotated evaluation access secret was added
through Cloudflare secrets. It is accepted only for staging
`/api/ask-carbon*` while evaluation telemetry is enabled, cannot fetch assets,
does not replace the separate ledger operator secret, and is not retained in
Git/chat/evidence.

No Cloudflare plan or paid resource change was made.

## Live compatibility smoke

The same public/synthetic question, `How does Carbon work?`, was sent once to
each registered candidate through the real Worker and shared Durable Object.
Both returned HTTP 200 `supported`, knowledge
`ask-carbon-staging-2026-09-18.1`, source `constitution-405a820b` and passage
`overview-purpose`. The model only selected the reviewed card; the returned
factual content and citation were server-owned.

| Configuration | Worker elapsed | Input / cached | Output | Exact cost |
| --- | ---: | ---: | ---: | ---: |
| `gpt-5.6-luna:low:v1` | 3,171 ms | 1,542 / 1,539 | 34 | 73 micro-USD |
| `gpt-5.6-terra:low:v1` | 1,543 ms | 1,542 / 1,539 | 34 | 722 micro-USD |

Compatibility and development calls made during WEB-QA-04 increased the
canonical ledger's settled exposure by 4,637 micro-USD. They added no new
unresolved exposure.

## Budget state and daily control

The real canonical Durable Object snapshot after compatibility work recorded:

- settled: 140,011 micro-USD;
- unresolved possible-dispatch exposure: 78,960 micro-USD;
- canonical exposure: 218,971 micro-USD;
- active attempts: zero;
- 84 admitted requests on UTC date 2026-09-17.

The separately retained closed Workbench ledger still contributes 13,151
micro-USD settled and 67,680 micro-USD unresolved exposure. Combined application
exposure is therefore 299,802 micro-USD: 153,162 settled plus 146,640
unresolved. Remaining nested evaluation balance is 4,700,198 micro-USD
(USD 4.700198), also leaving USD 49.700198 in the September application
ceiling. These are application-ledger figures, not an account-wide invoice cap.

The fixed daily limit is 100. A same-day two-model final run needs 64 requests,
so it was not started with only 16 admissions remaining. The limit was not
raised, bypassed or split into competing ledgers. The exact remaining action is
to run both unchanged final splits after 00:00 UTC.

## Tests completed before the frozen run

- `cd website/ask-carbon && npm test` — 61/61 passed.
- `npm run validate` — staging release valid; 26 cards, nine source digests,
  zero errors/warnings.
- `npm run eval:contract` — 40 single-turn and six conversation retrieval
  checks completed; no model-quality claim.
- `git diff --check` — passed.

The tests cover server-owned rendering, request-specific enums, unknown and
duplicate selections, stale follow-up exclusion, release expiry/withdrawal,
continuations, no-evidence, body/response bounds, provider usage and settlement,
shared ceilings, generated ledger event sequences, UI request races, private
staging auth, and the evaluation-only API credential. They do not replace the
pending live semantic review.

## Production boundary

Read-only verification after the private deployments returned the unchanged
production homepage SHA-256
`5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`
at 5,774,725 bytes. Production `/api/ask-carbon` returned 404. Production
homepage assets, Worker, routes, DNS and activation were not changed.

## Pending evidence

After the UTC daily reset:

1. deploy/verify the exact committed successor revisions;
2. run the unchanged frozen final split once through Luna and once through
   Terra with no retry or fallback;
3. retain full outputs/failures and reconcile the shared ledger;
4. manually score every final disposition against `eval/QUALITY_RUBRIC.md` and
   the pinned passages;
5. select the least-cost passing configuration or none;
6. run repository acceptance, merge the bounded PR, and keep production
   unchanged.
