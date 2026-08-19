# Codex handoff — A0_repo_layout.md only

Work only ticket `.agent/tickets/A0_repo_layout.md` in `carbonphysicsai/Carbon`, one ticket at a time.

Start from the current `main` HEAD and verify it before editing. Read, in order: root `AGENTS.md`; `agent_pack/EXECUTION_PROTOCOL.md`; `.agent/WAVE.md`; `.agent/INVARIANTS.md`; `.agent/DECISIONS.md`; `.agent/ORIENTATION.md`; `.agent/tickets/A0_repo_layout.md`; then the Build_Out v1.4 sections cited by the ticket. Treat `.agent/ORIENTATION.md` as an audit of commit `0eed4e92609b4f26bd095a90f8cba9b7376fbe09`, not as proof that later code has been audited. Inspect the current diff/tree for drift before acting.

Preserve the audit-first workflow:

1. Confirm A-1 is closed by its checked DoD, WAVE evidence, orientation pin, and recorded maintainer dispositions. If those disagree, stop and report the mismatch; do not implement A0.
2. Run and record the exact pre-change baseline/CI-equivalent commands required by A0. The inherited baseline is red, so the acceptance criterion is no new failures plus an explicit before/after delta—not a false claim that tests were green.
3. Inventory the current package roots and every required import using `carbon`, `Carbon_Logic`, `hydrogen`, or `Carbon`. Produce the smallest layout plan consistent with `.agent/DECISIONS.md`.
4. Establish lowercase `carbon/` as the canonical importable package. Promote or wrap only the minimum audited code needed for A0 layout acceptance. Treat Burgers as the first promotion source, Julia as the v0 generator-verification path, and `neurons/` as optional reuse—not as scientific qualification.
5. Preserve `poc/`, `Carbon_Logic/`, `neurons/`, Julia, specs, and historical tests as auditable inputs during A0. Do not mass rename/delete, copy the legacy tree wholesale, preserve retired namespaces by default, normalize context filenames, change scoring/science/LIVE values, fix broad CI, or begin A1–A12.
6. Update `.agent/DECISIONS.md` with the actual mapping, required migrated imports, deferred callers, commands, and results. Re-run the exact baseline commands and `python -c "import carbon"`.
7. Show the focused diff and evidence. Mark A0 done in `.agent/WAVE.md` only if every A0 DoD item is evidenced; otherwise leave it `in_progress` or `blocked` with the exact reason. Stop after A0 and request review before A1.

Do not infer semantic correctness from import success, legacy tests, filenames, or existing code. Current domain-owned specifications remain authoritative.
