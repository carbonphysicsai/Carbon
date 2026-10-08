"""Level 4 measurement runners (development only).

The Phase 0 spike's code now lives in `carbon.level4` (Carbon side) and
`carbon.level4.tooling` (miner side); each Challenge's adapter is
`carbon/<challenge>/level4.py`. What stays here reproduces the recorded
development evidence in `docs/development/graphite/level4/`:

* `run.py`: the Phase 0 record (allowlist v0);
* `run_design.py`: the Phase 1 design record (Q1, Q3);
* `probes.py`: primitive inventories, D6 measurements, serialization probes.

CPU only. No pods, no hidden data, no miner code, no chain, nothing in
`CONTRACTS`. No cap or limit is chosen: they stay `HUMAN_INPUT`.
"""
