# Prospective graph-v4 recipe fields

`battery-l4-graph-v4` is the explicitly selected DEVELOPMENT arm
`inert_fields`. V3 remains the default, registered at its original digest;
existing v3 submissions keep their interpretation and resolution.

With `parameters.composition_graphs`, v4 refuses any explicitly supplied
`width` or `depth`: `level4_field_inert:width` / `level4_field_inert:depth`,
with the corresponding `/parameters/<field>` issue. The submitted graph
sets the network, so these values would be dead controls. Both fields are
still permitted on ordinary non-graph recipes and under historical v3.

Select the prospective arm internally with:

```python
from carbon.battery.level4_v4 import starter_recipe
from carbon.reconstruction.development_variants import variant

policy = variant("battery-fastcharge-ageing-development-v1", 4, arm="inert_fields")
recipe = starter_recipe()
```

Stage the graph through the existing interface and put its digest in
`recipe["parameters"]["composition_graphs"]`. The v4 recipe omits width/depth;
ordinary compiler defaults still fill settings, while the graph remains the
trained network. Steps and other active training settings retain their
existing behavior. No pinned battery implementation, v3 policy, graph gate,
allowlist, constant/resource cap, compute budget or grading rule changes.

The exact inherited regression from WSL-local source 5e6300b6d exercises the
legacy property by training one public-TRAIN graph under different recipe
width/depth, omitted fields and doubled steps. The changed-steps negative
control prevents interpreting a non-running trainer as ignored fields.
Those CPU tests establish implementation behavior, not scientific validity.

This arm is never served to miners by registration alone. It does not select
a live migration, deployment, grant, security acceptance or qualification.
