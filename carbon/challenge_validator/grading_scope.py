"""Whether a grading-path change reaches the version a door serves (v2 RE-RULING #5, 22 Nov 2026).

ONE function, `not_served`, answers for the receiver's M2 migration (`direct_receiver._migrate_owner_manifest`) and for the
release precheck (`scripts/dev/release/exam_identity.py`), so Deploy and the door never disagree. It clears a changed
grading path for a door only in two shapes, and only when EVERY changed path is cleared:

* ``keyed-other``: a ``'<challenge> <version>'``-keyed registry (`KEYED_JSON`, with where its keyed dict sits) whose
  JSON-aware old/new diff keeps every other top-level field and every served pair's entry canonical-equal and present,
  and changes only other pairs' entries. Any other file, a parse failure or a duplicate key is GLOBAL.
* ``pure-addition``: a NEW ``.py`` file that no existing file imports statically, that no existing file names, that is no
  package ``__init__``, shadows no package and is no overlay dispatch module, and that no computed-name import site can
  resolve (`DYNAMIC_SITES`: every such site of the grade's import closure and the grading paths, each with the module
  names it can reach; a site the table does not list makes every addition GLOBAL). A modified, deleted or renamed file
  keeps today's check.

Anything else, any doubt and any failure (git, parse, an unknown file) is GLOBAL: the caller then behaves exactly as
before. Standard library only, so the release tool can load this file without importing carbon.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

#: This file, repo-relative: a caller's copy that differs from NEW's clears nothing.
SELF = "carbon/challenge_validator/grading_scope.py"
KEYED_OTHER = "keyed-other"
PURE_ADDITION = "pure-addition"
CLEARED = frozenset({KEYED_OTHER, PURE_ADDITION})
#: The grade-path JSON files keyed by ``'<challenge> <version>'`` and the key path of the keyed dict in each (read at
#: main 3ab2df10a: every other grade-path JSON is keyed otherwise or not at all, so it is GLOBAL).
KEYED_JSON = {
    "scripts/validator_host_classes/crown_official_score.json": ("versions",),
}
#: A ``'<challenge> <version>'`` key (``crown_official.registered`` builds it as ``f"{challenge_id} {version}"``).
PAIR = re.compile(r"[a-z0-9][a-z0-9-]* [0-9]+(?:\.[0-9]+)*")
#: Where the grade and the rebuild start (`tests/cpu/test_grading_paths.CORE`); the scope follows their imports.
CORE = (
    "carbon.challenge_validator.lean_recipe_retention",
    "carbon.development_session.bundle_construction_worker",
    "carbon.development_session.direct_graph_construction_worker",
)
#: Existing files a new module's name is searched in (the trees the grade and the door read code and registries from).
TEXT_ROOTS = ("carbon/", "scripts/validator_host_classes/")
#: Calls that import, load or run code by a computed name or path.
IMPORT_CALLS = frozenset(
    {
        "import_module",
        "__import__",
        "find_spec",
        "spec_from_file_location",
        "spec_from_loader",
        "module_from_spec",
        "exec_module",
        "load_module",
        "SourceFileLoader",
        "run_path",
        "run_module",
        "walk_packages",
        "iter_modules",
        "reload",
    }
)
#: Builtins that run code text (only as a bare name: ``model.eval()`` is not one).
CODE_CALLS = frozenset({"exec", "eval"})
_MODULE_TEXT = re.compile(r"carbon(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
_REV = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
#: A name no repository module has (`DYNAMIC_SITES` rows whose site never reaches a carbon module).
_NONE = None
_PUBLIC = r"carbon\.challenge_kit\.[a-z0-9_]+_public"
_POPULATION = r"carbon\..+\.(?:population|domain)"
_BACKBONES = r"carbon\.backbones\..+"

#: Every computed-name import site of the grade's import closure and of the grading paths:
#: ``(file, call, argument source, count, kind, pattern)``. ``pattern`` is the module names the site can resolve beyond
#: the names written in existing files (the text check, `_named_in_text`, already makes those GLOBAL), or None.
#: ``tests/cpu/test_grading_scope.py`` pins this table against an ast scan (`dynamic_sites`): a new site fails it.
DYNAMIC_SITES = (
    (
        "carbon/agent_campaign/attack/adapter.py",
        "find_spec",
        "BUILTIN_PACKAGE",
        1,
        "literal",
        _NONE,
    ),
    (
        "carbon/agent_campaign/attack/adapter.py",
        "import_module",
        "BUILTIN_PACKAGE",
        1,
        "literal",
        _NONE,
    ),
    (
        "carbon/agent_campaign/attack/adapters/__init__.py",
        "find_spec",
        '"carbon.agent_campaign.attack.adapter"',
        1,
        "literal",
        _NONE,
    ),
    (
        "carbon/agent_campaign/attack/adapters/__init__.py",
        "import_module",
        "name",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/agent_campaign/attack/adapters/battery.py",
        "exec",
        "_program_tail(practice.PROGRAM)",
        1,
        "program_text",
        _NONE,
    ),
    (
        "carbon/agent_campaign/attack/adapters/battery.py",
        "find_spec",
        "name",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/agent_campaign/attack/adapters/cooling.py",
        "exec",
        "program",
        1,
        "program_text",
        _NONE,
    ),
    (
        "carbon/backbones/__init__.py",
        "import_module",
        "module_name",
        1,
        "adapter_table",
        _BACKBONES,
    ),
    (
        "carbon/backbones/neural_operator.py",
        "import_module",
        '"neuralop.models"',
        1,
        "non_carbon",
        _NONE,
    ),
    (
        "carbon/backbones/physicsnemo.py",
        "import_module",
        '"physicsnemo.models.fno"',
        1,
        "non_carbon",
        _NONE,
    ),
    (
        "carbon/battery/level4_worker.py",
        "exec_module",
        "_module",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/battery/level4_worker.py",
        "module_from_spec",
        "_spec",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/battery/level4_worker.py",
        "spec_from_file_location",
        "_name",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/battery/plating_v2.py",
        "exec",
        'compile(raw, module.__file__, "exec")',
        1,
        "pinned_file",
        _NONE,
    ),
    ("carbon/battery/worker.py", "find_spec", "m", 1, "non_carbon", _NONE),
    (
        "carbon/challenge_kit/version_overlay.py",
        "find_spec",
        "name",
        1,
        "sealed_target",
        _NONE,
    ),
    (
        "carbon/challenge_kit/version_overlay.py",
        "import_module",
        'block["module"]',
        1,
        "overlay_dispatch",
        _NONE,
    ),
    (
        "carbon/challenge_pipeline/structures_readiness.py",
        "exec_module",
        "module",
        1,
        "pinned_file",
        _NONE,
    ),
    (
        "carbon/challenge_pipeline/structures_readiness.py",
        "module_from_spec",
        "spec",
        1,
        "pinned_file",
        _NONE,
    ),
    (
        "carbon/challenge_pipeline/structures_readiness.py",
        "spec_from_file_location",
        '"carbon_f08_deck"',
        1,
        "pinned_file",
        _NONE,
    ),
    (
        "carbon/challenge_registry/pinned_module.py",
        "import_module",
        "name",
        1,
        "pinned_row",
        _NONE,
    ),
    (
        "carbon/challenge_registry/registry.py",
        "find_spec",
        "module",
        1,
        "non_carbon",
        _NONE,
    ),
    (
        "carbon/challenge_validator/confirmation_sources.py",
        "import_module",
        'f"carbon.{self.module}.population"',
        1,
        "population_source",
        _POPULATION,
    ),
    (
        "carbon/challenge_validator/confirmation_sources.py",
        "import_module",
        'f"carbon.{self.module}.domain"',
        1,
        "population_source",
        _POPULATION,
    ),
    (
        "carbon/challenge_validator/confirmation_sources.py",
        "import_module",
        'f"carbon.{self.module}.{name}"',
        1,
        "population_source",
        _POPULATION,
    ),
    (
        "carbon/development_comparison/numerical.py",
        "exec_module",
        "module",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/development_comparison/numerical.py",
        "module_from_spec",
        "spec",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/development_comparison/numerical.py",
        "spec_from_file_location",
        "name",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/development_session/bundle_construction_worker.py",
        "import_module",
        'entry["module"]',
        1,
        "worker_image",
        _NONE,
    ),
    (
        "carbon/development_session/construction_level.py",
        "python -m",
        "CLI_MODULE",
        1,
        "literal",
        _NONE,
    ),
    (
        "carbon/development_session/gpu_code_cell.py",
        "run_path",
        '"carbon-miner-program.py"',
        1,
        "miner_file",
        _NONE,
    ),
    (
        "carbon/development_session/research_carrier.py",
        "exec",
        'compile(boot,"<string>","exec")',
        1,
        "program_text",
        _NONE,
    ),
    (
        "carbon/development_session/research_numerical.py",
        "exec_module",
        "module",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/development_session/research_numerical.py",
        "module_from_spec",
        "spec",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/development_session/research_numerical.py",
        "spec_from_file_location",
        "name",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/direct_campaign/spec.py",
        "import_module",
        "self.public_module",
        1,
        "public_module",
        _PUBLIC,
    ),
    ("carbon/level4/compile.py", "exec_module", "module", 1, "literal_list", _NONE),
    ("carbon/level4/compile.py", "module_from_spec", "spec", 1, "literal_list", _NONE),
    (
        "carbon/level4/compile.py",
        "spec_from_file_location",
        "name",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/level4/interpret.py",
        "import_module",
        "info.name",
        1,
        "non_carbon",
        _NONE,
    ),
    (
        "carbon/level4/interpret.py",
        "walk_packages",
        "lax_package.__path__",
        1,
        "non_carbon",
        _NONE,
    ),
    (
        "carbon/level4/tooling/__main__.py",
        "exec_module",
        "module",
        1,
        "miner_file",
        _NONE,
    ),
    (
        "carbon/level4/tooling/__main__.py",
        "module_from_spec",
        "spec",
        1,
        "miner_file",
        _NONE,
    ),
    (
        "carbon/level4/tooling/__main__.py",
        "spec_from_file_location",
        '"level4_submission_spec"',
        1,
        "miner_file",
        _NONE,
    ),
    (
        "carbon/motor/score_candidates.py",
        "__import__",
        '"json"',
        1,
        "non_carbon",
        _NONE,
    ),
    (
        "carbon/reconstruction/worker/backend_probe.py",
        "import_module",
        '"jax"',
        1,
        "non_carbon",
        _NONE,
    ),
    (
        "carbon/reconstruction/worker/backend_probe.py",
        "import_module",
        '"jaxlib"',
        1,
        "non_carbon",
        _NONE,
    ),
    (
        "carbon/reconstruction/worker/image_modules.py",
        "__import__",
        '"carbon"',
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/reconstruction/worker/image_modules.py",
        "find_spec",
        "name",
        1,
        "literal_list",
        _NONE,
    ),
    (
        "carbon/reconstruction/worker/image_modules.py",
        "import_module",
        "name",
        1,
        "literal_list",
        _NONE,
    ),
    ("carbon/research/model.py", "__import__", '"typing"', 1, "non_carbon", _NONE),
    (
        "carbon/scoring/cooling_encoded_dual_pack.py",
        "__import__",
        '"sys"',
        1,
        "non_carbon",
        _NONE,
    ),
    (
        "carbon/scoring/dev_grid.py",
        "import_module",
        "version_overlay.SEALED_TARGET[key[0]]",
        1,
        "sealed_target",
        _NONE,
    ),
    (
        "carbon/scoring/f02_sealed_dual_pack.py",
        "__import__",
        '"carbon.challenge_kit.f02_train"',
        1,
        "literal",
        _NONE,
    ),
    (
        "carbon/scoring/physical_dual_pack.py",
        "import_module",
        "module",
        1,
        "literal_target",
        _NONE,
    ),
    (
        "carbon/training_budget/adapter.py",
        "import_module",
        "module",
        2,
        "adapter_registry",
        _NONE,
    ),
)
#: What each kind resolves, said once (the pattern column carries the names a site reaches beyond literal text).
KINDS = {
    "adapter_table": "a name table in the same file; any carbon.backbones module, conservatively",
    "non_carbon": "a third-party or stdlib module only",
    "literal": "one literal name (found by the text check)",
    "literal_list": "names listed literally in existing files (the text check)",
    "literal_target": "'module:function' targets written literally by its callers (the text check)",
    "pinned_file": "one sha-pinned or fixed file outside carbon/",
    "sealed_target": "version_overlay.SEALED_TARGET's literal values (the text check)",
    "overlay_dispatch": "modules a version_overlay.json names: GLOBAL by the dispatch rule and the text check",
    "pinned_row": "modules an exam_registry.json or family_registry.json row names with their sha256 (the text check)",
    "population_source": "carbon.<package>.population / .domain of a PopulationSource",
    "public_module": "a Challenge's carbon.challenge_kit.<prefix>_public module",
    "adapter_registry": "training_budget/adapters.json and adapters' records 'module:attr' (the text check)",
    "worker_image": "a recipe entrypoint in the worker: only image files (build inputs) or literally staged modules",
    "miner_file": "the miner's own file named by path, never a repository module",
    "program_text": "a program text its caller passes (each such text is scanned as a program itself)",
}

_CACHE: dict = {}


class _Doubt(Exception):
    """Something could not be read or told: the change is GLOBAL."""


def _git(root, *args, data=None, timeout=180) -> bytes:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            input=data,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise _Doubt("git_failed") from exc
    if done.returncode != 0:
        raise _Doubt("git_failed")
    return done.stdout


class Tree:
    """One revision's tracked files (mode, type, object id) and their bytes, read through git only."""

    def __init__(self, root, rev):
        if type(rev) is not str or not _REV.fullmatch(rev):
            raise _Doubt("revision_not_a_full_id")
        self.root, self.rev, self.entries = root, rev, {}
        for record in _git(root, "ls-tree", "-r", "-z", "--full-tree", rev).split(
            b"\0"
        ):
            if not record:
                continue
            head, _, path = record.partition(b"\t")
            mode, kind, oid = head.decode("ascii").split(" ")
            self.entries[path.decode("utf-8")] = (mode, kind, oid)
        self._blobs: dict = {}

    def mode(self, path):
        entry = self.entries.get(path)
        return None if entry is None else entry[0]

    def read(self, paths) -> dict:
        """``{path: bytes}`` for tracked blobs (one ``cat-file --batch`` for those not read yet)."""
        want = sorted(
            {self.entries[p][2] for p in paths if p in self.entries} - set(self._blobs)
        )
        if want:
            raw = _git(
                self.root, "cat-file", "--batch", data=("\n".join(want) + "\n").encode()
            )
            at = 0
            for oid in want:
                end = raw.index(b"\n", at)
                got, kind, size = raw[at:end].decode("ascii").split(" ")
                if got != oid or kind != "blob":
                    raise _Doubt("object_not_a_blob")
                start = end + 1
                self._blobs[oid] = raw[start : start + int(size)]
                at = start + int(size) + 1
        return {p: self._blobs[self.entries[p][2]] for p in paths if p in self.entries}


# -- keyed registries -------------------------------------------------------------------------------------------------


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _Doubt("duplicate_key")
    return dict(pairs)


def _strict_json(raw: bytes):
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicates,
            parse_constant=lambda name: (_ for _ in ()).throw(_Doubt("non_finite")),
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise _Doubt("json_unreadable") from exc


def _canonical(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _keyed_verdict(path, old: Tree, new: Tree, served) -> str:
    locator = KEYED_JSON.get(path)
    if locator is None:
        return "global:not_a_keyed_registry"
    if old.mode(path) != "100644" or new.mode(path) != "100644":
        return "global:added_deleted_or_not_a_regular_file"
    try:
        docs = [_strict_json(tree.read([path])[path]) for tree in (old, new)]
    except _Doubt as doubt:
        return f"global:{doubt}"
    keyed, rest = [], []
    for doc in docs:
        holder = doc
        for key in locator[:-1]:
            holder = holder.get(key) if type(holder) is dict else None
        if type(holder) is not dict or type(holder.get(locator[-1])) is not dict:
            return "global:keyed_dict_missing"
        table = holder[locator[-1]]
        if any(type(key) is not str or not PAIR.fullmatch(key) for key in table):
            return "global:entry_keyed_otherwise"
        keyed.append(table)
        # the document with the keyed dict blanked: every other top-level field must be canonical-equal
        holder[locator[-1]] = None
        rest.append(_canonical(doc))
    if rest[0] != rest[1]:
        return "global:other_field_changed"
    for pair in served:
        if pair not in keyed[0] or pair not in keyed[1]:
            return "global:served_entry_absent"
        if _canonical(keyed[0][pair]) != _canonical(keyed[1][pair]):
            return "global:served_entry_changed"
    others = set(keyed[0]) | set(keyed[1])
    if not any(
        _canonical(keyed[0].get(key, _NONE)) != _canonical(keyed[1].get(key, _NONE))
        or (key in keyed[0]) != (key in keyed[1])
        for key in others
    ):
        # the bytes moved but no entry did (layout only): not a change confined to other pairs' entries
        return "global:no_entry_changed"
    return KEYED_OTHER


# -- pure .py additions ------------------------------------------------------------------------------------------------


def _module(path) -> str:
    return path[: -len(".py")].replace("/", ".").removesuffix(".__init__")


def _file(tree: Tree, module):
    base = module.replace(".", "/")
    for candidate in (base + ".py", base + "/__init__.py"):
        if candidate in tree.entries:
            return candidate
    return None


def _programs(tree_ast):
    """Program texts held as string constants (worker programs run with ``python -c`` or written to a file)."""
    for node in ast.walk(tree_ast):
        if (
            isinstance(node, ast.Constant)
            and type(node.value) is str
            and "import" in node.value
            and "\n" in node.value
        ):
            try:
                yield node.value, ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue


def _parse(raw: bytes):
    return ast.parse(raw.decode("utf-8"))


def _import_names(tree_ast, module, package) -> set:
    """Every dotted name ``tree_ast`` imports statically (``from a import b`` names ``a`` and ``a.b``)."""
    named = set()
    for node in ast.walk(tree_ast):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                named.update(".".join(parts[: i + 1]) for i in range(len(parts)))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = module.split(".") if package else module.split(".")[:-1]
                base = base[: len(base) - (node.level - 1)]
                source = ".".join(
                    [*base, *(node.module.split(".") if node.module else [])]
                )
            else:
                source = node.module or ""
            parts = source.split(".")
            named.update(".".join(parts[: i + 1]) for i in range(len(parts)))
            # ``from a import *`` can bind any submodule ``a.__all__`` lists: recorded as ``a.*``
            named.update(source + "." + alias.name for alias in node.names)
    return named


def _call_name(node):
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in IMPORT_CALLS:
        return func.attr
    if isinstance(func, ast.Name) and (
        func.id in IMPORT_CALLS or func.id in CODE_CALLS
    ):
        return func.id
    return None


def _segment(source, node) -> str:
    text = ast.get_source_segment(source, node) or ast.dump(node)
    return re.sub(r"\s+", " ", text).replace("'", '"').strip()


def _sites_in(source: str, tree_ast):
    """``(call, argument source)`` of every computed import / code-run site, in the file and in its program texts;
    plus every ``python -m <computed>`` argv."""
    for text, node_tree in ((source, tree_ast), *_programs(tree_ast)):
        for node in ast.walk(node_tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name is not None:
                    yield name, _segment(text, node.args[0]) if node.args else ""
            elif isinstance(node, (ast.List, ast.Tuple)):
                items = node.elts
                for i, item in enumerate(items[:-1]):
                    nxt = items[i + 1]
                    if (
                        isinstance(item, ast.Constant)
                        and item.value == "-m"
                        and not (
                            isinstance(nxt, ast.Constant) and type(nxt.value) is str
                        )
                    ):
                        yield "python -m", _segment(text, nxt)


def _edges(tree: Tree, module, path, tree_ast):
    """The carbon modules ``module`` reaches by name: static imports (its program texts' too) and literal module names."""
    package = path.endswith("/__init__.py")
    named = _import_names(tree_ast, module, package)
    for _text, program in _programs(tree_ast):
        named |= _import_names(program, "carbon.program", False)
    for node in ast.walk(tree_ast):
        if isinstance(node, ast.Constant) and type(node.value) is str:
            named.update(_MODULE_TEXT.findall(node.value))
    found = set()
    for name in named:
        if name != "carbon" and not name.startswith("carbon."):
            continue
        while name and _file(tree, name) is None:
            name = name.rpartition(".")[0]
        if name and name != "carbon":
            found.add(name)
    return found


def dynamic_sites(tree: Tree, grading) -> Counter:
    """``Counter((file, call, argument))`` of every computed-name site in the grade's closure (from `CORE`, following
    static imports and literal module names) and in every grading-path ``.py`` file of ``tree``.
    """
    sources = {
        path: raw.decode("utf-8")
        for path, raw in tree.read(
            [p for p in tree.entries if p.startswith("carbon/") and p.endswith(".py")]
        ).items()
    }
    parsed = {}

    def parse(path):
        if path not in parsed:
            parsed[path] = ast.parse(sources[path])
        return parsed[path]

    files = {p for p in sources if grading(p)}
    seen, todo = set(), list(CORE)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        path = _file(tree, name)
        if path is None or path not in sources:
            continue
        files.add(path)
        todo.extend(_edges(tree, name, path, parse(path)) - seen)
    found = Counter()
    for path in sorted(files):
        for call, argument in _sites_in(sources[path], parse(path)):
            found[(path, call, argument)] += 1
    return found


def _table() -> Counter:
    return Counter(
        {
            (path, call, argument): count
            for path, call, argument, count, _k, _p in DYNAMIC_SITES
        }
    )


def _defines_dispatch(tree_ast) -> bool:
    for node in tree_ast.body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [
                t.id
                for target in targets
                for t in ast.walk(target)
                if isinstance(t, ast.Name)
            ]
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [(alias.asname or alias.name).split(".")[0] for alias in node.names]
        if "dispatch" in names:
            return True
    return False


def _addition_verdicts(additions, old: Tree, new: Tree, grading) -> dict:
    verdict = {}
    for path in additions:
        module = _module(path)
        if new.mode(path) not in ("100644", "100755"):
            verdict[path] = "global:not_a_regular_file"
        elif path.endswith("/__init__.py") or path == "__init__.py":
            verdict[path] = "global:package_init"
        elif any(p.startswith(path[: -len(".py")] + "/") for p in new.entries):
            verdict[path] = "global:shadows_a_package"
        else:
            try:
                tree_ast = _parse(new.read([path])[path])
            except (SyntaxError, ValueError, UnicodeDecodeError):
                verdict[path] = "global:unparseable"
                continue
            if _defines_dispatch(tree_ast):
                # an overlay dispatch module is imported on every door that imports its sealed module (v2)
                verdict[path] = "global:dispatch_module"
                continue
            hit = next(
                (
                    f"global:dynamic_site:{site[0]}:{site[1]}"
                    for site in DYNAMIC_SITES
                    if site[5] is not None and re.fullmatch(site[5], module)
                ),
                None,
            )
            verdict[path] = hit or PURE_ADDITION
    pending = [p for p, why in verdict.items() if why == PURE_ADDITION]
    if not pending:
        return verdict
    if _table() != dynamic_sites(new, grading):
        # a computed-name site the table does not list (or a listed one gone): nothing can be cleared
        return {**verdict, **{p: "global:dynamic_site_unlisted" for p in pending}}
    existing = sorted(
        p
        for p, (_mode, kind, _oid) in new.entries.items()
        if p.startswith(TEXT_ROOTS) and kind == "blob" and p not in additions
    )
    blobs = new.read(existing)
    for path in pending:
        module, leaf = _module(path), path.rsplit("/", 1)[-1][: -len(".py")]
        needles = (module.encode(), path.encode())
        if any(n in raw for raw in blobs.values() for n in needles):
            verdict[path] = "global:named_in_text"
            continue
        for other, raw in blobs.items():
            if not other.endswith(".py") or (
                leaf.encode() not in raw and b"import *" not in raw
            ):
                continue
            try:
                tree_ast = _parse(raw)
            except (SyntaxError, ValueError, UnicodeDecodeError):
                verdict[path] = f"global:unparseable:{other}"
                break
            names = _import_names(
                tree_ast, _module(other), other.endswith("/__init__.py")
            )
            for _text, program in _programs(tree_ast):
                names |= _import_names(program, "carbon.program", False)
            if module in names or module.rpartition(".")[0] + ".*" in names:
                verdict[path] = f"global:imported_by:{other}"
                break
    return verdict


# -- the one shared verdict --------------------------------------------------------------------------------------------


def _lf(raw: bytes) -> bytes:
    """CRLF read as LF (a Windows checkout of the same blob)."""
    return raw.replace(b"\r\n", b"\n")


def scope(root, old, new, paths, served, grading, *, early=False) -> dict:
    """``{path: reason}`` for every changed grading path ``paths`` of OLD..NEW on a door serving ``served`` (a set of
    ``'<challenge> <version>'``): `KEYED_OTHER`, `PURE_ADDITION` or a ``global:...`` reason. ``grading`` is the M2
    predicate at NEW. ``early``: once one path is GLOBAL, the additions are not searched (``global:not_evaluated``).
    Raises `_Doubt` when git cannot tell."""
    old_tree, new_tree = Tree(root, old), Tree(root, new)
    own = new_tree.read([SELF]).get(SELF)
    if own is None or _lf(own) != _lf(Path(__file__).read_bytes()):
        # the table and the rules in force are NEW's own: a caller running other bytes clears nothing
        raise _Doubt("scope_code_differs_from_new")
    verdict, additions = {}, []
    for path in paths:
        if path in KEYED_JSON:
            verdict[path] = _keyed_verdict(path, old_tree, new_tree, served)
        elif (
            path.endswith(".py")
            and path not in old_tree.entries
            and path in new_tree.entries
        ):
            additions.append(path)
        elif path.endswith(".py"):
            verdict[path] = "global:modified_deleted_or_renamed_py"
        else:
            verdict[path] = "global:not_a_keyed_registry"
    if early and additions and set(verdict.values()) - CLEARED:
        verdict.update({path: "global:not_evaluated" for path in additions})
    else:
        verdict.update(_addition_verdicts(additions, old_tree, new_tree, grading))
    return {path: verdict[path] for path in paths}


def not_served(root, old, new, paths, served, grading):
    """``{path: reason}`` when EVERY changed grading path is cleared for this door (a keyed-other registry entry or a
    pure addition), else None: the caller then decides exactly as before. Never raises; any doubt is None.
    """
    try:
        paths = tuple(paths)
        served = frozenset(served)
        if (
            not paths
            or not served
            or any(type(p) is not str or not p or not grading(p) for p in paths)
            or any(type(s) is not str or not PAIR.fullmatch(s) for s in served)
        ):
            return None
        key = (str(root), old, new, paths, served)
        if key not in _CACHE:
            _CACHE[key] = scope(root, old, new, paths, served, grading, early=True)
        verdict = _CACHE[key]
    except Exception:  # noqa: BLE001 - fail closed: any doubt is the global check
        return None
    if set(verdict.values()) <= CLEARED and set(verdict) == set(paths):
        return dict(verdict)
    return None
