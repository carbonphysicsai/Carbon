"""Gate G5: compile a validated graph in isolation (development only).

XLA compiles what Carbon will run on a validated submission: the rebuilt
forward graph, a gradient step through it and the init graph. It does so in
the C-03 Carbon lane (`research_carrier._run`, Carbon provenance), never on
the host that grades. The program is Carbon's own (`PROGRAM`); the
submission's documents enter only as staged data, parsed again inside with
Carbon's strict parser.

Outcomes:

* the lane's deadline elapses: `compile_deadline`, a refusal on the
  submission (a compile bomb);
* the program fails inside the lane (an XLA error or exhausted memory on a
  graph that passed G3 and G4): `compile_failed`, the submission's;
* any other lane failure (no image, no Docker, a staging or cleanup fault):
  `CompileInfraFailure`, `FAILED_INFRA`, never charged to the submission.

The deadline is the owner's (OWNER-L4-VALUES-01, 120 s); a caller that
passes `HUMAN_INPUT` is blocked (`CompileBlocked`). The lane's profile for
this use is accepted for development and testnet only
(OWNER-L4-G5-COMPILE-ISOLATION-01, D3): the caller names its scope, and any
other scope, mainnet included, is blocked until a mainnet security review.
Nothing here is a security claim.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .allowlist import HUMAN_INPUT

#: Approved as proposed (`LEVEL4_VALUES_PROPOSAL.md` §4, OWNER-L4-VALUES-01).
#: The C-03 lane admits Carbon's own runs only between 40 and 600 s.
DEADLINE_SECONDS = 120
PROVENANCE = "LEVEL4_G5_COMPILE_DEVELOPMENT"
PROFILE_STATUS = "ACCEPTED_DEVELOPMENT_AND_TESTNET_ONLY"
PROFILE_DECISION = "OWNER-L4-G5-COMPILE-ISOLATION-01"
#: The scopes the accepted profile covers. Mainnet is not one of them.
SCOPES = ("development", "testnet")
MAINNET_BLOCKED = "mainnet_requires_security_review"
FAILED_INFRA = "FAILED_INFRA"
#: The Carbon modules the lane program needs, staged by name (flat).
MODULES = (
    "carbon.challenge_validator.strict_json",
    "carbon.level4.graph",
    "carbon.level4.params",
    "carbon.level4.allowlist",
    "carbon.level4.named",
    "carbon.level4.interpret",
)

PROGRAM = """
import importlib.util, json, sys, time, types
from pathlib import Path
for package in ('carbon', 'carbon.level4', 'carbon.challenge_validator'):
    module = types.ModuleType(package); module.__path__ = []; sys.modules[package] = module
for name in __MODULES__:
    spec = importlib.util.spec_from_file_location(name, Path(name + '.py'))
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
from carbon.level4 import graph, interpret
from carbon.level4.allowlist import Allowlist
out = Path('/scratch/output') if Path('/scratch/output').is_dir() else Path('..') / 'output'
request = json.loads(Path('request.json').read_bytes())
allowlist = Allowlist(Path('allowlist.json').read_bytes())
docs = {s: graph.parse(Path(s + '.json').read_bytes(), max_bytes=request['max_bytes']) for s in request['slots']}
wide = any(i['dtype'] in ('float64', 'int64', 'uint64') for d in docs.values()
           for g in d['graphs'].values() for i in g['inputs'] + [o for n in g['nodes'] for o in n['out']])
import jax, jax.numpy as jnp
jax.config.update('jax_enable_x64', wide)
forward = interpret.rebuild(docs['forward'], allowlist)
entry = docs['forward']['graphs'][docs['forward']['entry']]
avals = [(i['name'].startswith('params/'), jax.ShapeDtypeStruct(tuple(i['shape']), i['dtype'])) for i in entry['inputs']]
params = [a for is_param, a in avals if is_param]
inputs = [a for is_param, a in avals if not is_param]
def run(p, *xs):
    return forward(*p, *xs)
def step(p, *xs):
    return jax.grad(lambda q: sum(jnp.sum(jnp.real(o).astype(jnp.float32) ** 2) for o in forward(*q, *xs)))(p)
result = {}
started = time.perf_counter()
compiled = jax.jit(run).lower(params, *inputs).compile()
result['forward_seconds'] = time.perf_counter() - started
memory = compiled.memory_analysis()
cost = compiled.cost_analysis() or {}
cost = cost[0] if isinstance(cost, list) and cost else cost
result['forward_temp_bytes'] = int(memory.temp_size_in_bytes)
result['forward_flops'] = float(cost.get('flops', 0.0))
started = time.perf_counter()
jax.jit(step).lower(params, *inputs).compile()
result['train_step_seconds'] = time.perf_counter() - started
if 'init' in docs:
    init = interpret.rebuild(docs['init'], allowlist)
    started = time.perf_counter()
    jax.jit(lambda k: init(k)).lower(jax.ShapeDtypeStruct((2,), 'uint32')).compile()
    result['init_seconds'] = time.perf_counter() - started
(out / 'compile.json').write_text(json.dumps(result, sort_keys=True, separators=(',', ':')))
""".replace("__MODULES__", repr(MODULES))


class CompileBlocked(RuntimeError):
    """G5 cannot run: the deadline is unset (HUMAN_INPUT), or the scope is
    not one the accepted profile covers."""


class CompileInfraFailure(RuntimeError):
    """The lane failed for Carbon's own reasons (`FAILED_INFRA`)."""

    kind = FAILED_INFRA


def staged_files(parsed, allowlist, *, max_bytes):
    """Every byte the lane program receives, by staged name."""
    from . import graph

    repository = Path(__file__).resolve().parents[2]
    files = {
        name + ".py": (repository / (name.replace(".", "/") + ".py")).read_bytes()
        for name in MODULES
    }
    slots = sorted(s for s in parsed if s in ("forward", "init"))
    for slot in slots:
        files[slot + ".json"] = graph.dumps(parsed[slot])
    files["allowlist.json"] = allowlist.raw
    files["request.json"] = json.dumps(
        {"slots": slots, "max_bytes": max_bytes}, sort_keys=True
    ).encode()
    return files


def compile_in_isolation(
    parsed,
    allowlist,
    *,
    ledger,
    owner,
    image,
    deadline_seconds=DEADLINE_SECONDS,
    max_bytes,
    scope,
    runner=None,
):
    """G5 for a verified and validated submission: the lane's measurements.
    `scope` is the deployment the compile serves; only `SCOPES` run."""
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    from . import graph

    if scope not in SCOPES:
        raise CompileBlocked(MAINNET_BLOCKED)
    if deadline_seconds == HUMAN_INPUT or deadline_seconds is None:
        raise CompileBlocked("the G5 deadline is unset")
    if runner is None:
        from carbon.development_session.research_carrier import _run as runner
    files = staged_files(parsed, allowlist, max_bytes=max_bytes)
    body = json.dumps(
        {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}, sort_keys=True
    )
    identity = "level4-g5-" + hashlib.sha256(body.encode()).hexdigest()[:32]
    try:
        worker = runner(
            ledger,
            owner=owner,
            identity=identity,
            source=PROGRAM,
            files=files,
            image=image,
            seconds=deadline_seconds,
            provenance=PROVENANCE,
            extra_resources={},
        )
    except WorkerFailure as failure:
        if failure.code == WorkerCode.DEADLINE:
            raise graph.GraphRefused("compile_deadline") from None
        if failure.code == WorkerCode.RUNTIME:
            raise graph.GraphRefused("compile_failed") from None
        raise CompileInfraFailure(f"lane failure: {failure.code}") from None
    except Exception as failure:  # noqa: BLE001 - the lane's, not the submission's
        raise CompileInfraFailure(f"lane failure: {type(failure).__name__}") from None
    snapshot = Path(ledger.root) / worker["operation"] / "snapshot" / "compile.json"
    try:
        result = json.loads(snapshot.read_bytes())
    except (OSError, ValueError):
        raise CompileInfraFailure("lane produced no compile record") from None
    return {
        **result,
        "profile": PROFILE_STATUS,
        "profile_decision": PROFILE_DECISION,
        "scope": scope,
        "identity": identity,
    }
