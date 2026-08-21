"""Reference tests for the authoring-only PhysicalSystemSpec validator.

These tests exercise structural behavior only. They do not test scientific truth.
"""

from copy import deepcopy

from physical_system_spec_validator import (
    is_structurally_valid,
    validate_physical_system_spec,
)


def _base_spec():
    return {
        "physical_system_spec_id": "test_system_v1",
        "version": "0.1",
        "status": "authoring_candidate",
        "classification": "public_challenge_semantics",
        "system": {
            "family": "test_pde",
            "system_class": "pde",
            "spatial_dimension": 1,
        },
        "variables": {
            "independent": [
                {"symbol": "x", "role": "spatial"},
                {"symbol": "t", "role": "temporal"},
            ],
            "state": [{"symbol": "u", "depends_on": ["x", "t"]}],
            "fields": [],
            "observed": [],
        },
        "parameters": [{"symbol": "nu"}],
        "governing_relations": [
            {
                "relation_id": "governing_pde",
                "kind": "pde",
                "display_text": "d_t(u) = nu*d_xx(u)",
                "machine_semantics": {
                    "op": "eq",
                    "args": [
                        {
                            "op": "partial",
                            "expr": {"op": "var", "name": "u"},
                            "wrt": "t",
                            "order": 1,
                        },
                        {
                            "op": "mul",
                            "args": [
                                {"op": "param", "name": "nu"},
                                {
                                    "op": "partial",
                                    "expr": {"op": "var", "name": "u"},
                                    "wrt": "x",
                                    "order": 2,
                                },
                            ],
                        },
                    ],
                },
                "provenance": ["manual_test"],
            }
        ],
        "conditions": {"initial": [], "boundary": []},
        "domains": {"x": [0.0, 1.0], "t": [0.0, 1.0]},
        "assumptions": ["test only"],
        "provenance": {"source": "unit_test"},
    }


def _error_codes(spec):
    return {i.code for i in validate_physical_system_spec(spec) if i.severity == "ERROR"}


def test_valid_minimal_evolutionary_pde():
    assert is_structurally_valid(_base_spec())


def test_valid_elliptic_with_fields():
    spec = _base_spec()
    spec["system"] = {"family": "poisson", "system_class": "elliptic_pde", "spatial_dimension": 2}
    spec["variables"]["independent"] = [
        {"symbol": "x", "role": "spatial"},
        {"symbol": "y", "role": "spatial"},
    ]
    spec["variables"]["state"] = [{"symbol": "u", "depends_on": ["x", "y"]}]
    spec["variables"]["fields"] = [
        {"symbol": "k", "role": "coefficient", "depends_on": ["x", "y"]},
        {"symbol": "f", "role": "source", "depends_on": ["x", "y"]},
    ]
    spec["parameters"] = []
    spec["domains"] = {"x": [0.0, 1.0], "y": [0.0, 1.0]}
    spec["governing_relations"][0]["machine_semantics"] = {
        "op": "eq",
        "lhs": {
            "op": "neg",
            "arg": {
                "op": "add",
                "args": [
                    {
                        "op": "partial",
                        "wrt": "x",
                        "order": 1,
                        "expr": {
                            "op": "mul",
                            "args": [
                                {"op": "field", "name": "k"},
                                {"op": "partial", "expr": {"op": "var", "name": "u"}, "wrt": "x", "order": 1},
                            ],
                        },
                    },
                    {
                        "op": "partial",
                        "wrt": "y",
                        "order": 1,
                        "expr": {
                            "op": "mul",
                            "args": [
                                {"op": "field", "name": "k"},
                                {"op": "partial", "expr": {"op": "var", "name": "u"}, "wrt": "y", "order": 1},
                            ],
                        },
                    },
                ],
            },
        },
        "rhs": {"op": "field", "name": "f"},
    }
    spec["governing_relations"][0]["display_text"] = "-div(k grad u) = f"
    assert is_structurally_valid(spec)


def test_undeclared_relation_variable_fails():
    spec = _base_spec()
    spec["governing_relations"][0]["machine_semantics"]["args"][0]["expr"]["name"] = "v"
    assert "PSS061" in _error_codes(spec)


def test_undeclared_derivative_axis_fails():
    spec = _base_spec()
    spec["governing_relations"][0]["machine_semantics"]["args"][0]["wrt"] = "z"
    assert "PSS069" in _error_codes(spec)


def test_unsupported_operator_fails():
    spec = _base_spec()
    spec["governing_relations"][0]["machine_semantics"] = {
        "op": "laplacian",
        "expr": {"op": "var", "name": "u"},
    }
    assert "PSS060" in _error_codes(spec)


def test_duplicate_symbol_fails():
    spec = _base_spec()
    spec["variables"]["fields"] = [{"symbol": "nu", "role": "coefficient"}]
    assert "PSS053" in _error_codes(spec)


def test_malformed_extension_namespace_fails():
    spec = _base_spec()
    spec["extensions"] = {
        "features": {"extension_version": "0.1", "payload": {}},
    }
    assert "PSS091" in _error_codes(spec)


def test_namespaced_extension_passes_core_validation():
    spec = _base_spec()
    spec["extensions"] = {
        "carbon.regime_features": {
            "extension_version": "0.1",
            "payload": {"some_future_feature": "experimental"},
        },
    }
    assert is_structurally_valid(spec)


def test_forbidden_secret_key_fails_even_in_extension():
    spec = _base_spec()
    spec["extensions"] = {
        "carbon.example": {
            "extension_version": "0.1",
            "payload": {"official_seed": 123},
        },
    }
    assert "PSS100" in _error_codes(spec)


def test_unresolved_governing_relation_warns_not_errors():
    spec = _base_spec()
    spec["governing_relations"] = "UNRESOLVED_SCIENTIFIC_OWNER"
    issues = validate_physical_system_spec(spec)
    assert not any(i.severity == "ERROR" and i.path == "$.governing_relations" for i in issues)
    assert any(i.severity == "WARNING" and i.code == "PSS020" for i in issues)


def test_display_text_change_does_not_change_structural_validity():
    a = _base_spec()
    b = deepcopy(a)
    b["governing_relations"][0]["display_text"] = "same machine relation, different presentation"
    assert is_structurally_valid(a)
    assert is_structurally_valid(b)
