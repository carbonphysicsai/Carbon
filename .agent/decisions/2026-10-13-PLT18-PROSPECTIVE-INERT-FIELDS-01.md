# PLT18-D1: keep v3 resolvable; select v4 explicitly

The task's dead controls are width and depth when composition_graphs sets
the trained network. Refuse those fields prospectively, while reusing the
registered graph reconstruction, recipe compiler and worker unchanged.

The development registry's registered() searches current versions and named
arms only. Replacing its level-4 current v3 pointer would make v3 digests
unavailable to existing submissions even if its document stayed pinned.
Register v4 as the named arm `inert-fields`; retain v3 as the default.
This is an internal DEVELOPMENT selection, not miner serving or adoption.

The new pure-data leaf builds v4's policy from v3's existing limits plus an
explicit inert-field declaration, and validates only that exact version.
The generic compiler delegates that check after registered identity and
Challenge checks, before ordinary recipe compilation. Ablation and non-graph
recipes retain their base behavior. A starter recipe drops width/depth;
catalog defaults are reused without changing pinned implementations.

Alternatives rejected: mutating v3 breaks history; changing pinned recipes
breaks their digest; switching current removes live v3 resolution; using
only a notice leaves v4's dead controls accepted. A named arm is reversible:
a later explicit rollout can change current while retaining a legacy arm.
Supersede the new leaf/policy, generic hook and registry entry to change this
working choice. No human-reserved value or scientific threshold is selected.
