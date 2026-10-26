# OWNER-GRAPH-OPS-IN-LAUNCH-01: the v8 graph operations ship in the testnet launch

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-26 ~00:15Z.
- **Owner's words:** "graph operations are in launch, we need to figure that out".
- **Decided:** the launch build includes v8 graph ops (OWNER-GRAPH-OPS-OPEN-01 + the owner-approved kept limits). A v8-free build is not the launch build. The suspended v8 receipt (107 failing tests in the full tests/cpu run) is resolved by finding which failures v8 caused and fixing them, not by dropping v8.
- The Validator's receipt still decides whether a v8 head is correct; this record sets the priority, not the verdict.
