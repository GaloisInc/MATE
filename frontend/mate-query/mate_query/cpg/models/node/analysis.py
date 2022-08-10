"""Analysis nodes.

At runtime, the models here are accessed via attributes on a CPG, not directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, or_
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, relationship

from mate_common.models.cpg_types import EdgeKind, NodeKind
from mate_query.cpg.models.core.relationships import Direction
from mate_query.cpg.models.node._typechecking import NodeMixin

if TYPE_CHECKING:

    from sqlalchemy.orm import RelationshipProperty


class MemoryLocation(NodeMixin):
    _kind = NodeKind.MEMORY_LOCATION

    @declared_attr
    def loaded_to(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.LOAD_MEMORY, cls.cpg.Load, backref="loads_from")

    @declared_attr
    def stored_from(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.STORE_MEMORY, cls.cpg.Store, backref="stores_to")

    @declared_attr
    def may_alias(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.MAY_ALIAS, cls, direction=Direction.SYMMETRIC  # type: ignore[arg-type]
        )

    @declared_attr
    def must_alias(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.MUST_ALIAS, cls, direction=Direction.SYMMETRIC  # type: ignore[arg-type]
        )

    @declared_attr
    def contained_by(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.CONTAINS,
            cls,  # type: ignore[arg-type]
            direction=Direction.IN,
            backref="contains",
        )

    @declared_attr
    def subregion_of(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.SUBREGION,
            cls,  # type: ignore[arg-type]
            direction=Direction.IN,
            backref="subregions",
        )

    @declared_attr
    def accessed_by(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Instruction,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=or_(
                and_(
                    cls.cpg.Edge.kind == EdgeKind.LOAD_MEMORY,
                    cls.cpg.Edge.source == cls.uuid,
                ),
                and_(
                    cls.cpg.Edge.kind == EdgeKind.STORE_MEMORY,
                    cls.cpg.Edge.target == cls.uuid,
                ),
            ),
            secondaryjoin=or_(
                and_(
                    cls.cpg.Edge.kind == EdgeKind.LOAD_MEMORY,
                    cls.cpg.Edge.target == cls.cpg.Instruction.uuid,
                ),
                and_(
                    cls.cpg.Edge.kind == EdgeKind.STORE_MEMORY,
                    cls.cpg.Edge.source == cls.cpg.Instruction.uuid,
                ),
            ),
            backref=backref(
                "accesses", doc="Connects an instruction to memory locations that it loads/stores"
            ),
            lazy="dynamic",
            doc="Connects a memory location to instructions that may load or store from the location.",
        )

    @declared_attr
    def allocated_by(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.ALLOCATES,
                cls.cpg.Edge.target == cls.uuid,
            ),
            secondaryjoin=cls.cpg.Edge.source == cls.cpg.Node.uuid,
            lazy="dynamic",
            doc="Connects a memory location to the instruction that allocated it.",
            backref="allocates",
        )

    @declared_attr
    def pointers(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.POINTS_TO,
                cls.cpg.Edge.target == cls.uuid,
            ),
            secondaryjoin=cls.cpg.Node.uuid == cls.cpg.Edge.source,
            backref="points_to",
            lazy="dynamic",
            doc="Connects a memory location to other locations or values that point to it.",
        )


class DataflowSignature(NodeMixin):
    _kind = NodeKind.DATAFLOW_SIGNATURE

    @declared_attr
    def signature_for(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
            cls.cpg.Instruction,
            backref="dataflow_signatures",
        )

    @declared_attr
    def signature_for_function(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DATAFLOW_SIGNATURE_FOR_FUNCTION,
            cls.cpg.Function,
            backref="dataflow_signatures",
        )

    @declared_attr
    def directly_flows_from(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.DIRECT_DATAFLOW_SIGNATURE,
                cls.cpg.Edge.target == cls.uuid,
            ),
            secondaryjoin=cls.cpg.Node.uuid == cls.cpg.Edge.source,
            backref="directly_flows_to_dataflow_signature",
            lazy="dynamic",
            doc="Connects a dataflow signature to all nodes representing data that flows directly into the modeled operation.",
        )

    @declared_attr
    def indirectly_flows_from(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.INDIRECT_DATAFLOW_SIGNATURE,
                cls.cpg.Edge.target == cls.uuid,
            ),
            secondaryjoin=cls.cpg.Node.uuid == cls.cpg.Edge.source,
            backref="indirectly_flows_to_dataflow_signature",
            lazy="dynamic",
            doc="Connects a dataflow signature to all nodes representing data that flows indirectly into the modeled operation.",
        )

    @declared_attr
    def control_flows_from(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.CONTROL_DATAFLOW_SIGNATURE,
                cls.cpg.Edge.target == cls.uuid,
            ),
            secondaryjoin=cls.cpg.Node.uuid == cls.cpg.Edge.source,
            backref="control_flows_to_dataflow_signature",
            lazy="dynamic",
            doc="Connects a dataflow signature to all nodes representing whether data flows into the modeled operation.",
        )

    @declared_attr
    def flows_to(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE, cls.cpg.Edge.source == cls.uuid
            ),
            secondaryjoin=cls.cpg.Node.uuid == cls.cpg.Edge.target,
            backref="flows_from_dataflow_signature",
            lazy="dynamic",
            doc="Connects a dataflow signature to all nodes representing data that flows out of the modeled operation.",
        )

    @hybrid_property
    def is_allocator(self) -> bool:
        return self.deallocator is not None

    @is_allocator.expression  # type: ignore[no-redef]
    def is_allocator(cls) -> bool:
        return cls.deallocator.isnot(None)


class InputSignature(NodeMixin):
    _kind = NodeKind.INPUT_SIGNATURE

    @declared_attr
    def signature_for(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
            cls.cpg.Instruction,
            backref="input_signatures",
        )

    @declared_attr
    def signature_for_function(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DATAFLOW_SIGNATURE_FOR_FUNCTION,
            cls.cpg.Function,
            backref="input_signatures",
        )

    @declared_attr
    def flows_to(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE, cls.cpg.Edge.source == cls.uuid
            ),
            secondaryjoin=cls.cpg.Node.uuid == cls.cpg.Edge.target,
            backref="flows_from_input_signature",
            lazy="dynamic",
            doc="Connects an input signature to data values that may be affected by the modeled operation.",
        )


class OutputSignature(NodeMixin):
    _kind = NodeKind.OUTPUT_SIGNATURE

    @declared_attr
    def signature_for(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
            cls.cpg.Instruction,
            backref="output_signatures",
        )

    @declared_attr
    def signature_for_function(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DATAFLOW_SIGNATURE_FOR_FUNCTION,
            cls.cpg.Function,
            backref="output_signatures",
        )

    @declared_attr
    def flows_from(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE, cls.cpg.Edge.target == cls.uuid
            ),
            secondaryjoin=cls.cpg.Node.uuid == cls.cpg.Edge.source,
            backref="flows_to_output_signature",
            lazy="dynamic",
            doc="Connects an output signature to data values that may be affect the modeled operation.",
        )
