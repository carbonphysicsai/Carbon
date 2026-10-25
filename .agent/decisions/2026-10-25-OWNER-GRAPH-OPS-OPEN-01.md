# OWNER-GRAPH-OPS-OPEN-01: open the graph op set; integer constants counted by range bits

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-25.
- **Owner's words:** "We shouldn't be limiting those operations at all"; then, on the audit and option B' (count integer tables by the bits they need), "great".
- **Decided:**
  - The graph route admits every pure, deterministic array op: the 31 class A + 46 class B JAX ops in reports/GRAPH_OPS_FREEDOM_AUDIT_20261025.md, plus PyTorch Core ATen coverage with backend parity tests.
  - Only containment/exam-unsafe ops stay refused: host callbacks, native code/custom_call, infeed/outfeed, collectives, unkeyed RNG.
  - Integer and bool graph constants are counted by the bits their range needs, not 4 bytes each (option B'). The 16 KiB from-scratch cap for fitted values is unchanged.
- **Also directed:**
  - drop the init rule blocking identity/DFT bases unless the Validator names an exam reason;
  - allow float64 on request (backend parity applies);
  - replace the unmeasured 120 s compile deadline with a measured one.
- **Build:** Launchpad 2 (v8 allowlist for graph-route-v2 versions); Validator receipt.
