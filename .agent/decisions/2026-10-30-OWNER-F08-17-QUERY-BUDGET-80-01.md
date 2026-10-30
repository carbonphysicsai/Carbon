# OWNER-F08-17-QUERY-BUDGET-80-01: Ribbed Bracket 1.7 design-search query budget 60 → 80 (provisional, testnet)

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Validator session (local_9d14c86b-b50e-4cf2-a2ef-5c69ad1ed1e0); relayed by the Validator to the Lead, who records it here.
Owner's words: "Yes, budget 80"

Context: the F08 1.7 proof flash (report FLASH_BUDGET_SPLIT_F08_F02_20261030, sha256 bc852c0a…) showed that at B = 60 the oracle reaches 4 of 6 references, and at B ≥ 80 it reaches 6 of 6, with the honest pick ahead of the gaming controls (+0.003).

## Decided

- F08 (Ribbed Bracket) 1.7's registered pool query budget B becomes 80, provisional, testnet only.
- It ships in the next validator image move (Move B).
- Crowns on F08 1.7 open only once its proof row passes, which first needs the oracle-A tolerance item cleared.

## Bounds

- Other pool constants are unchanged.
- Mainnet is not covered.
- Sets no other threshold, score or economics.
