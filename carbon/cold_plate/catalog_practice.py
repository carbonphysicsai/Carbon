"""Cooling catalog practice (OWNER-BACKBONE-CATALOG-01): a catalog recipe built
on public TRAIN and scored on public PRACTICE, built as the receiver builds it.

A port of Motor's (`carbon.motor.catalog_practice`). A catalog recipe names one
of Carbon's tested backbones; it is expanded to the Carbon bundle it stands for
(`backbone_catalog.served.expand`) and rebuilt by the receiver's own two-phase
call, `bundle_construction_worker.reconstruct_and_infer_public`, with the
receiver's build inputs: the version's public construction material (kit,
limits, TRAIN, allowlist), its installed child image over the parent of the
bundle's pinned runtime, and seed 0. A `torch-cpu-py311` bundle builds on the
campaign's PyTorch CPU worker; a `python-cpu-py311` bundle on the C-03 CPU
worker that worker was built FROM. Inference stays on the PyTorch CPU worker.

Cooling's development bank holds no PRACTICE rows (only its 48 decision
cells), so the public probe and the query are the 100 public PRACTICE inputs,
laid out by the numeric interface's input names. Each predicted row is mapped
back to Cooling's outputs by the interface's own target slices (peak_c,
profile_c, pressure_drop_pa) and scored with Cooling's own practice scorer
(`carbon.cold_plate.practice.score_practice`); labels stay on this host and
nothing private is read. The result carries Cooling's practice provenance, so
a practised recipe supports a freeze as Level 0's does, and PRACTICE-SAFETY-01's
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

from .challenge import CHALLENGE, PUBLIC_OUTPUTS
from .practice import PROVENANCE

#: v3 adds the shared `practice_dual` block (C13), which for Cooling says it is
#: unavailable on practice (below); v2 added `safety`.
FEEDBACK_SCHEMA = "carbon.cold-plate.catalog-practice-feedback.v3"
FEEDBACK_SCHEMA_V2 = "carbon.cold-plate.catalog-practice-feedback.v2"
FEEDBACK_SCHEMA_V1 = "carbon.cold-plate.catalog-practice-feedback.v1"


class CoolingCatalogPractice:
    construction_mode = "direct"

    def __init__(
        self,
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
        from .campaign import CATALOG_VERSIONS

        if version not in CATALOG_VERSIONS:
            raise ValueError("cooling catalog version required")
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
            raise ValueError("cooling_catalog_recipe_required")
        return expand(recipe.to_dict(), runtime)

    def __call__(self, identity, strategy):
        import numpy as np

        from carbon.challenge_kit.interface_dtype import output_dtype
        from carbon.development_session.bundle_construction_worker import (
            reconstruct_and_infer_public,
        )
        from carbon.development_session.construction_recipe import ConstructionRecipe
        from carbon.development_session.profile import canonical, digest
        from carbon.development_session.research_workspace import ResearchWorkspace

        from .challenge import PublicMaterial
        from .practice import PracticeSet, score_practice
        from .research import safety_feedback

        material = self._material()
        from carbon.development_session.gpu_practice import device_build, gpu_overlay

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
        interface = material["interface_document"]
        slices = interface["target_slices"]
        width = max(end for _, end in slices.values())
        practice = PracticeSet.load(self.root)
        # The public PRACTICE inputs in the interface's input order and dtype:
        # the probe and the query (Cooling's bank has no PRACTICE rows).
        inputs = np.asarray(
            [
                [float(record["inputs"][name]) for name in interface["input_names"]]
                for record in practice.records
            ],
            dtype=interface["dtype"],
        )
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
            example=inputs,
            seed=0,
            inputs=inputs,
            expected_output_shape=(len(practice.records), width),
            allowlist_bytes=material["allowlist_bytes"],
            expected_output_dtype=output_dtype(interface),
            accelerator=accelerator,
            runner=self.runner,
        )
        if result.build.state_digest != result.inference.state_digest:
            raise ValueError("cooling catalog practice state differs between phases")
        rows = result.inference.predictions
        if len(rows) != len(practice.records):
            raise ValueError("cooling catalog practice row count differs")
        predictions = {
            record["case_id"]: _outputs(row, slices)
            for record, row in zip(practice.records, rows, strict=True)
        }
        _rows, summary = score_practice(
            predictions, practice, PublicMaterial.load(self.root)
        )
        source = json.loads(canonical(strategy))["source"]
        out = {
            "schema": FEEDBACK_SCHEMA,
            "provenance": PROVENANCE,
            "challenge": {"id": kit["id"], "version": kit["version"]},
            "catalog_id": source["catalog_id"],
            "catalog_digest": source["catalog_digest"],
            "recipe_digest": ConstructionRecipe.from_dict(strategy).digest,
            "bundle_recipe_digest": recipe.digest,
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
            "scientific_qualification": False,
            # PRACTICE-SAFETY-01: feedback only, on the same public cases.
            "safety": safety_feedback(predictions, practice),
            "recipe": strategy,
            # C13: the exam's dual measurement needs Cooling's development bank,
            # whose rows are the counted decision-study evidence the miner-side
            # read boundary denies (and its decision rules live in that study's
            # module). Until the bank has a public mirror and a public decision
            # module (the Validator's ruling), practice says so, never silently.
            "practice_dual": {
                "schema": "carbon.practice.dual-feedback.v1",
                "scope": "PUBLIC_PRACTICE_FEEDBACK",
                "challenge": {"id": kit["id"], "version": kit["version"]},
                "available": False,
                "reason": "practice_dual_not_public_for_cooling",
            },
        }
        ResearchWorkspace(self.ledger, self.owner).put(
            "trial-"
            + digest(identity.encode())[7:23]
            + "-cold-plate-catalog-practice.json",
            canonical(out),
        )
        return out


def _outputs(row, slices):
    """One predicted row as Cooling's named outputs, by the interface's target
    slices; a scalar output (shape []) is a number, a profile a list."""
    values = [float(v) for v in row]
    out = {}
    for name, (start, end) in slices.items():
        part = values[start:end]
        out[name] = part[0] if PUBLIC_OUTPUTS[name]["shape"] == [] else part
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
