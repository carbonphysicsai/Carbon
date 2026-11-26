"""A family registered by data is dispatched to its own pinned kit and grader; every other call is the code's (owner G-LEAD-97).

Claims (v2, row 7533): with no row nothing is wrapped; a family no code names is served only from its own row, by sha256, and
only when its grader's producer files bind every module the row names, so a changed file moves its own digest; a family the
code serves is never extended or replaced, and its calls reach the original function with the same arguments; live producer
digests do not move; modules are loaded at `install()` only. Synthetic modules only; nothing is graded here.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

import carbon

# An armed overlay version's module imports its sealed grader, whose import then loads that module (`version_overlay`
# `_extend`): the sealed graders come first, so neither is ever half loaded (release 7788).
import carbon.scoring.cooling_encoded_dual_pack
import carbon.scoring.motor_sealed_dual_pack
from carbon.challenge_kit import family_registry, version_overlay
from carbon.scoring import (
    battery_sealed_dual_pack,
    cooling_dual_pack,
    cooling_pool_baseline_dual_pack,
    copy_derivation,
    f02_dual_pack,
    f02_sealed_dual_pack,
    f08_dual_pack,
    f08_sealed_dual_pack,
    family_graders,
    motor18_dual_pack,
    motor_pool_baseline_dual_pack,
    motor_sealed_dual_pack,
    physical_adapters,
    physical_dual_pack,
    pool_version,
    sealed_batch_source,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "exam_registry" / "zz_synthetic_sealed.py"
FAMILY, VERSION = "zz-synthetic", "0.1"
NAMES = ("_kit", "_pool_graded", "_adapter")
BUILTIN = sorted(family_registry.BUILTIN)
PRODUCERS = (
    battery_sealed_dual_pack,
    cooling_dual_pack,
    cooling_pool_baseline_dual_pack,
    f02_dual_pack,
    f02_sealed_dual_pack,
    f08_dual_pack,
    f08_sealed_dual_pack,
    motor18_dual_pack,
    # (before the version its overlay dispatch adds to it)
    motor_sealed_dual_pack,
    motor_pool_baseline_dual_pack,
)


@pytest.fixture
def clean(monkeypatch):
    """Each test starts from the code's own tables and functions, and leaves them."""
    for module, name in (
        (pool_version, "KINDS"),
        (copy_derivation, "OPAQUE_BY_CHALLENGE"),
        (version_overlay, "SEALED_TARGET"),
        (physical_adapters, "_REGISTERED"),
    ):
        monkeypatch.setattr(module, name, dict(getattr(module, name)))
    for module in (family_registry, family_graders):
        monkeypatch.setattr(module, "_REFUSED", {})
    monkeypatch.setattr(family_registry, "_INSTALLED", {})
    monkeypatch.setattr(family_graders, "_SERVED", {})
    monkeypatch.setattr(family_graders, "_ORIGINAL", {})
    for name in NAMES:
        monkeypatch.setattr(
            sealed_batch_source, name, getattr(sealed_batch_source, name)
        )
    monkeypatch.setattr(carbon, "__path__", list(carbon.__path__))
    _forget()
    yield
    _forget()


def _forget():
    for name in [n for n in sys.modules if n.startswith("carbon.zz_")]:
        del sys.modules[name]


class _Modules:
    """Synthetic modules in a folder of their own, each bound by its own FILES unless the text says otherwise."""

    def __init__(self, folder):
        self.folder = folder
        carbon.__path__.append(str(folder))

    def write(self, name, *changes, files=None):
        """The fixture's text under ``carbon.<name>``, with ``changes`` [(old, new)]; its block."""
        path = self.folder / f"{name}.py"
        text = FIXTURE.read_text(encoding="utf-8")
        own = os.path.relpath(path, ROOT / "carbon" / "scoring").replace(os.sep, "/")
        names = [own] if files is None else files
        old = '("../../tests/fixtures/exam_registry/zz_synthetic_sealed.py",)'
        for before, after in ((old, repr(tuple(names))), *changes):
            assert text.count(before) >= 1, before
            text = text.replace(before, after)
        path.write_text(text, encoding="utf-8", newline="\n")
        importlib.invalidate_caches()
        return {
            "module": f"carbon.{name}",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }


@pytest.fixture
def modules(clean, tmp_path):
    return _Modules(tmp_path)


def _row(kit, grader, **extra):
    return {
        "kind": "zzsynthetic",
        "opacity": ["case_id"],
        "baseline": None,
        "modules": {"sealed_kit": kit, "sealed_grader": grader, **extra},
    }


def _install(tmp_path, families):
    path = tmp_path / "families.json"
    path.write_text(
        json.dumps({"schema": family_registry.SCHEMA, "families": families})
    )
    family_registry.install(path=path)
    return family_graders.install()


def test_with_no_row_nothing_is_wrapped(clean):
    before = [getattr(sealed_batch_source, name) for name in NAMES]
    assert family_registry.load() == {}
    assert family_graders.install() == ()
    assert [getattr(sealed_batch_source, name) for name in NAMES] == before
    assert family_graders._ORIGINAL == {}


def test_a_registered_family_is_dispatched_to_its_own_modules(modules, tmp_path):
    block = modules.write("zz_one")
    assert _install(tmp_path, {FAMILY: _row(block, block)}) == (FAMILY,)
    own = sys.modules["carbon.zz_one"]
    source = sealed_batch_source
    assert source._kit(FAMILY) is own
    assert source._pool_graded(FAMILY, VERSION) is True
    assert source._pool_graded(FAMILY, "0.2") is False
    bank = source._build(FAMILY, own, {"cases": [], "pool": {"rows": []}}, [], VERSION)
    assert bank["pool"] == {"rows": []} and bank["document"] == {"cases": []}
    assert source._adapter(FAMILY, bank, VERSION, None) is own
    # an unknown version, or another population, has no grader
    assert source._adapter(FAMILY, bank, "0.2", None) is None
    assert source._adapter(FAMILY, {"population": "other"}, VERSION, None) is None
    # a pool version refuses a batch without its pool, as for every family
    with pytest.raises(source.SealedBankRefused) as refused:
        source._build(FAMILY, own, {"cases": []}, [], VERSION)
    assert refused.value.code == "sealed_pool_material_mismatch"
    # the grade's own adapter dispatch
    assert physical_adapters.adapter(FAMILY, VERSION) is own
    assert physical_adapters.adapter(FAMILY, "0.2") is None
    # idempotent
    wrapped = [getattr(source, name) for name in NAMES]
    assert family_graders.install() == (FAMILY,)
    assert [getattr(source, name) for name in NAMES] == wrapped


def test_its_producer_digest_moves_with_its_own_file(modules, tmp_path):
    block = modules.write("zz_two")
    _install(tmp_path, {FAMILY: _row(block, block)})
    own = sys.modules["carbon.zz_two"]
    before = physical_dual_pack.producer_digest(own)
    path = modules.folder / "zz_two.py"
    path.write_bytes(path.read_bytes() + b"# changed\n")
    assert physical_dual_pack.producer_digest(own) != before


def test_the_live_producer_digests_do_not_move(modules, tmp_path):
    before = [physical_dual_pack.producer_digest(a) for a in PRODUCERS]
    block = modules.write("zz_three")
    assert _install(tmp_path, {FAMILY: _row(block, block)}) == (FAMILY,)
    assert [physical_dual_pack.producer_digest(a) for a in PRODUCERS] == before
    for adapter in PRODUCERS:
        names = {*physical_dual_pack._SHARED_FILES, *adapter.FILES}
        assert not names & {"family_graders.py", "family_registry.py"}, adapter


def test_a_call_for_a_family_the_code_serves_reaches_the_original(
    modules, tmp_path, monkeypatch
):
    calls = []
    for name in NAMES:
        monkeypatch.setattr(
            sealed_batch_source,
            name,
            lambda *args, _name=name: calls.append((_name, args)),
        )
    block = modules.write("zz_four")
    assert _install(tmp_path, {FAMILY: _row(block, block)}) == (FAMILY,)
    calls.clear()
    bank = object()
    for challenge in (*BUILTIN, "no-such-family", None, [], 7):
        sealed_batch_source._kit(challenge)
        sealed_batch_source._pool_graded(challenge, "1.0")
        sealed_batch_source._adapter(challenge, bank, "1.0", "development")
        assert calls == [
            ("_kit", (challenge,)),
            ("_pool_graded", (challenge, "1.0")),
            ("_adapter", (challenge, bank, "1.0", "development")),
        ], challenge
        calls.clear()


@pytest.mark.parametrize(
    "challenge",
    ["chip-cold-plate", "electric-motor-magnetics", "f02", "f08-ribbed-bracket"],
)
def test_live_results_are_equal_before_and_after(modules, tmp_path, challenge):
    source = sealed_batch_source
    versions = [f"{a}.{b}" for a in (1, 2) for b in range(10)]
    before = (
        source._kit(challenge),
        [source._pool_graded(challenge, v) for v in versions],
    )
    block = modules.write("zz_five")
    _install(tmp_path, {FAMILY: _row(block, block)})
    assert source._kit is family_graders._kit
    assert (
        source._kit(challenge),
        [source._pool_graded(challenge, v) for v in versions],
    ) == before
    assert source._kit("no-such-family") is None
    assert source._adapter("no-such-family", {}, VERSION, None) is None


@pytest.mark.parametrize("challenge", BUILTIN)
def test_a_family_the_code_serves_is_never_taken(modules, tmp_path, challenge):
    block = modules.write("zz_six", ('"zz-synthetic"', repr(challenge)))
    assert _install(tmp_path, {challenge: _row(block, block)}) == ()
    assert family_graders._ORIGINAL == {} and "carbon.zz_six" not in sys.modules


def test_a_family_the_original_functions_answer_is_refused_here_too(
    modules, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        sealed_batch_source, "_kit", lambda c: sys if c == FAMILY else None
    )
    block = modules.write("zz_seven")
    assert _install(tmp_path, {FAMILY: _row(block, block)}) == ()
    assert "the code serves this family" in family_graders.refused()[FAMILY]
    assert sealed_batch_source._kit(FAMILY) is sys


def test_a_module_that_does_not_hash_to_its_row_is_never_imported(modules, tmp_path):
    block = {**modules.write("zz_eight"), "sha256": "0" * 64}
    assert _install(tmp_path, {FAMILY: _row(block, block)}) == ()
    assert "carbon.zz_eight" not in sys.modules
    assert sealed_batch_source._kit(FAMILY) is None


def test_a_file_changed_after_its_row_was_kept_is_never_imported(modules, tmp_path):
    block = modules.write("zz_nine")
    path = tmp_path / "families.json"
    document = {
        "schema": family_registry.SCHEMA,
        "families": {FAMILY: _row(block, block)},
    }
    path.write_text(json.dumps(document))
    assert set(family_registry.install(path=path)) == {FAMILY}
    file = modules.folder / "zz_nine.py"
    file.write_bytes(file.read_bytes() + b"# changed\n")
    assert family_graders.install() == ()
    assert "sha256 differs" in family_graders.refused()[FAMILY]
    assert "carbon.zz_nine" not in sys.modules


def test_a_grader_that_does_not_bind_every_module_is_refused(modules, tmp_path):
    kit = modules.write("zz_kit")
    grader = modules.write("zz_grader")  # binds its own file only
    assert _install(tmp_path, {FAMILY: _row(kit, grader)}) == ()
    assert "do not bind" in family_graders.refused()[FAMILY]
    assert sealed_batch_source._kit(FAMILY) is None
    assert FAMILY not in physical_adapters._REGISTERED


def test_every_role_the_row_names_must_be_bound(modules, tmp_path):
    block = modules.write("zz_own")
    bank = modules.write("zz_bank")
    assert _install(tmp_path, {FAMILY: _row(block, block, bank=bank)}) == ()
    assert "do not bind" in family_graders.refused()[FAMILY]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (('"zz-synthetic"', '"f02"'), "another Challenge"),
        (('"zz-synthetic"', '"another-family"'), "another Challenge"),
        (("VERSIONS = dict(POOL_VERSIONS)", "VERSIONS = {}"), "no version tables"),
        (("def adapter_for_bank", "def _adapter_for_bank"), "no version tables"),
        (("def private_roles", "def _private_roles"), "no sealed bank"),
        (("import json", "raise RuntimeError"), "does not import"),
    ],
)
def test_a_refused_family_serves_nothing_and_stops_no_other(
    modules, tmp_path, change, reason
):
    bad = modules.write("zz_bad", change)
    good = modules.write("zz_good", ('"zz-synthetic"', '"zz-other"'))
    rows = {FAMILY: _row(bad, bad), "zz-other": {**_row(good, good), "kind": "zzother"}}
    assert _install(tmp_path, rows) == ("zz-other",)
    assert reason in family_graders.refused()[FAMILY]
    assert sealed_batch_source._kit(FAMILY) is None
    assert sealed_batch_source._kit("zz-other") is sys.modules["carbon.zz_good"]
    assert physical_adapters.adapter(FAMILY, VERSION) is None


def test_an_adapter_of_another_challenge_or_unbound_is_refused_at_the_grade(
    modules, tmp_path
):
    block = modules.write(
        "zz_ten",
        (
            "    return sys.modules[__name__]",
            "    return type(sys)('unbound')",
        ),
    )
    assert _install(tmp_path, {FAMILY: _row(block, block)}) == (FAMILY,)
    with pytest.raises(sealed_batch_source.SealedBankRefused) as refused:
        sealed_batch_source._adapter(FAMILY, {"population": "zz"}, VERSION, None)
    assert refused.value.code == "sealed_adapter_unbound"


def test_a_family_with_only_one_of_the_two_modules_is_not_served(modules, tmp_path):
    block = modules.write("zz_half")
    row = _row(block, block)
    del row["modules"]["sealed_grader"]
    assert _install(tmp_path, {FAMILY: row}) == ()
    assert "carbon.zz_half" not in sys.modules


def test_a_call_imports_nothing(modules, tmp_path, monkeypatch):
    block = modules.write("zz_eleven")
    _install(tmp_path, {FAMILY: _row(block, block)})

    def fail(*_args, **_kwargs):
        raise AssertionError("a call reached the registry")

    for name in ("module", "modules", "install", "load"):
        monkeypatch.setattr(family_registry, name, fail)
    monkeypatch.setattr(family_graders, "install", fail)
    assert sealed_batch_source._kit(FAMILY) is sys.modules["carbon.zz_eleven"]
    assert sealed_batch_source._pool_graded(FAMILY, VERSION) is True
    assert (
        sealed_batch_source._adapter(FAMILY, {"population": "zz"}, VERSION, None)
        is sys.modules["carbon.zz_eleven"]
    )


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("from carbon.scoring import pool_exam", "carbon.scoring.pool_exam"),
        ("import carbon.scoring.pool_exam", "carbon.scoring.pool_exam"),
        ("from carbon.scoring.pool_exam import exam", "pool_exam.exam"),
        ("import scipy", "scipy"),
        ("from . import other", "a relative import"),
        ("import importlib\n\nimportlib.import_module('json')", "import_module"),
        ("exec('1')", "a call of exec"),
        ("__import__('json')", "a call of __import__"),
    ],
)
@pytest.mark.parametrize("lazy", [False, True])
def test_a_module_that_reaches_code_outside_its_digest_is_refused(
    modules, tmp_path, text, reason, lazy
):
    if lazy:
        text = "def _later():\n" + "\n".join(
            "    " + line for line in text.splitlines()
        )
    block = modules.write("zz_reach", ("import json\n", f"import json\n\n{text}\n\n"))
    if not lazy:
        # (the text is read, so what it would do is never run: the module itself need not import)
        path = modules.folder / "zz_reach.py"
        assert family_graders._outside(path, {path.resolve()}) is not None
    assert _install(tmp_path, {FAMILY: _row(block, block)}) == ()
    if lazy:
        assert reason in family_graders.refused()[FAMILY]
    assert sealed_batch_source._kit(FAMILY) is None


def test_a_shared_producer_file_numpy_and_jax_may_be_imported(modules, tmp_path):
    text = (
        "import json\n\nimport numpy as np\nfrom carbon.scoring import copy_derivation\n"
        "from carbon.scoring.copy_derivation import opaque_for\n\n"
        "def _later():\n    import jax.numpy\n"
    )
    block = modules.write("zz_allowed", ("import json\n", text))
    assert _install(tmp_path, {FAMILY: _row(block, block)}) == (FAMILY,)


def test_no_other_code_registers_an_adapter_at_run_time():
    """A new lazy ``register()`` must name a Challenge in ``BUILTIN`` (so no row can shadow it) and be added here."""
    import ast

    found = set()
    for path in sorted((ROOT / "carbon").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if ".register(" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "register"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in ("physical_adapters", "sealed_batch_source")
            ):
                found.add(
                    (path.relative_to(ROOT).as_posix(), ast.unparse(node.args[0]))
                )
    assert found == {
        (
            "carbon/challenge_validator/lean_recipe_retention.py",
            "battery_dual_pack",
        ),
        (
            "carbon/challenge_validator/lean_recipe_retention.py",
            "battery_sealed_dual_pack",
        ),
        ("carbon/scoring/family_graders.py", "served[1]"),
    }
    assert sealed_batch_source.BATTERY in family_registry.BUILTIN
