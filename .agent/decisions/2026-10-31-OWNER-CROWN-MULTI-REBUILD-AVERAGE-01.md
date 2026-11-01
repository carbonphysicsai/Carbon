# OWNER-CROWN-MULTI-REBUILD-AVERAGE-01: a would-be king is rebuilt on several validator-chosen seeds, and crowns compare averages with a correspondingly smaller margin

Date: 2026-10-31 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae). Build in testnet week 1.
Owner's words: "I'm tempted to just rebuild a new king enough times to prove it...thoughts?", then, after the Lead's proposal (5 rebuilds, averaged) and "Want me to have the team build it this week?": "yeah the takeover margin should drop significantly if we're building that many times."

## Context

The training-noise study (codex-queue/reports/TRAINING_NOISE_STUDY_20261031.md) found no training lever that reduces seed noise without hurting accuracy or throughput. Averaging seed ensembles inside every rebuild was rejected by the owner because it slows throughput. Seed noise matters mainly because a miner can resubmit an equal model until a lucky seed beats the king; today the 2 × seed-SD margin (OWNER-CROWN-MARGIN-2SD-01) blocks that.

## Decided

- When an official grade beats the crown bar, the validator rebuilds that model N times on seeds the validator chooses (not the miner), grades each, and uses the average total. The candidate takes the crown only if its average beats the king's average by the margin. A king's score is set the same way when it is crowned.
- The margin's seed-spread term is recomputed for comparing two N-run averages, so it drops roughly with 1/√N. The Validator derives the exact formula and values from the existing control measurements. The rebuild-noise floor stays.
- N: the Lead proposed 5. The owner did not name a number, so N = 5 is the working value, to be confirmed by the owner before the switch goes live.
- Only would-be winners are rebuilt N times, so normal exam throughput is unchanged.
- This is a new crown-rule version, applied prospectively. On switch-over, each current king is re-measured once with N validator-chosen seeds. Nothing already graded is rescored.

## Bounds

- Testnet only. Mainnet adoption is a separate owner decision.
- Switching it on is a receiver-code push that needs the owner's live word.
- Validator-chosen seeds come from the validator side and are never miner-visible before grading.
