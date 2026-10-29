# OWNER-DOOR-BLOCK-RESEARCH-V2-01: the public front door blocks carbon_research_v2 (leaning A, pending the dependency check)

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:** "Let's check what it breaks. But I think A. Miners are almost strictly Adversarial"
- **Context:** EXPOSURE-03 accepted two door tools, submit and status. The intake also accepts `carbon_research_v2` (miner source-code staging, since d7d0cd0ba, 2026-10-17); the written scope missed it.
- **Decided, provisionally:** option A. The public front door allows ONLY submit and status, and `carbon_research_v2` is refused at the door, failing closed. Before this is final, the Validator lists every launch route or avenue that depends on `carbon_research_v2` and what blocking it breaks. If a launch route depends on it, that goes to the owner. Treat miners as adversarial by default.
- **Bounds:** this narrows exposure only and is not a security acceptance. Opening the tool later needs a security review plus a new owner acceptance.
