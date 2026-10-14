# INCENTIVE-OBSERVER-02: multi-Challenge test aide

Status: bounded fixture/test patch for Product's SAME observer PR; no standalone PR.
Assigned by Root Test Lead on 2026-10-13 under the owner's coordinated team mandate.
Starting main: `1ac383afa65f74d1cf4aa80f6f23bfc01198910f` (disjoint merges after
payout-plan basis `e976b36e91ef72468c27461ee15b5c05b587e3fc`).
Primary routing: INCENTIVE-OBSERVER-02; Hub retired under OWNER-WORKFLOW-SPEED-01.

## Contract and decision

KEEP the registered `testnet-winner-v1` policy, Q12 arithmetic, eligibility,
complete-target projector and network-parametric compiler. Add only a NEW
`tests/cpu/test_incentive_multichallenge_projection.py`; Product owns observer
implementation and `test_incentive_canary.py`. The local payout plan section 3,
item 3 identifies IMPLEMENTATION_LAG: `epoch_targets` sums the same hotkey's
per-Challenge earnings, while `verify_epoch` tests that total against one share.
No source adapter, scientific comparison, launch policy or allocation change.

Use the actual registered three Challenge IDs and policy digest. Synthetic
identities, first-incumbent records (null registered baselines), finalized-time
fixtures and in-memory/local temporary receipts exercise the existing rule.
No production owner record/authorization, backend, key, signature, provider,
chain RPC, deployment, private ledger, protected data, spend or transfer.
A loopback endpoint string is never opened. Fixture runtime spec 477 reuses the
already adopted testnet value; it proves no host/runtime compatibility.

The test constructs separate Challenge records with independently aged clocks,
projects through the real issuer, resolves its local intent and compiles the
complete conserved Q12 vector to its actual u16 representation. It checks the
same hotkey paid both full and decayed shares, absent winner/no source burns,
exact aggregate/burn remainder, invalid aggregate and identity refusals, and
observer acceptance of valid aggregate rows versus impossible/foreign/canary
rows. Observe only the pure `verify_epoch` interface; no production `check`.
Root relayed Product's optional `expected_targets` keyword: the complete
`epoch_targets` result `{winners: {hotkey: q12}, burn: q12}`. Exact-vector
checks use that projection, including burn. Without clocks/complete evidence,
a shared-hotkey observation must be UNVERIFIED rather than guessed or falsely
blocked. Malformed/nonconserved/conflicting expected evidence is UNVERIFIED;
a valid complete expectation with the wrong observed row is a BLOCKER.

The observer interface contains no per-Challenge promotion clocks, eligibility
records or policy digest: a valid sum of registered decay levels is only a
compatibility diagnostic, not proof of a particular age, complete source
coverage, mainnet readiness, incentive, Alpha credit or scientific winner.
An absent Challenge in this synthetic issuer is known no-source/no-winner;
missing public observation is distinct and must remain UNVERIFIED.

## Plan and acceptance

1. Record contract and source bindings before fixtures; open-PR scan found no
   overlap on either NEW aide path. Product's two owned paths stay untouched.
2. Run only existing decay/observer baseline canonically, then the new slice.
3. First capture the real legacy false-blocker (no new keyword), then add
   prospective complete-vector tests. The absent new keyword may produce a
   TypeError on old main; that is API-pending evidence, not the reproduced bug.
   Report actual RED/GREEN outcomes on the pinned main baseline without xfail
   or suppressing failures; Product integrates the patch and owns the repair.
4. Canonical Ruff/Black and encoding/diff checks. No broad regression suite,
   separate red-test PR, deployment, merge, new payout/freshness value or policy.

Maturity ceiling: executed synthetic regression evidence only. The existing
network-neutral math/compilation is mainnet-equivalent code, not registered
mainnet policy, deployment, chain publication or actual payment evidence.
Human input: no new value needed for this fixture; production freshness,
mainnet configuration/membership, allocation and acceptance remain reserved.

## Source bindings: raw Git bytes at the starting base

- `carbon/rewards/winner_decay.py`: `sha256:dcee598eeb5d62b74336dbfb4b376f635e5e38b80ca8663929f2e4a3699161ea`
- `carbon/rewards/weight_policies/testnet-winner-v1.json`: `sha256:b234dfdba8c5b8e588ec7aab8783394ee2244fab3838743d3fc4a6a8cf13a7b9`
- `carbon/rewards/weight_policies/registry.json`: `sha256:d4fab83765afaf022a38fc00d1f96e733a1b8ffb8a461ae01fc2742de7918799`
- `carbon/rewards/testnet_winner_publication.py`: `sha256:71bb2115085b846dc903c91889d4e088a0441c94a1a246552b99b56af3a5318d`
- `carbon/rewards/winner_eligibility.py`: `sha256:dad7772516d36bc7efeef534561c0c153c2900b69710b10aea0c5386beaefb06`
- `carbon/chain/publication.py`: `sha256:121f4d2ce18b8b2bd5447d163c84a442e750be58c4d78c506d413ded3befc28e`
- `scripts/dev/canary/incentive.py`: `sha256:368fff7ad2c4e3c24f8804322699893c5136655dac170943c5f3409541e4b27d`
- `tests/cpu/test_reward_winner_decay.py`: `sha256:ad43bd75c3caca4b454f8ee65213344165dfacb595e5b9acea5dfd99fddba978`
- `tests/cpu/test_incentive_canary.py`: `sha256:a765d6349694501091885fa3ac96a33e9c3b3df7a204de35e65d7ffe99032f9a`
