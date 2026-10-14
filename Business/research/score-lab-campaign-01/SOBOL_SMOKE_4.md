# Pick-and-freeze sensitivity: plumbing smoke only

The separate Sobol path generated four matched A/B base pairs with six assumed
error-structure axes. For each pair it evaluated A, B and the six A-with-one-B
hybrids against the N1 toy proxy. The result is a raw Saltelli first-order and
Jansen total-order index for the toy neighbourhood-blend Kendall tau. All
cases were analytic synthetic development fixtures; no Challenge references
or held-out material entered the run.

Four pairs are far too few for interpretable sensitivity. The raw estimates
include a negative first-order index (-0.438 for tail rate), as finite-sample
estimators may. They are never clipped or treated as owner guidance. The
purpose of this run was to verify the estimator and complete-shard contract.
The complete aggregate is `SOBOL_SMOKE_4.json.gz`
(`sha256:c2c329c145e88c25864745a1174c70ca7990e1690ada4f81585a62645da133bc`),
bound to plan `sha256:7c2b054d7c121ae923fd617d7b995c0c3d2f47eb2bcf9cbb29f2927d8979c99f`
and candidate file
`sha256:157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`.
