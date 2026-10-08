"""Battery's Level 4 attack adapter: graph-only submissions (LEVEL4-DEV-VARIANT-01).

The Level 4 surface is the registered development-only variant
`battery-l4-graph-v1` (`carbon.battery.level4`): a miner's model as a math
graph, judged by `carbon.level4`'s gates. This adapter attacks it with the
proposal's §8 suite (`docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md`),
one family per Track A check. Attack design and dispositions are the Test
Lead's; this module supplies the boundaries and the evidence.

* **The real boundary** of every graph family is Carbon's own: the strict
  parse (G3), validation (G4: allowlist, roles, named functions, init data
  flow, interface, caps) and the rebuild (`carbon.level4.interpret`). It
  answers OK or REFUSED with a typed code.
* **The vulnerable specimen** is a boundary that enforces nothing (plain
  `json.loads`), so a family whose specimen does not accept its attacks has
  a broken detector, never a pass (`family_oracle`).
* **Caps** are `carbon.level4.specimens.FIXTURE_CAPS`, test values only;
  every real cap stays HUMAN_INPUT.
* **The attacks are generated** from the shipped allowlist (every refused
  op) and the Level 4 specimens, so the families follow what Carbon refuses.
* **Rebuild** compiles a strategy under the variant to its graph record. No
  graph is compiled or trained here: G5's profile is accepted for development
  and testnet (OWNER-L4-G5-COMPILE-ISOLATION-01), but a record names only the
  submission's digest and no transport stages its documents into the rebuild
  worker yet; the rebuild label says so.

Nothing here is served to a miner, and nothing runs participant code.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping

from carbon.agent_campaign.attack import engine
from carbon.agent_campaign.attack.adapter import (
    Control,
    family_oracle,
    seam_oracle,
)
from carbon.agent_campaign.attack.adapters import battery as b

CHALLENGE_ID = b.CHALLENGE_ID
LEVEL = 4
PROFILE = "level-4"
ADAPTER_VERSION = "carbon.attack.adapter.battery-l4.v1"
CONTROLS_VERSION = "carbon.attack.controls.battery-l4.v1"
SPLITS = b.SPLITS
#: The parser bound of this adapter's own checks; not a G3 limit.
MAX_BYTES = 1 << 26


def _graph_refused():
    from carbon.level4 import graph

    return graph.GraphRefused


@functools.lru_cache(maxsize=1)
def _allowlist():
    from carbon.level4 import allowlist

    return allowlist.load()


def variant():
    from carbon.reconstruction import development_variants as dv

    return dv.variant(CHALLENGE_ID, LEVEL)


def _rebuild_label():
    from carbon.battery import level4_worker

    return level4_worker.REBUILD_LABEL


# -- boundaries --------------------------------------------------------------------


def _interface():
    from carbon.level4 import validate

    return validate.Interface(
        inputs=(("inputs/x", "float32", (3,)),), outputs=(("float32", (2,)),)
    )


def carbon_gates(value):
    """Carbon's G3, G4 and rebuild on one document: OK or REFUSED."""
    from carbon.level4 import graph, interpret, specimens, validate

    allowlist = _allowlist()
    try:
        doc = graph.parse(value["document"].encode(), max_bytes=MAX_BYTES)
        interface = _interface() if value.get("interface") else None
        validate.validate(
            doc, allowlist, interface=interface, caps=specimens.FIXTURE_CAPS
        )
        interpret.rebuild(doc, allowlist)
    except _graph_refused() as refused:
        return {"status": "REFUSED", "code": refused.code, "where": refused.where}
    return {"status": "OK"}


def unchecked_gate(value):
    """The vulnerable specimen: a boundary that enforces nothing, so it
    accepts every document, parseable or not."""
    del value
    return {"status": "OK"}


def miner_contract_gate(strategy):
    """The miner-facing Level 0 contract on a strategy naming a graph."""
    from carbon.reconstruction.challenge_contracts import (
        SubmissionRefused,
        compile_submission,
    )

    try:
        compile_submission(strategy)
    except SubmissionRefused as refused:
        return {"status": "REFUSED", "code": type(refused).__name__}
    return {"status": "OK"}


def variant_gate(strategy):
    """The development variant on a strategy (the ablation's specimen)."""
    from carbon.reconstruction import development_variants as dv

    try:
        dv.compile_development(strategy, variant())
    except dv.VariantRefused as refused:
        return {"status": "REFUSED", "code": refused.code}
    return {"status": "OK"}


def _accepted(result):
    return result["status"] == "OK"


# -- attack inputs -----------------------------------------------------------------


def _doc_value(doc, **extra):
    from carbon.level4 import graph

    return {"document": graph.dumps(doc).decode(), **extra}


def _lowered(fn, args, role, names):
    from carbon.level4.tooling import lower_jax

    closed = lower_jax.trace(fn, *args)
    return lower_jax.lower(closed, role=role, allowlist=_allowlist(), input_names=names)


@functools.lru_cache(maxsize=1)
def _honest():
    """Two honest forward graphs and one honest init graph."""
    import jax
    import jax.numpy as jnp

    from carbon.level4 import specimens

    small = specimens._small_document(_allowlist())
    w1, w2 = jnp.ones((3, 8)), jnp.ones((8, 2))
    deeper = _lowered(
        lambda a, b2, x: jax.nn.softplus(x @ a) @ b2,
        (w1, w2, jnp.ones((4, 3))),
        "forward",
        ["params/0", "params/1", "inputs/x"],
    )
    init = _lowered(
        lambda key: [jax.random.normal(key, (3, 2)), jnp.zeros(2)],
        (jax.random.PRNGKey(0),),
        "init",
        ["carbon/key"],
    )
    interfaced = _lowered(
        lambda a, x: jnp.tanh(x @ a),
        (jnp.ones((3, 2)), jnp.ones((4, 3))),
        "forward",
        ["params/0", "inputs/x"],
    )
    return {"small": small, "deeper": deeper, "init": init, "interfaced": interfaced}


def _swap(op):
    import copy

    doc = copy.deepcopy(_honest()["small"])
    node = next(n for n in doc["graphs"]["main"]["nodes"] if n["op"] == "tanh")
    node.update(op=op, params={})
    return _doc_value(doc)


def _program_docs(labels):
    """Documents lowered from the specimen programs named `labels`."""
    from carbon.level4 import specimens

    out = []
    for (
        section,
        family,
        specimen,
        (kind, payload),
        _expected,
    ) in specimens._attack_rows():
        if family in labels and kind == "program":
            fn, args, role = payload
            names = (
                ["carbon/key"]
                if role == "init"
                else [f"inputs/{i}" for i in range(len(args))]
            )
            out.append((specimen, _doc_value(_lowered(fn, args, role, names))))
    return out


def _escape_attacks():
    refused = sorted(
        name for name, e in _allowlist().ops.items() if e["default"] == "refuse"
    )
    return tuple((f"op_{name}", _swap(name)) for name in refused)


def _constant_attacks():
    rows = _program_docs(
        {
            "Model loaders, hidden assets",
            "Embedded weights or tables",
            "Constant splitting",
        }
    )
    return tuple((f"constants_{i}", v) for i, (_, v) in enumerate(rows))


def _compute_attacks():
    rows = _program_docs({"Compile bomb"})
    return (("while_loop", _swap("while")),) + tuple(
        (f"compile_bomb_{i}", v) for i, (_, v) in enumerate(rows)
    )


def _rng_state_attacks():
    import copy

    init = copy.deepcopy(_honest()["init"])
    rng_forward = dict(copy.deepcopy(init), role="forward")
    rng_loss = dict(copy.deepcopy(init), role="loss")
    rows = _program_docs(
        {"Caches, checkpoints, cross-attempt residue", "Initializer abuse"}
    )
    return (
        ("rng_in_forward", _doc_value(rng_forward)),
        ("rng_in_loss", _doc_value(rng_loss)),
    ) + tuple((f"init_{i}", v) for i, (_, v) in enumerate(rows))


def _interface_attacks():
    import jax.numpy as jnp

    widened = _lowered(
        lambda a, x: jnp.concatenate([jnp.tanh(x @ a), (x @ a)[:, :1] * 1e-7], axis=1),
        (jnp.ones((3, 2)), jnp.ones((4, 3))),
        "forward",
        ["params/0", "inputs/x"],
    )
    return (("extra_output_column", _doc_value(widened, interface=True)),)


def _integrity_attacks():
    from carbon.level4 import specimens

    return tuple(
        (label.replace(" ", "_").replace("-", "_"), {"document": raw.decode("latin-1")})
        for label, raw, _code in specimens.document_specimens(_allowlist())
    )


def _strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE_ID,
        "backbone": "mlp",
        "parameters": {"width": 16, "depth": 1, "steps": 16, **parameters},
    }


def _ablation_attacks():
    from carbon.battery import level4

    return (
        ("graph_slot_at_level_0", _strategy(**{level4.FIELD: "sha256:" + "ab" * 32})),
    )


# -- families, controls, seams --------------------------------------------------


@functools.lru_cache(maxsize=1)
def _family_table():
    """name -> (check, protocol boundary words, attacks, boundary, specimen,
    trained control input, held-out control input)."""
    honest = _honest()
    small, deeper = _doc_value(honest["small"]), _doc_value(honest["deeper"])
    return {
        "l4_escape_ops": (
            "construction_evaluation_isolation",
            "no op that escapes to Python, native code, the host or another device reaches a graph",
            _escape_attacks,
            carbon_gates,
            unchecked_gate,
            small,
            deeper,
        ),
        "l4_constant_smuggling": (
            "artifact_and_dependency_attacks",
            "embedded constants are counted after pruning against the constant cap (a fixture here)",
            _constant_attacks,
            carbon_gates,
            unchecked_gate,
            small,
            deeper,
        ),
        "l4_unbounded_compute": (
            "resource_and_failure_accounting",
            "no data-dependent loop; call depth and size within the caps (fixtures here)",
            _compute_attacks,
            carbon_gates,
            unchecked_gate,
            small,
            deeper,
        ),
        "l4_rng_state_and_init": (
            "adaptive_feedback_and_state_attacks",
            "keyed RNG only in init, from Carbon's key; every init output key-derived or a uniform fill",
            _rng_state_attacks,
            carbon_gates,
            unchecked_gate,
            _doc_value(honest["init"]),
            small,
        ),
        "l4_interface_abuse": (
            "score_exploitation_and_tail_failures",
            "outputs exactly the Challenge interface's dtypes and per-case shapes",
            _interface_attacks,
            carbon_gates,
            unchecked_gate,
            _doc_value(honest["interfaced"], interface=True),
            _doc_value(honest["small"]),
        ),
        "l4_document_integrity": (
            "reconstruction_and_recipient_rebuild",
            "strict JSON, declared shapes checked on rebuild, pinned allowlist version, no cycles",
            _integrity_attacks,
            carbon_gates,
            unchecked_gate,
            small,
            deeper,
        ),
        "l4_graph_slot_ablation": (
            "baseline_and_permission_ablation",
            "the graph slot is refused by the miner-facing contract; only the variant admits it",
            _ablation_attacks,
            miner_contract_gate,
            variant_gate,
            _strategy(),
            _strategy(width=32, depth=2),
        ),
    }


SEAMS = (
    (
        "l4_fresh_cases_rerun",
        "fresh_attack_confirmation",
        "fresh cases need Phase 3 live runs through the Launchpad (owner, 2026-10-07)",
    ),
    (
        "l4_compile_isolation",
        "construction_evaluation_isolation",
        "G5 compile in isolation: the profile is accepted for development and "
        "testnet (OWNER-L4-G5-COMPILE-ISOLATION-01); no adversarial compile runs "
        "here, and mainnet needs its security review",
    ),
    (
        "l4_procedural_tables",
        "score_exploitation_and_tail_failures",
        "a few constants plus arithmetic regenerate a table: unblockable by graph checks (D4, Track B)",
    ),
    (
        "l4_compute_under_counting",
        "resource_and_failure_accounting",
        "runtime far above the compiled count: R6 stress and the R7 safety net (Phase 4)",
    ),
    (
        "l4_gpu_nondeterminism",
        "reconstruction_and_recipient_rebuild",
        "review ops (gather, sort) and named functions on GPU: the A40 R1 leg",
    ),
    (
        "l4_nonfinite_outputs",
        "score_exploitation_and_tail_failures",
        "outputs typed by the exam's gates at G7 (tests/cpu/test_level4_grade.py); "
        "no training runs here until the submission's documents reach the rebuild worker",
    ),
)


class BatteryLevel4Adapter(b.BatteryLevel0Adapter):
    """Battery at construction Level 4 (the registered graph-only development
    variant), for the attack engine."""

    challenge_id = CHALLENGE_ID
    level = LEVEL
    version = ADAPTER_VERSION
    controls_version = CONTROLS_VERSION
    deterministic_baseline = None

    @property
    def contract_digest(self):
        from carbon.battery import level4
        from carbon.reconstruction import capability_registry as cr

        try:
            return cr.development_variant_registry()["versions"][level4.VERSION]
        except (RuntimeError, KeyError):
            return "sha256:" + "0" * 64

    def _engine(self, name):
        check, words, attacks, boundary, specimen, trained, _ = _family_table()[name]
        return engine.Family(
            name=name,
            check=check,
            boundary=boundary,
            attacks=attacks,
            specimen=specimen,
            breached=_accepted,
            control=lambda: _accepted(boundary(trained)),
            description=words,
        )

    def families(self):
        out = []
        for name, (check, words, attacks, *_rest) in _family_table().items():
            first = attacks()[0]
            out.append(
                b.FamilyDef(
                    name=name,
                    check=check,
                    boundary=words,
                    attack_example=first[0],
                    control_example=f"{name}_trained",
                    family=self._engine(name),
                )
            )
        return tuple(out)

    def controls(self, split):
        if split not in SPLITS:
            raise ValueError("split is trained or held_out")
        out = []
        for name, (
            _c,
            _w,
            _a,
            boundary,
            _s,
            trained,
            held_out,
        ) in _family_table().items():
            value = trained if split == "trained" else held_out
            out.append(
                Control(
                    name=f"{name}_{split}",
                    family=name,
                    split=split,
                    version=CONTROLS_VERSION,
                    check=lambda v=value, g=boundary: _accepted(g(v)),
                    input_digest=b._digest(value),
                )
            )
        return tuple(out)

    def oracle(self, family, attempt):
        if family in _family_table():
            return family_oracle(self._engine(family), attempt)
        for seam in self.level_families():
            if seam.name == family:
                return seam_oracle(seam, attempt)
        raise ValueError("oracle_for_an_unknown_family: " + str(family))

    def level_families(self):
        return tuple(
            b.SeamFamily(name=name, check=check, level=LEVEL, reason=reason)
            for name, check, reason in SEAMS
        )

    def rebuild(self, construction):
        """The strategy compiled under the variant to its graph record. No
        graph is compiled or trained here (the documents are not staged)."""
        from carbon.reconstruction import development_variants as dv

        strategy = construction
        if isinstance(construction, Mapping) and "strategy" in construction:
            strategy = construction["strategy"]
        if b._protected(strategy):
            return b.Unrebuildable(
                code="protected_material", detail="protected_material_named"
            )
        try:
            found = dv.compile_development(strategy, variant())
        except dv.VariantRefused as refused:
            issues = sorted({str(i[0]) for i in refused.issues})
            core = (
                "outside_level"
                if b.OUTSIDE_LEVEL_ISSUES & set(issues)
                else "refused_by_contract"
            )
            return b.Unrebuildable(
                code=core,
                detail=refused.code + (": " + ", ".join(issues) if issues else ""),
            )
        except Exception as failure:  # noqa: BLE001 - Carbon's own, never scored
            return b.Unrebuildable(
                code="rebuild_failed_infra", detail=type(failure).__name__
            )
        return b.Rebuilt(
            construction_digest=b._digest(strategy),
            rebuilt_digest=b._digest(found.reconstruction),
            detail={
                "record": found.reconstruction,
                "served": True,
                "rebuild": _rebuild_label(),
            },
        )

    def permission_inventory(self):
        """Level 0's inventory with the variant's Level 4 permission added."""
        inventory = dict(super().permission_inventory())
        found = variant()
        inventory["profile"] = PROFILE
        inventory["development_variant"] = found.digest
        inventory["permitted"] = list(inventory["permitted"]) + [
            {
                "id": w.capability_id,
                "surface": None,
                "applies_to": [],
                "planning_level": 4,
            }
            for w in found.widened
        ]
        inventory["not_permitted"] = [
            p
            for p in inventory["not_permitted"]
            if (p.get("id") if isinstance(p, Mapping) else p) not in found.permissions()
        ]
        return inventory

    def admission_refusals(self, construction):
        made = self.rebuild(construction)
        if isinstance(made, b.Rebuilt):
            return []
        return [self.carbon_code(made)] + [made.code]

    def surface(self):
        found = variant()
        return {
            "challenge": CHALLENGE_ID,
            "level": LEVEL,
            "profile": PROFILE,
            "contract_digest": self.contract_digest,
            "variant_version": found.version,
            "permissions": list(found.permissions()),
            "adapter_version": ADAPTER_VERSION,
            "rebuild": _rebuild_label(),
        }


ADAPTER = BatteryLevel4Adapter()
