# CI-QUALITY-REPAIR-01 — restore canonical quality after public research merge

**Trigger:** Canonical CI shard 0 for VERIFY-AWARE-SCORE-CODE-01 PR #1094
found three new Ruff diagnostics and two Black debt entries in the separately
merged `Business/research/question-resolution-rate/` research files.
The source commit is `63322f630`. This repair changes only those two public
Python files' import ordering, one unused import, and Black formatting.

The analysis, source pins, results and scientific interpretation remain
unchanged. The research's own synthetic/public test is the focused regression.
This is a prerequisite repository hygiene repair, not part of VERIFY-R's
scoring implementation and not a scientific decision. One separate PR to
main, with no hidden material, solver run, spend or LIVE change. The
Development Hub is retired under OWNER-WORKFLOW-SPEED-01.
