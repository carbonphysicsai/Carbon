# OWNER-GEN-SCOPE-AND-HARD-D-01: "similar problems" covers design changes of all kinds; design value must be hard too

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-24.
- **Owner's words:** "I think it should cover design changes of all kinds. But obviously at some point it's too much for us to compute? I feel like design value is probably way too easy still. Is there a way to make that half hard too"
- **Direction:**
  1. Each Challenge's extended validity region ("remotely similar") covers design changes of ALL kinds: geometry, materials, loads, boundary conditions, operating points, and topology where the solver supports it. It is bounded only by what the open solver can compute reliably and by the compute budget. The Validator proposes, per Challenge, the widest region the solver supports, sampled sparsely to keep cost bounded, with the cost per case in USD.
  2. Design value (D) must be as hard as accuracy. In scope:
     - near-limit close calls;
     - multi-constraint picks;
     - ranking many candidates, not only picking the best;
     - design decisions on the variant problems (D_gen);
     - strict regret scales;
     - trend and sensitivity correctness;
     - inverse-design queries;
     - calibrated confidence (knowing when it is wrong).
- **Bounds:** the owner sets the final values from the curves; changes ship as new exam versions; spend beyond approved figures goes to the owner. This binds OWNER-SCORE-SCALE-MEANING-01.
