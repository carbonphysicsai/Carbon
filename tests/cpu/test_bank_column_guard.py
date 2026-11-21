"""S18 bank column guard (DATA_HARVEST_PLAN_20261120 s6; owner B1 21 Nov 17:43Z; BANK contract rule 1).

The bank's code may learn and select on PUBLIC-SIGNAL data only. This pins it from the catalog's OWN class sections,
so a new hidden-derived table in the catalog is caught without editing this test:
(a) every table and column ``bank_features.BankReader`` allows sits in a PUBLIC-SIGNAL section of the catalog DDL
    (``evidence_catalog.DDL``), and every catalog table the DDL marks hidden-derived is refused by name;
(b) no ``scripts/dev/bank_*.py`` names a hidden-derived catalog table, nor a hidden-derived receiver / pool table
    (contract rows 12-20), in its code (docstrings and comments are prose and are skipped);
(c) the allow-list is closed: ``ALLOWED`` names exactly the tables the reader accepts.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import bank_features
import evidence_catalog

#: Receiver / pool-store tables the BANK contract tags hidden-derived (rows 12-20); never named by bank code.
RECEIVER_HIDDEN = {
    "direct_task_seeds",
    "exam_graded",
    "exam_requeues",
    "gate_failures_v1",
    "ladder_feedback_v2",
    "ladder_parts_v4",
    "design_reports",
    "quiz_reports",
}


def catalog_sections():
    """{table: 'public' | 'hidden' | 'meta'} from the catalog DDL's own '-- ' section headings."""
    section, out = "meta", {}
    for line in evidence_catalog.DDL.splitlines():
        text = line.strip()
        if text.startswith("--"):
            upper = text.upper()
            section = "public" if "PUBLIC-SIGNAL" in upper else "hidden"
            continue
        match = re.match(r"CREATE TABLE (\w+)\(", text)
        if match:
            out[match.group(1)] = section
    return out


def catalog_columns(table):
    import sqlite3

    db = sqlite3.connect(":memory:")
    db.executescript(evidence_catalog.DDL)
    cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
    db.close()
    return cols


def code_words(path):
    """Identifier-like words in a module's code: names, attributes and non-docstring string constants."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
            ):
                docstrings.add(id(body[0].value))
    words = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            words.add(node.id)
        elif isinstance(node, ast.Attribute):
            words.add(node.attr)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            words.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", node.value))
    return words


def test_the_catalog_ddl_has_both_classes():
    sections = catalog_sections()
    assert {t for t, s in sections.items() if s == "public"} >= {
        "recipes",
        "submissions",
        "builds",
    }
    assert {t for t, s in sections.items() if s == "hidden"} >= {
        "grades",
        "markers",
        "crown_events",
    }


def test_every_allowed_table_and_column_is_public_signal():
    sections = catalog_sections()
    for table, columns in bank_features.ALLOWED.items():
        if table == "meta":
            assert sections[table] == "meta"
            continue
        assert sections[table] == "public", table
        assert set(columns) <= catalog_columns(table), table


@pytest.mark.parametrize(
    "table", sorted(t for t, s in catalog_sections().items() if s == "hidden")
)
def test_every_hidden_catalog_table_is_refused_by_name(table):
    assert table not in bank_features.ALLOWED
    with pytest.raises(bank_features.BankRefused, match="table_not_allowed"):
        # the refusal comes before any SQL: no catalog file is needed to prove it
        bank_features.BankReader.rows(
            object.__new__(bank_features.BankReader), table, ("x",)
        )


@pytest.mark.parametrize(
    "path", sorted((ROOT / "scripts" / "dev").glob("bank_*.py")), ids=lambda p: p.name
)
def test_no_bank_script_names_a_hidden_derived_table(path):
    hidden = {
        t for t, s in catalog_sections().items() if s == "hidden"
    } | RECEIVER_HIDDEN
    assert not code_words(path) & hidden, path.name


def test_the_allow_list_is_closed():
    assert set(bank_features.ALLOWED) == set(bank_features.EXPECTED)
    for table, expected in bank_features.EXPECTED.items():
        assert expected == catalog_columns(table), table
