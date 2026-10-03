"""Carbon's product process never holds a miner's key (external signing).

The miner's hotkey lives in their own `carbon-miner-signer` process. Carbon's
product process - the Control Center and the MCP door, and every module either
can import, however deep and however lazily - contains no key-file open, no
password read, and no signer built from key material. It reaches the signer
through `carbon.chain.external_signer`, whose `ExternalSigner` cannot be built
from a key.

This is checked on the code, by walking the product's transitive import closure
and scanning each module's syntax tree, rather than on what today's tests happen
to exercise.

Every rule carries a specimen. The scanner is shown finding each forbidden
construct in the signer package, which really does open a key, and in a
deliberate violation shaped like the loader external signing removed. It is
also shown reaching the modules that used to open the key. A scanner that could
find none of these would pass on anything.

One permitted exception, named and itself a specimen:
`carbon.chain.sdk_weights.open_operator_wallet` opens the OPERATOR's validator
wallet for weight publication. It is importable from the product only because
the product reads the operator's chain configuration from the same package, on
the single-host deployment (#431 / OD-7). It is never the miner's key, and no
product module calls it.
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ENTRIES = (
    ROOT / "scripts" / "dev" / "miner_launchpad",
    ROOT / "carbon" / "miner_mcp",
)
SIGNER_PACKAGE = "carbon_miner_signer"

#: Names that open, decrypt or construct Bittensor key material.
KEY_NAMES = frozenset(
    {
        "Keyfile",
        "Keypair",
        "Wallet",
        "get_keypair",
        "get_hotkey",
        "get_coldkey",
        "unlock_hotkey",
        "unlock_coldkey",
        "hotkey_file",
        "coldkey_file",
        "decrypt_keyfile_data",
        "deserialize_keypair_from_keyfile_data",
        "create_from_uri",
        "create_from_mnemonic",
        "create_from_seed",
        "create_from_private_key",
        "create_from_encrypted_json",
        "open_external_hotkey",
        # Prompting for the key's password is the signer's job, in its terminal.
        "getpass",
    }
)
#: Identifiers that carry a key file's path or the password that decrypts it.
KEY_PATH_NAMES = frozenset({"key_file", "miner_password_file", "password_file"})

PERMITTED = {("carbon/chain/sdk_weights.py", "open_operator_wallet", "Wallet")}


def _module_path(name, root=ROOT):
    base = root.joinpath(*name.split("."))
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def _module_name(path, root=ROOT):
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_names(path, root=ROOT):
    """Every module name a file imports, anywhere in it, resolved absolutely."""
    name = _module_name(path, root)
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                parts = package.split(".")
                base = parts[: len(parts) - node.level + 1]
                module = ".".join([*base, module] if module else base)
            found.add(module)
            found.update(module + "." + alias.name for alias in node.names)
    return found


def product_closure(root=ROOT, entries=PRODUCT_ENTRIES):
    """The files the product process can import from this repository."""
    todo = [path for entry in entries for path in sorted(entry.glob("*.py"))]
    seen = set()
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        for module in imported_names(path, root):
            parts = module.split(".")
            if parts[0] not in {"carbon", "scripts", SIGNER_PACKAGE}:
                continue
            for depth in range(1, len(parts) + 1):
                found = _module_path(".".join(parts[:depth]), root)
                if found is not None:
                    todo.append(found)
    return seen


def violations(source, label):
    """(file, enclosing function, construct) for every key-material construct."""
    tree = ast.parse(source)
    found = set()

    def visit(node, function):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        construct = None
        if isinstance(node, ast.Name) and (
            node.id in KEY_NAMES or node.id in KEY_PATH_NAMES
        ):
            construct = node.id
        elif isinstance(node, ast.Attribute) and (
            node.attr in KEY_NAMES or node.attr in KEY_PATH_NAMES
        ):
            construct = node.attr
        elif isinstance(node, ast.arg) and node.arg in KEY_PATH_NAMES:
            construct = node.arg
        elif isinstance(node, ast.keyword) and node.arg in (
            KEY_PATH_NAMES | {"password"}
        ):
            construct = node.arg + "="
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value in KEY_PATH_NAMES
        ):
            construct = "[" + repr(node.slice.value) + "]"
        elif isinstance(node, ast.alias) and (
            node.name.split(".")[0] == SIGNER_PACKAGE
            or node.name.rpartition(".")[2] in KEY_NAMES
            or node.name in {"bittensor.keyfiles", "bittensor.wallet"}
        ):
            construct = "import " + node.name
        elif (
            (
                isinstance(node, ast.ImportFrom)
                and (node.module or "").split(".")[0] == SIGNER_PACKAGE
            )
            or isinstance(node, ast.ImportFrom)
            and node.module
            in {
                "bittensor.keyfiles",
                "bittensor.wallet",
            }
        ):
            construct = "import " + node.module
        if construct is not None:
            found.add((label, function, construct))
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(tree, "<module>")
    return found


def scan(paths, root=ROOT):
    found = set()
    for path in paths:
        label = path.relative_to(root).as_posix()
        found |= violations(path.read_text(encoding="utf-8"), label)
    return found


def test_the_product_process_contains_no_key_material_construct():
    found = scan(product_closure())
    assert found <= PERMITTED, sorted(found - PERMITTED)


def test_the_product_assertion_fails_on_a_planted_violation(tmp_path):
    """Specimen for the whole check, not only the scanner: a key open planted
    two lazy imports deep behind a product entry point is reached by the
    closure walk and fails the same assertion the product test makes."""
    entry = tmp_path / "scripts" / "dev" / "miner_launchpad"
    entry.mkdir(parents=True)
    (entry / "app.py").write_text("from carbon import door\n", encoding="utf-8")
    (tmp_path / "carbon").mkdir()
    (tmp_path / "carbon" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "carbon" / "door.py").write_text(
        "def submit():\n    from .deep import sign\n    return sign\n",
        encoding="utf-8",
    )
    (tmp_path / "carbon" / "deep.py").write_text(
        "import getpass\n"
        "def sign(profile):\n"
        "    from bittensor.keyfiles import Keyfile\n"
        "    password = getpass.getpass()\n"
        "    return Keyfile(profile['key_file']).get_keypair(password=password)\n",
        encoding="utf-8",
    )
    found = scan(product_closure(tmp_path, (entry,)), tmp_path)
    assert ("carbon/deep.py", "sign", "Keyfile") in found
    assert ("carbon/deep.py", "sign", "getpass") in found
    assert ("carbon/deep.py", "<module>", "import getpass") in found
    with pytest.raises(AssertionError):
        assert found <= PERMITTED, sorted(found - PERMITTED)


def test_the_scan_reaches_the_modules_that_used_to_open_the_key():
    """Specimen for reach: every module that held the miner's key before
    external signing is inside the scanned closure, as is the signer client."""
    closure = {path.relative_to(ROOT).as_posix() for path in product_closure()}
    assert {
        "carbon/battery/campaign.py",
        "carbon/development_session/research_campaign.py",
        "carbon/miner_mcp/standard_cli.py",
        "carbon/chain/auth.py",
        "carbon/chain/external_signer.py",
        "scripts/dev/miner_launchpad/runner.py",
    } <= closure


def test_the_scanner_finds_the_key_in_the_signer_package():
    """Specimen: the signer package does open the miner's key, and the scanner
    sees it - so the clean result above is not a scanner that finds nothing."""
    found = scan(sorted((ROOT / SIGNER_PACKAGE).glob("*.py")))
    constructs = {construct for _, _, construct in found}
    assert {"Keyfile", "get_keypair", "key_file", "import bittensor.keyfiles"} <= (
        constructs
    ), sorted(constructs)


def test_the_scanner_finds_each_rule_in_a_deliberate_violation():
    """Specimen: the loader external signing removed, and each other way key
    material could come back, are each caught by name."""
    violation = """
from pathlib import Path
from bittensor.keyfiles import Keyfile
import carbon_miner_signer

def open_external_hotkey(key_file, password_file, expected):
    return Keyfile(str(key_file)).get_keypair(password=password_file.read_text())

def prompt():
    import getpass
    return getpass.getpass("hotkey password: ")

def prepare(args, public):
    key = open_external_hotkey(
        Path(public["key_file"]), args.miner_password_file, public["hotkey"]
    )
    import bittensor as bt
    wallet = bt.Wallet(name="w", hotkey="h")
    pair = bt.Keypair.create_from_mnemonic("never")
    return key, wallet, pair
"""
    found = violations(violation, "specimen.py")
    constructs = {construct for _, _, construct in found}
    assert {
        "import bittensor.keyfiles",
        "import carbon_miner_signer",
        "open_external_hotkey",
        "key_file",
        "password_file",
        "Keyfile",
        "get_keypair",
        "password=",
        "['key_file']",
        "miner_password_file",
        "Wallet",
        "Keypair",
        "create_from_mnemonic",
        "import getpass",
        "getpass",
    } <= constructs, sorted(constructs)
    assert ("specimen.py", "prepare", "['key_file']") in found


def test_the_permitted_exception_is_present_and_found():
    """Specimen for the one exception: it exists where named and the scanner
    finds it, so the permit is not silently covering nothing - and nothing in
    the product's own entry points calls it."""
    wallet = ROOT / "carbon" / "chain" / "sdk_weights.py"
    assert PERMITTED <= scan([wallet])
    entries = [path for entry in PRODUCT_ENTRIES for path in entry.glob("*.py")]
    for path in entries:
        assert "open_operator_wallet" not in path.read_text(encoding="utf-8"), path


def test_the_signer_package_is_separable_from_carbon():
    """The key holder imports nothing from Carbon, so it can be read and
    audited alone, and nothing it does depends on Carbon's product code."""
    for path in sorted((ROOT / SIGNER_PACKAGE).glob("*.py")):
        roots = {name.split(".")[0] for name in imported_names(path)}
        assert "carbon" not in roots and "scripts" not in roots, path


def test_no_function_claims_externality_it_lacks():
    """`open_external_hotkey` claimed external signing while decrypting the key
    in-process. No function in the repository may carry that name again."""
    names = set()
    for path in [
        *ROOT.joinpath("carbon").rglob("*.py"),
        *ROOT.joinpath("scripts").rglob("*.py"),
    ]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
    assert "open_external_hotkey" not in names
    assert "open_external_wallet" not in names
    # Specimen: the walk does see function definitions, including the renamed one.
    assert {"open_operator_wallet", "connect_signer"} <= names


def test_a_raw_keypair_is_refused_even_when_valid():
    """By construction, not by check: a perfectly valid keypair cannot sign
    through Carbon, because it did not come from the miner's signer."""
    from bittensor.keyfiles import Keypair

    from carbon.chain.auth import BittensorMessageSigner
    from carbon.chain.external_signer import ExternalSigner

    with pytest.raises(TypeError):
        BittensorMessageSigner(Keypair.create_from_uri("//Alice"))
    with pytest.raises(TypeError):
        ExternalSigner(object(), Path("/nowhere"), 1.0, "5" * 48, 1, b"\0" * 32)
