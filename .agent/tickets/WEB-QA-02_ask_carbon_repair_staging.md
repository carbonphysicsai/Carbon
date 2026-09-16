# WEB-QA-02 — Ask Carbon repair, knowledge completion, and staging evaluation

**Status:** `implemented_with_external_staging_blockers`
**Owner authorization:** 2026-09-16 Ask Carbon successor direction
**Branch:** `agent/web-qa-02-repair-staging`
**Base:** `405a820b` (`origin/main` at ticket start)
**Primary Hub map:** `SYSTEM/PUBLICATION-AUTHORITY`

## Objective

Repair the inactive WEB-QA-01 integration, reconcile useful public knowledge,
and produce a tested private-staging candidate or an exact external-blocker
record. Production homepage content, routes, DNS, and activation remain
unchanged unless separately authorized after this ticket.

## Bounded scope

- durable, application-wide USD 50 UTC-calendar-month provider accounting,
  with the live evaluation nested inside a USD 5 cap;
- conversation-aware, relevance-gated public retrieval with server-issued
  continuation state and no private/evaluator access;
- claim-to-passage support validation, typed no-evidence/out-of-scope/service
  outcomes, strict provider schemas, and server-owned citations;
- one release contract shared by build validation, Worker activation, and
  saved-answer fallback, including withdrawal, expiry, and source-change
  behavior;
- repaired request races, streaming byte limits, bounded telemetry and visible
  maturity information;
- reconciliation of the recovered 31-card draft and supplied evaluation cases
  against current public authority;
- discovery of the actual hosting source/account path and private staging only
  where existing permissions, provider/privacy policy, and budget gates permit.

## Authority ceilings

- no production deploy, route, DNS, homepage, privacy-policy, security
  acceptance, source-rights expansion, or public activation decision;
- no access to private/customer/protected evaluator data and no Research
  Concierge or miner-execution expansion;
- no scientific threshold, Challenge state, qualification, economics, reward,
  or subnet contract change;
- credentials stay in approved secret stores and are never recorded in Git,
  chat, issues, test output, or evaluation artifacts.

## Definition of done

- [x] every reviewed defect is reproduced by a regression test and repaired;
- [x] generated accounting sequences and concrete examples preserve the
      monthly exposure invariant across restart, expiry, rollover, duplicates,
      late settlement, and multiple deployment environments;
- [x] current-source knowledge coverage is reviewed and release-gated without
      relying on an obsolete fixed card count;
- [x] deterministic retrieval, release, Worker, UI, and mock-evaluation tests
      pass; mock metrics are labelled as contract checks rather than quality;
- [x] two compatible OpenAI configurations are tested through the bounded
      Worker path when existing credentials and private staging permissions are
      available, otherwise the exact missing external fact is recorded;
- [x] the actual hosting source/account/routing/rollback path is established by
      authenticated evidence or left as an exact permission blocker;
- [x] staging/browser/runtime evidence and privacy/retention map distinguish
      tested, unavailable, and human-reserved checks;
- [ ] applicable repository acceptance and `Merge gate` pass before normal
      expected-head merge under `.agent/DELIVERY_PROTOCOL.md`.

## Reuse decision

KEEP the dependency-free component, homepage/Workbench boundaries,
server-only provider call, and text-safe rendering. REPAIR the ledger, Worker,
retrieval, release contract, knowledge, evaluation, and request-state modules.
The recovered `Carbon_Ask_v1.zip` is review input only, never a replacement
application or executable install source.
