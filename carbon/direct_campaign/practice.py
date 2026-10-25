"""Direct-recipe practice for F08 1.4 / F02 2.3, built as the receiver builds it.

Two recipe sources, each run by the receiver's own two-phase call on the
version's registered public material (`physical_material.bundle_material`):

- **catalog**: one of Carbon's tested backbones by catalog id, expanded to the
  Carbon bundle it stands for (`backbone_catalog.served.expand`) and rebuilt by
  `bundle_construction_worker.reconstruct_and_infer_public` over the parent of
  the bundle's pinned runtime (as Motor's and Cooling's catalog practice);
- **graph**: the miner's graph from its own workspace
  (`construction_recipe.graph_envelope_from_workspace`), trained by the
  version's registered graph training adapter (`graph_adapters`: F08/F02's, or
  Battery's on its base version's graph route; the version's limits block) through
  `direct_graph_construction_worker.reconstruct_and_infer_graph_public`.

The query is the version's exposed DEVELOPMENT bank inputs, seed 0. Outputs
must be of the interface's dtype (`OUTPUT_DTYPES`: F08's and F02's `<f4`,
Battery's float64), one finite row per case, of the interface's width;
anything else is refused.

Battery's catalog version (2.2, `battery.catalog_version`) serves catalog
recipes and graph recipes (Battery's graph adapter). Its practice is Battery's own registered practice measurement
(`practice.score_practice`: the exam's gates, TRAIN scales and frozen
tolerances) on the bank's public PRACTICE rows, the same feedback Battery's
practice gives; the bank's other rows are queried, never scored here.

Practice feedback (Validator rulings, 2026-10-20 and 2026-10-21): aggregate
errors on each Challenge's REGISTERED error scale, as Motor's and Cooling's
practice report theirs; no dual-pack Ladder (no A, D, TOP or leg minimum), no
per-case value and no new normalisation. The exposed bank's references are read
on this host only; nothing per case leaves. The scales and aggregations are the
records' own (`error_scale`):

- **F02:** TRAIN40-v2's exact ``train_peak_std_c`` (OWNER-F02-TRAIN40-V2-01:
  population std, ddof 0, of the 24 S1 rows' peak; recorded 6.701 degC and
  recomputed from the pinned rows, ``challenge_kit/f02_train.py:51-54,118-127``).
  Each case's error is ``|prediction - primary-rung reference| / train_peak_std_c``
  and the aggregate is ``max(mean, near-limit block mean, worst)``, the
  registered F02 measurement's own reduction
  (``scoring/private_evaluation_source.py:848,862-875``).
- **F08:** dev1 section 7's f08 scales
  (``docs/development/scorelab/four_challenge_design_fidelity_dev1.md:125``):
  static margin 0.003 mm/N, each dynamic margin 0.015 mm/N, resonance frequency
  10 Hz. A margin's error is its output's error (a margin is the limit minus
  the output, dev1:108); each peak frequency is a resonance (dev1:111). The
  aggregate is dev1 section 1's ``L = max over registered quantity and case of
  error / scale`` (dev1:19), with the mean recorded beside the worst (dev1:24).
  The bank's references are points, so the result is a
  ``POINT_ESTIMATE_DIAGNOSTIC`` (dev1:39).

The result carries the Challenge's practice provenance, so a practised recipe
supports a freeze.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from carbon.scoring import practice_speed

from .spec import key_for

OUTPUT_DTYPE = "<f4"
#: Each Challenge's registered output dtype, as its interface declares it.
OUTPUT_DTYPES = {"f08": "<f4", "f02": "<f4", "battery_catalog": "float64"}
F02_SCALE_RECORD = "OWNER-F02-TRAIN40-V2-01 train_peak_std_c"
F08_SCALE_RECORD = (
    "docs/development/scorelab/four_challenge_design_fidelity_dev1.md section 7 (f08)"
)
#: dev1 section 7's f08 scales, by interface output: (component, scale, unit).
#: DEVELOPMENT normalisation scales, not physical thresholds (dev1:118).
F08_SCALES = {
    "static_tip_mm_per_n": ("margin", 0.003, "mm/N"),
    **{
        f"peak_tip_{tag}_mm_per_n": ("margin", 0.015, "mm/N")
        for tag in ("z005", "z010", "z020")
    },
    **{
        f"peak_frequency_{tag}_hz": ("resonance", 10.0, "Hz")
        for tag in ("z005", "z010", "z020")
    },
}
#: The summary components each Challenge reports, in order.
COMPONENTS = {
    "f02": ("mean", "near_mean", "worst"),
    "f08": ("margin_mean", "margin_worst", "resonance_mean", "resonance_worst"),
    # Battery's exam components (`battery.exam.COMPONENTS`).
    "battery_catalog": ("voltage", "temperature", "plating", "capacity"),
}


def _f02_scale(version):
    from carbon.challenge_kit import f02_train

    # The exact computed value, never the rounded record (f02_train.py:51-54).
    return f02_train.load_public_train(version)["train_peak_std_c"]


SCORE_MEANING = "Practice error on the Challenge's registered scale: lower is better; 0 means the model matches the reference exactly on every scored case, and 1 means an error as large as that scale (a spread taken from the public TRAIN data). It is an error, not a grade, and not an exam score."


def error_scale(spec, version):
    """The registered practice error scale this Challenge reports on, and the
    record's error and aggregation (no value is chosen here)."""
    if spec.prefix == "f02":
        return {
            "record": F02_SCALE_RECORD,
            "scales": {"peak_top_c": {"value": _f02_scale(version), "unit": "degC"}},
            "error": "abs(prediction - primary-rung reference) / train_peak_std_c",
            "aggregation": "max(mean, near-limit block mean, worst) over the bank",
            "direction": "lower_is_better",
        }
    if spec.prefix == "f08":
        return {
            "record": F08_SCALE_RECORD,
            "scales": {
                name: {"component": component, "value": value, "unit": unit}
                for name, (component, value, unit) in F08_SCALES.items()
            },
            "error": "abs(prediction - point reference) / scale",
            "aggregation": (
                "max over registered quantity and case (dev1 section 1); "
                "the mean is recorded beside the worst"
            ),
            "reference": "POINT_ESTIMATE_DIAGNOSTIC",
            "direction": "lower_is_better",
        }
    if spec.prefix == "battery_catalog":
        from carbon.battery import catalog_version

        return catalog_version.error_scale(version)
    raise ValueError(spec.prefix + "_practice_error_scale_unregistered")


def _mean(values):
    # Divide before summing so large finite errors cannot overflow the sum.
    return math.fsum(v / len(values) for v in values)


def _f02_aggregate(rows, references, case_ids, scale):
    """The registered F02 reduction (private_evaluation_source.py:848,862-875):
    each case's ``|p - r| / train_peak_std_c``, then max(mean, near mean,
    worst); the near block is the ``-near-`` actions."""
    errors = [
        abs(row[0] - ref) / scale for row, ref in zip(rows, references, strict=True)
    ]
    near = [e for e, case in zip(errors, case_ids, strict=True) if "-near-" in case]
    components = {"mean": _mean(errors), "near_mean": _mean(near), "worst": max(errors)}
    return max(components.values()), components


def _f08_aggregate(rows, references, names):
    """dev1 section 1 over section 7's scales: each output's error over its
    scale; per component the worst over registered quantity and case (its L)
    and the mean beside it; the aggregate is the worst component."""
    errors = {"margin": [], "resonance": []}
    for row, reference in zip(rows, references, strict=True):
        for j, name in enumerate(names):
            component, scale, _unit = F08_SCALES[name]
            errors[component].append(abs(row[j] - reference[j]) / scale)
    components = {}
    for component, values in errors.items():
        components[component + "_mean"] = _mean(values)
        components[component + "_worst"] = max(values)
    return (
        max(components["margin_worst"], components["resonance_worst"]),
        components,
    )


def summary(spec, version, interface, rows, material):
    """What a practice reports under the Validator's rulings: the rows'
    structural facts and the aggregate errors on the registered scale. No
    per-case value, Ladder or new normalisation."""
    if spec.prefix == "battery_catalog":
        from carbon.battery import catalog_version

        return catalog_version.practice_summary(version, rows, material)
    names = list(interface["output"]["names"])
    case_ids = list(material["practice_case_ids"])
    values = [[float(v) for v in row] for row in rows]
    # A dev-grid version's practice bank carries public-seeded probe rows, which have no
    # reference: the error is reported on the exposed cells only (the probes still reach the
    # dual feedback, which grades them as the exam does).
    from carbon.scoring import probe_design

    scored = [
        i for i, case_id in enumerate(case_ids) if not probe_design.is_probe_id(case_id)
    ]
    if spec.prefix == "f02":
        from carbon.challenge_kit import physical_pack

        bank = physical_pack.development_bank(spec.challenge_id, version)
        if list(bank["case_ids"]) != case_ids:
            raise ValueError("f02_practice_bank_order")
        # The registered measurement's reference: each action's primary rung
        # (f02_dual_pack.reference, `rungs["primary"]`).
        references = [
            float(bank["reference_records"][i]["rung_peaks_c"]["primary"])
            for i in scored
        ]
        values = [values[i] for i in scored]
        case_ids = [case_ids[i] for i in scored]
        aggregate, components = _f02_aggregate(
            values, references, case_ids, _f02_scale(version)
        )
    elif spec.prefix == "f08":
        if set(names) != set(F08_SCALES):
            raise ValueError("f08_practice_outputs_unscaled")
        references = [
            [float(v) for v in material["practice_reference"][i]] for i in scored
        ]
        values = [values[i] for i in scored]
        aggregate, components = _f08_aggregate(values, references, names)
    else:
        raise ValueError(spec.prefix + "_practice_error_scale_unregistered")
    if not math.isfinite(aggregate) or not all(
        math.isfinite(v) for v in components.values()
    ):
        raise ValueError(spec.prefix + "_practice_error_nonfinite")
    return {
        "cases": len(rows),
        "outputs": names,
        "dtype": OUTPUT_DTYPE,
        "n_cases": len(rows),
        "n_scored": len(scored),
        "score": aggregate,
        # `score` is this error, not a grade (owner, 2026-10-25: "what the heck is with those
        # high scores"): said beside the number wherever the summary is shown.
        "score_meaning": SCORE_MEANING,
        "aggregate_error": aggregate,
        "components": {k: components[k] for k in COMPONENTS[spec.prefix]},
        "error_scale": error_scale(spec, version),
        "status": "aggregate_on_registered_scale",
    }


class DirectPractice:
    construction_mode = "direct"

    def __init__(
        self,
        spec,
        *,
        ledger,
        owner,
        parent,
        cache_root,
        version,
        root=".",
        runner=None,
        resolver=None,
        parents=None,
    ):
        self.spec = spec
        self.version = key_for(spec, version).version
        self.ledger, self.owner = ledger, owner
        self.parent, self.cache_root = parent, Path(cache_root)
        self.root, self.runner = Path(root), runner
        self.resolver = resolver
        self._parents = parents
        # Catalog bundles build on the PyTorch CPU worker; the fixed inference
        # program and the graph adapter run the C-03 JAX stack it carries.
        self.backends = ("torch_cpu", "jax")
        self.gpu_image = None

    # -- what this host can build ---------------------------------------------

    def parents(self):
        """The construction parent of each bundle runtime served here (as
        Motor's): the PyTorch CPU worker, and the C-03 CPU worker it was built
        FROM only when Docker finds that exact image installed."""
        if self._parents is None:
            from carbon.development_session.gpu_practice import (
                DirectParentRefused,
                DirectParents,
                derived_cpu_parent,
            )
            from carbon.reconstruction.worker.docker_runtime import doctor

            served = {"torch-cpu-py311": self.parent}
            try:
                cpu = derived_cpu_parent(self.parent)
                if doctor(image_id=cpu.image_id, image_identity=cpu).eligible:
                    served["python-cpu-py311"] = cpu
            except (DirectParentRefused, OSError):
                pass
            from carbon.development_session.gpu_practice import with_gpu_parent

            # The host's declared PyTorch GPU worker builds the entries' GPU
            # builds (one shared GPU path); unchanged without one.
            self._parents = with_gpu_parent(DirectParents(served), self.gpu_image)
        return self._parents

    def _resolve(self, bundle_ref):
        parent = self.parents().for_bundle(bundle_ref)
        if self.resolver is not None:
            return self.resolver(bundle_ref)
        from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver
        from carbon.reconstruction.worker.docker_runtime import DockerCLI

        return DirectOwnerImageResolver(
            self.cache_root, parents=self.parents()
        ).provision_admitted(bundle_ref, parent=parent, cli=DockerCLI())

    def installed(self):
        """The catalog ids whose child image is installed on this host."""
        from carbon.backbone_catalog import listing

        found = []
        for item in listing.entries(self.spec.challenge_id, self.version):
            try:
                self._resolve(_bundle_ref(item["bundle_ref"]))
            except (FileNotFoundError, ValueError, OSError):
                continue
            found.append(item["catalog_id"])
        return tuple(found)

    def backend_refusal(self, strategy):
        """The installed entries when a catalog recipe's entry has no installed
        child here (`backend_not_served`, before dispatch); None otherwise."""
        try:
            recipe = self._bound(strategy)
            if recipe.to_dict()["source"]["kind"] != "catalog":
                return None
            expanded = _expand(recipe)
        except (ValueError, TypeError, KeyError):
            return None
        try:
            self._resolve(_bundle_ref(expanded["source"]["bundle_ref"]))
        except (FileNotFoundError, ValueError, OSError):
            from carbon.development_session.gpu_practice import gpu_build_staged

            # Served on this host's GPU alone: not refused.
            if gpu_build_staged(
                self, lambda runtime: _expand(recipe, runtime), _bundle_ref
            ):
                return None
            return self.installed()
        return None

    # -- one practice -----------------------------------------------------------

    def _material(self):
        from carbon.challenge_kit import physical_material

        return physical_material.bundle_material(self.spec.challenge_id, self.version)

    def _bound(self, strategy, material=None):
        from carbon.development_session.construction_recipe import bind_recipe

        kit = (material or self._material())["construction_kit"]
        return bind_recipe(
            strategy,
            challenge_id=kit["id"],
            challenge_version=kit["version"],
            train_digest=kit["train_digest"],
            interface_digest=kit["interface_digest"],
            construction_limits_digest=kit["construction_limits_digest"],
        )

    def __call__(self, identity, strategy):
        import numpy as np

        from carbon.challenge_kit.interface_dtype import output_dtype
        from carbon.development_session.construction_recipe import ConstructionRecipe
        from carbon.development_session.profile import canonical, digest
        from carbon.development_session.research_workspace import ResearchWorkspace

        material = self._material()
        # The v2 practice grid: the public cells with the public-seeded probes
        # interleaved (the exam's own query design), when this version has a
        # sealed v2 grader; otherwise the exposed bank as before.
        material, cell_rows = self._practice_query(material)
        interface = material["interface_document"]
        dtype = OUTPUT_DTYPES[self.spec.prefix]
        if output_dtype(interface) != dtype:
            raise ValueError(self.spec.prefix + "_practice_dtype_unregistered")
        recipe = self._bound(strategy, material)
        kit = material["construction_kit"]
        binding = {
            "challenge_id": kit["id"],
            "challenge_version": kit["version"],
            "train_digest": kit["train_digest"],
            "interface_digest": kit["interface_digest"],
            "construction_limits_digest": kit["construction_limits_digest"],
        }
        source = recipe.to_dict()["source"]
        if source["kind"] == "catalog":
            result, backend, built = self._catalog(
                recipe, binding, material, identity, dtype
            )
        elif source["kind"] == "graph":
            result, backend, built = self._graph(recipe, binding, material, identity)
        else:
            raise ValueError(self.spec.prefix + "_direct_source_unserved")
        if result.build.state_digest != result.inference.state_digest:
            raise ValueError(
                self.spec.prefix + " practice state differs between phases"
            )
        rows = np.asarray(result.inference.predictions, dtype=np.float64)
        expected = tuple(material["expected_output_shape"])
        if (
            rows.shape != expected
            or not np.isfinite(rows).all()
            or (
                dtype == OUTPUT_DTYPE
                and not np.array_equal(rows, rows.astype(np.float32).astype(np.float64))
            )
        ):
            # Not one finite row of the interface's dtype and width per case.
            raise ValueError(self.spec.prefix + "_practice_output_invalid")
        out = {
            "schema": self.spec.practice_schema,
            "provenance": self.spec.practice_provenance,
            "challenge": {"id": kit["id"], "version": kit["version"]},
            "source_kind": source["kind"],
            "recipe_digest": ConstructionRecipe.from_dict(strategy).digest,
            "built_recipe_digest": built.digest,
            "summary": summary(
                self.spec,
                self.version,
                interface,
                rows if cell_rows is None else rows[cell_rows],
                material,
            ),
            "fit": {"state_digest": result.build.state_digest},
            "backend": backend,
            "adaptively_seen": True,
            "final_exam": False,
            "official_eligible": False,
            "scientific_qualification": False,
            "recipe": strategy,
            # C13: the same dual measurement the exam grades (gates first, then
            # A, D and the total in 0..1, 1 best) on the public development
            # bank, which is exactly the query above. Feedback only: public,
            # not the exam, and labelled practice. The model is queried once,
            # so the paired repeat is the same rows.
            "practice_dual": _dual_feedback(
                self.spec,
                self.version,
                rows,
                speed=practice_speed.from_result(
                    self.spec.prefix,
                    result,
                    designs=len(rows),
                    requested=practice_speed.measure(self.runner),
                ),
            ),
        }
        if source["kind"] == "catalog":
            plain = json.loads(canonical(strategy))["source"]
            out["catalog_id"] = plain["catalog_id"]
            out["catalog_digest"] = plain["catalog_digest"]
        ResearchWorkspace(self.ledger, self.owner).put(
            "trial-"
            + digest(identity.encode())[7:23]
            + "-"
            + self.spec.prefix
            + "-direct-practice.json",
            canonical(out),
        )
        return out

    def _practice_query(self, material):
        """``(material, cell_rows)``: for a version with a sealed v2 grader, the
        material with its practice inputs replaced by the practice grid query
        (cells and public probes, interleaved), and the index of each exposed case
        in that query (in ``practice_case_ids`` order); otherwise the material
        unchanged and None."""
        import numpy as np

        from carbon.scoring import practice_grid

        kind = self.spec.prefix
        if (
            kind not in ("f08", "f02")
            or practice_grid.adapter(kind, self.version) is None
        ):
            return material, None
        bank = practice_grid.practice_bank(kind, self.version)
        like = material["practice_inputs"]
        query = np.asarray(bank["inputs"]).astype(like.dtype)
        position = {case_id: i for i, case_id in enumerate(bank["case_ids"])}
        cell_rows = np.asarray(
            [position[c] for c in material["practice_case_ids"]], dtype=np.int64
        )
        width = tuple(material["expected_output_shape"])[1:]
        return (
            {
                **material,
                "practice_inputs": query,
                "expected_output_shape": (len(query), *width),
            },
            cell_rows,
        )

    def _catalog(self, catalog_recipe, binding, material, identity, dtype):
        from carbon.development_session.bundle_construction_worker import (
            reconstruct_and_infer_public,
        )
        from carbon.development_session.construction_recipe import ConstructionRecipe
        from carbon.development_session.gpu_practice import gpu_overlay, run_on_device

        def run(trial, built, image, parent, device):
            return reconstruct_and_infer_public(
                self.ledger,
                owner=self.owner,
                identity=trial,
                image=image,
                inference_image=self.parent,
                construction_parent=parent,
                recipe=ConstructionRecipe.from_dict(built),
                challenge_binding=dict(binding),
                limits_document=material["construction_limits_document"],
                train=material["train"],
                example=material["example"],
                seed=0,
                inputs=material["practice_inputs"],
                expected_output_shape=material["expected_output_shape"],
                allowlist_bytes=material["allowlist_bytes"],
                expected_output_dtype=dtype,
                accelerator=device,
                measure_query=practice_speed.measure(self.runner),
                timing_optional=True,
                runner=self.runner,
            )

        result, expanded, construction_parent, accelerator, gpu_note = run_on_device(
            self,
            identity,
            lambda runtime: _expand(catalog_recipe, runtime),
            _bundle_ref,
            lambda bundle, parent, built: gpu_overlay(
                self,
                identity,
                bundle,
                parent,
                built,
                {
                    "id": binding["challenge_id"],
                    "version": binding["challenge_version"],
                    **{
                        k: binding[k]
                        for k in (
                            "train_digest",
                            "interface_digest",
                            "construction_limits_digest",
                        )
                    },
                },
                material["construction_limits_document"],
            ),
            run,
        )
        recipe = ConstructionRecipe.from_dict(expanded)
        from carbon.development_session.catalog_gpu import backend_record

        backend = backend_record(
            accelerator, construction_parent, gpu_note, self.runner
        )
        return result, backend, recipe

    def _graph(self, recipe, binding, material, identity):
        from carbon.development_session.construction_recipe import (
            graph_envelope_from_workspace,
        )
        from carbon.development_session.direct_graph_construction_worker import (
            reconstruct_and_infer_graph_public,
        )
        from carbon.development_session.graph_adapters import for_version

        limits = material["construction_limits_document"]
        # The version's registered graph adapter (F08/F02's, or Battery's).
        adapter = for_version(self.spec.challenge_id, self.version)
        if adapter is None or "graph_training_adapter" not in limits:
            raise ValueError(self.spec.prefix + "_graph_unserved")
        spec = adapter.spec_for(self.spec.challenge_id, self.version)
        if limits.get("graph_training_adapter") != adapter.adapter_block(
            spec.challenge_id, spec.version
        ):
            raise ValueError(self.spec.prefix + "_graph_adapter_unregistered")
        # Refused here, with the adapter's own closed code, before anything runs.
        adapter.training_settings(recipe)
        envelope = graph_envelope_from_workspace(self.ledger, self.owner, recipe)
        result = reconstruct_and_infer_graph_public(
            self.ledger,
            owner=self.owner,
            identity=identity,
            image=self.parent,
            recipe=recipe,
            challenge_binding=dict(binding),
            limits_document=limits,
            source_envelope=envelope,
            train=material["train"],
            inputs=material["practice_inputs"],
            expected_output_shape=material["expected_output_shape"],
            allowlist_bytes=material["allowlist_bytes"],
            seed=0,
            measure_query=practice_speed.measure(self.runner),
            timing_optional=True,
            runner=self.runner,
            adapter_id=spec.adapter_id,
        )
        backend = {"kind": "C03_DOCKER", "adapter": spec.adapter_id}
        return result, backend, recipe


def _dual_feedback(spec, version, rows, speed=None):
    """The shared practice dual block for the rows of the exposed bank."""
    from carbon.scoring import practice_dual, practice_grid

    # The exam's own v2 grader on the full public bank, with public probes, when
    # this version has one (practice must match the exam).
    if (
        spec.prefix in ("f08", "f02")
        and practice_grid.adapter(spec.prefix, version) is not None
    ):
        return practice_dual.from_rows_v2(spec.prefix, version, rows, speed=speed)

    # A static dispatch: the code-authority inventory forbids a computed import.
    if spec.prefix == "f08":
        from carbon.scoring import f08_dual_pack as module
    elif spec.prefix == "f02":
        from carbon.scoring import f02_dual_pack as module
    elif spec.prefix == "battery_catalog":
        # Battery's own practice dual, on modules a miner surface may import
        # (Phase A), so practice feedback matches the exam (0.5 A + 0.5 D).
        from carbon.scoring import battery_public_adapter as module
    else:
        raise ValueError(spec.prefix + "_practice_dual_unregistered")
    adapter = practice_dual.versioned(module, version)
    if adapter is None:
        return practice_dual.unavailable(module, "practice_version_not_registered")
    return practice_dual.from_rows(adapter, rows)


def _expand(recipe, runtime=None):
    from carbon.backbone_catalog.served import expand

    return expand(recipe.to_dict(), runtime)


def _bundle_ref(value):
    from carbon.development_session.library_bundles import LibraryBundleRef

    return LibraryBundleRef(
        value["schema"],
        value["bundle_digest"],
        value["language"],
        value["runtime_profile_id"],
        value["environment_digest"],
    )
