## 2026-10-03 — OWNER-LICENSE-01: MIT for the subnet code; products and subnet outputs licensed separately

**Authority.** The owner, 2026-10-03, on #500: "I approve. The plan is MIT
for all subnet code/mechanism. Different licensing for products and outputs
of the subnet. MIT on everything a miner and validator need to run." On the
follow-up questions, the owner chose "MIT, except commercial docs" for the
documentation folders and "Carbon Physics, Inc." as the copyright holder.

1. **MIT.** Everything in the repository outside the three reserved
   directories below is MIT, copyright Carbon Physics, Inc. That includes
   `carbon/`, `carbon_miner_signer/`, `scripts/`, `tests/`, `deploy/`,
   `examples/`, the build and CI configuration, and the documentation
   (`docs/`, `Design_Specs/`, `launch/`, `.agent/`, `agent_pack/` and the root
   documents).
2. **Reserved.** `Business/` (products, including the Workbench),
   `website/` (Ask Carbon) and `presentations/` are proprietary, all rights
   reserved. Each has its own `LICENSE` notice.
3. **Third-party code** keeps its own license, as recorded next to it.
4. **Subnet outputs.** The MIT License grants no rights in models, weights,
   strategies or methods that miners submit, or in models and results the
   subnet produces. Their terms are separate and not yet written; drafting
   them is an owner and legal task, not an engineering one.
5. **Where.** The root `LICENSE` states the split, then the MIT text.
   `Business/LICENSE`, `website/LICENSE` and `presentations/LICENSE` carry the
   proprietary notice. No per-file SPDX headers: the root file governs, and
   touching every source file would conflict with every open PR.
6. **Supersedes** #500 (harshaa765), whose MIT text and outputs carve-out this
   carries forward.
