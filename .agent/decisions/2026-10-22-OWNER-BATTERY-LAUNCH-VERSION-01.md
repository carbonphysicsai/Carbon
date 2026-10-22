# OWNER-BATTERY-LAUNCH-VERSION-01: Battery launches as version 2.2 (2.1 plus the backbone catalog)

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), answering "which Battery version launches, 2.0, 2.1 or 2.2?": "2.2".
Resolves: HANDOFF_AUDIT H7 (Battery's launch version was undefined).
Maturity: DEVELOPMENT launch-scope decision. No qualification, LIVE or mainnet authority.

## Decided

- The launch Battery version is **2.2**: Battery 2.1 (the miner designs its own model graphs) plus the backbone catalog (the battery-2-2 work, 84eab481e).
- Under the owner's rule of showing only the latest Challenge version, 2.2 is the Battery entry miners see. Battery 1.0, 2.0 and 2.1 are not shown as launch versions.
- The physics, the data format and the score rule (0.5·A + 0.5·D) are unchanged from 2.x. The Battery grid sealed exams (OWNER-BATTERY-EXAM-GRID-01) grade 2.2: the Validator confirmed the bank-format binding, and the sealed adapter accepts 2.2 at 0677b094f.

## Why

- Maximum miner freedom: 2.2 offers both the graph route and the catalog route.
- No miner could practise Battery before this, because the registered 1.0 serves no catalog and its examples are refused.
