# WEB-QA-03 — Ask Carbon private staging and live evaluation

**Status:** `implemented_and_tested_no_production_candidate`
**Owner authorization:** 2026-09-16 Ask Carbon private-staging direction
**Branch:** `agent/web-qa-03-private-staging`
**Base:** `2fd842be8594a51cebde5b3f372bf23987a8cd30` (`origin/main` at ticket start)
**Primary Hub map:** `SYSTEM/PUBLICATION-AUTHORITY`

## Objective

Move the merged WEB-QA-02 candidate to an authenticated Cloudflare staging
environment, evaluate the two registered OpenAI configurations through the
real Worker and shared Durable Object budget authority, and leave the
production homepage unchanged for a separate owner release decision.

## Bounded scope

- discover and record the actual Cloudflare account, production static-hosting
  mechanism, hostnames and rollback path;
- deploy a route-less central budget authority and separate private staging
  Workers on the existing account only where the current free plan creates no
  new monetary commitment;
- isolate Ask Carbon in a dedicated OpenAI project/key, stored only as a
  Cloudflare secret, and verify the project data-control facts available to the
  operator;
- evaluate `gpt-5.6-luna:low:v1` and `gpt-5.6-terra:low:v1` on identical
  public/synthetic material under the existing USD 5 nested evaluation cap and
  USD 50 UTC-month application ceiling;
- test real Cloudflare Worker, static-asset and Durable Object behavior, then
  provide one authenticated owner-review URL and a rollback/delete procedure.

## Authority ceilings

- no change to `carbonwebsite`, `carbonphysics.ai`, `www.carbonphysics.ai`,
  production routes or DNS;
- no public activation, public knowledge release, production secret, customer
  or protected data, scientific/security qualification, miner execution,
  economics or payment-plan change;
- no API key, OAuth token, account token or secret in Git, chat, issues, PRs,
  logs or evaluation artifacts;
- no automatic increase above either provider ceiling and no paid Cloudflare
  plan or other recurring commitment.

## Definition of done

- [x] current `origin/main`, WEB-QA-01/02 and applicable authority inspected;
- [x] actual production Cloudflare account, static Worker, hostnames, upload
      workflow, current plan and rollback path established by authenticated
      account evidence;
- [x] private Cloudflare staging and shared Durable Object deployed with a
      documented no-charge basis and deletion/rollback path;
- [x] dedicated Ask Carbon OpenAI project/key provisioned outside repository
      and chat, with actual project data-control facts recorded;
- [x] Luna and Terra evaluated through the deployed Worker on identical cases,
      independently scored and retained with exact/uncertain spend and latency;
- [x] real Worker/Durable Object behavior exercised and browser limitations
      recorded without claiming unavailable native Safari/VoiceOver evidence;
- [x] no candidate selected because neither clears the frozen quality bar;
- [ ] focused tests, applicable repository acceptance and Merge gate pass;
- [ ] tested head merged normally with the expected-head guard while production
      remains byte/routing unchanged.

## Reuse decision

KEEP the WEB-QA-02 component, source release, provider adapter, retrieval,
publication contract and ledger. WRAP the same Worker with Cloudflare static
assets for staging and add evaluation-only observability. REPAIR only defects
demonstrated by real staging evidence. Do not redesign the application.
