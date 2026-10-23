"""Motor catalog practice (OWNER-BACKBONE-CATALOG-01): a catalog recipe built
on public TRAIN and scored on public PRACTICE, exactly as the receiver builds it.

A catalog recipe names one of Carbon's tested backbones; it is expanded to the
Carbon bundle it stands for (`backbone_catalog.served.expand`) and rebuilt by
the receiver's own two-phase call, `bundle_construction_worker.
reconstruct_and_infer_public`, with the receiver's inputs: the version's public
construction material, its installed child image over the parent of the
bundle's pinned runtime, and seed 0. So a practice predicts what the judge
will rebuild. A `torch-cpu-py311` bundle builds on the campaign's PyTorch CPU
worker; a `python-cpu-py311` bundle (jNO) on the C-03 CPU worker that worker
was built FROM. Inference stays on the PyTorch CPU worker, which carries the
C-03 JAX stack the fixed inference program reads.
The 30 PRACTICE rows of the development bank are scored with Motor's own
practice scorer; nothing private is read. The result carries PRACTICE-SAFETY-01's
feedback-only safety block for the same predictions, exactly as Level 0
practice attaches it, read through the provider (`research.safety_feedback`;
Validator, 2026-10-21), so this module never imports the safety code.

A catalog entry whose child image is not installed on this host is refused
before anything runs or is charged (`backend_not_served`, listing the entries
that are installed).
"""

from __future__ import annotations

import json
from pathlib import Path

from .challenge import CHALLENGE

VERSION = "1.2"
PROVENANCE = "MOTOR_PUBLIC_PRACTICE"
#: v2 adds the `safety` block (Validator, 2026-10-21); v1 had none.
#: v3 adds the shared `practice_dual` block (C13); v2 added `safety`.
FEEDBACK_SCHEMA = "carbon.motor.catalog-practice-feedback.v3"
FEEDBACK_SCHEMA_V2 = "carbon.motor.catalog-practice-feedback.v2"
FEEDBACK_SCHEMA_V1 = "carbon.motor.catalog-practice-feedback.v1"


class MotorCatalogPractice:
    construction_mode = "direct"

    def __init__(
        self,
        *,
        ledger,
        owner,
        parent,
        cache_root,
        root=".",
        version=VERSION,
        runner=None,
        resolver=None,
        parents=None,
    ):
        self.ledger, self.owner = ledger, owner
        self.parent, self.cache_root = parent, Path(cache_root)
        self.root, self.version, self.runner = Path(root), version, runner
        self.resolver = resolver
        self._parents = parents
        self.backends = ("torch_cpu",)
        self.gpu_image = None

    # -- what this host can build ---------------------------------------------

    def parents(self):
        """The construction parent of each bundle runtime served here.

        The PyTorch CPU worker always; the C-03 CPU worker it was built FROM
        only when Docker finds that exact image installed. Otherwise a
        `python-cpu-py311` entry is `backend_not_served` on this host.
        """
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
        # The parent comes from the bundle's pinned runtime alone; a runtime
        # with no parent here is refused before any image is looked up.
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
        for item in listing.entries(CHALLENGE.challenge_id, self.version):
            try:
                self._resolve(_bundle_ref(item["bundle_ref"]))
            except (FileNotFoundError, ValueError, OSError):
                continue
            found.append(item["catalog_id"])
        return tuple(found)

    def backend_refusal(self, strategy):
        """The installed entries when `strategy`'s entry has no installed child
        here (`backend_not_served`, before dispatch, nothing charged); None
        when it can run, or when the recipe itself is refused later by code."""
        try:
            expanded = self._expanded(strategy)
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

        return physical_material.bundle_material(CHALLENGE.challenge_id, self.version)

    def _expanded(self, strategy, material=None, runtime=None):
        from carbon.backbone_catalog.served import expand
        from carbon.development_session.construction_recipe import bind_recipe

        kit = (material or self._material())["construction_kit"]
        recipe = bind_recipe(
            strategy,
            challenge_id=kit["id"],
            challenge_version=kit["version"],
            train_digest=kit["train_digest"],
            interface_digest=kit["interface_digest"],
            construction_limits_digest=kit["construction_limits_digest"],
        )
        if recipe.to_dict()["source"]["kind"] != "catalog":
            raise ValueError("motor_catalog_recipe_required")
        return expand(recipe.to_dict(), runtime)

    def __call__(self, identity, strategy):
        from carbon.challenge_kit.interface_dtype import output_dtype
        from carbon.development_session.bundle_construction_worker import (
            reconstruct_and_infer_public,
        )
        from carbon.development_session.construction_recipe import ConstructionRecipe
        from carbon.development_session.profile import canonical, digest
        from carbon.development_session.research_workspace import ResearchWorkspace
        from carbon.scoring import motor_dual_pack, practice_dual

        from .challenge import PublicMaterial
        from .practice import PracticeSet, score_practice
        from .research import safety_feedback

        material = self._material()
        # Motor's practice query is the whole public development bank (90 cases,
        # of which the 30 PRACTICE cases are scored below), so the exam's dual
        # measurement (C13) is computable on the same rows.
        practice_inputs = material["practice_inputs"]
        adapter = practice_dual.versioned(motor_dual_pack, self.version)
        source_kind = (
            strategy.get("source", {}).get("kind")
            if type(strategy) is dict and type(strategy.get("source")) is dict
            else None
        )
        kit = material["construction_kit"]
        if source_kind == "graph":
            # Graph route v2: the miner's own graph on Carbon's graph training
            # adapter, one path for every Challenge (`graph_adapters.practise`).
            from carbon.development_session import graph_adapters
            from carbon.development_session.construction_recipe import bind_recipe

            bound = bind_recipe(
                strategy,
                challenge_id=kit["id"],
                challenge_version=kit["version"],
                train_digest=kit["train_digest"],
                interface_digest=kit["interface_digest"],
                construction_limits_digest=kit["construction_limits_digest"],
            )
            try:
                result, _backend = graph_adapters.practise(
                    self.ledger,
                    owner=self.owner,
                    parent=self.parent,
                    runner=self.runner,
                    recipe=bound,
                    binding={
                        "challenge_id": kit["id"],
                        "challenge_version": kit["version"],
                        "train_digest": kit["train_digest"],
                        "interface_digest": kit["interface_digest"],
                        "construction_limits_digest": kit["construction_limits_digest"],
                    },
                    material=material,
                    identity=identity,
                )
            except graph_adapters.GraphAdapterUnregistered:
                raise ValueError("motor_catalog_recipe_required") from None
            recipe = bound
            catalog_source = {"catalog_id": None, "catalog_digest": None}
            bundle_recipe_digest = None
            accelerator = construction_parent = gpu_note = None
        else:
            from carbon.development_session.gpu_practice import (
                device_build,
                gpu_overlay,
            )

            expanded, _bundle, image, construction_parent, accelerator, gpu_note = (
                device_build(
                    self,
                    lambda runtime: self._expanded(strategy, material, runtime),
                    _bundle_ref,
                    lambda bundle, parent, built: gpu_overlay(
                        self,
                        identity,
                        bundle,
                        parent,
                        built,
                        material["construction_kit"],
                        material["construction_limits_document"],
                    ),
                )
            )
            recipe = ConstructionRecipe.from_dict(expanded)
            kit = material["construction_kit"]
            result = reconstruct_and_infer_public(
                self.ledger,
                owner=self.owner,
                identity=identity,
                image=image,
                inference_image=self.parent,
                construction_parent=construction_parent,
                recipe=recipe,
                # The worker's trusted binding names the kit by challenge_id /
                # challenge_version (`_checked_binding`), as the receiver's does.
                challenge_binding={
                    "challenge_id": kit["id"],
                    "challenge_version": kit["version"],
                    "train_digest": kit["train_digest"],
                    "interface_digest": kit["interface_digest"],
                    "construction_limits_digest": kit["construction_limits_digest"],
                },
                limits_document=material["construction_limits_document"],
                train=material["train"],
                example=material["example"],
                seed=0,
                inputs=practice_inputs,
                expected_output_shape=material["expected_output_shape"],
                allowlist_bytes=material["allowlist_bytes"],
                expected_output_dtype=output_dtype(material["interface_document"]),
                accelerator=accelerator,
                runner=self.runner,
            )
            if result.build.state_digest != result.inference.state_digest:
                raise ValueError("motor catalog practice state differs between phases")
        rows = result.inference.predictions
        practice = PracticeSet.load(self.root)
        by_case = dict(zip(material["practice_case_ids"], rows))
        predictions = {
            record["case_id"]: {
                "torque_nm": [float(v) for v in by_case[record["case_id"]]]
            }
            for record in practice.records
            if record["case_id"] in by_case
        }
        _rows, summary = score_practice(
            predictions, practice, PublicMaterial.load(self.root)
        )
        if source_kind != "graph":
            source = json.loads(canonical(strategy))["source"]
            catalog_source = {
                "catalog_id": source["catalog_id"],
                "catalog_digest": source["catalog_digest"],
            }
            bundle_recipe_digest = recipe.digest
        out = {
            "schema": FEEDBACK_SCHEMA,
            "provenance": PROVENANCE,
            "challenge": {"id": kit["id"], "version": kit["version"]},
            **catalog_source,
            **({"source_kind": "graph"} if source_kind == "graph" else {}),
            "recipe_digest": ConstructionRecipe.from_dict(strategy).digest,
            "bundle_recipe_digest": bundle_recipe_digest,
            "summary": summary,
            "fit": {"state_digest": result.build.state_digest},
            "backend": {
                "kind": "C03_DOCKER_GPU" if accelerator else "C03_DOCKER",
                "parent": getattr(construction_parent, "image_id", None),
                **({"gpu_note": gpu_note} if gpu_note else {}),
            },
            "adaptively_seen": True,
            "final_exam": False,
            "official_eligible": False,
            # PRACTICE-SAFETY-01: feedback only, on the same public cases.
            "safety": safety_feedback(predictions, practice),
            "recipe": strategy,
            # C13: the exam's dual measurement on the public development bank.
            "practice_dual": (
                practice_dual.unavailable(
                    motor_dual_pack, "practice_version_not_registered"
                )
                if adapter is None
                else practice_dual.from_rows(adapter, rows)
            ),
        }
        ResearchWorkspace(self.ledger, self.owner).put(
            "trial-" + digest(identity.encode())[7:23] + "-motor-catalog-practice.json",
            canonical(out),
        )
        return out


def _bundle_ref(value):
    from carbon.development_session.library_bundles import LibraryBundleRef

    return LibraryBundleRef(
        value["schema"],
        value["bundle_digest"],
        value["language"],
        value["runtime_profile_id"],
        value["environment_digest"],
    )
