# PLT-17: introduced-line encoding guard

Authority: the Platform2 PLT-17 local queue item; current constitutional and
OWNER-DX-03 delivery boundaries apply. Starting base: bf2494ef478a96ea6403f86aea8d96e3e345482d.
Historical hub map_ref: SYSTEM/DEVELOPMENT-HUB; the hub is retired under current delivery authority.

Working decision: REPAIR the existing standard-library delivery checker. Refuse
introduced tracked lines with the three specified cp1252 round-trip signatures.
Compare merge-base text with distinct HEAD, index and worktree versions. Existing
corruption retained from the base is outside this bounded check, even with all-tree.
A separate initially empty policy file permits only exact path/full-line exceptions
with a meaningful reason. Preserve existing workstation and commit checks.

Manifest: this ticket, scripts/dev/check_delivery_hygiene.py,
scripts/dev/delivery_hygiene_mojibake_allowlist.txt, tests/cpu/test_delivery_hygiene.py.
No runtime, science, hidden-data, host acceptance, deployment or production qualification changes.

Plan: baseline focused tests; implement guard and empty policy; add rejecting and
passing Git fixtures for committed/staged/unstaged additions and exact exceptions;
run focused regression, formatting/lint and delivery preflight; submit one main PR.
Windows/WSL diagnostics are not canonical: acceptance requires actual exact-head CI
and a successful Merge gate. A linked Windows worktree cannot use the local canonical
wrapper; preserve that boundary. Codex Test Lead review precedes PR Head handoff.
Completion is conditional on required CI and independent review; merging/release
remain PR Head/owner work. No completion-only commits or unrelated corruption repair.
