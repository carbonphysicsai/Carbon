# Score Lab research session 01 (GRAPHITE-RESEARCH-SCORELAB-01)

One brief-driven, unscored research session: how to test inside the Score Lab, what to test and what to measure value
against, for the customers' problem. A closed Planner-role task (`carbon.agent_campaign.graphite.score_lab_research`),
tool-less, no pod, no proposal, development evidence only. It decides nothing and proposes no threshold.

- **`sources.json`** is the brief's source list: eleven excerpts of Carbon's own documents (the Business Canon sections on the
  customer, the product specification's decision-evidence, credibility-dossier and Decision Assistant sections, the
  credibility standards applicability map, the credibility crosswalk decision record, the Score Lab experiment plan
  sections 2 to 6, the Score Lab candidates README and the Track A priorities). Each is `{id, origin, text}`.
- **Left out on purpose:** every line naming a currency figure, a private path or an account-like identifier (each source
  says how many were dropped); the standards map's cost column; the holdout designs. The module refuses a source that
  names any of these before a call.
- **Labels rewritten:** the protected-material check watches for four label names. The excerpts carry them rewritten (the
  first and second design banks as `bank-1` and `bank-2`, the final check as `final-check`, a probe member as `probe`);
  the research needs the meaning, not the names.
- **Method cards (14, by id):** arxiv-2402.01960v2, arxiv-2311.00060v2, arxiv-2401.15305v2, arxiv-2304.04195v1,
  arxiv-2204.02488v2, arxiv-2309.16971v4, arxiv-2506.21894v3, arxiv-2603.17836v1, arxiv-2310.12526v1,
  arxiv-2203.03048v1, arxiv-2204.04259v1, arxiv-2502.00550v2, arxiv-2204.09157v2, arxiv-2208.05606v2, from the phase 3
  literature snapshot `4adb013d...` (uncertainty calibration, probabilistic scoring, active learning and Thompson
  sampling over neural operators, multi-fidelity surrogates, battery fast-charge optimisation, a verification-and-validation
  study of physics-informed surrogates).

## Source gaps (the brief says so, and the session must name them)
1. **ASME V&V 40 and NASA-STD-7009B clause text.** The repo holds an applicability map and the profile structure, not the
   clauses or abstracts. None was written for this brief.
2. **Decision-focused evaluation, value of information, Goodhart-resistant scoring.** The card store is surrogate and
   neural-operator literature. It holds adjacent cards only (active learning, Thompson sampling, calibration, one
   probabilistic scoring benchmark); there is no card on Goodhart effects or on the value of information as a theory.
3. **Customer cost of a wrong or slow decision.** The brief has no customer data and, by design, no money figures; the
   session can describe the decision structure, not price it.

## Run (the executor, after the grant merges; the owner-only Engy key file by path)
```
python -m carbon.agent_campaign.graphite.score_lab_research \
  --root <a private directory outside the repository> \
  --snapshot <card store>/backfill/cards/snapshots/4adb013dd64a18678ccb44589199b96d40b92944dd57fffb1a1218fe80efebfe.json \
  --sources docs/development/graphite/research/score-lab-research-01/sources.json \
  --grant docs/development/graphite/grants/GRAPHITE-GRANT-RESEARCH-SCORELAB-1.json \
  --credential-file <owner-only Engy key file> --run-id score-lab-research-1 \
  --card-id arxiv-2402.01960v2 ... (the fourteen ids above, one --card-id each)
```
Run under the crash guard (swap 0 plus earlyoom) and a hard memory cap. Exit 0 means COMPLETED; 4 is a typed stop.
The session writes `runs/score-lab-research-1/{brief.json,answers/,rejections/,report.json,session.json}` under the root.

## What the executor records
The agent (the Planner-role closed task `score-lab-research`), the model (`model` in `session.json`; the planner's start
rung is glm-5.2), whether the ladder escalated (it does not in a one-shot; a rung above glm-5.2 would be refused by the
run ledger), the item outcomes (ANSWERED / REJECTED, with codes) and `report_written`. No account ids, keys or balances.
The Graphite Testing Manager renders `report.json` into the operator note (at most three pages) and a copy under
`codex-queue/inputs/`.
