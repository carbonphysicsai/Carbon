# OWNER-SCORE-HEADROOM-REQUIRED-01: no launch without real room for miners to improve

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-24.
- **Owner's words:** "There's no way we shouldn't have lots of room for miners to improve. I don't know what needs to happen. Maybe harder robustness and OOD checks or harder design questions or just stricter grading. But I'm not comfortable launching like that at all."
- **Context:** on F08 practice the default scored 0.981, the good model 0.998 and the eligible backbones 0.973–0.991, leaving about 0.002–0.012 of headroom. The A and D scales are registered DEVELOPMENT assumptions.
- **Decided:** a NEW testnet ship requirement under condition 6 (scored correctly). For every launch Challenge, the score must leave large headroom above Carbon's good reference model, and must clearly separate the default model from the good model. The testnet release is blocked until that holds.
- **Levers the owner named, all in scope:**
  1. stricter grading (A and D scales and tolerances);
  2. harder robustness and out-of-distribution checks;
  3. harder design questions.
- **Process:**
  - The Validator designs options across all three levers for all 4 Challenges and proposes a numeric headroom/separation target with a rationale.
  - The Test Engineer produces the $0 practice curves; the proof run gives the sealed curves.
  - The OWNER picks the option and the target.
  - Agents set no production value.
  - Exam changes become new exam versions (accepted artifacts are not edited in place).
