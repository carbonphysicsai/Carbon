"""Standing audit: no construction capability Carbon rebuilds may be a no-op.

The construction contract's rule (`carbon.battery.compile.rebuild_issues`,
`carbon.development_session.research_catalog.rebuild_issues`): a supplied
field must change what Carbon rebuilds, and one the rest of the recipe would
ignore is refused by name. This audit holds that rule for every registered
construction contract, read from `capability_registry.CONTRACTS` (never a
hard-coded list), and for every REBUILDABLE_DEVELOPMENT capability in it.

For each base recipe a Challenge's adapter derives (one per rebuildable family,
and per reconstruction backend where the contract offers that choice), moving a
field away from the base, to a value taken from the field's own Surface, must
either:
- change the rebuild identity (the family and settings Carbon rebuilds) AND
  the trained-parameter digest of a small, fast CPU fit; or
- be refused at compile time with a typed code.

A value that changes the recipe digest but not the trained parameters is still
a no-op. Every value of every choice field must act on its own. A numeric
field's Surface values are tried in order until one acts, since a value can be
inert on a small fit (a clip above every gradient norm); a numeric field none
of whose values act is a no-op. Every family must build trained parameters
distinct from every other family's.

`KNOWN_NO_OPS` lists reported findings not fixed here. The audit asserts the
exact set: a new no-op fails, and a fixed one fails until it is removed.

A contract whose Challenge is RETIRED in the Challenge registry accepts no new
selection on the research path; it is audited at compile level only (every
field must change the compiled reconstruction profile). Every other contract
must have an adapter here, so a newly registered contract fails this audit
until it gets one.

Engineering fixtures only: tiny step counts, a 48-case TRAIN subset, seed 0.
Nothing here is evidence of quality, and nothing reaches a record.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from typing import ClassVar

import numpy as np
import pytest

from carbon.challenge_registry import registry as challenges
from carbon.development_session.research_catalog import RecipeRejected
from carbon.reconstruction import capability_registry as r
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
)

#: (contract token, capability id, base label) -> why it is not fixed here.
#: Each is a reported finding of NOOP-CAPABILITY-AUDIT-01
#: (`.agent/decisions/2026-10-05-NOOP-CAPABILITY-AUDIT-01.md`).
KNOWN_NO_OPS = {
    (r.BATTERY_CHALLENGE, "architecture.neighbours", "knn"): (
        "KNN's params_sha256 digests only the stored TRAIN targets, held "
        "bit-identical to the exam-design campaign's research recipe; the "
        "neighbour count changes predictions but not that digest. Binding k "
        "is a versioned fit-statistic change, reported as a finding."
    ),
}


def _digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode()).hexdigest()


def _strategy(token, family, parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": token,
        "backbone": family,
        "parameters": dict(parameters),
    }


def _refusal_codes(error):
    """The typed codes of a compile-time refusal, or None if untyped."""
    if isinstance(error, SubmissionRefused):
        issues = error.issues
    elif isinstance(error, RecipeRejected):
        issues = error.rejected.issues
    else:
        return None
    codes = tuple(sorted({i.code for i in issues}))
    if not codes or not all(type(c) is str and "." in c for c in codes):
        return None
    return codes


def rebuild_identity(construction):
    """What Carbon rebuilds, without the strategy's textual identity: a
    recipe's family and settings, or a profile's three configurations."""
    if hasattr(construction, "settings"):
        return _digest(
            {"family": construction.family, "settings": construction.settings}
        )
    return _digest(
        {
            name: json.loads(getattr(construction, name))
            for name in ("model_config_json", "task_config_json", "train_config_json")
        }
    )


def _torch_available():
    if os.environ.get("CARBON_REQUIRE_TORCH") == "1":
        return True
    try:
        import neuralop  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


# --- Adapters: how each Challenge fits a small recipe on CPU. ---


class BatteryAdapter:
    """Carbon's own rebuild (`compile.rebuild`, through the same
    `recipes.build(family, settings)` the practice PROGRAM and the GPU pod
    program call) on a 48-case TRAIN subset with tiny step counts."""

    SMALL: ClassVar[dict] = {
        "mlp": {"width": 8, "depth": 1, "steps": 32},
        "deeponet": {
            "width": 8,
            "deeponet_depth": 1,
            "basis_functions": 2,
            "steps": 32,
        },
        "fno": {"width": 8, "depth": 1, "n_modes": 2, "steps": 32},
        "knn": {},
    }
    #: Companion values under which a field acts; it is refused without them.
    ENABLING: ClassVar[dict] = {
        "ema_decay": {"inference_weights": "ema"},
        "weight_decay_mask": {"weight_decay": 0.05},
    }
    #: Every field on every family it applies to, and once on each backend.
    EVERY_BASE = True

    def __init__(self):
        pytest.importorskip("jax")
        from carbon.battery import challenge as ch

        self.material = ch.PublicMaterial.load()
        self.train = self.material.train.subset(48)

    def bases(self, token):
        """(label, family, parameters, lane): a base per family and backend."""
        surfaces = r.catalog_surfaces(token)
        backend = surfaces.get("backend")
        for family, _ in r.rebuildable_families(token):
            params = dict(self.SMALL[family])
            if backend is None or (backend[5] and family not in backend[5]):
                yield family, family, params, None
                continue
            for choice in backend[2]:
                label = family if choice == backend[4] else f"{family}/{choice}"
                yield label, family, {**params, "backend": choice}, choice

    @staticmethod
    def fittable(construction):
        """A PyTorch recipe is fitted only where torch is installed (CI's
        canonical lanes install it)."""
        return construction.settings.get("backend") != "pytorch" or _torch_available()

    def fit(self, construction):
        from carbon.battery.compile import rebuild

        _, stats = rebuild(construction, self.material, 0, train=self.train)
        return stats["params_sha256"]


class KernelRidgeAdapter:
    """Cold plate and Motor: the deterministic closed-form kernel-ridge fit on
    the full pinned public TRAIN (`compile.rebuild`); the digest is the fitted
    dual coefficients and target scaling."""

    ENABLING: ClassVar[dict] = {}
    EVERY_BASE = True

    def __init__(self, module):
        self.module = module
        self.material = module.PublicMaterial.load()

    def bases(self, token):
        for family, _ in r.rebuildable_families(token):
            yield family, family, {}, None

    def fit(self, construction):
        fitted = self.module.rebuild(construction, self.material)._model
        blob = b"".join(
            np.ascontiguousarray(a, dtype=np.float64).tobytes()
            for a in (fitted.alpha, fitted.mean, fitted.std)
        )
        return hashlib.sha256(blob).hexdigest()


class CompileOnlyAdapter:
    """A RETIRED Challenge: compile-level rebuild identity only."""

    ENABLING: ClassVar[dict] = {
        "ema_decay": {"inference_weights": "ema"},
        "physics_warmup_steps": {"pde_weight": 0.1},
    }
    #: Each field on the first family it applies to (compile level only).
    EVERY_BASE = False

    #: GINO's registry defaults (16 modes on a 12-point latent grid) are
    #: themselves refused, so its base names modes its latent grid holds.
    SMALL: ClassVar[dict] = {"gino": {"n_modes": 8}}

    def bases(self, token):
        for family, _ in r.rebuildable_families(token):
            params = {"steps": 8, "width": 8, **self.SMALL.get(family, {})}
            yield family, family, params, None

    @staticmethod
    def session():
        """Burgers' compiler rebuilds its (pure) catalog on every call; the
        audit builds it once."""
        from unittest import mock

        from carbon.development_session import research_catalog

        built = research_catalog.research_contracts()
        return mock.patch.object(
            research_catalog, "research_contracts", lambda *a, **k: built
        )

    fit = None


def _entry(token):
    return next((e for e in challenges.entries() if e.challenge_id == token), None)


def _cold_plate():
    from carbon.cold_plate import compile as module

    return KernelRidgeAdapter(module)


def _motor():
    from carbon.motor import compile as module

    return KernelRidgeAdapter(module)


#: Each registered, selectable contract's audit adapter, by Challenge token.
ADAPTERS = {
    r.BATTERY_CHALLENGE: BatteryAdapter,
    r.COLD_PLATE_CHALLENGE: _cold_plate,
    r.MOTOR_CHALLENGE: _motor,
}


def _adapter_factory(token):
    """The adapter factory for a registered contract, or None if it has none."""
    entry = _entry(token)
    if entry is not None and entry.status == challenges.RETIRED:
        return CompileOnlyAdapter
    return ADAPTERS.get(token)


# --- Probe values, from each field's own Surface. ---


def probes(surface, reference):
    """Values other than `reference` to try, in order, from the Surface."""
    kind, low, high = surface.kind, surface.low, surface.high
    if kind == "bool":
        values = [not reference]
    elif kind == "choice":
        values = list(low)
    elif kind == "uint":
        values = [low, reference + 1, reference - 1, reference + 2, high]
        values.append((low + high) // 2)
    else:
        span = high - low
        values = [low + 0.25 * span, low + 1e-4 * span, high, low]
    out = []
    for value in values:
        if kind in ("uint", "float") and not low <= value <= high:
            continue
        if value != reference and value not in out:
            out.append(value)
    return out


class Audit:
    """One contract's audit. Outcomes are keyed by (probe id, base label); a
    choice field's probe id names its value (`id=value`)."""

    def __init__(self, contract, adapter):
        self.contract, self.adapter = contract, adapter
        self.fits, self.compiled = {}, {}
        self.changed, self.refused, self.no_ops = {}, {}, {}
        #: Probes not fitted on this host (a backend it does not install).
        self.skipped = {}

    def compile(self, family, parameters):
        """(construction, rebuild identity), or (None, typed refusal codes)."""
        strategy = _strategy(self.contract.token, family, parameters)
        key = _digest(strategy)
        if key not in self.compiled:
            try:
                admitted = compile_submission(strategy)
            except (SubmissionRefused, RecipeRejected) as error:
                codes = _refusal_codes(error)
                assert codes is not None, f"untyped refusal of {strategy}"
                self.compiled[key] = None, codes
            else:
                construction = admitted.construction
                self.compiled[key] = construction, rebuild_identity(construction)
        return self.compiled[key]

    def fittable(self, construction):
        check = getattr(self.adapter, "fittable", None)
        return check is None or self.adapter.fit is None or check(construction)

    def trained(self, construction, identity):
        if self.adapter.fit is None:
            return None
        if identity not in self.fits:
            self.fits[identity] = self.adapter.fit(construction)
        return self.fits[identity]

    def run(self):
        session = getattr(self.adapter, "session", None)
        with session() if session else contextlib.nullcontext():
            return self._run()

    def _run(self):
        token = self.contract.token
        fields = [
            c
            for c in self.contract.capabilities
            if c.status is r.Status.REBUILDABLE_DEVELOPMENT and c.surface is not None
        ]
        # A family's primary base is the first one that compiles (its default
        # backend); every field runs there. A further base (another backend)
        # runs each field that lane has not yet run on any family.
        primary, further = [], []
        for label, family, base, lane in self.adapter.bases(token):
            if self.compile(family, base)[0] is None:
                continue  # this family is not rebuilt on this backend
            first = all(family != f for _, f, _, _ in primary)
            (primary if first else further).append((label, family, base, lane))
        families, chosen, done = {}, set(), set()
        bases = [(True, *b) for b in primary] + [(False, *b) for b in further]
        for is_primary, label, family, base, lane in bases:
            construction, identity = self.compile(family, base)
            if not self.fittable(construction):
                self.skipped[("base", label)] = family
                for capability in fields:
                    if not capability.applies_to or family in capability.applies_to:
                        self.skipped[(capability.capability_id, label)] = "base"
                continue
            if is_primary:
                families[family] = self.trained(construction, identity)
            every = is_primary and self.adapter.EVERY_BASE
            for capability in fields:
                if capability.applies_to and family not in capability.applies_to:
                    continue
                once = (capability.capability_id, lane)
                if once in done and not every:
                    continue
                done.add(once)
                self._field(capability, label, family, base, chosen)
        unfitted = {f for f, _ in r.rebuildable_families(token)} - set(families)
        for family in sorted(unfitted):
            assert family in self.skipped.values(), f"no base rebuilds {family}"
            self.skipped[("model_family." + family, family)] = "not fitted here"
        first = {}
        for family, trained in families.items():
            key = ("model_family." + family, family)
            if trained is not None and trained in first:
                self.no_ops[key] = [("same parameters as", first[trained])]
            else:
                first.setdefault(trained, family)
                self.changed[key] = family
        return self

    def _field(self, capability, label, family, base, chosen):
        name = capability.capability_id.partition(".")[2]
        reference = {**base, **self.adapter.ENABLING.get(name, {})}
        construction, identity = self.compile(family, reference)
        if construction is None:
            reference = base  # the enabling context does not apply here
            construction, identity = self.compile(family, reference)
        values = probes(
            capability.surface, reference.get(name, capability.surface.default)
        )
        if capability.surface.kind == "choice":
            # Every value once over the whole audit, and one on every base.
            todo = [v for v in values if (name, v) not in chosen] or values[:1]
            for value in todo:
                chosen.add((name, value))
                self._probe(
                    (f"{capability.capability_id}={value}", label),
                    family,
                    reference,
                    name,
                    [value],
                    identity,
                    self.trained(construction, identity),
                )
        else:
            self._probe(
                (capability.capability_id, label),
                family,
                reference,
                name,
                values,
                identity,
                self.trained(construction, identity),
            )

    def _probe(self, key, family, reference, name, values, ref_identity, ref_trained):
        """The first value that changes the artifact; else a no-op (some value
        compiled but changed nothing) or a typed refusal (every value refused)."""
        silent, refused = [], []
        for value in values:
            construction, identity = self.compile(family, {**reference, name: value})
            if construction is None:
                refused.append((value, identity))
            elif not self.fittable(construction):
                self.skipped[key] = value
                return
            elif identity == ref_identity:
                silent.append((value, "rebuild identity unchanged"))
            elif ref_trained is not None and (
                self.trained(construction, identity) == ref_trained
            ):
                silent.append((value, "trained parameters unchanged"))
            else:
                self.changed[key] = value
                return
        if silent:
            self.no_ops[key] = silent
        else:
            assert refused, f"{key}: no probe value"
            self.refused[key] = refused

    def no_op_ids(self):
        return {
            (self.contract.token, probe.split("=")[0], label)
            for probe, label in self.no_ops
        }


_AUDITS = {}


def _audit(token):
    if token not in _AUDITS:
        _AUDITS[token] = Audit(r.contract(token), _adapter_factory(token)()).run()
    return _AUDITS[token]


def test_every_registered_contract_has_an_audit_adapter():
    """A contract with no adapter (and not RETIRED) fails here."""
    assert [t for t in sorted(r.CONTRACTS) if _adapter_factory(t) is None] == []


def test_probe_values_come_from_the_surface():
    assert probes(r.Surface("train", "uint", 1, 8, 1), 1) == [2, 3, 8, 4]
    assert probes(r.Surface("task", "bool", None, None, True), True) == [False]
    choice = r.Surface("model", "choice", ("a", "b", "c"), None, "a")
    assert probes(choice, "a") == ["b", "c"]
    floats = probes(r.Surface("train", "float", 0.0, 1.0, 0.0), 0.0)
    assert floats and all(0.0 < v <= 1.0 for v in floats)


def test_known_no_ops_name_registered_rebuildable_capabilities():
    for token, capability_id, _ in KNOWN_NO_OPS:
        found = r.capability(capability_id, token)
        assert found.status is r.Status.REBUILDABLE_DEVELOPMENT


@pytest.mark.parametrize("token", sorted(r.CONTRACTS))
def test_no_rebuildable_capability_is_a_no_op(token):
    audit = _audit(token)
    known = {k for k in KNOWN_NO_OPS if k[0] == token}
    assert audit.no_op_ids() == known, "no-op capabilities (probe id, base): " + repr(
        sorted(audit.no_ops.items())
    )
    exercised = {probe.split("=")[0] for probe, _ in audit.changed}
    exercised |= {
        probe.split("=")[0]
        for probe, _ in (*audit.refused, *audit.no_ops, *audit.skipped)
    }
    rebuildable = {
        c.capability_id
        for c in r.contract(token).capabilities
        if c.status is r.Status.REBUILDABLE_DEVELOPMENT
    }
    assert rebuildable <= exercised, sorted(rebuildable - exercised)
