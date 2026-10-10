## 2026-10-09 — OWNER-LEVEL5-INTERNAL-LANE-01: the Level 5 internal-lane strategy

**Authority.** The owner approved the strategy. The Test Lead relayed the
owner's whole reply to the Level 4 engineer session:

> Approve and add in the level 5 strategy

Recorded by the Level 4 engineer session. The strategy is written into
`docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md` §12.1.

**Decided.**
1. **An internal lane, a future phase.** Level 5 is Carbon's internal
   research lane, gated on Level 4's stage C results. Miners never run code
   in it.
   - Graphite's Constructor explores honest gains.
   - Graphite's Attacker tries to break each one.
   - Attack findings never ship.
2. **Classification.** Each honest gain becomes one of four things:
   - plain math becomes an allowed op or library block;
   - a solver need becomes the solver op;
   - a speed kernel becomes a Carbon-owned, audited kernel registered by
     name;
   - a library is wrapped if it is pure, and otherwise stays internal.
3. **Shipping.** Carbon implements each gain, checks determinism and compute
   counting, and runs the Level 4 attack suite. The gain then ships in a
   versioned image and allowlist, tied to a new Challenge version. Nothing
   changes mid-competition, and old results stay bound to their toolkit.
4. **Four conditions.**
   - Every op is counted at its true cost in the compute budget, and
     solver-calling ops get a hard rule (for example, training only, never
     at inference).
   - Miner proposals are written specs, never code, earning credit and a
     bounty with no exclusive access.
   - Releases are batched, one toolkit version per competition period.
   - Every new kernel passes the existing backend-parity and GPU
     device-class acceptance.
5. **Starting now: a refused-capability log** of every capability Graphite
   asks for and Level 4 refuses during stages A to C
   (`docs/development/graphite/level4/REFUSED_CAPABILITY_LOG.md`).

**Open, `HUMAN_INPUT`, the owner's.**
- bounty terms for miner proposals;
- which findings stay Workbench-internal rather than shipping in the base
  image;
- GPL and licensing per op;
- per-run grants for internal Level 5 work;
- the security sign-off for running Attacker code on disposable hosts.

**Not decided.**
- **Nothing runs.** No Level 5 code, image, op, kernel or host is built,
  specified or accepted.
- **No security acceptance.** The Attacker-host sign-off above is the
  security owner's and is still open.
- **No miner-code path.** The strategy opens none. §12's requirements still
  bind any future one.
- **No other change.** No value, rule, allowlist or Challenge version
  changes.
