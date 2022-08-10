"""Core node models and functions.

At runtime, the models here are accessed via attributes on a CPG, not directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, Index, text
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.types import Enum as SAEnum

from mate_common.assertions import mate_assert
from mate_common.models.cpg_types.mate import NODE_PROVENANCE, EdgeKind, MATEComponent, NodeKind
from mate_query.cpg.models.core.base import Base
from mate_query.cpg.models.core.relationships import (
    add_properties_to_node_class,
    make_edge_relationship,
)

if TYPE_CHECKING:
    from typing import Any, Dict, List, Optional, Tuple, Type

    from sqlalchemy.orm import RelationshipProperty

    from mate_query.cpg.models.core.relationships import Direction


def node_kind_column() -> Column:
    return Column(
        "kind",
        SAEnum(NodeKind, values_callable=lambda x: [e.value for e in x], validate_strings=True),
        index=True,
        nullable=False,
    )


class BaseNode(Base):
    # NOTE(lb): This is shared between SQLite (declarative) and Postgres
    # (imperative) mappings.
    # TODO(#1044): Remove me!

    kind = node_kind_column()

    @classmethod
    def from_filename_line_no(cls, filepath: str, line_no: Optional[int] = None) -> Node:
        """Returns Nodes whose debug symbols contain the given filepath, or the matching filepath
        and line number."""
        session = cls._session().query(cls)
        if line_no:
            return session.filter(
                Node.attributes["location"]["file"].as_string() == filepath,
                Node.attributes["location"]["line"].as_integer() == line_no,
            ).all()
        return session.filter(Node.attributes["location"]["file"].as_string() == filepath).all()

    @classmethod
    def from_dirpath(cls, dirpath: str) -> List[Node]:
        """Returns Nodes whose debug symbols contain a filepath that includes the given dirpath."""
        return (
            cls._session()
            .query(cls)
            .filter(Node.attributes["location"]["file"].as_string().like("%" + dirpath + "/%"))
            .all()
        )

    @hybrid_property
    def provenance(self) -> MATEComponent:
        return NODE_PROVENANCE[self.kind]

    @property
    def location_string(self) -> str:
        """Return a human-readable source location string for this node."""
        # TODO: This should be optimized and specialized more.
        location = self.attributes.get("location")
        if location is None:
            return "<unknown>"
        filename = location.get("file", "<unknown>")
        line = location.get("line", "<unknown>")
        column = location.get("column")
        try:
            function = f":{self.parent_block.parent_function.demangled_name}"
        except:
            function = ""
        if column is not None:
            return f"{filename}:{line}:{column}{function}"
        else:
            return f"{filename}:{line}{function}"

    def __repr__(self) -> str:
        try:
            return f"<{self.__class__._kind.value}({self.uuid})>"
        except AttributeError:
            return f"<Node({self.uuid})>"

    @classmethod
    def edge_relationship(
        cls,
        edge_kind: EdgeKind,
        other: Type[Node],
        direction: Optional[Direction] = None,
        **kwargs: Any,
    ) -> RelationshipProperty:
        return make_edge_relationship(
            cls.cpg, edge_kind, cls, other, direction, **kwargs  # type: ignore[arg-type]
        )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """This function sets up properties like ``Instruction.opcode`` and relationships like
        ``Instruction.parent_block`` that can be used both inside SQL expression contexts (queries),
        and outside of them in Python-land.

        In detail:

        * Add a docstring to subclasses which is taken from the "description"
        field of the JSON schema for this node's kind (in ``nodes.json``).
        * Add SQLAlchemy relationships for each item in the subclass's
        ``_edges`` attribute. These relationships are automatically
        configured according to the ``endpoints.json`` and ``relationships``
        schemata.
        * Add a ``hybrid_property`` for each property in the JSON schema for
        this node kind.

            + In Python expression contexts, the ``hybrid_property`` will return
            an enum value if relevant, or just the JSON value
            + In SQL expression contexts, the ``hybrid_property`` will wrap the
            value in one of SQLAlchemy's scalar cast methods (e.g. ``as_string()``)
        """
        super().__init_subclass__(**kwargs)
        if getattr(cls, "_kind", None) is not None:
            add_properties_to_node_class(cls)  # type: ignore[arg-type]

    @declared_attr
    def __mapper_args__(cls) -> Dict[str, Any]:
        try:
            return {"polymorphic_identity": cls._kind}
        except AttributeError:
            return {"polymorphic_on": cls.kind, "polymorphic_identity": None}

    @declared_attr
    def __table_args__(cls) -> Tuple[Index, ...]:
        args = [
            Index(
                f"node_{cls.build_id}_location",
                text("(((attributes -> 'location') ->> 'file'))"),
                text("((((attributes -> 'location') ->> 'line')::int))"),
            ),
            Index(
                f"node_{cls.build_id}_allocation",
                text("((attributes ->> 'alias_set_identifier'))"),
            ),
        ]
        return tuple(args)


class Node(BaseNode):
    def __init__(
        self,
        uuid: str,  # pylint: disable=unused-argument
        kind: NodeKind,  # pylint: disable=unused-argument
        attributes: Dict[str, Any] = dict(),  # pylint: disable=unused-argument
    ):
        mate_assert(False, "Unused. Just exists to make Mypy happy.")
