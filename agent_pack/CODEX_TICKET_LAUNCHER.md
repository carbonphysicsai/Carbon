# Codex ticket launcher

Use this launcher only with the current repository authority. Detailed rules
live in `AGENTS.md`, `.agent/DELIVERY_PROTOCOL.md`, and
`agent_pack/EXECUTION_PROTOCOL.md`.

1. Fetch without `git pull`; verify the exact current `origin/main` commit and
   tree.
2. Read `CONSTITUTION.md`, `AGENTS.md`, `.agent/INVARIANTS.md`, the active Wave
   and board, the selected ticket, and its cited authority.
3. Use a dedicated ticket branch/worktree from the verified base. Preserve all
   other worktrees and local changes.
4. On a noncanonical host, run validation through
   `./scripts/dev/canonical.sh`.
5. Use one contract-first ticket pull request with coherent vertical commits.
   Record a qualifying exception before using a separate contract pull
   request.
6. Keep stable scope, decisions, commands, invariants, and the conditional
   completion predicate tracked. Keep final review/check/merge identities in
   the external completion receipt.
7. Notify issue #42 only for material lead-lane decisions. Route an explicit
   `DEFER_TO_OWNER` package to issue #41.
8. Wait for scope-required exact-head checks and `Merge gate`. Obtain a fresh
   read-only Codex/GPT review of the complete exact-head diff, repair valid
   findings, and require a distinct non-author human approval carrying the
   closed receipt, successful `GPT review gate`, and zero unresolved review
   threads.
9. When clean and not explicitly directed to stop, normally merge with the
   exact expected-head guard. Do not squash, rebase-merge, enable auto-merge,
   or ask for another prompt solely to merge.
10. Verify ordered parents, reviewed-tree preservation, fetched exact main,
    and exact-main `Merge gate`; post the external completion receipt; then
    advance to the next ready ticket authorized by the session.
11. Preserve all human-reserved science, security acceptance, rights,
    economics, qualification, `LIVE`, launch, deployment, and production
    decisions fail closed.
