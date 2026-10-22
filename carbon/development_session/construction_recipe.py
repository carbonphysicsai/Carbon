"""Inert identity for the prospective direct construction path.

This is the one public recipe shape shared by graph, source-bundle and
catalog builds (a catalog recipe runs as the Carbon bundle it names:
`carbon.backbone_catalog.served.expand`).
Parsing and binding never admit code, verify a graph, provision an image, or
grant scientific authority. The isolated builder must verify the referenced
bytes and execute the actual declared procedure against Challenge TRAIN.
Historical level/variant records keep their original reader and digests.
"""

from __future__ import annotations

import hashlib
import json
import re

from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy

SCHEMA = "carbon.construction-recipe.v1"
MAX_BYTES = 2 * 1024 * 1024
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*\Z")
_REF_SCHEMA = "carbon.library-bundle-ref.v1"
_CHALLENGE = {
    "id",
    "version",
    "train_digest",
    "interface_digest",
    "construction_limits_digest",
}
_PROCEDURE = {"entrypoint", "configuration", "train_use", "initial_state"}
#: A graph, a source bundle, or one of Carbon's tested backbones by catalog id.
SOURCE_KINDS = ("graph", "bundle", "catalog")
_OUTPUT = {"format", "interface_digest"}


class RecipeRefused(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise RecipeRefused("construction_recipe_malformed") from None


def _digest(value: object) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _document(value: object) -> dict:
    if (
        type(value) is not dict
        or set(value) != {"schema", "challenge", "source", "procedure", "output"}
        or value["schema"] != SCHEMA
    ):
        raise RecipeRefused("construction_recipe_malformed")
    challenge, source, procedure, output = (
        value["challenge"],
        value["source"],
        value["procedure"],
        value["output"],
    )
    if (
        type(challenge) is not dict
        or set(challenge) != _CHALLENGE
        or any(
            type(challenge[k]) is not str or not challenge[k] for k in ("id", "version")
        )
        or any(
            not _digest(challenge[k])
            for k in ("train_digest", "interface_digest", "construction_limits_digest")
        )
    ):
        raise RecipeRefused("construction_recipe_challenge_invalid")
    if type(source) is not dict or source.get("kind") not in SOURCE_KINDS:
        raise RecipeRefused("construction_recipe_source_invalid")
    if source["kind"] == "graph":
        if set(source) != {"kind", "submission_digest"} or not _digest(
            source["submission_digest"]
        ):
            raise RecipeRefused("construction_recipe_source_invalid")
    elif source["kind"] == "catalog":
        # One of Carbon's tested backbones by catalog id (OWNER-BACKBONE-
        # CATALOG-01). Structural only: which ids a Challenge version serves,
        # and what they run, is `carbon.backbone_catalog.served`'s.
        if (
            set(source) != {"kind", "catalog_id", "catalog_digest"}
            or type(source["catalog_id"]) is not str
            or _TOKEN.fullmatch(source["catalog_id"]) is None
            or not _digest(source["catalog_digest"])
        ):
            raise RecipeRefused("construction_recipe_source_invalid")
    else:
        ref = source.get("bundle_ref")
        if (
            set(source) != {"kind", "bundle_ref"}
            or type(ref) is not dict
            or set(ref)
            != {
                "schema",
                "bundle_digest",
                "language",
                "runtime_profile_id",
                "environment_digest",
            }
            or ref["schema"] != _REF_SCHEMA
            or not _digest(ref["bundle_digest"])
            or not _digest(ref["environment_digest"])
            or ref["language"] not in ("python", "julia")
            or type(ref["runtime_profile_id"]) is not str
            or not ref["runtime_profile_id"]
        ):
            raise RecipeRefused("construction_recipe_source_invalid")
    if type(procedure) is not dict or set(procedure) != _PROCEDURE:
        raise RecipeRefused("construction_recipe_procedure_invalid")
    entrypoint = procedure["entrypoint"]
    if source["kind"] in ("graph", "catalog"):
        if entrypoint is not None:
            raise RecipeRefused("construction_recipe_procedure_invalid")
    elif (
        type(entrypoint) is not dict
        or set(entrypoint) != {"module", "name"}
        or any(
            type(entrypoint[k]) is not str or _TOKEN.fullmatch(entrypoint[k]) is None
            for k in ("module", "name")
        )
    ):
        raise RecipeRefused("construction_recipe_procedure_invalid")
    if (
        type(procedure["configuration"]) is not dict
        or type(procedure["train_use"]) is not dict
    ):
        raise RecipeRefused("construction_recipe_procedure_invalid")
    # The schema offers no submitted trained-state input. The worker still
    # needs closure/provenance controls; arbitrary source can encode information.
    if procedure["initial_state"] is not None:
        raise RecipeRefused("construction_recipe_pretrained_state_forbidden")
    if (
        type(output) is not dict
        or set(output) != _OUTPUT
        or type(output["format"]) is not str
        or not output["format"]
        or not _digest(output["interface_digest"])
        or output["interface_digest"] != challenge["interface_digest"]
    ):
        raise RecipeRefused("construction_recipe_output_invalid")
    return value


class ConstructionRecipe:
    """Canonical immutable bytes; possession is never admission."""

    __slots__ = ("_raw",)

    def __init__(self, value: object):
        raw = _canonical(value)
        if len(raw) > MAX_BYTES:
            raise RecipeRefused("construction_recipe_oversized")
        try:
            parsed = parse_strategy(raw, max_bytes=MAX_BYTES)
        except MalformedStrategy:
            raise RecipeRefused("construction_recipe_malformed") from None
        _document(parsed)
        object.__setattr__(self, "_raw", _canonical(parsed))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("construction recipe is immutable")

    @classmethod
    def from_dict(cls, value: object) -> ConstructionRecipe:
        return cls(value)

    @classmethod
    def from_bytes(cls, value: bytes) -> ConstructionRecipe:
        if type(value) is not bytes or len(value) > MAX_BYTES:
            raise RecipeRefused("construction_recipe_malformed")
        try:
            parsed = parse_strategy(value, max_bytes=MAX_BYTES)
        except MalformedStrategy:
            raise RecipeRefused("construction_recipe_malformed") from None
        return cls(parsed)

    def to_dict(self) -> dict:
        return json.loads(self._raw)

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self._raw).hexdigest()

    @property
    def canonical_bytes(self) -> bytes:
        return self._raw


def bind_recipe(
    value: object,
    *,
    challenge_id: str,
    challenge_version: str,
    train_digest: str,
    interface_digest: str,
    construction_limits_digest: str,
) -> ConstructionRecipe:
    """Compare registered identities; execution and semantic checks remain separate."""
    recipe = ConstructionRecipe.from_dict(value)
    declared = recipe.to_dict()["challenge"]
    expected = {
        "id": challenge_id,
        "version": challenge_version,
        "train_digest": train_digest,
        "interface_digest": interface_digest,
        "construction_limits_digest": construction_limits_digest,
    }
    if declared != expected or any(
        not _digest(expected[k])
        for k in ("train_digest", "interface_digest", "construction_limits_digest")
    ):
        raise RecipeRefused("construction_recipe_binding_mismatch")
    return recipe


def recipe_graph_bounds(recipe: ConstructionRecipe) -> dict:
    """The intake bounds of the recipe's exact Challenge version's graph
    allowlist (`served_versions.graph_intake_bounds`). Host side only: the
    isolated workers do not stage `carbon.challenge_kit`."""
    from carbon.challenge_kit.served_versions import graph_intake_bounds

    challenge = recipe.to_dict()["challenge"]
    return graph_intake_bounds(challenge["id"], challenge["version"])


def graph_workspace(
    recipe: ConstructionRecipe,
    raw_manifest: bytes,
    files: dict,
    *,
    max_bytes: int,
) -> dict[str, bytes]:
    """Bind bounded graph bytes to a recipe before existing G0–G4 checks.

    This is byte identity and staging only. The caller still runs the
    Challenge's registered interface, operation and resource validation.
    """
    from carbon.level4 import graph, staging

    if type(recipe) is not ConstructionRecipe:
        raise RecipeRefused("construction_recipe_malformed")
    source = recipe.to_dict()["source"]
    if source["kind"] != "graph":
        raise RecipeRefused("construction_recipe_source_invalid")
    if (
        type(max_bytes) is not int
        or max_bytes <= 0
        or type(raw_manifest) is not bytes
        or type(files) is not dict
        or len(raw_manifest) > max_bytes
        or any(
            type(name) is not str
            or type(body) is not bytes
            or len(name.encode("utf-8")) + len(body) > max_bytes
            for name, body in files.items()
        )
        or sum(len(name.encode("utf-8")) + len(body) for name, body in files.items())
        + len(raw_manifest)
        > max_bytes
    ):
        raise RecipeRefused("construction_recipe_graph_bytes_invalid")
    try:
        actual = staging.check(raw_manifest, files)
    except graph.GraphRefused:
        raise RecipeRefused("construction_recipe_graph_bytes_invalid") from None
    if actual != source["submission_digest"]:
        raise RecipeRefused("construction_recipe_graph_digest_mismatch")
    return staging.workspace(raw_manifest, files)


def graph_envelope_from_workspace(
    ledger, owner: str, recipe: ConstructionRecipe
) -> bytes:
    """Resolve exact graph bytes from this owner's existing flat workspace.

    The public recipe names only a content digest. No caller path or second
    upload format is accepted: the already-served ResearchWorkspace supplies
    the manifest and its digest-named documents, which the worker rechecks.
    """
    from carbon.level4 import staging

    from .research_workspace import ResearchWorkspace, WorkspaceFileMissing

    if (
        type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] != "graph"
    ):
        raise RecipeRefused("construction_recipe_source_invalid")
    bounds = recipe_graph_bounds(recipe)
    workspace = ResearchWorkspace(ledger, owner)
    try:
        raw_manifest = workspace.get(staging.WORKSPACE_MANIFEST)
    except WorkspaceFileMissing:
        raise RecipeRefused("construction_recipe_graph_workspace_missing") from None
    try:
        manifest = parse_strategy(raw_manifest, max_bytes=bounds["manifest_bytes"])
    except MalformedStrategy:
        raise RecipeRefused("construction_recipe_graph_manifest_invalid") from None
    names = manifest.get("documents") if type(manifest) is dict else None
    if type(names) is not dict or not set(names) <= {
        "forward",
        "loss",
        "init",
        "init_spec",
    }:
        raise RecipeRefused("construction_recipe_graph_manifest_invalid")
    files = {}
    for document in names.values():
        if type(document) is not str or not _SHA.fullmatch(document):
            raise RecipeRefused("construction_recipe_graph_manifest_invalid")
        try:
            files[document] = workspace.get(
                staging.WORKSPACE_PREFIX + document[7:] + ".json"
            )
        except WorkspaceFileMissing:
            raise RecipeRefused("construction_recipe_graph_workspace_missing") from None
    graph_workspace(recipe, raw_manifest, files, max_bytes=bounds["submission_bytes"])
    return _canonical(staging.envelope(raw_manifest, files))
