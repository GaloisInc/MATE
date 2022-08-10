from __future__ import annotations

import logging
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterator, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import aliased

import mate_query.db as db
from mate.poi.poi_types import Analysis, POIGraphsPair
from mate_common.models.analyses import POI
from mate_common.models.cpg_types.mate import EdgeKind
from mate_common.models.graphs import GraphKind, NodeRequest, SliceRequest
from mate_query.db import Session

if TYPE_CHECKING:
    from mate_query.cpg.models.core import Node
    from mate_query.db import Graph as CPG


logger = logging.getLogger(__name__)


class IteratorInvalidationsPOI(POI):
    iterator_ctor: str
    invalidation_op: str
    usage_op: str


class IteratorInvalidations(Analysis):
    _background: str = dedent(
        """
        The C++ standard library supports a number of containers (`vector`, `set`, `map`, etc). Each
        container type has a corresponding iterator type that is designed to allow users to iterate across
        and access its elements.

        There are some rules around iterator usage. Some container methods cause "iterator invalidation",
        meaning that any iterators that were retrieved from the container before the call can only be safely
        destructed and are otherwise unsafe to use. For example, the following iterator usage invokes
        undefined behaviour:

        ```c++
        std::vector<int> vec = populate_vec();
        auto iter = vec.begin();
        vec.push_back(1); // invalidates `iter`
        std::cout << *iter; // accesses invalid iterator, UB
        ```

        MATE finds execution paths where invalid iterators are accessed. It does this by looking for
        container methods such as `begin` that return iterators into a given container. It then looks for
        invalidating methods on the container found in the previous step. Finally, it checks whether the
        iterator from the first step is accessed with `operator*` or `operator->`. If this is the case, MATE
        will flag the code as a point of interest. The initial graph loaded for this point of interest
        shows:

        * The call to the container method that constructed the iterator (e.g. `begin`)
        * The call to the container method that invalidated the iterator (e.g. `push_back`)
        * The usage of the invalid iterator
        """
    )

    def run(self, session: Session, graph: CPG, _inputs: Dict[str, Any]) -> Iterator[POIGraphsPair]:
        logger.debug("Running iterator invalidation analysis...")

        for iterator_ctor, invalidation_op, usage_op in compute_iterator_invalidations(
            session, graph
        ):
            ctor_location = iterator_ctor.location_string
            invalidation_location = invalidation_op.location_string
            usage_location = usage_op.location_string

            poi = IteratorInvalidationsPOI(
                insight=(
                    f"Iterator constructed with a call at `{ctor_location}` was subsequently "
                    f"invalidated with a call to `{invalidation_op.callees[0].demangled_name}` at "
                    f"`{invalidation_location}`, which was subsequently used at `{usage_location}`."
                ),
                iterator_ctor=iterator_ctor.uuid,
                invalidation_op=invalidation_op.uuid,
                usage_op=usage_op.uuid,
                source=invalidation_location,
                sink=usage_location,
                salient_functions=list(
                    {
                        iterator_ctor.parent_block.parent_function.as_salient(),
                        invalidation_op.parent_block.parent_function.as_salient(),
                        usage_op.parent_block.parent_function.as_salient(),
                    }
                ),
            )

            yield (
                poi,
                [
                    SliceRequest(
                        build_id=graph.build,
                        source_id=iterator_ctor.uuid,
                        sink_id=invalidation_op.uuid,
                        kind=GraphKind.ForwardDataflow,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    ),
                    SliceRequest(
                        build_id=graph.build,
                        source_id=invalidation_op.uuid,
                        sink_id=usage_op.uuid,
                        kind=GraphKind.ForwardDataflow,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=iterator_ctor.uuid,
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=invalidation_op.uuid,
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=usage_op.uuid,
                    ),
                ],
            )


def compute_iterator_invalidations(
    session: Session, cpg: db.Graph
) -> Iterator[Tuple[Node, Node, Node]]:
    # The check works as follows:
    # 1) Look for calls where we retrieve an iterator from a `std::vector<T>`
    # 2) Look for calls to iterator-invalidating methods on the vector in 1
    # 3) Look for a value-using edge for the iterator returned by 1
    # 4) Find a code path that goes 1 => 2 => 3

    # There are more complicated ways to get an iterator that we'll need to eventually support. Off
    # the top of my head:
    #
    # 1) Using an STL algorithm like `std::find`
    # 2) Copying constructing from an existing iterator
    #
    # Figuring out the container that the iterators originate from could be a challenge.

    # 1) Look for methods that return an iterator. While we're here, we should keep track of the
    #    vector it came from
    IteratorCtor = aliased(cpg.CallSite)

    iterator_ctors = (
        session.query(cpg.Function)
        .filter(
            or_(
                cpg.Function.demangled_name.like("std::vector<%>::begin()"),
                cpg.Function.demangled_name.like("std::vector<%>::rbegin()"),
                cpg.Function.demangled_name.like("std::vector<%>::cbegin() const"),
                cpg.Function.demangled_name.like("std::vector<%>::crbegin() const"),
                cpg.Function.demangled_name.like("std::vector<%>::end()"),
                cpg.Function.demangled_name.like("std::vector<%>::rend()"),
                cpg.Function.demangled_name.like("std::vector<%>::cend() const"),
                cpg.Function.demangled_name.like("std::vector<%>::crend() const"),
            )
        )
        .join(IteratorCtor, cpg.Function.callsites)
        .with_entities(IteratorCtor)
        .all()
    )

    # 2) Find method calls on the original vector that invalidate the iterator we recorded in step 1
    InvalidationCall = aliased(cpg.CallSite)
    invalidation_ops = (
        session.query(cpg.Function)
        .filter(
            or_(
                cpg.Function.demangled_name.like("std::vector<%>::assign(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::push_back(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::pop_back(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::insert(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::erase(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::swap(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::clear(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::emplace(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::emplace_back(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::resize(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::operator=(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::swap(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::reserve(%)"),
                cpg.Function.demangled_name.like("std::vector<%>::shrink_to_fit(%)"),
            )
        )
        .join(InvalidationCall, cpg.Function.callsites)
        .with_entities(InvalidationCall)
        .distinct()
        .all()
    )

    # 3) Find usages of the iterator we found above
    UsageCall = aliased(cpg.CallSite)
    usage_ops = (
        session.query(cpg.Function)
        .filter(
            or_(
                cpg.Function.demangled_name.like(
                    "__gnu_cxx::__normal_iterator<%*, std::vector<%, std::allocator<%> > >::operator*() const"
                ),
                cpg.Function.demangled_name.like(
                    "__gnu_cxx::__normal_iterator<%*, std::vector<%, std::allocator<%> > >::operator->() const"
                ),
            )
        )
        .join(UsageCall, cpg.Function.callsites)
        .with_entities(UsageCall)
        .all()
    )

    iterator_uuids = [n.uuid for n in iterator_ctors]

    # 4) Find dataflows that connect the 3 steps above
    #
    # Create mapping from invalidation callsites to iterator constructor calls
    ctor_invalidation_cf = (
        db.PathBuilder(db.Path)
        .starting_at(lambda Node: Node.uuid.in_(iterator_uuids))
        .continuing_while(
            lambda _, Edge: Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
        )
        .stopping_at(lambda Node: Node.uuid.in_([n.uuid for n in invalidation_ops]))
        .build(cpg)
    )
    invalidation_usage_cf = (
        db.PathBuilder(db.Path)
        .starting_at(lambda Node: Node.uuid.in_([n.uuid for n in invalidation_ops]))
        .continuing_while(
            lambda _, Edge: (Edge.source.notin_(iterator_uuids))
            & (Edge.target.notin_(iterator_uuids))
            & (Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION)
        )
        .stopping_at(lambda Node: Node.uuid.in_([n.uuid for n in usage_ops]))
        .build(cpg)
    )

    with db.join_collapse_limit(session):
        InvalidationArg = aliased(cpg.Node)
        InvalidationMemoryLoc = aliased(cpg.Node)
        IteratorArg = aliased(cpg.Node)
        IteratorMemoryLoc = aliased(cpg.MemoryLocation)
        IteratorStore = aliased(cpg.Store)
        IteratorVecMemoryLoc = aliased(cpg.Node)
        UsageArg = aliased(cpg.Node)
        UsageArgPointer = aliased(cpg.Node)
        for (ctor, invalidation_op, usage) in (
            session.query(ctor_invalidation_cf)
            .join(IteratorCtor, IteratorCtor.uuid == ctor_invalidation_cf.source)
            .join(InvalidationCall, InvalidationCall.uuid == ctor_invalidation_cf.target)
            .join(IteratorArg, IteratorCtor.argument0)
            .join(InvalidationArg, InvalidationCall.argument0)
            .join(IteratorVecMemoryLoc, IteratorArg.points_to)
            .join(InvalidationMemoryLoc, InvalidationArg.points_to)
            .filter(IteratorVecMemoryLoc.uuid == InvalidationMemoryLoc.uuid)
            .join(
                invalidation_usage_cf, ctor_invalidation_cf.target == invalidation_usage_cf.source
            )
            .filter(InvalidationCall.uuid == invalidation_usage_cf.source)
            .join(UsageCall, UsageCall.uuid == invalidation_usage_cf.target)
            .join(UsageArg, UsageCall.argument0)
            .join(IteratorStore, IteratorCtor.used_by)
            .join(IteratorMemoryLoc, IteratorStore.stores_to)
            .join(UsageArgPointer, UsageArg.points_to)
            .filter(UsageArgPointer.uuid == IteratorMemoryLoc.uuid)
            .with_entities(IteratorCtor, InvalidationCall, UsageCall)
            .all()
        ):
            yield (ctor, invalidation_op, usage)
