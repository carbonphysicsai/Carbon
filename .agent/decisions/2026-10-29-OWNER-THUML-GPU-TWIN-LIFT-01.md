# OWNER-THUML-GPU-TWIN-LIFT-01: lift the GPU-twin withdrawal for the 10 legacy THUML ids

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:** "Lift". This answers the Lead's question, which named the licences: timm (Apache-2.0) and einops (MIT).
- **Decided:**
  - The GPU-twin withdrawal recorded under OWNER-CATALOG-LICENCES-01 for these 10 legacy THUML ids is lifted: thuml.FNO, thuml.F_FNO, thuml.Factformer, thuml.Galerkin_Transformer, thuml.Transolver, and the five f08.thuml.* counterparts.
  - Their GPU twins are re-derived under the current cu130 lock, which pins timm and einops.
- **Reason:** the withdrawal was technical (the twins failed under an older lock that lacked timm and einops), not a licence restriction.
- **Bounds:**
  - Every other part of OWNER-CATALOG-LICENCES-01 stands.
  - The licence list (LICENCES.md) must name timm (Apache-2.0) and einops (MIT).
  - Official grading still needs each twin's official GPU receipt (OWNER-GPU-OPEN-WITH-READY-01).
