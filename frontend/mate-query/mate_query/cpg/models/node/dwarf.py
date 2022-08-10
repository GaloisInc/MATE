"""Nodes in the source-level AST (as recovered from DWARF debug info)

At runtime, the models here are accessed via attributes on a CPG, not directly.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import RelationshipProperty

from mate_common.models.cpg_types import (
    CountSubrange,
    DWARFEnumerator,
    DWARFScope,
    DWARFSubrange,
    DWARFSubrangeKind,
    DWARFTypeCommonInfo,
    DWARFTypeKind,
    EdgeKind,
    GlobalVariableSubrange,
    LocalVariableSubrange,
    NodeKind,
    mate_assert,
)
from mate_query.cpg.models.core.relationships import Direction, EnumComparator
from mate_query.cpg.models.node._typechecking import NodeMixin


class DWARFType(NodeMixin):
    _kind = NodeKind.DWARF_TYPE

    @declared_attr
    def arguments(cls) -> RelationshipProperty:
        """A list of `DWARFArgument` instances that have this type."""
        return cls.edge_relationship(
            EdgeKind.HAS_DWARF_TYPE, cls.cpg.DWARFArgument, backref="dwarf_type"
        )

    @declared_attr
    def local_variables(cls) -> RelationshipProperty:
        """A list of `DWARFLocalVariable` instances that have this type."""
        return cls.edge_relationship(
            EdgeKind.HAS_DWARF_TYPE, cls.cpg.DWARFLocalVariable, backref="dwarf_type"
        )

    @declared_attr
    def parents(cls) -> RelationshipProperty:
        """The parent types of this type."""
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_PARENT_TYPE, cls, Direction.OUT  # type: ignore[arg-type]
        )

    @declared_attr
    def children(cls) -> RelationshipProperty:
        """The child types of this type."""
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_PARENT_TYPE, cls, Direction.IN  # type: ignore[arg-type]
        )

    @declared_attr
    def deriving_types(cls) -> RelationshipProperty:
        """Any types that derive directly from this type.

        For the fully expanded derivation set, use `all_derived_types`.
        """
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_BASE_TYPE, cls, Direction.IN  # type: ignore[arg-type]
        )

    @hybrid_property
    def common(self) -> DWARFTypeCommonInfo:
        """A `DWARFTypeCommonInfo` model of this type's baseline information."""
        return DWARFTypeCommonInfo(**self.dwarf_type["common"])

    @hybrid_property
    def name(self) -> str:
        """The type's name."""
        return self.common.name

    @name.expression  # type: ignore[no-redef]
    def name(cls):
        return cls.dwarf_type["common"]["name"].as_string()

    @hybrid_property
    def tag(self) -> str:
        """The type's tag (i.e., ``DW_TAG_*``)."""
        return self.common.tag

    @tag.expression  # type: ignore[no-redef]
    def tag(cls):
        return cls.dwarf_type["common"]["tag"].as_string()

    @hybrid_property
    def type_kind(self) -> DWARFTypeKind:
        """The type's `DWARFTypeKind`"""
        return DWARFTypeKind(self.dwarf_type["kind"])

    @type_kind.expression  # type: ignore[no-redef]
    def type_kind(cls):
        return EnumComparator(cls.dwarf_type["kind"].as_string())

    # TODO(ww): These predicates can probably be removed now that we can query
    # for explicit DWARFType subclasses.

    @hybrid_property
    def is_void(self) -> bool:
        """Whether this type is a ``void`` type."""
        return self.name == "void" and self.tag == "DW_TAG_unspecified_type"

    @is_void.expression  # type: ignore[no-redef]
    def is_void(cls) -> bool:
        return cls.name == "void" and cls.tag == "DW_TAG_unspecified_type"

    @hybrid_property
    def is_varargs(self) -> bool:
        """Whether this type is a variable argument (vaarg) type."""
        return self.name == "..." and self.tag == "DW_TAG_unspecified_parameters"

    @is_varargs.expression  # type: ignore[no-redef]
    def is_varargs(cls) -> bool:
        return cls.name == "..." and cls.tag == "DW_TAG_unspecified_parameters"

    @hybrid_property
    def is_pointer(self) -> bool:
        """Whether this type is a pointer type."""
        return self.tag == "DW_TAG_pointer_type"

    @is_pointer.expression  # type: ignore[no-redef]
    def is_pointer(cls) -> bool:
        return cls.tag == "DW_TAG_pointer_type"

    @hybrid_property
    def is_member(self) -> bool:
        """Whether this type is a member type."""
        return self.tag == "DW_TAG_member"

    @is_member.expression  # type: ignore[no-redef]
    def is_member(cls) -> bool:
        return cls.tag == "DW_TAG_member"

    @hybrid_property
    def is_const(self) -> bool:
        """Whether this type is ``const``."""
        return self.tag == "DW_TAG_const_type"

    @is_const.expression  # type: ignore[no-redef]
    def is_const(cls) -> bool:
        return cls.tag == "DW_TAG_const_type"

    @hybrid_property
    def is_reference(self) -> bool:
        """Whether this type is an (lvalue) reference."""
        return self.tag == "DW_TAG_reference_type"

    @is_reference.expression  # type: ignore[no-redef]
    def is_reference(cls) -> bool:
        return cls.tag == "DW_TAG_reference_type"

    @hybrid_property
    def is_rvalue_reference(self) -> bool:
        """Whether this type is an rvalue reference."""
        return self.tag == "DW_TAG_rvalue_reference_type"

    @is_rvalue_reference.expression  # type: ignore[no-redef]
    def is_rvalue_reference(cls) -> bool:
        return cls.tag == "DW_TAG_rvalue_reference_type"

    @hybrid_property
    def is_basic(self) -> bool:
        """Whether this type is basic, i.e. `DWARFTypeKind.BASIC`."""
        return self.type_kind == DWARFTypeKind.BASIC

    @hybrid_property
    def is_composite(self) -> bool:
        return self.type_kind == DWARFTypeKind.COMPOSITE

    @hybrid_property
    def is_structure(self) -> bool:
        """Whether this type is a ``struct`` type."""
        return self.type_kind == DWARFTypeKind.STRUCTURE

    @hybrid_property
    def is_array(self) -> bool:
        """Whether this type is an array type."""
        return self.type_kind == DWARFTypeKind.ARRAY

    @hybrid_property
    def is_enum(self) -> bool:
        """Whether this type is an ``enum`` type."""
        return self.type_kind == DWARFTypeKind.ENUM

    @hybrid_property
    def is_union(self) -> bool:
        """Whether this type is a ``union`` type."""
        return self.type_kind == DWARFTypeKind.UNION

    @hybrid_property
    def is_class(self) -> bool:
        """Whether this type is a ``class`` type."""
        return self.type_kind == DWARFTypeKind.CLASS

    @hybrid_property
    def is_derived(self) -> bool:
        """Whether this type is derived from another type."""
        return self.type_kind == DWARFTypeKind.DERIVED

    @hybrid_property
    def is_subroutine(self) -> bool:
        """Whether this type is a subroutine (i.e., function) type."""
        return self.type_kind == DWARFTypeKind.SUBROUTINE

    @declared_attr
    def __mapper_args__(cls) -> Dict[str, Any]:
        try:
            return {"polymorphic_identity": cls._kind}
        except AttributeError:
            return {"polymorphic_identity": NodeKind.DWARF_TYPE}

    @hybrid_property
    def all_derived_types(self) -> List[DWARFType]:
        """Returns a list of all `DWARFType` instances that derive from this type, including
        indirect derivations (e.g. ``T -> T* -> const T*``)."""
        curr = deque(self.deriving_types)
        derived = set()
        while curr:
            base_type = curr.popleft()
            derived.add(base_type)
            curr.extend(base_type.deriving_types)
        return list(derived)


class BasicType(DWARFType):
    _kind = NodeKind.BASIC_TYPE

    @hybrid_property
    def is_unsigned(self) -> bool:
        """Whether this type is unsigned."""
        return self.dwarf_type["unsigned"]


class CompositeType(DWARFType):
    _kind = NodeKind.COMPOSITE_TYPE

    @declared_attr
    def base_type(cls) -> RelationshipProperty:
        """The base type."""
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_BASE_TYPE, cls.cpg.DWARFType, Direction.OUT
        )

    @declared_attr
    def elements(cls) -> RelationshipProperty:
        """The member elements of this composite type."""
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_MEMBER_TYPE, cls.cpg.DWARFType, Direction.OUT
        )


class CompositeCachedType(DWARFType):
    _kind = NodeKind.COMPOSITE_CACHED_TYPE

    @declared_attr
    def recursive_type(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_RECURSIVE_TYPE, cls.cpg.DWARFType, Direction.OUT
        )


class StructureType(DWARFType):
    _kind = NodeKind.STRUCTURE_TYPE

    @declared_attr
    def base_type(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_BASE_TYPE, cls.cpg.DWARFType, Direction.OUT
        )

    @declared_attr
    def members(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_MEMBER_TYPE, cls.cpg.DWARFType, Direction.OUT
        )


class ArrayType(DWARFType):
    _kind = NodeKind.ARRAY_TYPE

    @declared_attr
    def base_type(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_BASE_TYPE, cls.cpg.DWARFType, Direction.OUT
        )

    @hybrid_property
    def subrange(self) -> Optional[DWARFSubrange]:
        """Returns a `DWARFSubrange` for this array type's subrange.

        The subrange can be a `CountSubrange`, `GlobalVariableSubrange`, or `LocalVariableSubrange`.
        """
        subrange = self.dwarf_type["subrange"]
        if DWARFSubrangeKind.COUNT.value in subrange:
            return CountSubrange(kind=DWARFSubrangeKind.COUNT, **subrange)
        elif DWARFSubrangeKind.GLOBAL_VARIABLE.value in subrange:
            return GlobalVariableSubrange(
                kind=DWARFSubrangeKind.GLOBAL_VARIABLE,
                **subrange[DWARFSubrangeKind.GLOBAL_VARIABLE.value],
            )
        elif DWARFSubrangeKind.LOCAL_VARIABLE.value in subrange:
            return LocalVariableSubrange(
                kind=DWARFSubrangeKind.LOCAL_VARIABLE,
                **subrange[DWARFSubrangeKind.LOCAL_VARIABLE.value],
            )
        else:
            mate_assert(False, f"Impossible subrange type {subrange}")
        return None


class EnumType(DWARFType):
    _kind = NodeKind.ENUM_TYPE

    @declared_attr
    def base_type(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_BASE_TYPE, cls.cpg.DWARFType, Direction.OUT
        )

    @hybrid_property
    def enumerators(self) -> List[DWARFEnumerator]:
        """Returns a list of `DWARFEnumerator` variants."""
        return [DWARFEnumerator(**enum) for enum in self.dwarf_type["enumerators"]]


class UnionType(DWARFType):
    _kind = NodeKind.UNION_TYPE

    @declared_attr
    def base_type(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_BASE_TYPE, cls.cpg.DWARFType, Direction.OUT
        )

    @declared_attr
    def members(cls) -> RelationshipProperty:
        """Returns the member types of this ``union``."""
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_MEMBER_TYPE, cls.cpg.DWARFType, Direction.OUT
        )


class ClassType(DWARFType):
    _kind = NodeKind.CLASS_TYPE

    @declared_attr
    def base_type(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_BASE_TYPE, cls.cpg.DWARFType, Direction.OUT
        )

    @declared_attr
    def members(cls) -> RelationshipProperty:
        """Returns the member types of this ``class``."""
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_MEMBER_TYPE, cls.cpg.DWARFType, Direction.OUT
        )

    @declared_attr
    def template_params(cls) -> RelationshipProperty:
        """Returns the template parameter types for this ``class``."""
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_TEMPLATE_PARAM_TYPE, cls.cpg.DWARFType, Direction.OUT
        )


class DerivedType(DWARFType):
    _kind = NodeKind.DERIVED_TYPE

    @declared_attr
    def base_type(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_BASE_TYPE, cls.cpg.DWARFType, Direction.OUT
        )


class SubroutineType(DWARFType):
    _kind = NodeKind.SUBROUTINE_TYPE

    @declared_attr
    def return_type(cls) -> RelationshipProperty:
        """Returns the subroutine's return type."""
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_RETURN_TYPE, cls.cpg.DWARFType, Direction.OUT
        )

    @declared_attr
    def param_types(cls) -> RelationshipProperty:
        """Returns the parameter type for each parameter in the subroutine."""
        return cls.edge_relationship(
            EdgeKind.DWARF_TYPE_TO_PARAM_TYPE, cls.cpg.DWARFType, Direction.OUT
        )

    @hybrid_property
    def has_varargs(self) -> bool:
        """Returns whether the subroutine has a variable number of arguments."""
        return any(param_type.is_varargs for param_type in self.param_types)


class DWARFLocalVariable(NodeMixin):
    """Represents a DWARF view of a local variable."""

    _kind = NodeKind.DWARF_LOCAL_VARIABLE

    @property
    def dwarf_scope(self) -> DWARFScope:
        """Returns the `DWARFScope` for this local variable."""
        return DWARFScope(**self.attributes["dwarf_scope"])


class DWARFArgument(NodeMixin):
    """Represents a DWARF view of a formal function parameter."""

    _kind = NodeKind.DWARF_ARGUMENT

    @property
    def dwarf_scope(self) -> DWARFScope:
        """Returns the `DWARFScope` for this function argument."""
        return DWARFScope(**self.attributes["dwarf_scope"])
