# OWNER-EXAM-DESIGN-DECISIONS-BATCH-01: the owner's 5 Nov exam-design decisions (one record, items A10–P12)

Date: 2026-11-05 (CST)
Status: DECIDED by the owner. Each item's words were typed by him in the session named. They were relayed onto TEAM_BOARD at the line cited, and they are carried in codex-queue/reports/DECISION_LEDGER_20261105.md (the exam foundation; snapshot on this branch at .agent/exam-foundation/).
This record holds his words and their plain meaning only. It contains no hidden values: no thresholds, seeds, region bounds or case inputs.

## Physics scoring
- **A10.** Typed in Exam Quality, ~09:02, board 3082. Owner's words: "Physics scoring: score only classes/outputs where the fit loses. Outside the training data". Meaning: physics points come only from (class, output) cells where a TRAIN-only fit loses.
- **A11.** Typed in Exam Quality, ~09:03, board 3083. Owner's words: "In-range accuracy is a gate, threshold from the curves". Meaning: in-range accuracy is pass/fail. The threshold is the owner's pick from a dry-run curve and stays OPEN (HUMAN_INPUT, fail closed).
- **A12.** Typed in Exam Quality, ~09:10, board 3094. Owner's words: "Yes we can rotate and only show scores." / "we should be able to get much more than 6 cases". Meaning: hidden cases may rotate, and only scores are shown. The rotation interval stays OPEN, and the 90-day maximum stands.
- **A13.** Typed in Exam Quality, ~09:14, board 3098. Owner's words: "Physics test = generalization battery (beyond range, new combinations, regime changes, changed conditions, trends, changed requirements; scaling/consistency and unseen outputs from next versions), each family scored only where the fit loses, surviving families weighted equally."
- **A14.** Typed in Exam Quality, 17:45, board 3530. Owner's words: "as long as we can still get all the data we need through the gates". Meaning: in-range accuracy is measured and published but not scored. The gate records full per model × output × class aggregates.

## Design value
- **D6.** Typed in Exam Quality, ~08:5x, board 3059. Owner's words: "Prove fixed-optimizer design value first: ~10 solves per version on custody hosts, fit vs physics-informed model; build only where it separates."
  - **Not decided by D6 (Carbon Validator, 5 Nov):** D6 is the PROOF directive. It does not define D's zero. The owner's zero rule on record is OWNER-DESIGN-VALUE-ENGINEER-BASELINE-01: zero = the registered engineer shortcut at the budget B he picks. Whether the TRAIN-only fit's pick, or a lookup, also sets the zero is an OPEN owner question (Sat 7 sheet). Nothing here decides it.
- **D7.** Typed in Exam Quality, ~09:21, board 3106. Owner's words: "Design value scoring: trusted-zone interpolation, solve outside it, solves join zone. Yeah I was thinking something like that if it's fair." Meaning: CONDITIONAL on the fairness tests.
- **D9.** Typed in the Learned-physics researcher / EQ thread, ~16:3x, LPCD §15. Owner's words: "lets try that route. Just a completely new and different optimization task that's in the same category or something." Meaning: the adjacent-task design-value proof.
- **D10.** Typed in Exam Quality, 17:50, board 3537. Owner's words: "I still think 50/50 unless we find that that's sub optimal or design value isn't actually working". Meaning: the physics vs design-value split stays 50/50. This replaces the earlier "weight the parts higher" direction.
- **D11.** Typed in the Learned-physics researcher session, ~14:07, LPCD §13. Owner's words: "These new heavy versions with expensive solves make me nervous for our design value test … I can't spend $1000s". Meaning: D solving is cost-capped. The weekly D-solve budget per Challenge stays OPEN.

## Versions
- **V7.** Typed in the Lead session, ~11:3x, board 3228. Owner's words: "push for 3.1". Meaning: Burst Thermal 3.1 replaces 3.0, and 3.0 does not launch.
- **V7b.** Typed in the Learned-physics researcher session, 14:01, board 3382. Owner's words: "okay. keep us at the highest value path to a nov 13 launch then planned versions for those upgrades".
- **V9.** Typed in Exam Quality, 17:55, board ~3544. Owner's words: "we are building only the physics relevant ribbed bracket version". Meaning: one RB build, with no separate 2.0 or 2.1 (see OWNER-RB-ONE-BUILD-DOWN-01). The version label stays the owner's.

## Process
- **P9.** Typed in the Lead session, ~09:4x, board 3135. Owner's words: "are we holding all exam solves until we get good data from exam quality and research on what we actually need." Meaning: the old-design solve hold, until the needs list.
- **P10.** Typed in Exam Quality, 10:56, board 3209. Owner's words: "I want internal sign offs from a subagent for things that are not high risk". Meaning: low-risk work gets a fresh-subagent sign-off, and high-risk work keeps the Validator first.
- **P11.** Typed in Exam Quality, 12:47, board 3302. Owner's words: "1 an 2 yes". Meaning: an E1 published benchmark first, plus an outside review.
- **P12.** Typed in the Learned-physics researcher session, 14:19, board 3386. Owner's words: "build these small upgrades into whatever the current plan is. Tell the whole team and press for this now before we start solving anything. It shouldn't delay us if we do it now". Meaning: RECORD NOW, GRADE LATER.

## D zero + launch rule (typed in Exam Quality, ~18:1x–18:2x; the exchange quoted verbatim by EQ)
- EQ put two recommendations to him (~18:1x). Verbatim: "**My recommendation:** the zero is the best of all three [the engineer's registered cheap shortcut, the cheap fit's design, and the best design already in the training data]. A fit then can never earn design-value points." And: "each version launches only if its measurements show at least one generalization category where a learned model beats the fit by your margin. Versions that don't meet that hold, rather than ship."
- **Owner's words:** "approved your decisions there"
- EQ then asked (AskUserQuestion, "No-D total"): if Motor 1.7's design value still doesn't separate after tonight's new-task proof, what should its total be? **Owner's selection:** "Physics score alone". The option text: "Motor 1.7 launches scored only on the physics side (gate plus generalization families), as long as at least one family separates. Design value joins when a proof shows it works."
- **Owner's words, typed right after:** "we will make those decisions when we get there"

**Recorded as:**
1. D's zero = the best of {the registered engineer shortcut, the TRAIN-only fit's pick, the best design in TRAIN}. APPROVED. It supersedes the open question in the D6 note above.
2. The launch rule (launch only if ≥1 family separates by his margin) and the no-D total ("physics score alone") are his stated lean. He deferred the final call: "we will make those decisions when we get there". Both are confirmed when the results are in. No code may treat them as final before then.

## Foundation rule
Owner, typed in the Lead session ~18:1x: "don't lose any of this exam stuff it's the foundation of this build after a bunch of today decisions!" Every exam plan item must trace to a CURRENT line of the decision ledger.
