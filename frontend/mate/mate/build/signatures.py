from __future__ import annotations

import itertools
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Final,
    Iterable,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.expression import func

from mate.logging import logger
from mate_common.models.cpg_types import EdgeKind, NodeKind
from mate_query import db

if TYPE_CHECKING:
    from re import Pattern

    from mate_query.cpg.models.core import Node
    from mate_query.cpg.models.node.ast.llvm import CallSite


class InvalidSignature(Exception):
    def __init__(self, message: str = "Invalid signature") -> None:
        self.message = message
        super().__init__(self.message)


class UnknownSignature(Exception):
    def __init__(self, message: str = "Unknown signature") -> None:
        self.message = message
        super().__init__(self.message)


T = TypeVar("T", bound="SignatureSelector")


class SignatureSelector(ABC):

    argument_types: List[type]

    @classmethod
    def parse_arguments(cls: Type[T], arguments: List[Union[int, str]]) -> SignatureSelector:
        expected = len(cls.argument_types)
        if len(arguments) != expected:
            raise InvalidSignature(f"{cls.__name__} expected {expected} arguments, got {arguments}")
        for (arg, ty) in zip(arguments, cls.argument_types):
            if type(arg) is not ty:
                raise InvalidSignature(
                    f"{cls.__name__} expected arguments of types {cls.argument_types}, got {arguments}"
                )
        return cls(*arguments)

    @abstractmethod
    def _uuids_at_callsite(
        self,
        cpg: db.Graph,
        session: Session,
        callsite: CallSite,
        context: str,
    ) -> Iterable[Tuple[str]]:
        pass


class ReturnSelector(SignatureSelector):

    argument_types: List[type] = []

    def __repr__(self) -> str:
        return "<ReturnSelector()>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, _context: str
    ) -> Iterable[Tuple[str]]:
        return session.query(cpg.CallSite.uuid).filter_by(uuid=callsite.uuid).all()


class ReturnPointsToSelector(SignatureSelector):

    argument_types: List[type] = []

    def __repr__(self) -> str:
        return "<ReturnPointsToSelector()>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, context: str
    ) -> Iterable[Tuple[str]]:
        Edge2 = aliased(cpg.Edge)
        return (
            session.query(cpg.Edge)
            .filter(
                cpg.Edge.kind == EdgeKind.POINTS_TO,
                cpg.Edge.source == callsite.uuid,
                cpg.Edge.attributes["context"].as_string() == context,
            )
            .join(Edge2, (Edge2.source == cpg.Edge.target) & (Edge2.kind == EdgeKind.MAY_ALIAS))
            .with_entities(Edge2.target)
            .all()
        )


class ReturnPointsToAggregateSelector(SignatureSelector):

    argument_types: List[type] = []

    def __repr__(self) -> str:
        return "<ReturnPointsToAggregateSelector()>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, context: str
    ) -> Iterable[Tuple[str]]:
        Edge2 = aliased(cpg.Edge)
        return (
            session.query(cpg.Edge)
            .filter(
                cpg.Edge.kind == EdgeKind.POINTS_TO,
                cpg.Edge.source == callsite.uuid,
                cpg.Edge.attributes["context"].as_string() == context,
            )
            .join(
                Edge2,
                (Edge2.source == cpg.Edge.target)
                & Edge2.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]),
            )
            .with_entities(Edge2.target)
            .all()
        )


class ReturnReachableSelector(SignatureSelector):

    argument_types: List[type] = []

    def __repr__(self) -> str:
        return "<ReturnReachableSelector()>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, context: str
    ) -> Iterable[Tuple[str]]:
        PointsTo = aliased(cpg.Edge)
        MayAlias = aliased(cpg.Edge)
        base_step = (
            session.query(PointsTo)
            .filter(
                PointsTo.kind == EdgeKind.POINTS_TO,
                PointsTo.source == callsite.uuid,
                PointsTo.attributes["context"].as_string() == context,
            )
            .join(
                MayAlias,
                (PointsTo.target == MayAlias.source)
                & MayAlias.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]),
            )
            .with_entities(MayAlias.target.label("location"))
            .cte("cte", recursive=True)
        )
        recursive_step = (
            session.query(PointsTo)
            .join(
                base_step,
                (PointsTo.source == base_step.c.location) & (PointsTo.kind == EdgeKind.POINTS_TO),
            )
            .join(
                MayAlias,
                (PointsTo.target == MayAlias.source)
                & MayAlias.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]),
            )
            .with_entities(MayAlias.target.label("location"))
        )

        return session.query(base_step.union(recursive_step)).all()


class ArgSelector(SignatureSelector):

    argument_types: List[type] = [int]

    def __init__(self, index: int) -> None:
        self.index = index

    def __repr__(self) -> str:
        return f"<ArgSelector({self.index})>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, _context: str
    ) -> Iterable[Tuple[str]]:
        return (
            session.query(cpg.Edge)
            .filter(
                cpg.Edge.target == callsite.uuid,
                cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE,
                cpg.Edge.attributes["operand_number"].as_integer() == self.index,
                cpg.Edge.attributes["is_argument_operand"].as_boolean() == True,
            )
            .with_entities(cpg.Edge.source)
            .all()
        )


class ArgPointsToSelector(SignatureSelector):

    argument_types: List[type] = [int]

    def __init__(self, index: int) -> None:
        self.index = index

    def __repr__(self) -> str:
        return f"<ArgPointsToSelector({self.index})>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, context: str
    ) -> Iterable[Tuple[str]]:
        ThisEdge = aliased(cpg.Edge)
        PointsTo = aliased(cpg.Edge)
        MayAlias = aliased(cpg.Edge)
        return (
            session.query(ThisEdge)
            .filter(
                ThisEdge.target == callsite.uuid,
                ThisEdge.kind == EdgeKind.VALUE_DEFINITION_TO_USE,
                ThisEdge.attributes["operand_number"].as_integer() == self.index,
                ThisEdge.attributes["is_argument_operand"].as_boolean() == True,
            )
            .join(
                PointsTo,
                (
                    (PointsTo.kind == EdgeKind.POINTS_TO)
                    & (PointsTo.source == ThisEdge.source)
                    & (PointsTo.attributes["context"].as_string() == context)
                ),
            )
            .join(
                MayAlias,
                (MayAlias.kind == EdgeKind.MAY_ALIAS) & (MayAlias.source == PointsTo.target),
            )
            .with_entities(MayAlias.target)
            .all()
        )


class ArgPointsToAggregateSelector(SignatureSelector):

    argument_types: List[type] = [int]

    def __init__(self, index: int) -> None:
        self.index = index

    def __repr__(self) -> str:
        return f"<ArgPointsToAggregateSelector({self.index})>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, context: str
    ) -> Iterable[Tuple[str]]:
        ThisEdge = aliased(cpg.Edge)
        PointsTo = aliased(cpg.Edge)
        MayAlias = aliased(cpg.Edge)
        return (
            session.query(ThisEdge)
            .filter(
                ThisEdge.target == callsite.uuid,
                ThisEdge.kind == EdgeKind.VALUE_DEFINITION_TO_USE,
                ThisEdge.attributes["operand_number"].as_integer() == self.index,
                ThisEdge.attributes["is_argument_operand"].as_boolean() == True,
            )
            .join(
                PointsTo,
                (
                    (PointsTo.kind == EdgeKind.POINTS_TO)
                    & (PointsTo.source == ThisEdge.source)
                    & (PointsTo.attributes["context"].as_string() == context)
                ),
            )
            .join(
                MayAlias,
                (MayAlias.source == PointsTo.target)
                & MayAlias.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]),
            )
            .with_entities(MayAlias.target)
            .all()
        )


class ArgReachableSelector(SignatureSelector):

    argument_types: List[type] = [int]

    def __init__(self, index: int) -> None:
        self.index = index

    def __repr__(self) -> str:
        return f"<ArgReachableSelector({self.index})>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, context: str
    ) -> Iterable[Tuple[str]]:
        PointsTo = aliased(cpg.Edge)
        MayAlias = aliased(cpg.Edge)
        base_step = (
            session.query(cpg.Edge)
            .filter(
                cpg.Edge.target == callsite.uuid,
                cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE,
                cpg.Edge.attributes["operand_number"].as_integer() == self.index,
                cpg.Edge.attributes["is_argument_operand"].as_boolean() == True,
            )
            .join(
                PointsTo,
                (
                    (cpg.Edge.source == PointsTo.source)
                    & (PointsTo.kind == EdgeKind.POINTS_TO)
                    & (PointsTo.attributes["context"].as_string() == context)
                ),
            )
            .join(
                MayAlias,
                (PointsTo.target == MayAlias.source)
                & MayAlias.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]),
            )
            .with_entities(MayAlias.target.label("location"))
            .cte("cte", recursive=True)
        )
        recursive_step = (
            session.query(PointsTo)
            .join(
                base_step,
                (PointsTo.source == base_step.c.location) & (PointsTo.kind == EdgeKind.POINTS_TO),
            )
            .join(
                MayAlias,
                (PointsTo.target == MayAlias.source)
                & MayAlias.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]),
            )
            .with_entities(MayAlias.target.label("location"))
        )

        return session.query(base_step.union(recursive_step)).all()


def _find_strings(cpg: db.Graph, session: Session, operand: Node) -> Iterable[bytes]:
    base_step = (
        session.query(cpg.Node)
        .filter(
            cpg.Node.uuid == operand.uuid,
            cpg.Node.kind.in_(
                [NodeKind.CONSTANT_STRING, NodeKind.CONSTANT, NodeKind.GLOBAL_VARIABLE]
            ),
        )
        .with_entities(cpg.Node.uuid.label("uuid"))
        .cte("cte", recursive=True)
    )
    recursive_step = (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE)
        .join(base_step, base_step.c.uuid == cpg.Edge.target)
        .with_entities(cpg.Edge.source.label("uuid"))
    )

    second_base_step = session.query(base_step.union_all(recursive_step)).cte("base")
    second_recursive_step = (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.GLOBAL_TO_INITIALIZER)
        .join(second_base_step, second_base_step.c.uuid == cpg.Edge.source)
        .with_entities(cpg.Edge.target.label("uuid"))
    )

    return [
        n.string_value
        for n in (
            session.query(cpg.ConstantString)
            .filter(cpg.ConstantString.uuid.in_(second_base_step.union_all(second_recursive_step)))
            .all()
        )
    ]


# Match libc format string specifications, using the following reference:
# https://www.gnu.org/software/libc/manual/html_node/Formatted-Output.html
#
#    % [ param-no $] flags width [ . precision ] type conversion
# or
#    % [ param-no $] flags width . * [ param-no $] type conversion
cfmt = b"""\
(                                      # start of capture group 1
%                                      # literal "%"
(?:(?P<paramno>\d+)\$)?                # [ param-no $ ]
(?P<flags>[-+0 #]{0,5})                # flags
(?P<width>\d+|\*)?                     # width
(?P<precision>(?:\.(?P<precisionval>\d+))|(?:\.\*(?P<precisionno>\d+)\$))? # precision
(?P<type>hh|h|j|l|L|ll|q|t|z|Z)?       # type
(?P<conversion>[diouxXfeEgGaAcCsSpnm]) # conversion
)
"""


@dataclass(eq=True, frozen=True)
class ParamNo:
    num: int


@dataclass(eq=True, frozen=True)
class FormatSpecifier:
    param_no: Optional[ParamNo]
    flags: str
    width: Optional[Union[int, Literal["*"]]]
    precision: Optional[Union[int, Literal["*"], ParamNo]]
    type_modifier: Optional[str]
    conversion: str


def _make_param_no(parsed: Optional[bytes]) -> Optional[ParamNo]:
    return ParamNo(int(parsed)) if parsed is not None else None


def _make_width(parsed: Optional[bytes]) -> Optional[Union[int, Literal["*"]]]:
    if parsed is None:
        return None
    elif parsed == b"*":
        return "*"
    else:
        return int(parsed)


def _make_precision(
    full: Optional[bytes], val: Optional[bytes], no: Optional[bytes]
) -> Optional[Union[int, Literal["*"], ParamNo]]:
    logger.debug(f"got precision info {full=} {val=} {no=}")
    if full is None:
        return None
    elif val is not None:
        return int(val)
    elif no is not None:
        return ParamNo(int(no))
    else:
        return "*"


def _make_type(parsed: Optional[bytes]) -> Optional[str]:
    if parsed is not None:
        return str(parsed, "ascii")
    else:
        return None


@lru_cache(maxsize=None)
def _extract_specifiers(format_string: bytes) -> List[FormatSpecifier]:
    return [
        FormatSpecifier(
            _make_param_no(m.group("paramno")),
            str(m.group("flags"), "ascii"),
            _make_width(m.group("width")),
            _make_precision(
                m.group("precision"),
                m.group("precisionval"),
                m.group("precisionno"),
            ),
            _make_type(m.group("type")),
            str(m.group("conversion"), "ascii"),
        )
        for m in re.finditer(cfmt, format_string, flags=re.X)
    ]


@lru_cache(maxsize=None)
def _parse_specifiers(
    specifiers: Tuple[FormatSpecifier], start: int
) -> Tuple[List[int], List[int], List[int]]:
    current_param = start
    read = []
    deref = []
    written = []
    for spec in specifiers:
        # Handle width
        if spec.width == "*":
            read.append(current_param)
            current_param += 1

        # Handle precision
        if spec.precision is not None:
            if spec.precision == "*":
                read.append(current_param)
                current_param += 1
            elif isinstance(spec.precision, ParamNo):
                read.append(spec.precision.num + start)

        # Handle conversion
        if spec.conversion not in ["s", "S", "n", "m"]:
            if spec.param_no:
                read.append(spec.param_no.num + start)
            else:
                read.append(current_param)
                current_param += 1
        elif spec.conversion in ["s", "S"]:
            if spec.param_no:
                deref.append(spec.param_no.num + start)
            else:
                deref.append(current_param)
                current_param += 1
        elif spec.conversion == "n":
            if spec.param_no:
                written.append(spec.param_no.num + start)
            else:
                written.append(current_param)
                current_param += 1
        else:
            # TODO(sm): handle %m (error message)
            pass

    return (read, deref, written)


def _get_specifiers(
    cpg: db.Graph, session: Session, operand: Node, index: int
) -> List[Tuple[bytes, Tuple[List[int], List[int], List[int]]]]:
    return [
        (string, _parse_specifiers(tuple(_extract_specifiers(string)), index))
        for string in _find_strings(cpg, session, operand)
    ]


class FormatStringReadSelector(SignatureSelector):

    argument_types: List[type] = [int]

    def __init__(self, index: int) -> None:
        self.index = index

    def __repr__(self) -> str:
        return f"<FormatStringReadSelector({self.index})>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, context: str
    ) -> Iterable[Tuple[str]]:
        max_operand = (
            session.query(cpg.Edge)
            .filter(
                cpg.Edge.target == callsite.uuid, cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE
            )
            .with_entities(func.max(cpg.Edge.attributes["operand_number"].as_integer()))
            .one()
        )[0]
        format_operand = (
            session.query(cpg.Edge)
            .filter(
                cpg.Edge.target == callsite.uuid,
                cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE,
                cpg.Edge.attributes["operand_number"].as_integer() == self.index,
            )
            .join(cpg.Node, cpg.Edge.source == cpg.Node.uuid)
            .with_entities(cpg.Node)
            .one_or_none()
        )
        found = False
        selectors: List[SignatureSelector] = [ArgPointsToSelector(self.index)]
        for (format_string, (read, deref, _written)) in _get_specifiers(
            cpg, session, format_operand, self.index + 1
        ):
            found = True
            logger.debug(f"Found potential format string {format_string!r}")
            for i in read:
                logger.debug(f"Adding argument selector for operand {i}")
                selectors.append(ArgSelector(i))
            for i in deref:
                logger.debug(f"Adding argument points to selector for operand {i}")
                selectors.append(ArgPointsToSelector(i))
        if found:
            return itertools.chain.from_iterable(
                map(
                    lambda selector: selector._uuids_at_callsite(cpg, session, callsite, context),
                    selectors,
                )
            )
        else:
            logger.debug("Didn't find constant format string, adding conservative signatures")
            return itertools.chain.from_iterable(
                itertools.chain(
                    ArgSelector(i)._uuids_at_callsite(cpg, session, callsite, context),
                    ArgPointsToSelector(i)._uuids_at_callsite(cpg, session, callsite, context),
                )
                for i in range(self.index, max_operand)
            )


class FormatStringWriteSelector(SignatureSelector):

    argument_types: List[type] = [int]

    def __init__(self, index: int) -> None:
        self.index = index

    def __repr__(self) -> str:
        return f"<FormatStringWriteSelector({self.index})>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, callsite: CallSite, context: str
    ) -> Iterable[Tuple[str]]:
        format_operand = (
            session.query(cpg.Edge)
            .filter(
                cpg.Edge.target == callsite.uuid,
                cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE,
                cpg.Edge.attributes["operand_number"].as_integer() == self.index,
            )
            .join(cpg.Node, cpg.Edge.source == cpg.Node.uuid)
            .with_entities(cpg.Node)
            .one_or_none()
        )
        found = False
        selectors = list()
        for (format_string, (_read, _deref, written)) in _get_specifiers(
            cpg, session, format_operand, self.index + 1
        ):
            found = True
            logger.debug(f"Found potential format string {format_string!r}")
            for i in written:
                logger.debug(f"Adding argument points-to selector for operand {i}")
                selectors.append(ArgPointsToSelector(i))
        if found:
            return itertools.chain.from_iterable(
                map(
                    lambda selector: selector._uuids_at_callsite(cpg, session, callsite, context),
                    selectors,
                )
            )
        else:
            return []


class GlobalSelector(SignatureSelector):

    argument_types: List[type] = [str]

    def __init__(self, global_name: str) -> None:
        self.global_name = global_name

    def __repr__(self) -> str:
        return f"<GlobalSelector({self.global_name})>"

    def _uuids_at_callsite(
        self, cpg: db.Graph, session: Session, _callsite: CallSite, _context: str
    ) -> Iterable[Tuple[str]]:
        # TODO: should return points-to locations as well?
        return session.query(cpg.GlobalVariable.uuid).filter_by(name=self.global_name).all()


class Signature(ABC):
    @abstractmethod
    def apply_to_cpg(
        self, build: db.Build, cpg: db.Graph, session: Session, check_duplicates: bool
    ) -> None:
        pass


class InputSignature(Signature):
    def __init__(
        self, function: Pattern, tags: List[str], selectors: List[SignatureSelector]
    ) -> None:
        self.function = function
        self.tags = tags
        self.selectors = selectors

    def __repr__(self) -> str:
        selector_reprs = ", ".join(map(repr, self.selectors))
        return f"<InputSignature({self.function}, tags: {self.tags}, to: [{selector_reprs}])>"

    def _signature_already_exists(
        self,
        callsite: CallSite,
        context: str,
        tags: List[str],
        to_nodes: Set[Tuple[str]],
    ) -> bool:
        """Helper function that reports whether a given signature already exists."""
        for sig in callsite.input_signatures:
            if (
                sig.context == context
                and to_nodes == {(n.uuid,) for n in sig.flows_to}
                and set(tags) == set(sig.tags)
            ):
                logger.debug(f"Signature matches existing signature {sig} for callsite {callsite}")
                return True
        return False

    def apply_to_cpg(
        self, build: db.Build, cpg: db.Graph, session: Session, check_duplicates: bool = True
    ) -> None:
        CallSite = aliased(cpg.CallSite)
        for callsite, context, function in (
            session.query(cpg.Function)
            .filter(cpg.Function.name.re_match(self.function))
            .join(
                cpg.Edge,
                (cpg.Edge.kind == EdgeKind.CALL_TO_FUNCTION)
                & (cpg.Edge.target == cpg.Function.uuid),
            )
            .join(CallSite, cpg.Edge.source == CallSite.uuid)
            .with_entities(
                CallSite, cpg.Edge.attributes["caller_context"].as_string(), cpg.Function
            )
            .yield_per(100)
        ):
            logger.debug(f"Applying signature {self} to {callsite.attributes} in context {context}")
            nodes = set()
            for s in self.selectors:
                nodes.update(set(s._uuids_at_callsite(cpg, session, callsite, context)))

            nulls = {
                n[0]
                for n in (
                    session.query(cpg.MemoryLocation)
                    .filter(
                        cpg.MemoryLocation.attributes["alias_set_identifier"].astext == "*null*"
                    )
                    .with_entities(cpg.MemoryLocation.uuid)
                    .all()
                )
            }
            nodes = nodes - nulls

            logger.debug(f"Found {len(nodes)} 'input' nodes")

            if check_duplicates and self._signature_already_exists(
                callsite, context, self.tags, nodes
            ):
                logger.debug("Signature already exists, continuing...")
                continue

            sig_uuid = f"{callsite.uuid}-input-{uuid.uuid4().hex}"
            session.add(
                cpg.InputSignature(
                    uuid=sig_uuid,
                    kind=NodeKind.INPUT_SIGNATURE,
                    attributes={
                        "tags": self.tags,
                        "context": context,
                    },
                )
            )
            session.add(
                cpg.Edge(
                    uuid=f"{sig_uuid}-for",
                    kind=EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
                    source=sig_uuid,
                    target=callsite.uuid,
                    attributes={"context": context},
                )
            )
            session.add(
                cpg.Edge(
                    uuid=f"{sig_uuid}-for-function",
                    kind=EdgeKind.DATAFLOW_SIGNATURE_FOR_FUNCTION,
                    source=sig_uuid,
                    target=function.uuid,
                    attributes={"context": context},
                )
            )
            for idx, to_uuid in enumerate(nodes):
                session.add(
                    cpg.Edge(
                        uuid=f"{sig_uuid}-{idx}",
                        kind=EdgeKind.DATAFLOW_SIGNATURE,
                        source=sig_uuid,
                        target=to_uuid[0],
                        attributes={"context": context},
                    )
                )


class OutputSignature(Signature):
    def __init__(
        self, function: Pattern, tags: List[str], selectors: List[SignatureSelector]
    ) -> None:
        self.function = function
        self.tags = tags
        self.selectors = selectors

    def __repr__(self) -> str:
        selector_reprs = ", ".join(map(repr, self.selectors))
        return f"<OutputSignature({self.function}, tags: {self.tags}, from: [{selector_reprs}])>"

    def _signature_already_exists(
        self,
        callsite: CallSite,
        context: str,
        tags: List[str],
        from_nodes: Set[Tuple[str]],
    ) -> bool:
        """Helper function that reports whether a given signature already exists."""
        for sig in callsite.output_signatures:
            if (
                sig.context == context
                and from_nodes == {(n.uuid,) for n in sig.flows_from}
                and set(tags) == set(sig.tags)
            ):
                logger.debug(f"Signature matches existing signature {sig} for callsite {callsite}")
                return True
        return False

    def apply_to_cpg(
        self, build: db.Build, cpg: db.Graph, session: Session, check_duplicates: bool = True
    ) -> None:
        CallSite = aliased(cpg.CallSite)
        for callsite, context, function in (
            session.query(cpg.Function)
            .filter(cpg.Function.name.re_match(self.function))
            .join(
                cpg.Edge,
                (cpg.Edge.kind == EdgeKind.CALL_TO_FUNCTION)
                & (cpg.Edge.target == cpg.Function.uuid),
            )
            .join(CallSite, cpg.Edge.source == CallSite.uuid)
            .with_entities(
                CallSite, cpg.Edge.attributes["caller_context"].as_string(), cpg.Function
            )
            .yield_per(100)
        ):
            logger.debug(f"Applying signature {self} to {callsite.attributes} in context {context}")
            nodes: Set[Tuple[str]] = set()
            for s in self.selectors:
                selected = set(s._uuids_at_callsite(cpg, session, callsite, context))
                logger.debug(f"Found {len(selected)} 'output' nodes for selector {s}")
                nodes.update(selected)

            nulls = {
                n[0]
                for n in (
                    session.query(cpg.MemoryLocation)
                    .filter(
                        cpg.MemoryLocation.attributes["alias_set_identifier"].astext == "*null*"
                    )
                    .with_entities(cpg.MemoryLocation.uuid)
                    .all()
                )
            }
            nodes = nodes - nulls

            if check_duplicates and self._signature_already_exists(
                callsite, context, self.tags, nodes
            ):
                logger.debug("Signature already exists, continuing...")
                continue

            sig_uuid = f"{callsite.uuid}-output-{uuid.uuid4().hex}"
            session.add(
                cpg.OutputSignature(
                    uuid=sig_uuid,
                    kind=NodeKind.OUTPUT_SIGNATURE,
                    attributes={
                        "tags": self.tags,
                        "context": context,
                    },
                )
            )
            session.add(
                cpg.Edge(
                    uuid=f"{sig_uuid}-for",
                    kind=EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
                    source=sig_uuid,
                    target=callsite.uuid,
                    attributes={"context": context},
                )
            )
            session.add(
                cpg.Edge(
                    uuid=f"{sig_uuid}-for-function",
                    kind=EdgeKind.DATAFLOW_SIGNATURE_FOR_FUNCTION,
                    source=sig_uuid,
                    target=function.uuid,
                    attributes={"context": context},
                )
            )
            for idx, from_uuid in enumerate(nodes):
                session.add(
                    cpg.Edge(
                        uuid=f"{sig_uuid}-{idx}",
                        kind=EdgeKind.DATAFLOW_SIGNATURE,
                        source=from_uuid[0],
                        target=sig_uuid,
                        attributes={"context": context},
                    )
                )


_DATAFLOW_TYPE_MAP: Final[Dict[str, EdgeKind]] = {
    "direct": EdgeKind.DIRECT_DATAFLOW_SIGNATURE,
    "indirect": EdgeKind.INDIRECT_DATAFLOW_SIGNATURE,
    "control": EdgeKind.CONTROL_DATAFLOW_SIGNATURE,
}

# We often want only the keys, so we set up another variable here for convenience
_DATAFLOW_TYPES = _DATAFLOW_TYPE_MAP.keys()


class DataflowSignature(Signature):
    def __init__(
        self,
        function: Pattern,
        tags: List[str],
        fromSelectors: Dict[str, List[SignatureSelector]],
        toSelectors: List[SignatureSelector],
        deallocator: Optional[str],
    ) -> None:
        self.function = function
        self.tags = tags
        self.fromSelectors = fromSelectors
        self.toSelectors = toSelectors
        self.deallocator = deallocator

    def __repr__(self) -> str:
        from_selector_reprs = repr(self.fromSelectors)
        to_selector_reprs = ", ".join(map(repr, self.toSelectors))
        return f"<DataflowSignature({self.function}, tags: {self.tags}, from: {from_selector_reprs}, to: [{to_selector_reprs}], deallocator: {self.deallocator})>"

    def _signature_already_exists(
        self,
        callsite: CallSite,
        context: str,
        tags: List[str],
        from_nodes: Dict[str, Set[Tuple[str]]],
        to_nodes: Set[Tuple[str]],
    ) -> bool:
        """Helper function that reports whether a given signature already exists."""
        for sig in callsite.dataflow_signatures:
            if (
                sig.context == context
                and (from_nodes["direct"] == {(n.uuid,) for n in sig.directly_flows_from})
                and (from_nodes["indirect"] == {(n.uuid,) for n in sig.indirectly_flows_from})
                and (from_nodes["control"] == {(n.uuid,) for n in sig.control_flows_from})
                and to_nodes == {(n.uuid,) for n in sig.flows_to}
                and set(tags) == set(sig.tags)
            ):
                logger.debug(f"Signature matches existing signature {sig} for callsite {callsite}")
                return True
        return False

    def apply_to_cpg(
        self, build: db.Build, cpg: db.Graph, session: Session, check_duplicates: bool = True
    ) -> None:
        CallSite = aliased(cpg.CallSite)
        for callsite, context, function in (
            session.query(cpg.Function)
            .filter(cpg.Function.name.re_match(self.function))
            .join(
                cpg.Edge,
                (cpg.Edge.kind == EdgeKind.CALL_TO_FUNCTION)
                & (cpg.Edge.target == cpg.Function.uuid),
            )
            .join(CallSite, cpg.Edge.source == CallSite.uuid)
            .with_entities(
                CallSite, cpg.Edge.attributes["caller_context"].as_string(), cpg.Function
            )
            .yield_per(100)
        ):
            logger.debug(f"Applying signature {self} to {callsite.attributes} in context {context}")

            nulls = {
                n[0]
                for n in (
                    session.query(cpg.MemoryLocation)
                    .filter(
                        cpg.MemoryLocation.attributes["alias_set_identifier"].astext == "*null*"
                    )
                    .with_entities(cpg.MemoryLocation.uuid)
                    .all()
                )
            }

            # from_nodes looks like {'direct': {('515',), ('511',)}, ...}
            from_nodes: Dict[str, Set[Tuple[str]]] = dict()
            for df_type, selectors in self.fromSelectors.items():
                from_nodes[df_type] = set()
                for s in selectors:
                    from_nodes[df_type].update(
                        set(s._uuids_at_callsite(cpg, session, callsite, context)) - nulls
                    )

            to_nodes: Set[Tuple[str]] = set()
            for s in self.toSelectors:
                to_nodes.update(set(s._uuids_at_callsite(cpg, session, callsite, context)) - nulls)

            logger.debug(f"Found {len(from_nodes)} 'from' nodes")
            logger.debug(f"Found {len(to_nodes)} 'to' nodes")

            if check_duplicates and self._signature_already_exists(
                callsite, context, self.tags, from_nodes, to_nodes
            ):
                logger.debug("Signature already exists, continuing...")
                continue

            sig_uuid = f"{callsite.uuid}-dataflow-{uuid.uuid4().hex}"
            session.add(
                cpg.DataflowSignature(
                    uuid=sig_uuid,
                    kind=NodeKind.DATAFLOW_SIGNATURE,
                    attributes={
                        "tags": self.tags,
                        "context": context,
                        "deallocator": self.deallocator,
                    },
                )
            )
            session.add(
                cpg.Edge(
                    uuid=f"{sig_uuid}-for",
                    kind=EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
                    source=sig_uuid,
                    target=callsite.uuid,
                    attributes={"context": context},
                )
            )
            session.add(
                cpg.Edge(
                    uuid=f"{sig_uuid}-for-function",
                    kind=EdgeKind.DATAFLOW_SIGNATURE_FOR_FUNCTION,
                    source=sig_uuid,
                    target=function.uuid,
                    attributes={"context": context},
                )
            )
            for df_type, from_uuid_sets in from_nodes.items():
                for idx, from_uuid in enumerate(from_uuid_sets):
                    session.add(
                        cpg.Edge(
                            uuid=f"{sig_uuid}-from-{df_type}-{idx}",
                            kind=_DATAFLOW_TYPE_MAP[df_type],
                            source=from_uuid[0],
                            target=sig_uuid,
                            attributes={"context": context},
                        )
                    )
            for idx, to_uuid in enumerate(to_nodes):
                session.add(
                    cpg.Edge(
                        uuid=f"{sig_uuid}-to-{idx}",
                        kind=EdgeKind.DATAFLOW_SIGNATURE,
                        source=sig_uuid,
                        target=to_uuid[0],
                        attributes={"context": context},
                    )
                )


_SELECTOR_MAP: Final[Dict[str, Type[SignatureSelector]]] = {
    "return": ReturnSelector,
    "return_points_to": ReturnPointsToSelector,
    "return_points_to_aggregate": ReturnPointsToAggregateSelector,
    "return_reachable": ReturnReachableSelector,
    "arg": ArgSelector,
    "arg_points_to": ArgPointsToSelector,
    "arg_points_to_aggregate": ArgPointsToAggregateSelector,
    "arg_reachable": ArgReachableSelector,
    "global": GlobalSelector,
    "format_string_reads": FormatStringReadSelector,
    "format_string_writes": FormatStringWriteSelector,
}
_OUTPUT_SIGNATURE_KEYS = {"tags", "from"}
_INPUT_SIGNATURE_KEYS = {"tags", "to"}
_DATAFLOW_SIGNATURE_KEYS = {"to", "from", "tags", "deallocator"}


def parse_dataflow_type(dataflow_spec: Dict[str, Any]) -> Dict[str, List[SignatureSelector]]:
    """Extracts the dataflow type and its consituent selectors.

    The return value is a dictionary with one key for each value in _DATAFLOW_TYPES, whose value is
    a list of signature selectors corresponding to that dataflow type.
    """
    if type(dataflow_spec) is not dict:
        raise InvalidSignature(f"Invalid dataflow specification: {dataflow_spec}")

    if not all([x in _DATAFLOW_TYPES for x in dataflow_spec.keys()]):
        raise InvalidSignature(
            f"Unknown dataflow type: {dataflow_spec}. Known types are: {_DATAFLOW_TYPES}."
        )

    # default each dataflow type to be an empty list
    parsed_dataflow_types: Dict[str, List[SignatureSelector]] = {key: [] for key in _DATAFLOW_TYPES}

    for dataflow_type in _DATAFLOW_TYPES:
        if dataflow_spec.get(dataflow_type):
            parsed_dataflow_types[dataflow_type] = list(
                map(parse_selector, dataflow_spec[dataflow_type])
            )

    return parsed_dataflow_types


def parse_selector(selector: Dict[str, Any]) -> SignatureSelector:
    if (type(selector) is not dict) or (len(selector.keys()) != 1):
        raise InvalidSignature(f"Invalid selector: {selector}")

    name = next(iter(selector.keys()))
    selector_class = _SELECTOR_MAP.get(name)

    if selector_class is None:
        raise InvalidSignature(f"Unknown selector {name}")
    else:
        return selector_class.parse_arguments(selector[name])


def parse_input_signature(function: Pattern, sigcontent: Dict) -> InputSignature:
    if type(sigcontent) is not dict:
        raise InvalidSignature(f"Invalid input signature: {sigcontent}")

    if not set(sigcontent.keys()).issubset(_INPUT_SIGNATURE_KEYS) or "to" not in sigcontent:
        raise InvalidSignature(f"Invalid input signature: {sigcontent}")

    tags = sigcontent.get("tags", [])
    if type(tags) is not list or not all(map(lambda e: type(e) is str, tags)):
        raise InvalidSignature(f"Invalid input signature: {sigcontent})")

    try:
        selectors = list(map(parse_selector, sigcontent["to"]))
    except InvalidSignature as e:
        raise InvalidSignature(f"Invalid input signature: {sigcontent}: {e.message}")

    return InputSignature(function, tags, selectors)


def parse_output_signature(function: Pattern, sigcontent: Dict) -> OutputSignature:
    if type(sigcontent) is not dict:
        raise InvalidSignature("Invalid output signature: {sigcontent}")

    if not set(sigcontent.keys()).issubset(_OUTPUT_SIGNATURE_KEYS) or "from" not in sigcontent:
        raise InvalidSignature(f"Invalid output signature: {sigcontent}")

    tags = sigcontent.get("tags", [])
    if type(tags) is not list or not all(map(lambda e: type(e) is str, tags)):
        raise InvalidSignature(f"Invalid output signature: {sigcontent})")

    try:
        selectors = list(map(parse_selector, sigcontent["from"]))
    except InvalidSignature as e:
        raise InvalidSignature(f"Invalid output signature: {sigcontent}: {e.message}")

    return OutputSignature(function, tags, selectors)


def parse_dataflow_signature(function: Pattern, sigcontent: Dict) -> DataflowSignature:
    if type(sigcontent) is not dict:
        raise InvalidSignature(f"Invalid dataflow signature: {sigcontent}")

    if not set(sigcontent.keys()).issubset(_DATAFLOW_SIGNATURE_KEYS):
        raise InvalidSignature(f"Invalid dataflow signature: {sigcontent}")

    tags = sigcontent.get("tags", [])
    if type(tags) is not list or not all(map(lambda e: type(e) is str, tags)):
        raise InvalidSignature(f"Invalid dataflow signature: {sigcontent})")

    if not {"to", "from"}.issubset(set(sigcontent.keys())):
        raise InvalidSignature(f"Invalid dataflow signature: {sigcontent}")

    try:
        from_selectors = parse_dataflow_type(sigcontent["from"])
    except InvalidSignature as e:
        raise InvalidSignature(
            f"Invalid dataflow signature ('from' selector): {sigcontent}: {e.message}"
        )

    try:
        to_selectors = list(map(parse_selector, sigcontent["to"]))
    except InvalidSignature as e:
        raise InvalidSignature(
            f"Invalid dataflow signature ('to' selector): {sigcontent}: {e.message}"
        )

    deallocator = sigcontent.get("deallocator")

    return DataflowSignature(function, tags, from_selectors, to_selectors, deallocator)


def parse_cpg_signature(function: Pattern, signame: str, sigcontent: Dict) -> Signature:
    if signame == "input":
        return parse_input_signature(function, sigcontent)
    elif signame == "output":
        return parse_output_signature(function, sigcontent)
    elif signame == "dataflow":
        return parse_dataflow_signature(function, sigcontent)
    else:
        raise UnknownSignature(f"Unknown signature {signame} for {function}")


def load_signatures(raw_sigs: Dict[str, List[Any]]) -> List[Signature]:
    logger.info(f"Processing points-to signatures")

    cpg_signatures = []
    for function, signatures in raw_sigs.items():
        for sig in signatures:
            if (type(sig) is not dict) or (len(sig.keys()) != 1):
                raise InvalidSignature(f"Invalid signature for {function}: {raw_sigs[function]}")

            for signame in sig:
                if signame.startswith("pts_"):
                    continue
                newsig = parse_cpg_signature(re.compile(function), signame, sig[signame])
                cpg_signatures.append(newsig)

                logger.debug(f"Loaded signature {newsig}")

    return cpg_signatures


def process_cpg_signatures(
    signatures: List[Signature],
    build: db.Build,
    cpg: db.Graph,
    session: Session,
    check_duplicates: bool,
) -> None:
    logger.info(f"Connecting to CPG {cpg.name} to insert signatures")
    for sig in signatures:
        sig.apply_to_cpg(build, cpg, session, check_duplicates)
    session.commit()
    logger.info("Finished applying signatures")
