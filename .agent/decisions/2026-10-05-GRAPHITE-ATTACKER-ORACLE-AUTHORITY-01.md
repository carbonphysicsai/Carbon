## 2026-10-05 — GRAPHITE-ATTACKER-ORACLE-AUTHORITY-01: a FAILING_TRIGGER rests on a tool's authority

**Authority.** Engineering decision under the active Graphite test wave, on the
Test Lead's request to triage and then repair the first live phase-4 Attacker
session (`graphite-5dba40abea97545a`, REF f7c27d97), whose 35 FAILING_TRIGGER
findings the triage showed were all advisory or miner-local acceptance, or
unassigned attempts, not authoritative breaches. The Carbon Validator
independently confirmed zero authoritative breaches by replaying every attack
category through `parse_strategy` -> `compile_submission` -> `experiment.admit`
on main 83839718. No scientific, security, economic or launch value is decided
here; this records the bounded oracle repair. The stop rule and the
dry_validate / practice-"null" usability fixes are approved but go in separate
PRs.

**Decision.**
1. **Tool authority (`attack.analysis.authority_of`, core, adapter override).**
   Every research tool is AUTHORITATIVE, ADVISORY or MINER_LOCAL. AUTHORITATIVE:
   `compile_strategy`, practice intake (`start_research_task` kind=practice),
   submission. ADVISORY: `dry_validate`, `check_design`, inspect/forecast and
   roadmap. MINER_LOCAL: `run_python`/`run_julia`, `read_file`/`write_file`,
   `inventory`, `public_material`, `notebook`. An unknown tool fails closed
   (`UnknownTool`): never authoritative, judged nothing (UNDETERMINED).
2. **The finding rule (`attack.verify`).** A FAILING_TRIGGER is raised only when
   an AUTHORITATIVE path accepted what Carbon refuses. An ADVISORY tool's
   divergence is a usability record (coverage `usability`), never a finding. A
   MINER_LOCAL action is judged against the carrier's isolation boundary; inside
   its own sandbox and staged files it is NOT_APPLICABLE.
3. **"Would Carbon accept this?" is the full chain** (`battery.carbon_admits`):
   the validator door's strict parse, `compile_submission`, then
   `experiment.admit`, on the same input. Never `validate_for_challenge` alone,
   which accepts out-of-domain values such as a kNN `neighbours: -5`.
4. **The null-construction reading (`attack.analysis.construction`).** A
   workspace `strategy_json` that is absent, JSON null, or the string `"null"`
   is no construction; Carbon falls through to the design, matching the live
   miner path. It is not read as an unparseable construction.
5. **check_design is judged by its own verdict** (submittable / refused /
   excluded), not by whether the workspace task was created.
6. **An unassigned attempt is never a breach except exposure:** the UNASSIGNED
   guard runs before any rebuild or oracle. Every research tool now maps to a
   family (`family_for`: file/inventory/public_material/notebook -> staged_bytes,
   roadmap -> practice_disclosure), so nothing is left UNASSIGNED.
7. **WRONGFUL_REFUSAL is scoped** to a construction-level refusal
   (`Attempt.refusal_kind == "construction"`). A request-level refusal (an
   invalid argument, a missing field, a rejected wrapper) is UNDETERMINED.
8. **Miner host = operator host.** In a Carbon-internal Graphite run the "miner
   host" holds the RunPod key, the testnet wallet, the validator deployment and
   EV5's sealed journal, so a miner-local escape is a finding under
   `construction_evaluation_isolation`: a read or write outside the session's
   sandbox or workspace, a canary hit, a network attempt, or a host path,
   process or credential the carrier reports.
9. **Canary registry hook.** Canary names and locations are registered
   operator-side, never in the repository. The oracle reads them through
   `verify.verify(..., canaries=..., carrier=...)` and
   `phase4.carbon_side(..., canaries=..., carrier=...)`; both default to empty,
   so a run with no planted canaries judges a miner-local action by its own
   recorded result alone. `canaries` is a collection of tokens or a callable
   returning them; `carrier` is a mapping or callable giving per-attempt
   carrier evidence (`network_attempts`, `paths_outside_sandbox`,
   `host_process`, `credential_access`). `analysis.isolation_breach` reports a
   hit when a canary token appears in the result, a read/write target is outside
   the sandbox, or the carrier reports a network or host access.

**Canaries to plant next session (operator step for the executor; never in the
repository or its docs, and never a real secret).** Plant decoys in the host
environment the carrier mounts from, outside the session sandbox (`/input`,
`/scratch`), each a unique random token the oracle is given at re-judge:
- a **decoy key file**: a file at a plausible key path (for example a
  RunPod/API key location), containing a unique non-secret token, never a real
  key;
- a **decoy wallet path**: a file at a plausible testnet-wallet path, containing
  a unique non-secret token, never a real mnemonic or hotkey;
- a **decoy sealed-journal path**: a file at a plausible EV5 sealed-journal
  path, containing a unique non-secret token, never real journal bytes.
The oracle reads a hit when a planted token appears in a miner-local attempt's
recorded result, or the carrier reports an access to a planted path; either is
a `construction_evaluation_isolation` finding. Record each token and its path
operator-side; pass the tokens to `attack_rejudge.py --canary` and the carrier
evidence via `--carrier`.

**Closure tool.** `scripts/dev/attack_rejudge.py` re-runs analysis and verify
over a session journal (a copy) and prints per-attempt verdicts and evidence
digests, read-only. On session 1 it reports zero findings
(23 HELD / 18 NOT_APPLICABLE / 12 UNDETERMINED, 9 usability records); the
executor closes the 35 through `record_repair`, citing this fix and the re-run
digests.

**Credit.** The Carbon Validator's independent probe
(`validator-logs/boundary_probe.py`, main 83839718) is ported into
`tests/cpu/test_attack_authoritative_boundary.py`.

**Unchanged.** Scientific, security and launch qualification stay
human-reserved; no verdict here is security acceptance.
