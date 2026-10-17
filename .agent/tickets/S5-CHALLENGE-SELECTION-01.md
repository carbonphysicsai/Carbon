# S5-CHALLENGE-SELECTION-01: show selected Challenge construction options

Status: bounded implementation candidate for Root review; no S5 acceptance claim.
Base: `origin/main` `6308675ce5636db8c27a1ab5f9d1ab2c0e8e5cba` in an isolated worktree.
Primary map reference: `WAVE-C/LAUNCHPAD`; Hub impact: none, because the purpose, placement, authority and maturity of the existing Launchpad surface do not change. Hub maintenance is retired under OWNER-DX-03.

Decision: KEEP the maintained launch wizard and options operation; REPAIR its single selected-Challenge lookup. The wizard stores `{id, version}` on a normal radio selection, while `construction_options` is keyed by the Challenge ID string. Index by `wizard.challenge?.id`, retaining an absent result for an unknown or unselected Challenge. Do not widen the construction contract, register libraries, or infer an L4 check from displayed options.

Test: extend the existing Control Center DOM scenario runner with a normal radio selection against a keyed response and an unrelated-key negative. This exercises the page behavior that the response-only options test cannot see. Run the focused maintained canonical CPU test when the canonical environment is available; otherwise keep that validation unearned for Root. No provider, signer, model, Docker build or installed miner state is involved.

Completion predicate: the selected Challenge's document appears after normal selection; a document for another key stays hidden; the scoped DOM test and applicable canonical checks pass; independent complete-diff review and delivery controls remain Root-owned. Maturity ceiling: implemented/tested UI repair only, not S5/L4 scientific or validator acceptance.
