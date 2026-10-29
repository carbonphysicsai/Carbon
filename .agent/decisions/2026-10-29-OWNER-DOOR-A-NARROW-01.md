# OWNER-DOOR-A-NARROW-01: the door allows graph uploads only (supersedes the provisional A in OWNER-DOOR-BLOCK-RESEARCH-V2-01)

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:** "Narrow A I guess. I don't want to limit graph architecture work at all."
- **Decided:**
  - The public front door allows `submit`, `status`, and `carbon_research_v2` with op `stage_research_source` (graph upload) ONLY.
  - Every other op, including `stage_research_material`, is refused, failing closed.
  - The existing limits stay: signed, owner-bound to the authenticated hotkey, Challenge-pinned.
  - Graph architecture work must not be limited beyond exam protection.
  - A door test is required.
- **Bounds:** this narrows exposure; it is not a security acceptance. Mainnet still needs the security review plus a new owner acceptance.
- **Also from the owner:** "I told codex to end all. Said all stopped." The Codex sessions are ended; the Claude team is the sole operator.
