"""Direct-recipe practice for F08 1.4 / F02 2.3, built as the receiver builds it.

Two recipe sources, each run by the receiver's own two-phase call on the
version's registered public material (`physical_material.bundle_material`):

- **catalog**: one of Carbon's tested backbones by catalog id, expanded to the
  Carbon bundle it stands for (`backbone_catalog.served.expand`) and rebuilt by
  `bundle_construction_worker.reconstruct_and_infer_public` over the parent of
  the bundle's pinned runtime (as Motor's and Cooling's catalog practice);
- **graph**: the miner's graph from its own workspace
  (`construction_recipe.graph_envelope_from_workspace`), trained by Carbon's
  registered graph training adapter (the version's limits block) through
  `direct_graph_construction_worker.reconstruct_and_infer_graph_public`.

The query is the version's exposed DEVELOPMENT bank inputs, seed 0. Outputs
must be float32 (the interface's `<f4`), one finite row per case, of the
interface's width; anything else is refused.

Practice feedback (Validator ruling, 2026-10-20): aggregate errors on
registered scales only, no dual-pack Ladder, no per-case labels, no new
normalisation. No practice error scale is registered for F08 or F02, so the
summary carries structural facts only and its error scale is `HUMAN_INPUT`:
no error is computed and no reference label is read. The result carries the
Challenge's practice provenance, so a practised recipe supports a freeze.
"""

from __future__ import annotations

import json
from pathlib import Path

from .spec import HUMAN_INPUT, key_for

#: The practice error scale this Challenge's summary would report on: none
#: is registered, so it is the unresolved decision itself.
ERROR_SCALE = HUMAN_INPUT
OUTPUT_DTYPE = "<f4"


def summary(interface, rows):
    """What a practice may report under the Validator's ruling: the rows'
    structural facts. No error, normalisation or per-case value."""
    return {
        "cases": len(rows),
        "outputs": list(interface["output"]["names"]),
        "dtype": OUTPUT_DTYPE,
        "aggregate_error": None,
        "error_scale": ERROR_SCALE,
        "status": "practice_error_scale_unregistered",
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
            self._parents = DirectParents(served)
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
        interface = material["interface_document"]
        if output_dtype(interface) != OUTPUT_DTYPE:
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
            result, backend, built = self._catalog(recipe, binding, material, identity)
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
            or not np.array_equal(rows, rows.astype(np.float32).astype(np.float64))
        ):
            # Not one finite float32 row of the interface's width per case.
            raise ValueError(self.spec.prefix + "_practice_output_invalid")
        out = {
            "schema": self.spec.practice_schema,
            "provenance": self.spec.practice_provenance,
            "challenge": {"id": kit["id"], "version": kit["version"]},
            "source_kind": source["kind"],
            "recipe_digest": ConstructionRecipe.from_dict(strategy).digest,
            "built_recipe_digest": built.digest,
            "summary": summary(interface, rows),
            "fit": {"state_digest": result.build.state_digest},
            "backend": backend,
            "adaptively_seen": True,
            "final_exam": False,
            "official_eligible": False,
            "scientific_qualification": False,
            "recipe": strategy,
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

    def _catalog(self, catalog_recipe, binding, material, identity):
        from carbon.development_session.bundle_construction_worker import (
            reconstruct_and_infer_public,
        )
        from carbon.development_session.construction_recipe import ConstructionRecipe

        recipe = ConstructionRecipe.from_dict(_expand(catalog_recipe))
        bundle = _bundle_ref(recipe.to_dict()["source"]["bundle_ref"])
        image = self._resolve(bundle)
        construction_parent = self.parents().for_bundle(bundle)
        result = reconstruct_and_infer_public(
            self.ledger,
            owner=self.owner,
            identity=identity,
            image=image,
            inference_image=self.parent,
            construction_parent=construction_parent,
            recipe=recipe,
            challenge_binding=dict(binding),
            limits_document=material["construction_limits_document"],
            train=material["train"],
            example=material["example"],
            seed=0,
            inputs=material["practice_inputs"],
            expected_output_shape=material["expected_output_shape"],
            allowlist_bytes=material["allowlist_bytes"],
            expected_output_dtype=OUTPUT_DTYPE,
            runner=self.runner,
        )
        backend = {
            "kind": "C03_DOCKER",
            "parent": getattr(construction_parent, "image_id", None),
        }
        return result, backend, recipe

    def _graph(self, recipe, binding, material, identity):
        from carbon.development_session import physical_graph_adapter as adapter
        from carbon.development_session.construction_recipe import (
            graph_envelope_from_workspace,
        )
        from carbon.development_session.direct_graph_construction_worker import (
            reconstruct_and_infer_graph_public,
        )

        spec = adapter.spec_for(self.spec.challenge_id, self.version)
        limits = material["construction_limits_document"]
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
            runner=self.runner,
            adapter_id=spec.adapter_id,
        )
        backend = {"kind": "C03_DOCKER", "adapter": spec.adapter_id}
        return result, backend, recipe


def _expand(recipe):
    from carbon.backbone_catalog.served import expand

    return expand(recipe.to_dict())


def _bundle_ref(value):
    from carbon.development_session.library_bundles import LibraryBundleRef

    return LibraryBundleRef(
        value["schema"],
        value["bundle_digest"],
        value["language"],
        value["runtime_profile_id"],
        value["environment_digest"],
    )
