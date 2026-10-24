# OWNER-PUBLISH-WHAT-IS-TESTED-01: miners see what is tested

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-24.
- **Owner's words:** "I think them knowing what's tested is net positive for the outcome".
- **Context:** the agent-kit audit (OWNER-AGENT-START-PROOF-01) asks whether miners' agents see the physics requirements, gates and scoring rules before they practise.
- **Direction:** add to the miner-visible allow-list, per Challenge: each gate and physics requirement, by name, with its pass condition and registered values; the score formula (0.5·A + 0.5·D, D = min(V, C)); and the score-part minimums.
- **Still protected (unchanged):** hidden exam cases, seeds, draw ids, private metadata and anything that reconstructs them. The Validator confirms each published item is exam-safe before it ships, and may withhold any value that would expose exam cases.
- **Scope:** testnet release under the scope freeze. It is a disclosure and docs change only; no grading behaviour changes.
