## 2026-10-04 — OWNER-GRAPHITE-TEST-WAVE-03: maximize discovery — development-only levels for Graphite, findings stop locking rather than exploration, and Level 4–5 isolation assessed now

**Authority.** The owner, 2026-10-04, in the Test Lead session.

The owner set the test wave's stance:

> As a part of our testing we are trying to maximize freedom, but catch where
> the freedom allows too many attack vectors that we can't figure out how to
> fix. So I'm nervous about any hard rules that could limit our discovery.
> That is what the test is for! As test lead you need to have that
> perspective. Max freedom, Max scoring alignment with value, and Minimum
> attack surfaces

Asked three questions, listed below, the owner answered "yes to all three".

**Amends:**
- OWNER-GRAPHITE-TEST-WAVE-01 (the wave's scope);
- for internal development testing only, the "on a finding, escalate" rule of
  OWNER-CHALLENGE-ADMISSION-01 as amended (`Design_Specs/Challenge_Admission.md`
  §3.1, `admission_expansion_after_finding`).

It also resolves the open owner decision in GRAPHITE-ADMISSION-01, "How a level
is served to Graphite's development campaigns without reaching miners", in
favour of option (a).

**The stance.** Attack surface is something the test measures, not a
precondition it imposes. For each construction level the wave records three
things side by side:
- the freedom granted;
- score-to-value alignment (τ/ρ, regret, false-feasible rate);
- open findings, split into fixable and not fixable.

The owners then choose a level from that frontier, as the Challenge Roadmap
already provides. Construction-side freedom is made as wide as can be tested.
Grading-side authority does not move: "Carbon can widen what participants are
allowed to discover without changing who controls the grade."

1. **Development-only contract variants for Graphite (GRAPHITE-ADMISSION-01
   option a).**
   - **Where they live.** A level above a Challenge's miner-facing contract
     may be served to Carbon's own registered Graphite campaigns, the
     Constructor and the Attacker, through a development-only contract
     variant. The variant is held outside `capability_registry.CONTRACTS` and
     pinned by its own digest.
   - **Who reads them.** Only Carbon's development runners read it. The miner
     MCP server, the Launchpad, the validator, the intake and any
     miner-facing registry path never do, and tests prove each refusal.
   - **Climb procedure still applies.** Every variant follows the climb
     procedure: an accepted level proposal, an expansion record for the
     development variant, Carbon's reconstruction shipped with it (the
     reconstruction rule, OWNER-GRAPHITE-02), matched valid and attack panels,
     ablations and combined-permission attacks.
   - **Scope for this wave:** battery Levels 1–3, whose six level proposals
     the technical owner already accepted. Cooling and motor follow when
     their Level 0 contracts exist.
   - **Unchanged.** A level tested internally is never opened to miners to
     gather acceptance data. Opening a level to miners is still a locked,
     released contract chosen by the owners.

2. **For internal testing, a finding stops locking, not exploration.**
   - **A finding still:**
     - escalates and is never suppressed;
     - blocks `LOCK` of the affected level and anything that opens a level to
       miners;
     - blocks any frozen admission run that would cite the affected state.
   - **Exploration continues.** Internal exploration on development-only
     variants may continue past an open finding, including recording further
     development expansions and running higher levels.
   - **Conditional tagging.** Every result produced while a finding is open is
     tagged with the open findings' ids and digests ("conditional on"). It
     cannot be cited as unconditional evidence until those findings are
     repaired and the affected attacks re-run.
   - **Implementation.** The controller's `admission_expansion_after_finding`
     refusal is kept for miner-facing and LOCK paths. For development-variant
     expansions it is replaced by the conditional tag.
   - **Why.** Mapping where freedom becomes unfixable needs exploration beyond
     the first defect. The cost is attribution: a later result may depend on
     an earlier unrepaired defect, and the tag carries that.

3. **Assess Level 4–5 isolation now.**
   - **The assessment.** The Test Engineer assesses, read-only, how close the
     existing isolated-execution work is to running participant-supplied code
     in Graphite's internal campaigns: the C-03 isolated reconstruction
     worker, `Design_Specs/Isolated_Reconstruction_Worker.md`, and the
     sandbox carrier. It also reports what is missing, including the open
     security item that the pod's RunPod key sits under the program's uid.
   - **What still gates execution.** Running hostile executables still needs
     the security owner's isolation acceptance. This decision brings the
     assessment forward; it does not grant that acceptance.

**Kept, because they protect what the test can believe rather than what
participants may try:**
- no Graphite access to sealed or confirmation material;
- grader, ledger and reference separation;
- isolation before participant code runs where real secrets live;
- held-out controls, pinned knowledge-store snapshots and honest coverage
  reporting.

**Rules as hypotheses.** Test-side classification rules that encode an
assumption are registered, versioned policies with their raw evidence kept, so
the Attacker can test them. VALIDATOR-01's failure-attribution policy is the
first example. They are not fixed logic.

**No execution and no spend.** Live runs at any level stay bound by their
grants. This record creates no grant.
