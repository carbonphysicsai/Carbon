# Read-only owner inputs

The owner explicitly supplied Windows copies at
`codex-queue/inputs/margin-sizing-01/` and stated they use the **200 public
PRACTICE cases as stand-ins for the private bank**. Research accepted that public
scope; it did not read private bank material or AX42. The original WSL route
was unavailable. The copied directory is not part of this PR and was not edited.

These immutable content fingerprints identify exactly what was reviewed.
Citations I1–I14 in REVIEW refer to these documents/functions/JSON fields, not
to claims that their private-bank predictions have been independently validated.
No source paths beyond the owner-approved files were followed or executed.

| ID | Input | Bytes | SHA-256 |
|---|---|---:|---|
| I1 | MARGIN_SIZING_02.md | 6921 | a73da558d7c5a704fa317b7085d077b006d26f7ac9dd2e89acb013fec5d893ea |
| I2 | MARGIN_SIZING_03.md | 4727 | 2e5ce65e24a1af5dade1966790a870a480887a34945088a3fd0732a221f9db11 |
| I3 | MARGIN_SIZING_04.md | 5531 | af4e5209f7165e7b35f185d10e67cdfd38ad19931fb0cb68857fbf81e8ab8a1c |
| I4 | PROPOSAL.md | 5772 | 8a35185b4c66254c6c1b8f1a4a43bd38470b816f1cc4d2ca54adb46870df9a0e |
| I5 | margin_02.json | 8262 | 57256baa1141838fbecfcfb108e400a140f5b0a894cc891e69217c0c8d002aae |
| I6 | margin_03.json | 11889 | 4b74b628920c41692e2de9fc48340070ee17b842c108d88dcace2118bbbd4f43 |
| I7 | margin_04.json | 11203 | 61583cd7aa0b33496b4d09684611e0eb2745acb96c770b5dd13c53c784a04198 |
| I8 | analysis.json | 4782 | 7c55d01faab9bec2759c6f068d92fd50ebd97fd4b4fd412dc793200d90a47798 |
| I9 | paired.json | 1995 | bd94c4d1c33bad766fbdd80da3c7eb153a435a0754cae391880762d1a30a68a2 |
| I10 | m04.py | 3691 | 4831f3e2834b580776e2c61806b848b18b66eaf01541e76aa99cb5755c30d62a |
| I11 | margin_02.py | 4396 | adc73240c1d960489a9a68fa3ada6986d652548bed9c7f00f1e8e994f4a7d174 |
| I12 | margin_03.py | 2952 | 643e89d4449d6a05dbaa9e442722ad99d20ee9a9b6f3645cc7cdf54b61d33ebe |
| I13 | margin_sizing.py | 6011 | 689f4c64ea1baee8587172ee5941149ade6c65d4af35b05ef68b57385e1fd65c |
| I14 | paired.py | 1893 | ea9b23eabeab2108f058d8cb6161462a5d7fccb0ffd60ca9c43963f08ad95e44 |

I9 contains six pair summaries and four same-recipe/different-seed summaries,
not raw per-case arrays. I14 reads `seed-variance-01/rows.jsonl` on its original
WSL path, which is not in the supplied set. The owner was asked for a permitted
copy of those public rows. Until supplied, distribution/tail/block validation
is an explicit gap. I9's correlation is **between two models on the same cases**;
it is not measured between-round dependence.

The audit output stores these fingerprints, reproduced counts and synthetic
aggregate diagnostics only. Public simulation seeds 3 and 731 are typed as
synthetic; no official seed, case identifier or protected sample is published.
The review's numerical inputs are sourced fixed points or labeled assumptions;
its Wilson intervals concern independent Monte Carlo paths only.
