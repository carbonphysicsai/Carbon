# OPT-15c 25-axis synthetic stress readout (development diagnostic)

Sixteen analytic toy configurations were drawn from the 25-axis example at
plan digest `15cdfec87cecad30c7f4f8db66bfd257cb8a8f60da575da614a3c54c7be95f22`
and candidate-file digest `157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`.
Two complete, non-overlapping eight-profile shards produced 1,120 candidate ×
physics-switch rows. Measured local WSL CPU was 96.43 s for shard 0 and
139.67 s for shard 1 (236.10 s total); no solver, pod, EV4 label, sealed bank,
or Test Engineer holdout was accessed.

Every candidate proxy's OFF-switch worst-profile neighbourhood-blend Kendall
τ was negative. Among candidates with all 16 τ values estimable, OFF-switch
median τ ranged from −0.200 to +0.067. The in-force proxy had only five
estimable values, so its median is not comparable to a complete candidate.
This result demonstrates fragility **under these toy assumptions**. It does
not select a score, set a threshold, or establish a real Challenge effect.

The descriptive atlas is `BROAD_ATLAS_16.json.gz` (SHA-256
`5c7e8d2d69fe53212bcb6767e67e191a5b0fd1b555cca34ec0e92827972d5625`).
The replay inputs are `BROAD_PLAN_S0.json.gz`
(`c8000e237e9d38ef85fbeb6117c782dfc13fc7c17c63709dc37b75ebe3c80dfe`)
and `BROAD_PLAN_S1.json.gz`
(`ad05a12a17541b89b3af7e66cf1a106af128d82d7b83add37e416dbfa118fde0`).
The raw synthetic outputs are `BROAD_SWEEP_S0.json.gz`
(`b644c9d18e6e6cd185dcc7d0e7d5c0cbeed4f0a3255bf9d8395555de3391f2fa`)
and `BROAD_SWEEP_S1.json.gz`
(`12ae3ed5c13d0652fd4783dc24d484470932afdfb9ab7b4d96f86b09f9ec7432`).
The atlas contains exploratory LHS axis associations, not Sobol indices. The
one-dimensional toy still omits several §2 task families; the 142-member
realism calibration, D3-dependent EV4 fitting, tier-2 replay, and independent
final holdout remain outstanding.
