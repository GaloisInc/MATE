"""Core edge models and functions.

At runtime, the models here are accessed via attributes on a CPG, not directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKeyConstraint, Index, Table, text
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import RelationshipProperty, backref, relationship
from sqlalchemy.types import Enum as SAEnum
from sqlalchemy.types import String

from mate_common.assertions import mate_assert
from mate_common.models.cpg_types.mate import EdgeKind
from mate_query.cpg.models.core.base import Base

if TYPE_CHECKING:
    from typing import Any, ClassVar, Dict, Optional, Tuple, Union

    from mate_query.cpg.models.core.node import BaseNode
    from mate_query.db import Graph as CPG


def edge_kind_column() -> Column:
    return Column(
        "kind",
        SAEnum(EdgeKind, values_callable=lambda x: [e.value for e in x], validate_strings=True),
        index=True,
        nullable=False,
    )


def source_column(_node_uuid_column: Optional[Column] = None) -> Column:
    return Column(
        "source",
        String,
        doc="The uuid of the edge's source node.",
        nullable=False,
    )


def target_column(_node_uuid_column: Optional[Column] = None) -> Column:
    return Column(
        "target",
        String,
        doc="The uuid of the edge's target node.",
        nullable=False,
    )


def edge_foreign_key_constraints(node_table: Table) -> Tuple[ForeignKeyConstraint, ...]:
    return (
        ForeignKeyConstraint(["source"], [node_table.c.uuid]),
        ForeignKeyConstraint(["target"], [node_table.c.uuid]),
    )


class BaseEdge(Base):
    # NOTE(lb): This is shared between SQLite (declarative) and Postgres
    # (imperative) mappings.
    # TODO(#1044): Remove me!

    cpg: ClassVar[CPG]

    # NOTE(lb): Why Node when we already have cpg.Node in scope? We map db.Node
    # and db.Edge without a CPG handy, so the ClassVar[CPG] is a bit of a fib
    # in that specific case.
    Node: ClassVar[BaseNode]

    kind = edge_kind_column()

    @declared_attr
    def __table_args__(cls) -> Tuple[Union[ForeignKeyConstraint, Index], ...]:
        args = list(edge_foreign_key_constraints(cls.Node.__table__))
        args.extend(
            [
                Index(
                    f"edge_{cls.build_id}_kind_source",
                    edge_kind_column(),
                    source_column(cls.Node.uuid),
                ),
                Index(
                    f"edge_{cls.build_id}_kind_target",
                    edge_kind_column(),
                    target_column(cls.Node.uuid),
                ),
                Index(
                    f"edge_{cls.build_id}_source_kind",
                    source_column(cls.Node.uuid),
                    edge_kind_column(),
                ),
                Index(
                    f"edge_{cls.build_id}_target_kind",
                    target_column(cls.Node.uuid),
                    edge_kind_column(),
                ),
                Index(
                    f"edge_{cls.build_id}_kind_source_context",
                    edge_kind_column(),
                    source_column(cls.Node.uuid),
                    text("(attributes->>'context')"),
                ),
                Index(
                    f"edge_{cls.build_id}_kind_target_context",
                    edge_kind_column(),
                    target_column(cls.Node.uuid),
                    text("(attributes->>'context')"),
                ),
                Index(
                    f"edge_{cls.build_id}_kind_source_caller",
                    edge_kind_column(),
                    source_column(cls.Node.uuid),
                    text("(attributes->>'caller_context')"),
                ),
                Index(
                    f"edge_{cls.build_id}_kind_target_callee",
                    edge_kind_column(),
                    target_column(cls.Node.uuid),
                    text("(attributes->>'callee_context')"),
                ),
            ]
        )
        return tuple(args)

    @declared_attr
    def source(cls) -> Column:
        return source_column(cls.Node.uuid)

    @declared_attr
    def target(cls) -> Column:
        return target_column(cls.Node.uuid)

    @declared_attr
    def source_node(cls) -> RelationshipProperty:
        return relationship(
            cls.Node,
            backref=backref("outgoing", doc="All edges where this node is the source."),
            foreign_keys=cls.source,
        )

    @declared_attr
    def target_node(cls) -> RelationshipProperty:
        return relationship(
            cls.Node,
            backref=backref("incoming", doc="All edges where this node is the target."),
            foreign_keys=cls.target,
        )

    def __repr__(self) -> str:
        return f"<Edge({self.uuid}: {self.source} -[{self.kind}]> {self.target})>"

    if TYPE_CHECKING:
        # Make Mypy happier. Unused by SQLAlchemy.
        def __init__(
            self,
            uuid: str,  # pylint: disable=unused-argument
            kind: EdgeKind,  # pylint: disable=unused-argument
            source: str,  # pylint: disable=unused-argument
            target: str,  # pylint: disable=unused-argument
            attributes: Dict[str, Any] = dict(),  # pylint: disable=unused-argument
        ):
            mate_assert(False, "Unused. Just exists to make Mypy happy.")


class Edge(BaseEdge):
    # Make Mypy happier. Unused by SQLAlchemy.
    def __init__(
        self,
        uuid: str,  # pylint: disable=unused-argument
        kind: EdgeKind,  # pylint: disable=unused-argument
        source: str,  # pylint: disable=unused-argument
        target: str,  # pylint: disable=unused-argument
        attributes: Dict[str, Any] = dict(),  # pylint: disable=unused-argument
    ):
        mate_assert(False, "Unused. Just exists to make Mypy happy.")
