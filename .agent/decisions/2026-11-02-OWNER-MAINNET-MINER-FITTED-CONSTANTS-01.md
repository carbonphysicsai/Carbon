# OWNER-MAINNET-MINER-FITTED-CONSTANTS-01: miners may ship physics plus small constant tables fitted on their own simulations

Date: 2026-11-02 (CST), ~17:30
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes let's lock in allowing that." This answers the Lead's proposal: "on mainnet, miners may keep physics coded in the graph plus small constant tables fitted on their own simulations, inside the recipe-information budget (counted on stored numbers); no pretrained network weights; everything else trains from scratch through Carbon's rebuild."

## Decided (testnet now and mainnet)
- A graph may hold physics code plus constants a miner fitted offline on its own solver data, inside the recipe-information budget. For the new versions that budget is counted on stored numbers only (OWNER-INFO-BUDGET-DATA-CHANNELS-01).
- **No pretrained network weights:** a recipe ships no initial_state. Every trainable parameter trains from scratch through Carbon's rebuild on the public TRAIN.
- The strong checks and G1–G9 (OWNER-STRONG-CHECKS-GENERALIZATION-AXES-01) still decide merit. A table that only memorizes loses out of range.
- **Follow-up:** the miner operator guide's wording ("a pre-fitted state cannot be shipped") is clarified to match. Launchpad drafts it, the Validator receipts it, and it goes to main on the owner's words.

## Principle (owner, 2 Nov ~17:35 CST)
"it's our job to not make a fitted solution win. So let them."
Submission rules stay PERMISSIVE: miners may build fits, tables and hybrids. Making fits LOSE is the exam's job, through the strong checks, G1–G9, the hardness and TRAIN cards, and harder physics. Never by banning approaches.
