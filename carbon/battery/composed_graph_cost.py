"""Bound supplemental composed-graph costs produced in the isolated G5 lane.

The consumer validates metadata only. It never prepares or compiles a graph.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

SCHEMA = "carbon.battery.composed-graph-cost.v1"
UNPRICED = "cost_composed_part_unmeasured"
OPAQUE = frozenset({"svd", "eig", "eigh", "qr", "lu", "cholesky", "while"})


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def g5_digest(result):
    from carbon.training_budget.cost import CostRefused

    try:
        return digest(
            {
                k: v
                for k, v in result.items()
                if k not in {"composed_profile", "composed_workspace"}
            }
        )
    except (TypeError, ValueError):
        raise CostRefused("cost_profile_g5_invalid", "composition_graphs") from None


def binding(recipe, record):
    if not isinstance(recipe, dict):
        recipe = {
            "recipe_digest": recipe.recipe_digest,
            "family": recipe.family,
            "settings": recipe.settings,
        }
    return digest(
        {
            "recipe_digest": recipe["recipe_digest"],
            "family": recipe["family"],
            "settings": recipe["settings"],
            "record": record,
        }
    )


def _program(record):
    from . import development_rebuild
    from .worker import RECONSTRUCT_PROGRAM

    source, files, _ = development_rebuild.stage(
        record, RECONSTRUCT_PROGRAM, {}, level1_program=lambda: 1 / 0
    )
    anchor = '    stats = model.fit(train, structure, recipe["seed"])\n'
    if source.count(anchor) != 1:
        raise RuntimeError("the reconstruct fit line moved")
    replacement = r"""    for _package in ("carbon.training_budget",):
        _module = _types.ModuleType(_package)
        _module.__path__ = []
        sys.modules[_package] = _module
    for _name in ("carbon.level4.compile", "carbon.training_budget.adapter", "carbon.training_budget.cost"):
        _spec = _util.spec_from_file_location(_name, work / (_name + ".py"))
        _module = _util.module_from_spec(_spec)
        sys.modules[_name] = _module
        _spec.loader.exec_module(_module)
    shutil.copyfile(work / "battery-composed-cost.py", lab / "composed_graph_cost.py")
    from carbon_battery_lab import composed_graph_cost
    context = json.loads((work / "composed-cost-context.json").read_text())
    record = json.loads((work / "composed-cost-record.json").read_text())
    from carbon.training_budget.cost import CostRefused
    try:
        result = composed_graph_cost._worker_measure(model, train, structure, recipe, record, context)
    except CostRefused as refused:
        result = {"schema": composed_graph_cost.SCHEMA, "status": "REFUSED", "binding": composed_graph_cost.binding(recipe, record), **context, "code": composed_graph_cost.UNPRICED, "field": "composition_graphs", "reason": refused.code}
    (out / "cost-profile.json").write_text(json.dumps(result, sort_keys=True, allow_nan=False))
    raise SystemExit(0)
"""
    return source.replace(anchor, replacement), files


def _algorithms(record):
    from .worker import _code_files

    source, files = _program(record)
    files.update(_code_files())
    carbon = Path(__file__).resolve().parents[1]
    files.update(
        {
            "battery-composed-cost.py": Path(__file__).read_bytes(),
            "carbon.training_budget.adapter.py": (
                carbon / "training_budget" / "adapter.py"
            ).read_bytes(),
            "carbon.training_budget.cost.py": (
                carbon / "training_budget" / "cost.py"
            ).read_bytes(),
            "carbon.level4.compile.py": (carbon / "level4" / "compile.py").read_bytes(),
        }
    )
    code = {
        name: hashlib.sha256(raw).hexdigest()
        for name, raw in files.items()
        if name.endswith(".py")
    }
    return source, files, digest({"program": source, "algorithms": code})


def require_g5(result):
    from carbon.training_budget.cost import CostRefused

    if type(result) is not dict:
        raise CostRefused("cost_level4_graph_pending", "composition_graphs")
    value = result.get("train_step_flops")
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise CostRefused("cost_level4_graph_unmeasured", "composition_graphs")


def _verified(workspace, record):
    from carbon.level4 import allowlist, intake, staging, submission
    from carbon.level4 import compile as g5

    from .level4_model import CHALLENGE

    raw, files = staging.from_workspace(workspace, record["graph"]["submission"])
    declared = json.loads(raw)
    loaded = allowlist.load()
    _, parsed = submission.verify(
        raw,
        files,
        allowlist=loaded,
        challenge=CHALLENGE,
        interface=declared["interface"],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    if record["expression"] is not None and "loss" in parsed:
        from carbon.training_budget.cost import CostRefused

        raise CostRefused(
            "construction_rebuild_unavailable", "loss_expressions+composition_graphs"
        )
    return raw, files, parsed, g5.input_digest(parsed, loaded)


def _objective(record, parsed):
    return (
        "graph"
        if "loss" in parsed
        else ("expression" if record["expression"] is not None else "default")
    )


def _names(closed, cost):
    names = set()
    for eqn in closed.jaxpr.eqns:
        names.add(eqn.primitive.name)
        for sub in cost._subjaxprs(eqn):
            names.update(_names(sub, cost))
    return names


def _worker_measure(model, train, structure, recipe, record, context):
    """Keep capture and all subsequent compilation in the recipe's precision."""
    import jax

    with jax.enable_x64(recipe["settings"]["precision"] == "float64"):
        return _measure_precision(model, train, structure, recipe, record, context)


def _measure_precision(model, train, structure, recipe, record, context):
    """Private fixed-worker implementation; the caller owns precision scope."""
    import jax
    import jax.numpy as jnp

    from carbon.level4 import allowlist, intake, submission
    from carbon.level4 import compile as g5
    from carbon.training_budget import cost

    from . import composed_training, level3_numerics
    from .level4_model import CHALLENGE

    seen = []
    original = composed_training.train

    def capture_train(**kwargs):
        seen.append(kwargs)
        return original(**kwargs)

    composed_training.train = capture_train
    try:
        closed, args = cost._capture(
            lambda steps: model.fit(train, structure, recipe["seed"]),
            recipe["settings"]["steps"] - recipe["settings"]["polish_steps"],
        )
    finally:
        composed_training.train = original
    if len(seen) != 1:
        raise cost.CostRefused(UNPRICED, "composition_graphs:training_program")
    loaded = allowlist.load()
    _, parsed = submission.verify(
        model.raw_manifest,
        model.files,
        allowlist=loaded,
        challenge=CHALLENGE,
        interface=model._interface().digest(),
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    input_hash = g5.input_digest(parsed, loaded)
    if (
        context["input_digest"] != input_hash
        or context["submission"] != model.submission
        or context["objective"] != _objective(record, parsed)
    ):
        raise cost.CostRefused("cost_profile_identity_mismatch", "composition_graphs")
    opaque = _names(closed, cost) & OPAQUE
    if opaque:
        field = (
            "muon_spectral"
            if opaque == {"svd"} and record["spectral"] is not None
            else "composition_graphs"
        )
        return {
            "schema": SCHEMA,
            "status": "REFUSED",
            "binding": binding(recipe, record),
            **context,
            "code": UNPRICED,
            "field": field,
            "reason": "+".join(sorted(opaque)),
        }
    loops = cost._loops(closed)
    if len(loops) != 1:
        raise cost.CostRefused(UNPRICED, "composition_graphs:training_loops")
    (loop,) = loops
    expected_steps = recipe["settings"]["steps"] - recipe["settings"]["polish_steps"]
    if loop.params["length"] != expected_steps:
        raise cost.CostRefused(UNPRICED, "composition_graphs:step_count")
    body = loop.params["jaxpr"]
    main_flops = cost._xla_flops(body) + cost._extra(body)
    params = args[0]
    count = sum(math.prod(p.shape) for p in jax.tree_util.tree_leaves(params))
    kwargs = seen[0]
    cases = kwargs["f"].shape[0]
    batch = min(recipe["settings"]["batch_size"], cases)
    polish_flops = gradient = loss_dtype = None
    if record["numerics"] is not None:
        objective = composed_training.loss_program(
            jax=jax,
            **{
                name: kwargs[name]
                for name in (
                    "apply",
                    "f",
                    "z",
                    "sw",
                    "gw",
                    "trajectory",
                    "settings",
                    "order",
                    "case_loss",
                    "objective",
                )
            },
        )
        full = jax.make_jaxpr(
            jax.value_and_grad(
                lambda p: objective(p, jnp.arange(cases), expected_steps)
            )
        )(params)
        opaque = _names(full, cost) & OPAQUE
        if opaque:
            return {
                "schema": SCHEMA,
                "status": "REFUSED",
                "binding": binding(recipe, record),
                **context,
                "code": UNPRICED,
                "field": "composition_graphs",
                "reason": "+".join(sorted(opaque)),
            }
        loss_dtype = str(full.out_avals[0].dtype)
        gradient = cost._xla_flops(full) + cost._extra(full)
        numerics = record["numerics"]
        polish_flops = gradient * level3_numerics.evaluations_per_step(
            numerics["line_search"]
        )
        if numerics["routine"] in level3_numerics.DENSE:
            polish_flops += 4 * count * count  # existing registered L3 convention
    return {
        "schema": SCHEMA,
        "status": "MEASURED",
        "binding": binding(recipe, record),
        **context,
        "main_step_flops": main_flops,
        "polish_step_flops": polish_flops,
        "polish_gradient_flops": gradient,
        "polish_loss_dtype": loss_dtype,
        "parameter_count": count,
        "batch_size": batch,
        "precision": recipe["settings"]["precision"],
    }


def compile_in_isolation(
    compiled,
    workspace,
    g5_result,
    *,
    ledger,
    owner,
    image,
    scope,
    runner=None,
    root=None,
):
    from carbon.level4 import compile as g5
    from carbon.level4 import staging

    from .worker import reconstruct_files

    if scope not in g5.SCOPES:
        raise g5.CompileBlocked(g5.MAINNET_BLOCKED)
    require_g5(g5_result)
    record = compiled.record
    raw, graph_files, parsed, input_hash = _verified(workspace, record)
    if (
        g5_result.get("input_digest") != input_hash
        or g5_result.get("image") != image
        or g5_result.get("scope") != scope
    ):
        from carbon.training_budget.cost import CostRefused

        raise CostRefused("cost_profile_g5_mismatch", "composition_graphs")
    source, files, algorithm_hash = _algorithms(record)
    files.update(
        reconstruct_files(
            Path(root) if root is not None else Path(__file__).resolve().parents[2],
            compiled.construction,
            0,
        )
    )
    files.update(staging.workspace(raw, graph_files))
    context = {
        "input_digest": input_hash,
        "g5_digest": g5_digest(g5_result),
        "submission": record["graph"]["submission"],
        "source_digest": algorithm_hash,
        "image": image,
        "scope": scope,
        "objective": _objective(record, parsed),
    }
    files["composed-cost-context.json"] = json.dumps(context, sort_keys=True).encode(
        "utf-8"
    )
    files["composed-cost-record.json"] = json.dumps(record, sort_keys=True).encode(
        "utf-8"
    )
    identity = (
        "level4-composed-cost-"
        + digest(
            {
                "source": source,
                "files": {n: hashlib.sha256(b).hexdigest() for n, b in files.items()},
                "image": image,
            }
        )[7:39]
    )
    if runner is None:
        from carbon.development_session.research_carrier import _run as runner
    try:
        worker = runner(
            ledger,
            owner=owner,
            identity=identity,
            source=source,
            files=files,
            image=image,
            seconds=g5.DEADLINE_SECONDS,
            provenance=g5.PROVENANCE,
            extra_resources={},
        )
    except Exception as failure:  # noqa: BLE001 - external lane infrastructure boundary
        from carbon.level4 import graph
        from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

        if isinstance(failure, WorkerFailure):
            if failure.code == WorkerCode.DEADLINE:
                raise graph.GraphRefused("compile_deadline") from None
            if failure.code == WorkerCode.RUNTIME:
                raise graph.GraphRefused("compile_failed") from None
        raise g5.CompileInfraFailure(
            "composed cost lane failed:" + type(failure).__name__
        ) from None
    try:
        profile = json.loads(
            (
                Path(ledger.root)
                / worker["operation"]
                / "snapshot"
                / "cost-profile.json"
            ).read_bytes()
        )
    except (OSError, ValueError, KeyError):
        raise g5.CompileInfraFailure("lane produced no composed cost profile") from None
    return {
        **g5_result,
        "composed_profile": profile,
        "composed_workspace": staging.envelope(raw, graph_files),
    }


def program(recipe, record, g5_result, cases):
    """Host-side metadata validation and arithmetic; no graph execution."""
    from carbon.level4 import compile as g5
    from carbon.level4 import staging
    from carbon.level4.validate import parameters
    from carbon.training_budget.adapter import Program
    from carbon.training_budget.cost import CostRefused

    from . import level3_numerics

    require_g5(g5_result)
    profile = g5_result.get("composed_profile")
    if type(profile) is not dict or profile.get("schema") != SCHEMA:
        raise CostRefused(
            UNPRICED,
            "+".join(
                name
                for name, active in (
                    ("composition_graphs", True),
                    ("loss_expressions", record["expression"] is not None),
                    ("muon_spectral", record["spectral"] is not None),
                    ("quasi_newton_family/line_search", record["numerics"] is not None),
                )
                if active
            ),
        )
    if profile.get("binding") != binding(recipe, record):
        raise CostRefused("cost_profile_binding_mismatch", "composition_graphs")
    envelope = g5_result.get("composed_workspace")
    if type(envelope) is not dict:
        raise CostRefused("cost_profile_workspace_missing", "composition_graphs")
    try:
        declared, raw, files = staging.from_envelope(envelope)
        _, _, parsed, input_hash = _verified(staging.workspace(raw, files), record)
    except CostRefused:
        raise
    except (ValueError, RuntimeError):
        raise CostRefused(
            "cost_profile_workspace_mismatch", "composition_graphs"
        ) from None
    _, _, algorithm_hash = _algorithms(record)
    expected = {
        "input_digest": input_hash,
        "g5_digest": g5_digest(g5_result),
        "submission": declared,
        "source_digest": algorithm_hash,
        "image": g5_result.get("image"),
        "scope": g5_result.get("scope"),
        "objective": _objective(record, parsed),
    }
    if (
        declared != record["graph"]["submission"]
        or g5_result.get("input_digest") != input_hash
        or expected["scope"] not in g5.SCOPES
        or type(expected["image"]) is not str
        or not expected["image"]
        or any(profile.get(k) != v for k, v in expected.items())
    ):
        raise CostRefused("cost_profile_identity_mismatch", "composition_graphs")
    if profile.get("status") == "REFUSED":
        field = profile.get("field")
        if field not in {
            "composition_graphs",
            "muon_spectral",
            "loss_expressions",
            "quasi_newton_family",
            "line_search",
        }:
            raise CostRefused("cost_profile_invalid", "composition_graphs")
        raise CostRefused(UNPRICED, field)
    if profile.get("status") != "MEASURED":
        raise CostRefused("cost_profile_invalid", "composition_graphs")
    settings = recipe.settings
    used = (
        cases
        if settings["train_fraction"] >= 1
        else int(cases * settings["train_fraction"])
    )
    if (
        type(profile.get("batch_size")) is not int
        or profile["batch_size"] != min(settings["batch_size"], used)
        or profile.get("precision") != settings["precision"]
    ):
        raise CostRefused("cost_profile_shape_mismatch", "composition_graphs")
    main, polish = profile.get("main_step_flops"), profile.get("polish_step_flops")
    count = profile.get("parameter_count")
    if (
        type(count) is not int
        or count
        != sum(math.prod(shape) for _, _, shape in parameters(parsed["forward"]))
        or type(main) not in (int, float)
        or not math.isfinite(main)
        or main <= 0
    ):
        raise CostRefused("cost_profile_invalid", "composition_graphs:main_step_flops")
    if polish is not None and (
        type(polish) not in (int, float) or not math.isfinite(polish) or polish < 0
    ):
        raise CostRefused("cost_profile_invalid", "quasi_newton_family/line_search")
    gradient = profile.get("polish_gradient_flops")
    numerics = record["numerics"]
    dense = 0
    factor = None
    if numerics is not None:
        if polish is None or gradient is None:
            raise CostRefused(UNPRICED, "quasi_newton_family/line_search")
        if (
            type(gradient) not in (int, float)
            or not math.isfinite(gradient)
            or gradient < 0
        ):
            raise CostRefused("cost_profile_invalid", "quasi_newton_family/line_search")
        dense = 4 if numerics["routine"] in level3_numerics.DENSE else 0
        gradient_work = gradient * level3_numerics.evaluations_per_step(
            numerics["line_search"]
        )
        if polish != gradient_work + dense * count * count:
            raise CostRefused("cost_profile_invalid", "quasi_newton_family/line_search")
        factor = gradient_work / main
    elif polish is not None or gradient is not None:
        raise CostRefused("cost_profile_invalid", "quasi_newton_family/line_search")
    return Program(
        backend="jax",
        members=1,
        main_steps=settings["steps"] - settings["polish_steps"],
        polish_steps=settings["polish_steps"],
        cases_per_update=profile["batch_size"],
        fit=None,
        parameters=None,
        measured_step_flops=float(main),
        measured_parameters=count,
        polish_factor=factor,
        polish_dense_flops_per_p2=dense,
    )
