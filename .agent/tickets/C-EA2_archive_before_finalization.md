# C-EA2 — Archive-before-finalization integration

**Wave:** C1 real scientific execution foundations
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Integrate C-EA1 with canonical orchestration so a required real official result cannot finalize before its evidence acknowledgement.

**Prerequisites/owners:** C-EA1 plus the selected C1 orchestration/reconstruction/execution tickets; A7/current lifecycle and evaluation-result owners remain authoritative.

**Scope and reuse:** Add durable admission before dispatch, stage journal events, source-result linkage, archive acknowledgement gating, transactional outbox consumption, and safe resume. Preserve retries, cancellation, authorized early-stop, infra/reference/generator/measurement/science distinctions and existing publication/finalization ownership.

**Interfaces/failure/limits:** Archive outage pauses/fails closed finalization; it does not manufacture a scientific failure, rerun science, or create a second result. Duplicate delivery cannot duplicate attempts/results/effects. Rollback disables new integration safely but never discards admitted evidence.

**Acceptance tests:** crash/restart before and after dispatch, result persistence, object writes, catalogue transaction, acknowledgement, finalization, and publication; duplicate/out-of-order events; missing evidence; finalization denial; lifecycle-state compatibility.

**Definition of Done:** [ ] Every admitted attempt reconciles exactly once to explicit state. [ ] Required evidence is acknowledged before canonical finalization. [ ] Existing lifecycle and public projections remain authoritative.

**Handoff:** C-EA3 performs recovery qualification; Wave D may assess exact production readiness separately.
