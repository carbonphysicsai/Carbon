## 2026-10-04 — OWNER-LAUNCH-PORTFOLIO-02: the eight Foundation Plan challenges are the launch portfolio; their bounded designs are the design basis

**Authority.** The owner, 2026-10-04: "I want you to create a PR that locks
in the new 8 challenges and their designs from the Foundation Plan". The plan
is the owner-supplied *Carbon Eight Challenge Foundation Plan* (2026-10-03),
committed as `Design_Specs/Eight_Challenge_Foundation_Plan.md`.

**Amends** OWNER-LAUNCH-PORTFOLIO-01 (2026-09-26, four challenges) on
portfolio membership. OWNER-CHALLENGE-FOUNDATION-01 (2026-10-03) stands: AI
cooling remains the first bounded implementation.

1. **The launch portfolio is eight challenges.** The plan's §4 names them;
   these are planning labels, not registered challenge IDs.

   | # | Challenge | Family | Role |
   | --- | --- | --- | --- |
   | 1 | AI accelerator cooling design | f04 | Commercial flagship; the current cold plate is its starting asset |
   | 2 | Burst-power thermal envelopes for AI chips | f02 | Separate challenge from 1; shares materials, geometry and thermal representations |
   | 3 | Manufacturing-tolerant fiber-to-chip grating couplers | f06 (f14 support) | Frontier bet; replaces the symmetric coupler as photonics' headline, which stays as supporting evidence and a regression asset |
   | 4 | Cell-specific fast charging with degradation constraints | f05 | Battery; the existing ageing programme and EV5's frozen evidence are kept |
   | 5 | Low torque-variation motors for precision robotics | f09 | Motor; the existing full-curve work is kept |
   | 6 | Resonance-resistant precision automation structures | f08 (f01, f12 support) | New |
   | 7 | Compact industrial compressor silencers | f13 | New |
   | 8 | Passive micromixer cartridges for lab automation | f17 (f04, f24 support) | New |

2. **The designs are locked as the design basis.** For each challenge, the
   plan's §4 entry is its design basis: job, first scope and exclusions, inputs
   and outputs, reference proposal, baselines, decision test and reality
   route. So are §3's common foundation (the ten-section design packet,
   reference and failure handling, verification before volume, decision
   economics, the research and construction rules) and §6's path to
   experimental evidence. Changing a challenge's design basis takes a new
   owner decision.
3. **Still open, with their existing owners.** The plan's §4 and §7 leave
   these to the design packets and the responsible owners, and this decision
   doesn't fill them:
   - populations, numeric ranges, materials, output grids, mandatory gates
     and decision resolution;
   - solver packaging and licensing, CPU/GPU execution profiles and spend;
   - per-challenge budget-study sheets and construction-data permissions;
   - experimental data and rig scope.

   The Challenge Roadmap's roles still apply. The science owner accepts each
   challenge's scope at pipeline step 1, and the process approver locks the
   protocol and selects deployment.
4. **Unchanged by this decision.**
   - the Challenge Roadmap's deployment rule (rev 2.0): portfolio membership
     states intent to launch and is not a launch approval; deployment goes to
     the challenges the process owner picks from the leaderboard;
   - the three-factor family queue and the protocol state in
     `carbon/challenge_pipeline/`;
   - the challenge registry (no new IDs, and nothing reserved becomes
     implemented);
   - the four readiness records;
   - battery's frozen studies, including EV5;
   - the Control Center catalog and Graphite's challenge set.

   Mapping the eight onto these is the plan's F0 work package, under its own
   tickets.
5. **Selection weighting.** The plan's 25% Bittensor investor-alignment
   factor is a portfolio-selection input only. It never enters a physics
   score, gate, deployment rubric or reward formula.
6. **No execution.** Nothing is dispatched, provisioned or spent. No solver is
   installed, and no campaign or Graphite session is launched.
