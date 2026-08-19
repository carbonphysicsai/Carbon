# Agent decisions log

## 2026-08-19 — Evaluation evidence / validator audit extension

- `Design_Specs/Evaluation_Evidence_and_Validator_Audit.md` is the normative owner for execution evidence, receipts, reproducibility qualification, validator audit/re-execution, and scientific-vs-emission separation.
- `Design_Specs/Build_Out_Protocol_Extension.md` is an additive sequencing extension pending fold-in to the next `Build_Out.md` revision.
- **Do not reorder Wave A.** Continue A0 → A12 in the current board order.
- Fold receipt/evidence hooks into existing Wave A tickets only where the extension explicitly assigns them.
- JAX is the first P0 backend targeted for qualification; other backend adapters are non-emission-capable until separately qualified.
- Do not expose raw official seeds/draw IDs in receipts, cards, logs, MCP, leaderboard, or public evidence.
- No ZK/proof-of-training work is required for P0.

## 2026-08-18 — A-1 maintainer dispositions for A0

These decisions govern A0 planning; they do not implement A0 or qualify any scientific behavior.

- Establish lowercase `carbon/` as the canonical package. Support only import paths that remain necessary; do not preserve `Carbon_Logic`, `hydrogen`, or `Carbon` as canonical namespaces.
- Use the Burgers PoC as the first vertical promotion source, without treating its current science, fixed values, scoring, or disclosure behavior as qualified.
- Retire the legacy `Carbon_Logic`, `hydrogen`, and `Carbon` namespaces; reuse `neurons/` only where an A0 audit finds it useful.
- Include Julia in the first build as the verification path for the v0 data generator. Repair and scientific validation remain explicitly owned work, not implied by inclusion.
- Normalize the `docs/context/` filenames in the appropriate scoped ticket. Treat the proposal appendix in `Open_Questions.md` as the v0 direction, subject to team audit; it does not override domain-owned specifications or authorize LIVE values.

## 2026-08-17 — Canonical .agent path

- Root `/.agent/` is the only board/ticket location.
- `agent_pack/` holds protocol docs only; Hermes notes under `agent_pack/executors/hermes/`.
- Build_Out pin: **v1.4**.

## 2026-08-14 — Pack bootstrap (historical)

- Early path used Hermes + Engy; execution is now executor-agnostic.
- Scope lock: Wave A only until WAVE.md checklist is done.
- Existing repo dirs (`poc/`, `neurons/`, `Design_Specs/`) are mapped, not deleted.

## Escalate / spend log (agent fills)

| Date | Ticket | Why stop/escalate | Outcome |
|------|--------|-------------------|---------|
| | | | |
