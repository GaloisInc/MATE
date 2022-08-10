"""This module contains implementation details; it is not part of the MATE API.

Helpers for deriving documentation and relationships from the MATE JSON schemata.
"""
from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import and_
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.orm import backref as backref_
from sqlalchemy.orm import relationship

from mate_common.assertions import mate_assert
from mate_common.models.cpg_types import (
    EdgeKind,
    LLVMIntrinsic,
    NodeJSON,
    NodeKind,
    Opcode,
    Relationship,
)
from mate_common.schemata import EDGE_SCHEMA_BY_KIND, ENDPOINTS, NODE_SCHEMA_BY_KIND, RELATIONSHIPS
from mate_query.cpg.models.docs import description_for_node_kind
from mate_query.string import StringComparator

if TYPE_CHECKING:
    from typing import Any, Callable, Dict, Optional, Type

    from mate_query.cpg.models.core.node import Node
    from mate_query.db import Graph as CPG


class Direction(Enum):
    IN = "in"
    OUT = "out"
    SYMMETRIC = "symmetric"  # For relationships where either IN or OUT would be suitable


class EnumComparator(Comparator):
    """A specialized SQLAlchemy Comparator for ``enum.Enum``."""

    @staticmethod
    def __cast__(value: Any) -> Any:
        """Turns an ``Enum`` or an iterable into its underlying value(s), if appropriate."""
        if isinstance(value, Enum):
            return value.value

        # NOTE(ww): We support direct comparisons to strings and bytes, which happen
        # to be iterable. Check them here to prevent unintended recursion.
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            return [EnumComparator.__cast__(v) for v in value]
        return value

    def operate(self, op: Any, other: Any, **_kwargs: Any) -> Any:
        return op(self.__clause_element__(), EnumComparator.__cast__(other))


# Map node kinds and attribute names to the Python enums that represent their
# values
_ENUMS = {
    (NodeKind.INSTRUCTION, NodeJSON.OPCODE.value): Opcode,
    (NodeKind.INSTRUCTION, NodeJSON.INTRINSIC.value): LLVMIntrinsic,
}

# NOTE(ww): We include "array" and "object" here for completeness, but we don't coerce
# their inner elements (since SQLAlchemy only needs explicit coercions for scalar properties).
_JSON_SCHEMA_TYPE_TO_PYTHON_TYPE = {
    "boolean": bool,
    "integer": int,
    "string": str,
    "array": list,
    "object": dict,
}


def _coerce_attr(attr: Any, type_: Type) -> Any:
    """Given a class-level SQLAlchemy JSON attribute, attempt to call the appropriate type coercion
    method for ``type_``."""
    if type_ == str:
        return attr.as_string()
    elif type_ == bool:
        return attr.as_boolean()
    elif type_ == int:
        return attr.as_integer()

    mate_assert(type_ in (list, dict), f"uncoercable type: {type_}")
    return attr


def _is_many_end(this_is_source: bool, edge_kind: EdgeKind) -> bool:
    """Decide whether or not to use a list at one end of a ``relationship``"""
    this_is_target = not this_is_source
    rel = RELATIONSHIPS[edge_kind]
    if rel == Relationship.ONE_TO_ONE:
        return False
    if (
        rel == Relationship.MANY_TO_ONE
        and this_is_source
        or rel == Relationship.ONE_TO_MANY
        and this_is_target
    ):
        return False
    if (
        rel == Relationship.ONE_TO_MANY
        and this_is_source
        or rel == Relationship.MANY_TO_ONE
        and this_is_target
    ):
        return True
    if rel == Relationship.MANY_TO_MANY:
        return True
    mate_assert(False, f"Unreachable: {edge_kind}")
    return False


def _use_list_arguments(this_is_source: bool, edge_kind: EdgeKind) -> Dict:
    if _is_many_end(this_is_source, edge_kind):
        return {}
    return {"uselist": False, "lazy": "select"}


def _doc_string(this_is_source: bool, edge_kind: EdgeKind) -> Optional[str]:
    return EDGE_SCHEMA_BY_KIND[edge_kind.value].get(
        "description" if this_is_source else "backref_description"
    )


def _backref_doc(this_is_source: bool, edge_kind: EdgeKind) -> Dict:
    desc = _doc_string(this_is_source, edge_kind)
    if desc:
        return {"doc": desc}
    return {}


def make_edge_relationship(
    cpg: CPG,
    edge_kind: EdgeKind,
    this: Type[Node],
    other: Type[Node],
    direction: Optional[Direction] = None,
    back_populates: Optional[str] = None,
    backref: Optional[str] = None,
) -> RelationshipProperty:
    """Generate a SQLAlchemy relationship given an edge kind."""
    summary = f"kind: {edge_kind}, this: {this}, other: {other}"
    if this == other:
        mate_assert(direction is not None, f"Specified direction required on self-edges: {summary}")
        mate_assert(
            0
            < len(
                [
                    spec
                    for spec in ENDPOINTS[edge_kind]
                    if this._kind in spec.sources and this._kind in spec.targets
                ]
            ),
            f"Invalid relationship spec, no match found in schema: {summary}",
        )
        # NOTE(lb): If the Direction is SYMMETRIC, we can make an arbitrary choice.
        this_is_source = direction == Direction.OUT
    else:
        # Deduce the direction from the spec
        candidates = [
            spec
            for spec in ENDPOINTS[edge_kind]
            if (this._kind in spec.sources and other._kind in spec.targets)
            or (this._kind in spec.targets and other._kind in spec.sources)
        ]
        mate_assert(
            len(candidates) > 0,
            f"Invalid edge relationship spec: {summary}, endpoints: {ENDPOINTS[edge_kind]}",
        )
        mate_assert(
            len(candidates) == 1,
            f"Ambiguous edge relationship spec: {summary}, {ENDPOINTS[edge_kind]}",
        )
        spec = candidates[0]
        this_is_source = this._kind in spec.sources

    # Decide whether or not to use a list (at either end)
    extra_args = _use_list_arguments(this_is_source, edge_kind)
    if back_populates is not None:
        extra_args["back_populates"] = back_populates
    if backref is not None:
        extra_args["backref"] = backref_(
            backref,
            **_use_list_arguments(not this_is_source, edge_kind),
            **_backref_doc(not this_is_source, edge_kind),
        )

    # Figure out what ends of the edge the models should be on
    this_edge_end = cpg.Edge.source if this_is_source else cpg.Edge.target
    other_edge_end = cpg.Edge.target if this_is_source else cpg.Edge.source

    return relationship(
        other,
        secondary=cpg.Edge.__table__,
        primaryjoin=and_(
            this.uuid == this_edge_end,
            cpg.Edge.kind == edge_kind,
        ),
        secondaryjoin=and_(
            other.uuid == other_edge_end,
        ),
        doc=_doc_string(this_is_source, edge_kind),
        **extra_args,
    )


def _make_hybrid_property(
    name: str, type_: Type, enum: Optional[Type[Enum]] = None, docs: Optional[str] = None
) -> Callable:
    @hybrid_property
    def getter0(self: Any) -> Any:
        attr = self.attributes[name]
        if enum is not None:
            return enum(attr)
        return attr

    # If we're building an expression for a field that has a mapped enum,
    # we construct a comparator instead of an expression. This allows
    # us to do e.g. `filter_by(prop=enum)` instead of `filter_by(prop=enum.value)`.
    #
    # Additionally, if the field in question is a string, then we use a custom
    # comparator with regex support (for the purposes of signatures).
    if enum is None:

        if type_ == str:

            @getter0.comparator
            def getter1(cls: Type[Node]) -> Any:
                attr = cls.attributes[name]
                return StringComparator(_coerce_attr(attr, type_))

        else:

            @getter0.expression
            def getter1(cls: Type[Node]) -> Any:
                attr = cls.attributes[name]
                return _coerce_attr(attr, type_)

    else:

        @getter0.comparator
        def getter1(cls: Type[Node]) -> Any:
            attr = cls.attributes[name]
            return EnumComparator(_coerce_attr(attr, type_))

    # NOTE(ww): Cheese Sphinx into adding the return type to these properties.
    # TODO(ww): Why doesn't this work?
    # getter0.fget.__annotations__ = {"return": type_}
    # getter1.fget.__annotations__ = {"return": type_}
    if docs is None:
        docs = f":rtype: {type_.__name__}"
    else:
        docs = f"{docs}\n\n\t:rtype: {type_.__name__}"

    getter0.__name__ = name
    getter1.__name__ = name
    getter0.__doc__ = docs
    getter1.__doc__ = docs
    return getter1


def _hybrid_properties_for_kind(cls: Type[Node]) -> Dict[str, hybrid_property]:
    properties: Dict[str, hybrid_property] = dict()
    # Attach hybrid properties
    for (property_name, property_schema) in NODE_SCHEMA_BY_KIND[cls._kind.value][
        "properties"
    ].items():
        # Don't overwrite properties that were customized/already set
        if property_name == "node_kind" or getattr(cls, property_name, None) is not None:
            continue

        # Types can either be specified directly, or we can deduce the
        # type from one-element "enum" clauses
        if "type" in property_schema:
            schema_type = property_schema["type"]
            mate_assert(
                schema_type in _JSON_SCHEMA_TYPE_TO_PYTHON_TYPE,
                f"Unmapped JSON schema type: {schema_type}",
            )
            type_: Type = _JSON_SCHEMA_TYPE_TO_PYTHON_TYPE[schema_type]
        elif "enum" in property_schema:
            enum = property_schema["enum"]
            mate_assert(len(enum) == 1, f"Non-unary enum with no explicit type: {enum}")
            type_ = type(enum[0])
        else:
            message = (
                f"Schema error: can't infer Python type for {property_name}: {property_schema}"
            )
            if "$ref" in property_schema:
                message = (
                    f"{message}\nHint: {property_name} looks like it contains a reference; "
                    "maybe increase the gas limit in schemata._organize_schema?"
                )
            mate_assert(False, message)

        properties[property_name] = _make_hybrid_property(
            property_name,
            type_=type_,
            enum=_ENUMS.get((cls._kind, property_name)),
            docs=property_schema.get("description"),
        )
    return properties


def add_properties_to_node_class(cls: Type[Node]) -> Any:
    """Add documentation and hybrid properties from the JSON schema to a node class."""
    cls.__doc__ = description_for_node_kind(cls._kind.value)
    for (name, prop) in _hybrid_properties_for_kind(cls).items():
        setattr(cls, name, prop)
