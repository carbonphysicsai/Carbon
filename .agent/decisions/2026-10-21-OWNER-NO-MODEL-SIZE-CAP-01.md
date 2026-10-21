# OWNER-NO-MODEL-SIZE-CAP-01: no model-size caps; only the training and rebuild resources bind

Date: 2026-10-21
Status: APPROVED by the owner.
- **Main decision:** in the Test Lead's session, verbatim: "No cap. Only cap should be if it fits the training resource limit. That goes for everything not just CODANO".
- **Constant cap:** the owner kept it, directly in the Carbon Validator's session ("Keep it").

Implementation: **not yet implemented.** The spec is `codex-queue/reports/VALIDATOR_NO_MODEL_SIZE_CAP_SPEC_20261021.md`, and the Test Engineer builds it.

## Decided

- **No fixed model-size cap on any Challenge or route:** no node count, intermediate size, depth, parameter count or similar.
- **What binds instead:** the registered rebuild wall time (OWNER-REBUILD-TIME-LIMIT-01) and the worker's memory, CPU and process limits.
- **Kept: the 16 KiB cap on constants baked into a graph.** It enforces from-scratch training, because trained weights can't ship as constants (pretrained weights stay excluded). A real architecture that needs more gets a case-specific raise by receipt.

## Containment, not modelling (Validator)

- **Parser guards stay,** labelled as containment: graph document size (proposed 64 MiB) and parser recursion depth (proposed 256).
- They bound what the host parses before isolation. They are proposals, and acceptance stays with the owner's security review.

## Versions

- **The next version of each Challenge only,** bundled with what's already pending for that version. Existing versions keep their caps.
