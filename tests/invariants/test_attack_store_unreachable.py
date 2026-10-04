"""Nothing a miner receives can reach Carbon's attack engine or its store.

OWNER-GRAPHITE-ATTACKER-01 §3 (owner, 2026-10-04): the attack modules
(`carbon/agent_campaign/attack/`) and the attack-knowledge store they keep are
unreachable from anything miners receive. What miners receive is:

- the miner edition of Graphite (`carbon/agent_campaign/graphite/miner/`),
  which holds the shared card pack, its loader and the miner's Library;
- the method cards (`carbon/agent_campaign/graphite/method_cards.py`);
- the Launchpad (`scripts/dev/miner_launchpad/`);
- the MCP door (`carbon/miner_mcp/`).

This is checked on the code, as the product's key invariant
(`test_product_process_holds_no_key`) checks it: by walking every import
statement those surfaces contain, however deep and however lazily, and every
parent package Python runs on the way. A string that names the attack package
or the store (an `importlib` import, a path, the store's schema or directory)
counts as reaching it too, and the shipped data files are searched for the
same names. A fresh interpreter that imports every importable module of those
surfaces is shown to hold no attack module afterwards.

Every check runs in every lane that runs this file, including the
contract-authority lane, which installs no numerical stack: the store's names
are read from its source, and the fresh interpreter imports numpy as an inert
stand-in only when it is not installed (the canonical shards import the real
one).

Every check carries a specimen: a planted import of the store from a miner
path, two lazy imports deep behind a Launchpad entry, and a string import, are
each found and fail the same assertion the real check makes; a store import by
a name built at run time fails the import check; a renamed or computed store
name fails the name check.
"""

import ast
import gzip
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
#: The attack engine's package, by path and by import name.
ATTACK_PATH = "carbon/agent_campaign/attack"
ATTACK_MODULE = "carbon.agent_campaign.attack"
#: Everything a miner receives (directories are walked recursively).
MINER_SURFACES = (
    "carbon/agent_campaign/graphite/miner",
    "carbon/agent_campaign/graphite/method_cards.py",
    "scripts/dev/miner_launchpad",
    "carbon/miner_mcp",
)
#: The shared card pack the miner edition ships.
SHARED_PACK = "carbon/agent_campaign/graphite/miner/packs"
#: Text that names the attack package or its store. Kept literal here so a
#: rename in the store cannot quietly empty the check (see the test below).
ATTACK_NAMES = (
    ATTACK_MODULE,
    ATTACK_PATH,
    "graphite-attack-knowledge",
    "carbon.graphite.attack-knowledge",
)
_ROOTS = {"carbon", "scripts", "carbon_miner_signer"}


def _scan_module():
    """The product invariant's import resolution, loaded from its own file."""
    path = ROOT / "tests/invariants/test_product_process_holds_no_key.py"
    spec = importlib.util.spec_from_file_location("_attack_store_no_key_scan", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _scan_module()


def _starts(root, surfaces):
    found = []
    for surface in surfaces:
        path = root / surface
        if path.is_dir():
            found.extend(
                p for p in sorted(path.rglob("*.py")) if "node_modules" not in p.parts
            )
        else:
            found.append(path)
    return found


def closure(root=ROOT, surfaces=MINER_SURFACES):
    """Every repository file the surfaces can import, with parent packages."""
    todo, seen = _starts(root, surfaces), set()
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        for module in SCAN.imported_names(path, root):
            parts = module.split(".")
            if parts[0] not in _ROOTS:
                continue
            for depth in range(1, len(parts) + 1):
                found = SCAN._module_path(".".join(parts[:depth]), root)
                if found is not None:
                    todo.append(found)
    return seen


def _named_in(text):
    return sorted(name for name in ATTACK_NAMES if name in text)


def _attack_import(module):
    return module == ATTACK_MODULE or module.startswith(ATTACK_MODULE + ".")


def reach(paths, root=ROOT):
    """`(file, how)` for every way the files reach the attack package: being
    in it, an import statement naming it (whether or not the name resolves
    to a file, so an implicit namespace package is caught too), or a string
    constant that names it or its store."""
    found = set()
    for path in paths:
        label = path.relative_to(root).as_posix()
        if label == ATTACK_PATH + ".py" or label.startswith(ATTACK_PATH + "/"):
            found.add((label, "is the attack package"))
            continue
        for module in SCAN.imported_names(path, root):
            if _attack_import(module):
                found.add((label, "imports " + module))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and type(node.value) is str:
                for name in _named_in(node.value):
                    found.add((label, "names " + name))
    return found


def test_no_miner_surface_reaches_the_attack_engine_or_its_store():
    found = reach(closure())
    assert not found, sorted(found)


def test_the_walk_reaches_every_miner_surface():
    """Specimen for reach: the walk covers the miner edition, the shared pack's
    loader, the Library, the method cards, the Launchpad, the MCP door and the
    internal Graphite modules they share (the protected rule and the roles)."""
    names = {path.relative_to(ROOT).as_posix() for path in closure()}
    assert {
        "carbon/agent_campaign/graphite/miner/edition.py",
        "carbon/agent_campaign/graphite/miner/driver.py",
        "carbon/agent_campaign/graphite/miner/pack.py",
        "carbon/agent_campaign/graphite/miner/library.py",
        "carbon/agent_campaign/graphite/method_cards.py",
        "carbon/agent_campaign/graphite/tools.py",
        "carbon/agent_campaign/graphite/roles.py",
        "carbon/agent_campaign/__init__.py",
        "carbon/agent_campaign/graphite/__init__.py",
        "scripts/dev/miner_launchpad/runner.py",
        "carbon/miner_mcp/service.py",
        "carbon/miner_mcp/standard_cli.py",
    } <= names
    # The store itself exists where the check looks for it.
    assert (ROOT / ATTACK_PATH / "knowledge.py").is_file()


#: The store's module and the names in it that ATTACK_NAMES must hold.
STORE_FILE = ATTACK_PATH + "/knowledge.py"
STORE_NAMES = ("STORE_DIRNAME", "SCHEMA_PREFIX")


def store_constants(path):
    """The value each STORE_NAMES name is bound to in the file, read from its
    source without importing it (the store imports the numerical stack, which
    the contract lane does not install). Each name must be bound exactly once,
    anywhere in the file, to a string literal at module level: any other form
    fails here, so the value read is the value the module holds."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bound = {name: [] for name in STORE_NAMES}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in bound:
            if not isinstance(node.ctx, ast.Load):
                bound[node.id].append(node)
        elif isinstance(node, ast.alias) and (node.asname or node.name) in bound:
            bound[node.asname or node.name].append(node)
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if (
                isinstance(target, ast.Name)
                and target.id in bound
                and isinstance(node.value, ast.Constant)
                and type(node.value.value) is str
            ):
                values[target.id] = node.value.value
    for name, nodes in bound.items():
        assert len(nodes) == 1 and name in values, (
            f"{name} must be bound once, to a string literal, at module level"
        )
    return values


def test_the_names_searched_for_are_the_stores_own():
    """The literal names above are the store's: its schema prefix and its
    directory name. A rename there fails here before it can empty the check."""
    path = ROOT / STORE_FILE
    values = store_constants(path)
    assert values["STORE_DIRNAME"] in ATTACK_NAMES
    assert values["SCHEMA_PREFIX"] in ATTACK_NAMES
    assert SCAN._module_name(path, ROOT).startswith(ATTACK_MODULE + ".")


def test_a_renamed_or_computed_store_name_fails_the_check(tmp_path):
    """Specimen for the store-name check: a renamed directory, a schema prefix
    built at run time, and a second binding are each refused."""
    cases = {
        "renamed": 'STORE_DIRNAME = "renamed"\nSCHEMA_PREFIX = "carbon.graphite.attack-knowledge"\n',
        "computed": 'STORE_DIRNAME = "graphite-attack-knowledge"\nSCHEMA_PREFIX = "carbon." + "x"\n',
        "rebound": (
            'STORE_DIRNAME = "graphite-attack-knowledge"\n'
            'SCHEMA_PREFIX = "carbon.graphite.attack-knowledge"\n'
            "if True:\n    STORE_DIRNAME = 'elsewhere'\n"
        ),
    }
    for case, text in cases.items():
        path = tmp_path / (case + ".py")
        path.write_text(text, encoding="utf-8")
        with pytest.raises(AssertionError):
            values = store_constants(path)
            assert values["STORE_DIRNAME"] in ATTACK_NAMES
            assert values["SCHEMA_PREFIX"] in ATTACK_NAMES


def _shipped_files():
    for surface in (*MINER_SURFACES, SHARED_PACK):
        path = ROOT / surface
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for item in files:
            if item.is_file() and "node_modules" not in item.parts:
                yield item


def test_no_shipped_file_names_the_attack_engine_or_its_store():
    """The shared pack (decompressed) and every file the Launchpad and the MCP
    door ship (scripts, pages, styles, manifests) name neither the attack
    package nor the store."""
    found, packs = [], 0
    for path in _shipped_files():
        body = path.read_bytes()
        if path.suffix == ".gz":
            body = gzip.decompress(body)
            packs += 1
        text = body.decode("utf-8", errors="replace")
        if _named_in(text):
            found.append((path.relative_to(ROOT).as_posix(), _named_in(text)))
    assert packs >= 1, "the shared pack was not searched"
    assert not found, found


def _importable_modules():
    names = []
    for path in _starts(ROOT, MINER_SURFACES):
        if path.relative_to(ROOT).parts[0] != "carbon":
            continue  # the Launchpad is not a package; the static walk covers it
        name = SCAN._module_name(path, ROOT)
        names.append(name)
    return sorted(set(names))


#: Third-party packages a lane may lack that the miner modules import. The
#: contract-authority lane installs no numerical stack, and nearly every miner
#: module imports numpy on load. Only these, and only when the interpreter
#: cannot find them, are replaced by an inert stand-in; any other missing
#: module still fails the import, and so the test.
STUBBABLE = ("numpy",)

#: Run in a fresh interpreter: import the named modules and print every module
#: it then holds, and every name the inert stand-in had to supply. The
#: stand-in's finder sits last on `sys.meta_path`, so a lane that installs the
#: package (the canonical shards) imports the real one and stubs nothing.
_IMPORT_ALL = textwrap.dedent("""
    import importlib, importlib.abc, importlib.machinery, json, sys, types

    STUBBABLE = set(json.loads(sys.argv[2]))
    stubbed = []

    class Inert:
        # Any value read from an absent package: inert, never a real result.
        def __getattr__(self, name):
            if name.startswith("__") and name.endswith("__"):
                raise AttributeError(name)
            return INERT

        def __call__(self, *args, **kwargs):
            return INERT

        def __getitem__(self, key):
            return INERT

        def __iter__(self):
            return iter(())

        def __mro_entries__(self, bases):
            return (object,)

    for op in ("add", "sub", "mul", "truediv", "floordiv", "pow", "mod",
               "matmul", "neg", "pos", "abs", "or", "and", "xor"):
        setattr(Inert, "__%s__" % op, lambda self, *other: INERT)
        setattr(Inert, "__r%s__" % op, lambda self, *other: INERT)
    INERT = Inert()

    class InertModule(types.ModuleType):
        def __getattr__(self, name):
            if name.startswith("__") and name.endswith("__"):
                raise AttributeError(name)
            return INERT

    class AbsentPackage(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, name, path=None, target=None):
            top, _, rest = name.partition(".")
            if top not in STUBBABLE:
                return None
            if rest and not isinstance(sys.modules.get(top), InertModule):
                return None  # a real package's missing submodule stays missing
            stubbed.append(name)
            return importlib.machinery.ModuleSpec(name, self, is_package=True)

        def create_module(self, spec):
            module = InertModule(spec.name)
            module.__path__ = []
            return module

        def exec_module(self, module):
            pass

    sys.meta_path.append(AbsentPackage())
    for name in json.loads(sys.argv[1]):
        importlib.import_module(name)
    print(json.dumps({"loaded": sorted(sys.modules), "stubbed": sorted(stubbed)}))
    """)


def import_all(modules, root=ROOT):
    """`(loaded, stubbed)` after a fresh interpreter in `root` imports
    `modules`: every module it then holds, and every module the inert
    stand-in supplied because the package was not installed."""
    done = subprocess.run(
        [sys.executable, "-c", _IMPORT_ALL, json.dumps(modules), json.dumps(STUBBABLE)],
        capture_output=True,
        text=True,
        check=False,  # the return code is asserted below, with the stderr
        cwd=root,
        env={**os.environ, "JAX_PLATFORMS": "cpu"},
        timeout=600,
    )
    assert done.returncode == 0, done.stderr[-4000:]
    report = json.loads(done.stdout.strip().splitlines()[-1])
    stubbed = set(report["stubbed"])
    assert all(name.split(".")[0] in STUBBABLE for name in stubbed), stubbed
    for package in STUBBABLE:
        if importlib.util.find_spec(package) is not None:
            # Where the package is installed the real one is imported.
            assert not any(n.split(".")[0] == package for n in stubbed), stubbed
    return set(report["loaded"]), stubbed


def test_importing_every_miner_module_loads_no_attack_module():
    """A fresh interpreter imports every importable module of the miner
    surfaces; afterwards it holds no attack module. In a lane without the
    numerical stack, numpy is an inert stand-in (STUBBABLE); in the canonical
    shards the real package is imported."""
    modules = _importable_modules()
    assert "carbon.agent_campaign.graphite.miner.library" in modules
    assert "carbon.miner_mcp.service" in modules
    loaded, _stubbed = import_all(modules)
    assert set(modules) <= loaded
    leaked = sorted(name for name in loaded if _attack_import(name))
    assert not leaked, leaked


def test_a_runtime_import_of_the_store_fails_the_import_check(tmp_path):
    """Specimen for the import check: a miner module that reaches the store by
    a name built at run time (which no import statement or string constant
    shows, so the static walk cannot see it), where the store imports numpy,
    leaves the attack module loaded and fails the same assertion the real
    check makes, with or without numpy installed."""
    files = {
        "carbon/__init__.py": "",
        "carbon/agent_campaign/__init__.py": "",
        "carbon/agent_campaign/attack/__init__.py": "",
        "carbon/agent_campaign/attack/knowledge.py": (
            "import numpy as np\nFLOOR = np.float64(0.5) * 2\n"
        ),
        "carbon/agent_campaign/graphite/__init__.py": "",
        "carbon/agent_campaign/graphite/miner/__init__.py": "",
        "carbon/agent_campaign/graphite/miner/planted.py": (
            "import importlib\n"
            "_PARTS = ('carbon', 'agent_campaign', 'attack', 'knowledge')\n"
            "importlib.import_module('.'.join(_PARTS))\n"
        ),
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    planted = "carbon.agent_campaign.graphite.miner.planted"
    assert not reach(
        closure(tmp_path, ("carbon/agent_campaign/graphite/miner",)), tmp_path
    )
    loaded, stubbed = import_all([planted], tmp_path)
    # The store's numpy import took the stand-in exactly where numpy is absent.
    assert ("numpy" in stubbed) == (importlib.util.find_spec("numpy") is None)
    assert planted in loaded
    leaked = sorted(name for name in loaded if _attack_import(name))
    assert ATTACK_MODULE + ".knowledge" in leaked
    with pytest.raises(AssertionError):
        assert not leaked, leaked


def _plant(tmp_path):
    """A repository in miniature: the store, a miner path that imports it
    lazily, a Launchpad entry two lazy imports away from it, and an MCP door
    that names it in a string import."""
    files = {
        "carbon/__init__.py": "",
        "carbon/agent_campaign/__init__.py": "",
        "carbon/agent_campaign/attack/__init__.py": "",
        "carbon/agent_campaign/attack/knowledge.py": "class AttackStore:\n    pass\n",
        "carbon/agent_campaign/graphite/__init__.py": "",
        "carbon/agent_campaign/graphite/method_cards.py": "",
        "carbon/agent_campaign/graphite/miner/__init__.py": "",
        "carbon/agent_campaign/graphite/miner/edition.py": (
            "def priors(root):\n"
            "    from carbon.agent_campaign.attack.knowledge import AttackStore\n"
            "    return AttackStore(root)\n"
        ),
        "scripts/dev/miner_launchpad/app.py": "from carbon import door\n",
        "carbon/door.py": (
            "def submit():\n    from .deep import hint\n    return hint()\n"
        ),
        "carbon/deep.py": (
            "def hint():\n"
            "    from .agent_campaign.attack import knowledge\n"
            "    return knowledge\n"
        ),
        "carbon/miner_mcp/__init__.py": "",
        "carbon/miner_mcp/service.py": (
            "import importlib\n"
            "def load():\n"
            "    return importlib.import_module(\n"
            "        'carbon.agent_campaign.attack.knowledge'\n"
            "    )\n"
        ),
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_a_planted_import_of_the_store_from_a_miner_path_fails_the_check(tmp_path):
    """Specimen for the whole check (the mutation 'plant an import of the store
    from a miner path'): each planted way in is reached and fails the same
    assertion the real check makes."""
    root = _plant(tmp_path)
    found = reach(closure(root, MINER_SURFACES), root)
    assert ("carbon/agent_campaign/attack/knowledge.py", "is the attack package") in (
        found
    )
    assert ("carbon/miner_mcp/service.py", "names " + ATTACK_MODULE) in found
    with pytest.raises(AssertionError):
        assert not found, sorted(found)
    # Each route alone is enough: the miner path, the Launchpad's lazy chain
    # and the MCP door's string import.
    for surface in MINER_SURFACES:
        if (root / surface).exists():
            alone = reach(closure(root, (surface,)), root)
            if surface.endswith("method_cards.py"):
                assert not alone
            else:
                assert alone, surface


def test_a_lazy_import_of_a_namespace_attack_package_fails_the_check(tmp_path):
    """Specimen for the import-name route: with no `attack/__init__.py` (an
    implicit namespace package, which resolves to no file) a lazy
    `import carbon.agent_campaign.attack` in a miner path is still reached,
    by its import statement alone (no file, string or runtime route sees it)."""
    root = _plant(tmp_path)
    (root / "carbon/agent_campaign/attack/__init__.py").unlink()
    probe = root / "carbon/agent_campaign/graphite/miner/probe.py"
    probe.write_text(
        "def hint():\n    import carbon.agent_campaign.attack\n", encoding="utf-8"
    )
    assert SCAN._module_path(ATTACK_MODULE, root) is None
    found = reach(closure(root, MINER_SURFACES), root)
    label = "carbon/agent_campaign/graphite/miner/probe.py"
    assert {how for where, how in found if where == label} == {
        "imports " + ATTACK_MODULE
    }
    with pytest.raises(AssertionError):
        assert not found, sorted(found)
