"""The four public pass names (exam feedback v8 `failure.pass`) are each described in one plain line, on the Motor kit page
and in the launchpad's words, and those lines are the same text. The ids are held equal to the set the door can serve.
"""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTAKE = ROOT / "carbon" / "challenge_validator" / "direct_intake.py"
PAGE = ROOT / "kits" / "motor" / "HOW_YOURE_TESTED.md"
WORDS = ROOT / "scripts" / "dev" / "miner_launchpad" / "pass_words.py"

#: The ids the door serves, as the Lead and Validator-2B named them (TE-B's head 371fe649: closed set, else None).
PASSES = ("graded_pass", "inference_pair", "menu_rowcheck", "early_stop")
NEWLINE = chr(10)


def _words():
    spec = importlib.util.spec_from_file_location("pass_words_under_test", WORDS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _page_lines():
    text = PAGE.read_text(encoding="utf-8")
    return dict(re.findall(r"^  - `([a-z_]+)`: (.+)$", text, flags=re.MULTILINE))


def test_launchpad_words_describe_exactly_the_four_passes_in_one_plain_line():
    words = _words()
    assert tuple(words.PASS_IDS) == PASSES
    assert set(words.PASS_LINES) == set(PASSES)
    for pass_id, line in words.PASS_LINES.items():
        assert NEWLINE not in line and line.endswith("."), pass_id
        assert len(line.split()) >= 8, pass_id
        # what the pass is, nothing measured: no seconds, no counts, no digits at all
        assert not any(character.isdigit() for character in line), pass_id


def test_kit_page_names_every_pass_with_the_launchpad_line_word_for_word():
    page = _page_lines()
    words = _words()
    assert (
        tuple(page) == PASSES
    ), "the page must name each of the four passes, in order, once"
    for pass_id in PASSES:
        assert page[pass_id] == words.PASS_LINES[pass_id], pass_id


def test_the_page_pass_ids_equal_what_the_door_can_serve_once_it_serves_them():
    """Before the door carries `failure.pass` (exam feedback v8) there is no door set to compare; once it does, the page and
    the launchpad must name exactly that closed set."""
    # read as source, not imported: the door module needs POSIX-only modules (fcntl) a Windows run lacks
    tree = ast.parse(INTAKE.read_text(encoding="utf-8"))
    door = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "FAILURE_PASSES"
                for target in node.targets
            )
            and isinstance(node.value, ast.Tuple)
        ):
            door = tuple(element.value for element in node.value.elts)
    if door is None:
        return
    assert door == PASSES
