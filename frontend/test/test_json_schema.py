from typing import Dict

from jsonschema.exceptions import RefResolutionError
from jsonschema.validators import RefResolver
from pytest import raises

from mate_common.schemata import inline_refs


def test_inline_refs_empty():
    schema: Dict = {}
    assert schema == inline_refs(RefResolver.from_schema(schema), schema, gas=5)


def test_inline_refs_comment():
    schema = {"$comment": "Some comment"}
    assert schema == inline_refs(RefResolver.from_schema(schema), schema, gas=5)


def test_inline_refs_single_ref():
    schema = {"definitions": {"foo": {"type": "string"}}, "allOf": [{"$ref": "#definitions/foo"}]}
    assert {
        "allOf": [{"type": "string"}],
        "definitions": {"foo": {"type": "string"}},
    } == inline_refs(RefResolver.from_schema(schema), schema, gas=5)


def test_inline_refs_nonexistent_ref():
    schema = {"definitions": {"bar": {"type": "string"}}, "allOf": {"$ref": "#definitions/foo"}}
    with raises(RefResolutionError):
        inline_refs(RefResolver.from_schema(schema), schema, gas=5)
