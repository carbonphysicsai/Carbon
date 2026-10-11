## 2026-10-08 — OWNER-L4-G5-COMPILE-ISOLATION-01: G5 compile isolation accepted for development and testnet only (D3)

**Authority.** The owner, 2026-10-08, verbatim: "yes". The Test Lead session
relayed it, answering decision D3 of
`docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md` (§11) in the
narrowed form OWNER-LEVEL4-GRAPH-ONLY-01 records ("security-owner acceptance,
narrowed under B′ to G5 compile isolation and Carbon's own parser"). The scope
the owner said yes to, as relayed:

> D3 / G5 is accepted for testnet and development only. Compiling a
> Carbon-checked strict-JSON Level 4 graph inside the existing C-03 worker
> lane (sandboxed, no network, no participant code) is sufficient compile
> isolation for development and testnet. A mainnet security review stays
> required before any LIVE use.

The owner then confirmed it directly in the Level 4 engineer session,
2026-10-08, verbatim: "confirm". Recorded by the Level 4 engineer session.

**Decided.**
1. **G5's profile is accepted for development and testnet.** A Level 4
   graph that Carbon's strict parser (G3) and validator (G4) have checked
   may be compiled by Carbon's own program in the existing C-03 worker lane
   (`carbon.level4.compile`, `research_carrier._run`, provenance
   `LEVEL4_G5_COMPILE_DEVELOPMENT`).
2. **Mainnet stays fail-closed.** G5 runs only when its caller names the
   scope, and only `development` or `testnet` is admitted. Any other scope,
   `mainnet` included, is `CompileBlocked` with
   `mainnet_requires_security_review`. A mainnet security review is required
   before any LIVE use; this record grants none.

**What it changes in code.**
- `carbon/level4/compile.py`: `PROFILE_STATUS` becomes
  `ACCEPTED_DEVELOPMENT_AND_TESTNET_ONLY`, naming this record
  (`PROFILE_DECISION`), and `compile_in_isolation` requires `scope`.
- `carbon/battery/level4_worker.py`: the development Level 4 rebuild no
  longer stops on D3. It still fails closed, as Carbon's environment and never
  the candidate's, for the next blocker, which is not D3 (below). Its code and
  rebuild label now name that blocker.

**Still not unlocked (each fails closed; none is decided here).**
- **Transport.** A Level 4 construction record names only the submission's
  digest. No path yet stages the submission's documents into the rebuild
  worker: the Launchpad's Level 4 slot (LAUNCHPAD-LEVELS-01 S3) and the
  validator's transport (Carbon Validator) are not wired. Until they are,
  every Level 4 rebuild stops with `level4_submission_documents_not_staged`.
- **Values.** G0's intake bounds, G4's caps, G5's deadline, the inference
  cost rule and battery's compute budget stay `HUMAN_INPUT`. Unset, each
  blocks its gate; this record sets none of them.
- **Other decisions.** D2 and D4–D6 are unchanged.

**Documentation lag (classified).** The registered variant document
`battery-l4-graph-v1` lists its gate as "G5 compile in isolation
(carbon.level4.compile): fail-closed until D3". It is a pinned historical
policy record and is not rewritten. This record supersedes that phrase for
development and testnet. A new variant version will carry the new wording
when the transport lands and the record's lane changes.

**Unchanged.**
- Development variants are never served to miners. Opening Level 4 to
  miners is still a locked, released contract that the owners choose
  (OWNER-GRAPHITE-TEST-WAVE-03).
- Level 5 stays refused. No participant code runs at any level.
- Nothing here is a production security claim. The C-03 lane's sandbox is
  accepted for development and testnet use by the owner; it is not security
  qualified.
