# CHALLENGE-PORTFOLIO-F1 — common design packet

**Status:** implementation in progress; not a protocol lock or Challenge activation.
**Authority:** `Design_Specs/Eight_Challenge_Foundation_Plan.md` §3 and §5,
adopted by `OWNER-LAUNCH-PORTFOLIO-02`; current `AGENTS.md`.
**Start:** `origin/main` `37ed2912cf4b5c590ceef8965a432652884bea9c`.
**Related sequence:** Challenge Protocol Phase 1 step 2 remains independently
`todo` in `carbon/challenge_pipeline/protocol.json`.

## Working contract

Provide the ten-section, Challenge-neutral packet in
`docs/development/challenge_pipeline/COMMON_DESIGN_PACKET_V1.md`, with each
section mapped to an existing authoring, readiness or execution owner. Provide
a Battery worked example based on current public repository records, without
changing its live contract or sealed evidence. Record which of the five newer
portfolio briefs can reuse an existing component and which require a new
science/engineering decision. This is the F0 inventory input to F1, not five
runtime adapters or a change to the active family queue.

## Decisions and boundaries

- `F1-D1`: The packet is a documentation template, not a new public schema.
  Existing typed contracts remain authoritative; missing fields stay `OPEN`
  with an owner and cannot be filled from another Challenge's fixture.
- `F1-D2`: The Battery example illustrates section completeness and cites
  extant evidence; it does not rescore, requalify or modify Battery, EV5,
  journal sequence 14, the live exam, or its protected batches.
- `F1-D3`: The five foundation-plan labels are not registered Challenge IDs.
  Their physical scopes are planning inputs. Runtime registration, solver
  spending, population approval, score adoption and protocol lock remain
  separately gated.
- `F1-D4`: This work coordinates with Phase 1 step 2 but does not complete its
  four stage definitions or edit `protocol.json`.

## Definition of done

- Template and Battery example contain exactly the adopted ten sections in
  order, with explicit `OPEN` values and owner boundaries.
- Static conformance tests protect section order and the separation from
  protocol state, EV5 and protected material.
- Focused tests and applicable canonical acceptance are run or a concrete
  environment limitation is recorded. A lessons entry follows execution.
- One reviewable PR is handed to PR Lead; Codex does not merge it.

## Maturity ceiling

Specified/documented and statically tested only. No scientific, security,
network, customer or launch qualification; no official evaluation authority.
