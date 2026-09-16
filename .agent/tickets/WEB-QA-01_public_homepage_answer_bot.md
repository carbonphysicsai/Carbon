# WEB-QA-01 — Public homepage answer bot

**Status:** IMPLEMENTED AND LOCALLY TESTED / PUBLIC ACTIVATION BLOCKED
**Owner authorization:** 2026-09-16 Codex integration handoff
**Branch:** `agent/web-qa-01-public-answer-bot`
**Base:** `a5a520166e97268ec32e546b12edcd448e46d210`

## Objective

Integrate a bounded, source-inspectable answer surface for public questions
about how Carbon works without replacing the live homepage, widening the
authenticated Research Concierge, or exposing private evaluation data.

## Bounded scope

- dependency-free custom element and stylesheet that can be injected into the
  established static homepage;
- reviewed-source manifest, saved explanations, topic starters, follow-ups,
  source inspection, keyboard focus, mobile layout, loading/error handling,
  and thread reset/race handling;
- exact `/api/ask-carbon` and `/api/ask-carbon/health` Cloudflare Worker
  handlers with server-side provider credentials, signed bounded context,
  strict structured-output validation, fixed source mapping, publication
  gates, and a Durable Object usage ledger;
- deterministic integration, validation, and evaluation tooling;
- evidence that distinguishes local/mock validation from live model and
  production-runtime evidence.

## Explicit exclusions

- no homepage replacement, iframe, CRM, or parallel application framework;
- no private archive, customer data, protected exam, evaluator, Landscape, or
  Research Concierge access;
- no changes to miner contracts, economics, scientific thresholds,
  qualification, or Challenge state;
- no production route, provider spend, secret creation, publication approval,
  or deployment.

## Known inputs and blockers

- The only located public-site source is an external saved `index.html` whose
  SHA-256 matches the bytes served at `https://carbonphysics.ai/` on
  2026-09-16. This repository does not establish the deploy repository,
  production branch, Cloudflare project, or route owner.
- The referenced `Carbon_Ask_v1` implementation candidate, its 31 candidate
  cards, and its supplied live evaluation cases were not present in the
  attachment or accessible repositories. They cannot be represented as
  reviewed.
- No owner-approved provider model, API credential, pricing acceptance,
  privacy decision, source release, cost ceiling, production routing, or
  deployment authorization is available.

The Worker and UI therefore fail closed. Local preview content is marked
`DRAFT_NOT_APPROVED`; production activation remains impossible until all
required configuration and owner-controlled decisions are present.

## Definition of done

- [x] component integrates into a copy of the current static homepage without
      changing existing homepage routes or content;
- [x] public knowledge validation rejects stale, unapproved, or unknown
      sources and records the missing 31-card review;
- [x] API tests cover activation, origins, validation, signed context,
      provider output, ledger concurrency/expiry/recovery, price arithmetic,
      and rollback;
- [x] UI tests cover reset/races, loading/error states, source inspection,
      injection-safe rendering, and keyboard behavior;
- [ ] repository acceptance and one applicable automated acceptance pass;
- [x] local staging is visually inspected at desktop and 390×844 responsive
      sizes; iOS Mobile Safari remains unavailable and unverified;
- [x] completion evidence states live calls, limitations, activation state,
      and whether production changed.

Evidence: `website/ask-carbon/evidence/WEB-QA-01.md`.
