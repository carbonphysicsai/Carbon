# NET-1 plan — bounded read-only ChainAdapter

**Ticket:** NET-1
**Delivery:** one separate implementation branch and PR from the merged Wave-C
transition
**Primary Hub map_ref:** `WAVE-C/NET-1`

1. Re-read current main authority after the transition merge; verify the exact
   Bittensor SDK release and read-only API against official package metadata
   and documentation before pinning.
2. Audit `carbon.chain`, package/import tests, dependency/lock conventions, without importing archived executable code. Classify existing
   code KEEP/WRAP/REPAIR/REPLACE.
3. Record reversible engineering decisions for immutable snapshot semantics,
   Carbon-owned failure types, and SDK injection/translation; notify issue #42.
4. Implement Carbon-owned types and protocol first, then one SDK-backed
   translator with lazy client construction and no write surface.
5. Add deterministic fake-backed focused and invariant tests, update the lock,
   and prove scientific modules remain SDK-independent.
6. Reconcile NET-1 evidence, board, maturity, and Hub source; regenerate derived
   views; run focused checks and one applicable ready-revision CI acceptance.
7. Normally merge the tested expected head, post a brief completion comment,
   then select and execute NET-2 under OWNER-C0-REWARD-01.
