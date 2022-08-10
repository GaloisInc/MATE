"""See documentation on ``CFLPath``"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import case, exists, func, insert, join, literal, select, true, union
from sqlalchemy.types import Boolean, String

from mate_common.models.cpg_types.llvm import Opcode
from mate_common.models.cpg_types.mate import EdgeKind, NodeKind
from mate_query.db import (
    BOT,
    AdvisoryLockBuildTransaction,
    Path,
    _make_edge_symbol_table,
    _make_transition_table,
    set_n_distinct,
)

if TYPE_CHECKING:
    from typing import ClassVar, Type

    from sqlalchemy.sql.expression import ClauseElement, Select

    from mate_query.db import Graph as CPG


logger = logging.getLogger(__name__)


class CFLPath(ABC, Path):
    """A Context-Free-Language path query.

    CFL queries find paths in the CPG such that concatenation of all the
    symbols/labels of the edges of the path form a word in some context-free
    language. Incremental detection of CFL-paths is done by a push-down
    automaton (PDA) encoded as a recursive SQL query.

    These 'queries' actually consist of a few distinct database operations:

    1. ``populate_edge_symbol_table`` constructs a table of symbols for (a relevant subset of) CPG edges. The mapping from edges to symbols is surjective and functional.
    2. ``populate_transition_table`` constructs a table of transitions for this PDA, where a transition consists of a functional mapping from a (source state, source stack, input symbol) tuple to a (new state, new stack) tuple.
    3. The recursive query that finds CFL-paths is defined in ``db.PathBuilder.build``.
    """

    cfl: ClassVar[bool] = True

    @classmethod
    @abstractmethod
    def table_name_prefix(cls) -> str:
        """Returns a table prefix to be used when creating edge symbol and transition tables.

        If multiple instantiations of a ``Path`` class return the same prefix, the resulting tables
        will be shared between instances, reducing the amount of pre-computation required.

        If different instances require distinct tables, ``table_name_prefix`` should return
        distinct prefixes.

        The name will be converted to lower case and truncated to 16 characters.
        """
        pass

    @classmethod
    def edge_symbol_table_name(cls, graph: CPG) -> str:
        # NB: Maximum length for SQL table name is apparently 63 chars, which
        # is why we truncate.
        return cls.table_name_prefix().lower()[:16] + "_" + graph.build

    @classmethod
    def transition_symbol_table_name(cls, graph: CPG) -> str:
        # NB: Maximum length for SQL table name is apparently 63 chars, which
        # is why we truncate.
        return (
            cls.table_name_prefix().lower()[:16]
            + ("_rev" if cls.is_reversed else "")
            + "_"
            + graph.build
        )

    @classmethod
    def _create_edge_symbol_table(cls, graph: CPG) -> bool:
        """This table only needs to be created once per CPG. Because it is not possible to
        atomically create the table from the selection (since ``CREATE IF NOT EXISTS ... AS ...`` is
        not atomic), this method requests a Postgres transaction-level advisory lock.

        If the table already exists, this method releases the lock immediately and returns
        ``False``. If this method creates the table for the first time, the lock is held until the
        next commit or rollback, and this method returns ``True``.
        """
        graph.session.execute(AdvisoryLockBuildTransaction(graph.build))
        cls.edge_symbol_table = _make_edge_symbol_table(
            cls.edge_symbol_table_name(graph), graph.BaseEdge.__table__
        )
        cls.edge_symbol_table.create(bind=graph.session.bind, checkfirst=True)
        if graph.session.query(cls.edge_symbol_table).first() is not None:
            graph.session.commit()  # free the lock
            return False
        return True

    @classmethod
    def _create_transition_table(cls, graph: CPG) -> bool:
        """This table only needs to be created once per CPG. Because it is not possible to
        atomically create the table from the selection (since ``CREATE IF NOT EXISTS ... AS ...`` is
        not atomic), this method requests a Postgres transaction-level advisory lock.

        If the table already exists, this method releases the lock immediately and returns
        ``False``. If this method creates the table for the first time, the lock is held until the
        next commit or rollback, and this method returns ``True``.
        """
        graph.session.execute(AdvisoryLockBuildTransaction(graph.build))
        cls.transition_table = _make_transition_table(cls.transition_symbol_table_name(graph))
        cls.transition_table.create(bind=graph.session.bind, checkfirst=True)
        if graph.session.query(cls.transition_table).first() is not None:
            graph.session.commit()  # free the lock
            return False
        return True

    @classmethod
    @abstractmethod
    def populate_transition_table(cls, graph: CPG) -> None:
        pass

    @classmethod
    @abstractmethod
    def populate_edge_symbol_table(cls, graph: CPG) -> None:
        pass

    @classmethod
    def update_transition_table_statistics(cls, graph: CPG) -> None:
        # Manually override postgres' n_distinct statistics for the transition table.
        #
        # We do this to avoid poor query planning during recursive CFL exploration by
        # providing better estimates for the three-way join:
        #              exploration <-> edge symbol <-> transition table
        # with the join conditions:
        #    base_select.c.target       == edge_symbol.table.c.source (or vice versa in reverse)
        #    base_select.c.state        == transition_table.c.old_state
        #    base_select.c.stack_top    == transition_table.c.old_stack
        #    edge_symbol_table.c.symbol == transition_table.c.input
        #
        # Because the base_select part of this join is materialized during the query,
        # the planner cannot use multi-variable statistics about the correlations between the
        # tables and falls back on estimating selectivity as the product of 1/n_distinct for
        # each referenced column. This is consistently a large underestimate, partially because
        # of the correlated values of old_stack and input in the transition table. This results
        # in very low selectivity estimates and poor plans.
        #
        # To approximate the multi-variable statistics, we will manually set n_distinct for
        # each of input, old_state, and old_stack such that their product is the number of
        # distinct entries in the table. In general, n_distinct(old_state) is very small and the
        # inaccuracy is due to the correlation of input and old_stack, so we will leave old_state
        # unchanged but set n_distinct(input) and n_distinct(old_stack) to
        # sqrt(n_distinct(entries) / n_distinct(old_state)).
        tablename = cls.transition_table.name  # type: ignore[union-attr]
        (entries, states) = graph.session.execute(
            f"SELECT COUNT(DISTINCT (input,old_stack,old_state)),"
            f"       COUNT(DISTINCT (old_state)) FROM {tablename}"
        ).fetchone()
        n_distinct = math.ceil(math.sqrt(entries / states))

        logger.debug(f"Updating statistics for {tablename}")
        logger.debug(f"{entries} distinct (input, old_stack, old_state) triples")
        logger.debug(f"{states} distinct (old_state) values")

        logger.debug(f"Setting (input, old_stack) n_distinct each to {n_distinct}")
        set_n_distinct(
            graph.session,
            tablename,
            set(["old_stack", "input"]),
            n_distinct,
        )

        logger.debug(f"Setting (old_state) n_distinct each to {states}")
        set_n_distinct(
            graph.session,
            tablename,
            set(["old_state"]),
            states,
        )

    @classmethod
    def update_edge_symbol_table_statistics(cls, graph: CPG) -> None:
        # Manually override postgres' n_distinct statistics for the edge_symbol_table
        #
        # We do this to avoid poor query planning during recursive CFL exploration by
        # providing better estimates for the three-way join:
        #              exploration <-> edge symbol <-> transition table
        # with the join conditions:
        #    base_select.c.target       == edge_symbol.table.c.source (or vice versa in reverse)
        #    base_select.c.state        == transition_table.c.old_state
        #    base_select.c.stack_top    == transition_table.c.old_stack
        #    edge_symbol_table.c.symbol == transition_table.c.input
        #
        # Because the base_select part of this join is materialized during the query,
        # the planner cannot use multi-variable statistics about the correlations between the
        # tables and falls back on estimating selectivity as the product of 1/n_distinct for
        # each referenced column. This is consistently a large underestimate, partially because
        # of the correlated values of old_stack and input in the transition table. This results
        # in very low selectivity estimates and poor plans.
        #
        # To approximate the multi-variable statistics, we will manually set n_distinct for
        # each of source, target, and symbol such that the product of n_distinct(symbol) and
        # either n_distinct(source) or n_distinct(target) is approximately the number of
        # distinct entries in the table.
        #
        # Because we expect a relatively small number of symbols per source / target and
        # want source and target to appear more selective to encourage joins on these first,
        # we will set n_distinct(source) and n_distinct(target) to their actual values but
        # set n_distinct(symbol) to n_distinct(entries) / max(n_distinct(source),n_distinct(target)).
        tablename = cls.edge_symbol_table.name  # type: ignore[union-attr]
        (entries, sources, targets, symbols) = graph.session.execute(
            f"SELECT COUNT(DISTINCT (source,target,symbol)),"
            f"       COUNT(DISTINCT (source)),"
            f"       COUNT(DISTINCT (target)),"
            f"       COUNT(DISTINCT (symbol)) FROM {tablename}"
        ).fetchone()

        new_symbols = math.ceil(entries / max(sources, targets))

        logger.debug(f"Updating statistics for {tablename}")
        logger.debug(f"{entries} distinct (source,target,symbol) triples")
        logger.debug(f"{sources} distinct (source) values")
        logger.debug(f"{targets} distinct (target) values")
        logger.debug(f"{symbols} distinct (symbol) values")

        logger.debug(f"Setting (source) n_distinct to {sources}")
        set_n_distinct(
            graph.session,
            tablename,
            set(["source"]),
            sources,
        )

        logger.debug(f"Setting (target) n_distinct to {targets}")
        set_n_distinct(
            graph.session,
            tablename,
            set(["target"]),
            targets,
        )

        logger.debug(f"Setting (symbol) n_distinct to {new_symbols}")
        set_n_distinct(
            graph.session,
            tablename,
            set(["symbol"]),
            new_symbols,
        )


def ConfigureCFGPath(*, allow_unmatched_returns: bool = False) -> Type[Path]:
    class CFGPath(CFLPath):
        """Inter-procedural control-flow graph (CFG) paths.

        The PDA encoded by this class has:

        * States:
            * ``INTRA``: The next step should follow intra-procedural control
              flow
            * ``INTER``: The next step should follow inter-procedural control
              flow

        * Edge symbols (variables appear ``<in angle brackets>``, tokens are
          separated by spaces for clarity):

            * Symbol:
              * ``step_instruction``
              * Edge kinds: ``EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION``
              * Condition: The target node is an instruction which is not a
                ``call``, ``invoke`` or ``ret``, **or** it is a ``call`` or
                invoke to a externally defined function (i.e., an LLVM
                declaration).

            * Symbol:
                * ``step_instruction_stop``
                * Edge kinds: ``EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION``
                * Condition: The target node is a ``call``, ``invoke`` or
                  ``ret`` instruction to a defined function.

            * Symbol:
                * ``call : <call instruction>``
                * Edge kinds: ``EdgeKind.CALL_TO_FUNCTION``
                * Condition: None

            * Symbol:
                * ``entry_block``
                * Edge kinds: ``EdgeKind.FUNCTION_TO_ENTRY_BLOCK``o
                * Condition: None

            * Symbol:
                * ``entry_instruction``
                * Edge kinds: ``EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION``
                * Condition: None

            * Symbol:
                * ``return_instruction``
                * Edge kinds: ``EdgeKind.RETURN_INSTRUCTION_TO_CALL_RETURN``
                * Condition: None

            * Symbol:
                * ``return : <instruction>``
                * Edge kinds: ``EdgeKind.CALL_RETURN_TO_CALLER``
                * Condition: None

        * Transitions (variables appear ``<in angle brackets>``, ``push`` is
          the cons constructor for the stack type, ``bot`` is the bottom of the stack):
            * Transition:
                * Input state: ``INTRA``
                * Input stack: ``<s>``
                * Edge symbol: ``step_instruction``
                * New state: ``INTRA``
                * New stack: ``<s>``

            * Transition:
                * Input state: ``INTRA``
                * Input stack: ``<s>``
                * Edge symbol: ``step_instruction_stop``
                * New state: ``INTER``
                * New stack: ``<s>``

            * Transition:
                * Input state: ``INTER``
                * Input stack: ``<s>``
                * Edge symbol: ``call : <call instruction>``
                * New state: ``INTRA``
                * New stack: ``push(<call instruction>, <s>)``

            * Transition:
                * Input state: ``INTRA``
                * Input stack: ``<s>``
                * Edge symbol: ``entry_block``
                * New state: ``INTRA``
                * New stack: ``<s>``

            * Transition:
                * Input state: ``INTRA``
                * Input stack: ``<s>``
                * Edge symbol: ``entry_instruction``
                * New state: ``INTRA``
                * New stack: ``<s>``

            * Transition:
                * Input state: ``INTER``
                * Input stack: ``<s>``
                * Edge symbol: ``return_instruction``
                * New state: ``INTRA``
                * New stack: ``<s>``

            * Transition:
                * Input state: ``INTRA``
                * Input stack: ``push(<call instruction>, <s>)``
                * Edge symbol: ``return : <call instruction>``
                * New state: ``INTRA``
                * New stack: ``<s>``

            * Transition (only enabled if ``allow_unmatched_returns`` is ``True``):
                * Input state: ``INTRA``
                * Input stack: ``push(<s>)``
                * Edge symbol: ``return : <call instruction>``
                * New state: ``INTRA``
                * New stack: ``push(bot, <s>)``
        """

        @classmethod
        def table_name_prefix(cls) -> str:
            # The tables can be re-used as long as we're not stepping over any functions, but
            # the tables are different depending on whether unmatched returns are allowed.
            if not cls.stepped_over_functions:
                return "cfg_unmatched" if allow_unmatched_returns else "cfg"
            else:
                # Use the randomly generated Path name
                return cls.__name__

        @classmethod
        def initial_state(cls) -> ClauseElement:
            return literal("INTRA").cast(String)

        @classmethod
        def initial_stack(cls) -> ClauseElement:
            return array([BOT]).cast(ARRAY(String))

        @classmethod
        def populate_edge_symbol_table(cls, graph: CPG) -> None:
            """Preprocess the graph's edge table and give each edge a symbol to be used during
            during CFL-based path extension."""
            if not cls._create_edge_symbol_table(graph):
                return

            current_edge = graph.Edge
            current_node = aliased(graph.Node)
            outgoing_edge = aliased(graph.Edge)
            outgoing_node = aliased(graph.Node)

            # NOTE(lb): Any update to this query should be reflected in the
            # class docstring.
            edge_symbol_query = (
                select(
                    [
                        current_edge.uuid,
                        current_edge.source,
                        current_edge.target,
                        case(
                            [
                                (
                                    (
                                        current_edge.kind
                                        == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
                                    )
                                    & (
                                        ~(
                                            current_node.attributes["opcode"].astext.in_(
                                                [
                                                    Opcode.CALL.value,
                                                    Opcode.INVOKE.value,
                                                    Opcode.RET.value,
                                                ]
                                            )
                                        )
                                        | exists(
                                            select([outgoing_node]).select_from(
                                                join(
                                                    outgoing_edge,
                                                    outgoing_node,
                                                    (
                                                        (current_node.uuid == outgoing_edge.source)
                                                        & (
                                                            outgoing_edge.target
                                                            == outgoing_node.uuid
                                                        )
                                                        & (
                                                            outgoing_edge.kind
                                                            == EdgeKind.CALL_TO_FUNCTION
                                                        )
                                                        & (
                                                            # Step over (i.e. do not step into) any function which is
                                                            # just a declaration, or any function that has been
                                                            # explicitly marked as to be stepped over. Since this is a
                                                            # CASE statement with first-match-wins, these do not need to
                                                            # be excluded in the next case (step_instruction_stop).
                                                            (
                                                                outgoing_node.attributes[
                                                                    "is_declaration"
                                                                ].cast(Boolean)
                                                            )
                                                            | (
                                                                outgoing_node.attributes[
                                                                    "name"
                                                                ].astext.in_(
                                                                    cls.stepped_over_functions
                                                                )
                                                            )
                                                        )
                                                    ),
                                                )
                                            )
                                        )
                                    ),
                                    literal("step_instruction"),
                                ),
                                (
                                    (
                                        current_edge.kind
                                        == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
                                    )
                                    & (
                                        (
                                            current_node.attributes["opcode"].astext.in_(
                                                [
                                                    Opcode.CALL.value,
                                                    Opcode.INVOKE.value,
                                                    Opcode.RET.value,
                                                ]
                                            )
                                        )
                                    ),
                                    literal("step_instruction_stop"),
                                ),
                                (
                                    (current_edge.kind == EdgeKind.CALL_TO_FUNCTION),
                                    func.concat(
                                        literal("call"),
                                        ":",
                                        current_edge.source,
                                    ),
                                ),
                                (
                                    (current_edge.kind == EdgeKind.FUNCTION_TO_ENTRY_BLOCK),
                                    literal("entry_block"),
                                ),
                                (
                                    (current_edge.kind == EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION),
                                    literal("entry_instruction"),
                                ),
                                (
                                    (
                                        current_edge.kind
                                        == EdgeKind.RETURN_INSTRUCTION_TO_CALL_RETURN
                                    ),
                                    literal("return_instruction"),
                                ),
                                (
                                    (current_edge.kind == EdgeKind.CALL_RETURN_TO_CALLER),
                                    func.concat(
                                        literal("return"),
                                        ":",
                                        current_edge.target,
                                    ),
                                ),
                            ],
                        ).label("symbol"),
                    ]
                )
                .select_from(
                    join(current_edge, current_node, current_edge.target == current_node.uuid)
                )
                .alias()
            )

            graph.session.execute(
                insert(cls.edge_symbol_table).from_select(
                    ["uuid", "source", "target", "symbol"],
                    select(
                        [
                            edge_symbol_query.c.uuid,
                            edge_symbol_query.c.source,
                            edge_symbol_query.c.target,
                            edge_symbol_query.c.symbol,
                        ]
                    ).where(edge_symbol_query.c.symbol != None),
                )
            )
            cls.update_edge_symbol_table_statistics(graph)
            graph.session.commit()

        @classmethod
        def populate_transition_table(cls, graph: CPG) -> None:
            if not cls._create_transition_table(graph):
                return

            all_stack_symbols = union(
                select([graph.Edge.source.label("stack_symbol")]).where(
                    graph.Edge.kind == EdgeKind.CALL_TO_FUNCTION
                ),
                select([literal(BOT).label("stack_symbol")]),
            ).alias()

            # NOTE(lb): Any update to these rules should be reflected in the
            # class docstring.
            rules = {
                "step_instruction": select(
                    [
                        literal("INTRA"),
                        all_stack_symbols.c.stack_symbol,
                        literal("step_instruction"),
                        literal("INTRA"),
                        array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                    ],
                ).select_from(all_stack_symbols),
                "step_instruction_stop": select(
                    [
                        literal("INTRA"),
                        all_stack_symbols.c.stack_symbol,
                        literal("step_instruction_stop"),
                        literal("INTER"),
                        array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                    ],
                ).select_from(all_stack_symbols),
                "call": select(
                    [
                        literal("INTER"),
                        all_stack_symbols.c.stack_symbol,
                        func.concat(
                            literal("call"),
                            ":",
                            graph.Edge.source,
                        ),
                        literal("INTRA"),
                        array(
                            [
                                graph.Edge.source,
                                all_stack_symbols.c.stack_symbol,
                            ]
                        ).cast(ARRAY(String)),
                    ],
                ).select_from(
                    join(
                        all_stack_symbols,
                        graph.Edge,
                        (graph.Edge.kind == EdgeKind.CALL_TO_FUNCTION),
                    )
                ),
                "entry_block": select(
                    [
                        literal("INTRA"),
                        all_stack_symbols.c.stack_symbol,
                        literal("entry_block"),
                        literal("INTRA"),
                        array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                    ]
                ).select_from(all_stack_symbols),
                "entry_instruction": select(
                    [
                        literal("INTRA"),
                        all_stack_symbols.c.stack_symbol,
                        literal("entry_instruction"),
                        literal("INTRA"),
                        array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                    ]
                ).select_from(all_stack_symbols),
                "return_instruction": select(
                    [
                        literal("INTER"),
                        all_stack_symbols.c.stack_symbol,
                        literal("return_instruction"),
                        literal("INTRA"),
                        array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                    ]
                ).select_from(all_stack_symbols),
                "return": select(
                    [
                        literal("INTRA"),
                        all_stack_symbols.c.stack_symbol,
                        func.concat(literal("return"), ":", all_stack_symbols.c.stack_symbol),
                        literal("INTRA"),
                        array([]).cast(ARRAY(String)),
                    ],
                ).select_from(all_stack_symbols),
            }

            if allow_unmatched_returns:
                rules["unmatched_return"] = select(
                    [
                        literal("INTRA"),
                        literal(BOT),
                        func.concat(literal("return"), ":", all_stack_symbols.c.stack_symbol),
                        literal("INTRA"),
                        array([BOT]).cast(ARRAY(String)),
                    ]
                ).select_from(all_stack_symbols)

            graph.session.execute(
                insert(cls.transition_table).from_select(
                    ["old_state", "old_stack", "input", "new_state", "new_stack"],
                    union(*[rules[i] for i in rules]),
                )
            )
            cls.update_transition_table_statistics(graph)
            graph.session.commit()

    return CFGPath


ForwardCFGPath = ConfigureCFGPath(allow_unmatched_returns=False)
"""Inter-procedural control-flow graph (CFG) paths, in the forwards direction.

Matches calls and returns up to unbounded depth, rather than using
context-sensitivity information from the pointer analysis.

When encountering a return when the call stack is empty, can return to any
callsite, which is problematic for performance and precision (in contract to
context-sensitive variants below which use points-to analysis information).
"""

UnmatchedForwardCFGPath = ConfigureCFGPath(allow_unmatched_returns=True)
"""Like ``ForwardCFGPath`` but doesn't match calls and returns.
"""


class ContextSensitiveCFLPath(CFLPath):
    @classmethod
    def select_callsite_stack_symbols(self, graph: CPG) -> Select:
        """Construct partial stack symbols of the form:

          <call instruction> : <caller context> --> <callee context>

        With columns:

        * ``stack_symbol``: The overall symbol
        * ``callsite``: caller instruction
        * ``caller``: calling function
        * ``callee``: called function
        * ``caller_context``
        * ``caller_context``

        This select is used as a variable in complex rules in PDAs, where the
        above partial stack symbol gets concatenated onto the tokens ``call:``
        or ``return:``, e.g.

        .. code-block::

             call : <call instruction> : <caller context> --> <callee context>

        This overall symbol gets pushed to or popped from the PDA stack during
        transitions.
        """
        block_edge = aliased(graph.Edge)
        function_edge = aliased(graph.Edge)
        return (
            select(
                [
                    func.concat(
                        graph.Edge.source,
                        ":",
                        graph.Edge.attributes["caller_context"].astext,
                        "-->",
                        graph.Edge.attributes["callee_context"].astext,
                    ).label("stack_symbol"),
                    graph.Edge.source.label("callsite"),
                    graph.Edge.attributes["caller_context"].astext.label("caller_context"),
                    function_edge.target.label("caller"),
                    graph.Edge.attributes["callee_context"].astext.label("callee_context"),
                    graph.Edge.target.label("callee"),
                ]
            ).select_from(
                join(
                    join(
                        graph.Edge,
                        block_edge,
                        (graph.Edge.kind == EdgeKind.CALL_TO_FUNCTION)
                        & (block_edge.kind == EdgeKind.INSTRUCTION_TO_PARENT_BLOCK)
                        & (graph.Edge.source == block_edge.source),
                    ),
                    function_edge,
                    (function_edge.kind == EdgeKind.BLOCK_TO_PARENT_FUNCTION)
                    & (block_edge.target == function_edge.source),
                )
            )
        ).alias()

    @classmethod
    def select_context_stack_symbols(self, graph: CPG) -> Select:
        """Construct stack symbols of the form ``<context>``.

        with columns:

        * ``stack_symbol``: The context
        * ``function``: The function

        where there exists some callgraph edge out of (resp., into)
        ``<function>`` with caller (resp., callee) context ``<context>``.

        This select is used as a variable in complex rules in PDAs.
        """
        return union(
            select(
                [
                    graph.Edge.attributes["caller_context"].astext.label("stack_symbol"),
                    graph.Edge.source.label("function"),
                ]
            )
            .where(graph.Edge.kind == EdgeKind.CALLGRAPH)
            .select_from(graph.Edge),
            select(
                [
                    graph.Edge.attributes["callee_context"].astext.label("stack_symbol"),
                    graph.Edge.target.label("function"),
                ]
            )
            .where(graph.Edge.kind == EdgeKind.CALLGRAPH)
            .select_from(graph.Edge),
        ).alias()


class CSCFGPath(ContextSensitiveCFLPath):
    """Inter-procedural context-sensitive (CS) control-flow graph (CFG) paths.

    These use context-sensitive information from the points-to analysis, and do
    call-return matching. If an unmatched return is encountered, then the PDA
    returns to any feasible control-flow context of the caller (as determined
    by the MATE pointer analysis).

    In the PDA for this class, "context" usually refers to a k-limited (where k
    is usually relatively low, like 1 or 2) list of callsites (stack frames).
    The PDA encoded by this class has:

    * States:
        * ``INTRA``: The next step should follow intra-procedural control
            flow
        * ``INTER``: The next step should follow inter-procedural control
            flow

    * Edge symbols (variables appear ``<in angle brackets>``, tokens are
      separated by spaces for clarity):

        * Symbol:
            * ``step_instruction``
            * Edge kinds: ``EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION``)
            * Condition: The target node is an instruction which is not a ``call``,
              ``invoke`` or ``ret``, **or** it is a ``call`` or invoke to a
              externally defined function (i.e., an LLVM declaration).

        * Symbol:
            * ``step_instruction_stop``
            * Edge kinds: ``EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION``
            * Condition: The target node is a ``call``, ``invoke`` or ``ret``
              instruction to a defined function.

        * Symbol:
            * ``call : <call instruction> : <caller context> --> <callee context>``
            * Edge kinds: ``EdgeKind.CALL_TO_FUNCTION``
            * Condition: The target node is a ``Function`` called by the source
              (instruction) node in (control-flow) context ``<caller
              context>``, resulting in context ``<callee context>``.

        * Symbol:
            * ``entry_block``
            * Edge kinds: ``EdgeKind.FUNCTION_TO_ENTRY_BLOCK``
            * Condition: None

        * Symbol:
            * ``entry_instruction``
            * Edge kinds: ``EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION``
            * Condition: None

        * Symbol:
            * ``return_instruction``
            * Edge kinds: ``EdgeKind.RETURN_INSTRUCTION_TO_CALL_RETURN``
            * Condition: None

        * Symbol:
            * ``return : <instruction> : <caller context> --> <callee context>``
            * Edge kinds: ``EdgeKind.CALL_RETURN_TO_CALLER``
            * Condition: The target is the ``call`` or ``invoke`` instruction
              for the call to the function that the control flow is returning
              from. The call occurred in context ``<caller context>``,
              resulting in context ``<callee context>``.

    * Stack symbol templates/formats:
       * ``call : <call instruction> : <caller context> --> <callee context>``
       * ``<context>``

    * Transitions (variables appear ``<in angle brackets>``, ``push`` is the
      cons constructor for the stack type, ``bot`` is the bottom of the stack):

        * Transition:
            * Input state: ``INTRA``
            * Input stack: ``<s>``
            * Edge symbol: ``step_instruction``
            * New state: ``INTRA``
            * New stack: ``<s>``
        * Transition:
            * Input state: ``INTRA``
            * Input stack: ``<s>``
            * Edge symbol: ``step_instruction_stop``
            * New state: ``INTER``
            * New stack: ``<s>``
        * Transition:
            * Description: TODO(lb)
            * Input state: ``INTER``
            * Input stack: ``push(call : <call instruction 0> : <caller context 0> --> <callee context 0>)``
            * Edge symbol: ``call : <call instruction> : <caller context> --> <callee context>``
            * New state: ``INTRA``
            * New stack: ``push(call : <call instruction> : <caller context> --> <callee context>, push(call : <call instruction 0> : <caller context 0> : <callee context 0>))``
            * Where: ``<callee context 0> = <caller context>`` and the callee
              function of the existing stack frame is the caller context of the
              new stack frame.
            * TODO(lb): how does that relate to ``<call instruction>``?
        * Transition:
            * Description: Call with empty stack
            * Input state: ``INTER``
            * Input stack: ``bot``
            * Edge symbol: ``call : <call instruction> : <caller context> --> <callee context>``
            * New state: ``INTRA``
            * New stack: ``push(<call instruction> : <caller context> --> <callee context>, bot)``
        * Transition:
            * Description: TODO(lb)
            * Input state: ``INTER``
            * Input stack: ``push(<caller context>, <s>)``
            * Edge symbol: ``call : <call instruction> : <caller context> --> <callee context>``
            * New state: ``INTRA``
            * Input stack: ``push(call : <call instruction> : <caller context> --> <callee context>, push(<caller context>, <s>))``
            * Where: ``<call instruction>`` may call ``<function>``
        * Transition:
            * Input state: ``INTRA``
            * Input stack: ``<s>``
            * Edge symbol: ``entry_block``
            * New state: ``INTRA``
            * New stack: ``<s>``
        * Transition:
            * Input state: ``INTRA``
            * Input stack: ``<s>``
            * Edge symbol: ``entry_instruction``
            * New state: ``INTRA``
            * New stack: ``<s>``
        * Transition:
            * Input state: ``INTER``
            * Input stack: ``<s>``
            * Edge symbol: ``return_instruction``
            * New state: ``INTRA``
            * New stack: ``<s>``
        * Transition:
            * Description: Return with a call on the stack
            * Input state: ``INTRA``
            * Input stack: ``push(call : <call instruction> : <caller context> --> <callee context>, <s>)``
            * Edge symbol: ``return : <call instruction> : <caller context> --> <callee context>``
            * New state: ``INTRA``
            * New stack: ``<s>``
        * Transition:
            * Description: Return with an empty stack
            * Input state: ``INTRA``
            * Input stack: ``bot``
            * Edge symbol: ``return : <call instruction> : <caller context> --> <callee context>``
            * New state: ``INTRA``
            * New stack: ``push(<caller context>, bot)``
        * Transition:
            * Input state: ``INTRA``
            * Input stack: ``push(<callee context>, <s>)``
            * Edge symbol: ``return : <call instruction> : <caller context> : <callee context>``
            * New state: ``INTRA``
            * New stack: ``push(<caller context>, <s>)``
    """

    @classmethod
    def table_name_prefix(cls) -> str:
        # The tables can be re-used as long as we're not stepping over any functions
        if not cls.stepped_over_functions:
            return "cscfg"
        else:
            # Use the randomly generated Path name
            return cls.__name__

    @classmethod
    def initial_state(cls) -> ClauseElement:
        return literal("INTRA").cast(String)

    @classmethod
    def initial_stack(cls) -> ClauseElement:
        return array([BOT]).cast(ARRAY(String))

    @classmethod
    def populate_edge_symbol_table(cls, graph: CPG) -> None:
        """Preprocess the graph's edge table and give each edge a symbol to be used during during
        CFL-based path extension."""
        if not cls._create_edge_symbol_table(graph):
            return

        current_edge = graph.Edge
        current_node = aliased(graph.Node)
        outgoing_edge = aliased(graph.Edge)
        outgoing_node = aliased(graph.Node)

        # NOTE(lb): Any update to this query should be reflected in the class
        # docstring.
        edge_symbol_query = (
            select(
                [
                    current_edge.uuid,
                    current_edge.source,
                    current_edge.target,
                    case(
                        [
                            (
                                (current_edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION)
                                & (
                                    ~(
                                        current_node.attributes["opcode"].astext.in_(
                                            [
                                                Opcode.CALL.value,
                                                Opcode.INVOKE.value,
                                                Opcode.RET.value,
                                            ]
                                        )
                                    )
                                    | exists(
                                        select([outgoing_node]).select_from(
                                            join(
                                                outgoing_edge,
                                                outgoing_node,
                                                (
                                                    (current_node.uuid == outgoing_edge.source)
                                                    & (outgoing_edge.target == outgoing_node.uuid)
                                                    & (
                                                        outgoing_edge.kind
                                                        == EdgeKind.CALL_TO_FUNCTION
                                                    )
                                                    & (
                                                        # Step over (i.e. do not step into) any function which is
                                                        # just a declaration, or any function that has been
                                                        # explicitly marked as to be stepped over. Since this is a
                                                        # CASE statement with first-match-wins, these do not need to
                                                        # be excluded in the next case (step_instruction_stop).
                                                        (
                                                            outgoing_node.attributes[
                                                                "is_declaration"
                                                            ].cast(Boolean)
                                                        )
                                                        | (
                                                            outgoing_node.attributes[
                                                                "name"
                                                            ].astext.in_(cls.stepped_over_functions)
                                                        )
                                                    )
                                                ),
                                            )
                                        )
                                    )
                                ),
                                literal("step_instruction"),
                            ),
                            (
                                (current_edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION)
                                & (
                                    (
                                        current_node.attributes["opcode"].astext.in_(
                                            [
                                                Opcode.CALL.value,
                                                Opcode.INVOKE.value,
                                                Opcode.RET.value,
                                            ]
                                        )
                                    )
                                ),
                                literal("step_instruction_stop"),
                            ),
                            (
                                (current_edge.kind == EdgeKind.CALL_TO_FUNCTION),
                                func.concat(
                                    literal("call"),
                                    ":",
                                    current_edge.source,
                                    ":",
                                    current_edge.attributes["caller_context"].astext,
                                    "-->",
                                    current_edge.attributes["callee_context"].astext,
                                ),
                            ),
                            (
                                (current_edge.kind == EdgeKind.FUNCTION_TO_ENTRY_BLOCK),
                                literal("entry_block"),
                            ),
                            (
                                (current_edge.kind == EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION),
                                literal("entry_instruction"),
                            ),
                            (
                                (current_edge.kind == EdgeKind.RETURN_INSTRUCTION_TO_CALL_RETURN),
                                literal("return_instruction"),
                            ),
                            (
                                (current_edge.kind == EdgeKind.CALL_RETURN_TO_CALLER),
                                func.concat(
                                    literal("return"),
                                    ":",
                                    current_edge.target,
                                    ":",
                                    current_edge.attributes["caller_context"].astext,
                                    "-->",
                                    current_edge.attributes["callee_context"].astext,
                                ),
                            ),
                        ],
                    ).label("symbol"),
                ]
            )
            .select_from(join(current_edge, current_node, current_edge.target == current_node.uuid))
            .alias()
        )

        graph.session.execute(
            insert(cls.edge_symbol_table).from_select(
                ["uuid", "source", "target", "symbol"],
                select(
                    [
                        edge_symbol_query.c.uuid,
                        edge_symbol_query.c.source,
                        edge_symbol_query.c.target,
                        edge_symbol_query.c.symbol,
                    ]
                ).where(edge_symbol_query.c.symbol != None),
            )
        )
        cls.update_edge_symbol_table_statistics(graph)
        graph.session.commit()

    @classmethod
    def populate_transition_table(cls, graph: CPG) -> None:
        if not cls._create_transition_table(graph):
            return

        callsite_stack_symbols = cls.select_callsite_stack_symbols(graph)
        callsite_stack_symbols2 = aliased(callsite_stack_symbols)
        context_stack_symbols = cls.select_context_stack_symbols(graph)

        all_stack_symbols = union(
            select([callsite_stack_symbols.c.stack_symbol]).select_from(callsite_stack_symbols),
            select([context_stack_symbols.c.stack_symbol]).select_from(context_stack_symbols),
            select([literal(BOT).label("stack_symbol")]),
        ).alias()

        # NOTE(lb): Any update to these rules should be reflected in the class
        # docstring.
        rules = {
            "step_instruction": select(
                [
                    literal("INTRA"),
                    all_stack_symbols.c.stack_symbol,
                    literal("step_instruction"),
                    literal("INTRA"),
                    array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                ],
            ).select_from(all_stack_symbols),
            "step_instruction_stop": select(
                [
                    literal("INTRA"),
                    all_stack_symbols.c.stack_symbol,
                    literal("step_instruction_stop"),
                    literal("INTER"),
                    array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                ],
            ).select_from(all_stack_symbols),
            "call": select(
                [
                    literal("INTER"),
                    callsite_stack_symbols2.c.stack_symbol,
                    func.concat(
                        literal("call"),
                        ":",
                        callsite_stack_symbols.c.stack_symbol,
                    ),
                    literal("INTRA"),
                    array(
                        [
                            callsite_stack_symbols.c.stack_symbol,
                            callsite_stack_symbols2.c.stack_symbol,
                        ]
                    ).cast(ARRAY(String)),
                ],
            ).select_from(
                join(
                    callsite_stack_symbols,
                    callsite_stack_symbols2,
                    (callsite_stack_symbols2.c.callee == callsite_stack_symbols.c.caller)
                    & (
                        callsite_stack_symbols2.c.callee_context
                        == callsite_stack_symbols.c.caller_context
                    ),
                )
            ),
            "empty_call": select(
                [
                    literal("INTER"),
                    literal(BOT),
                    func.concat(
                        literal("call"),
                        ":",
                        callsite_stack_symbols.c.stack_symbol,
                    ),
                    literal("INTRA"),
                    array([callsite_stack_symbols.c.stack_symbol, BOT]).cast(ARRAY(String)),
                ],
            ).select_from(callsite_stack_symbols),
            "context_call": select(
                [
                    literal("INTER"),
                    context_stack_symbols.c.stack_symbol,
                    func.concat(
                        literal("call"),
                        ":",
                        callsite_stack_symbols.c.stack_symbol,
                    ),
                    literal("INTRA"),
                    array(
                        [
                            callsite_stack_symbols.c.stack_symbol,
                            context_stack_symbols.c.stack_symbol,
                        ]
                    ).cast(ARRAY(String)),
                ],
            ).select_from(
                join(
                    context_stack_symbols,
                    callsite_stack_symbols,
                    (
                        context_stack_symbols.c.stack_symbol
                        == callsite_stack_symbols.c.caller_context
                    )
                    & (context_stack_symbols.c.function == callsite_stack_symbols.c.caller),
                )
            ),
            "entry_block": select(
                [
                    literal("INTRA"),
                    all_stack_symbols.c.stack_symbol,
                    literal("entry_block"),
                    literal("INTRA"),
                    array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                ]
            ).select_from(all_stack_symbols),
            "entry_instruction": select(
                [
                    literal("INTRA"),
                    all_stack_symbols.c.stack_symbol,
                    literal("entry_instruction"),
                    literal("INTRA"),
                    array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                ]
            ).select_from(all_stack_symbols),
            "return_instruction": select(
                [
                    literal("INTER"),
                    all_stack_symbols.c.stack_symbol,
                    literal("return_instruction"),
                    literal("INTRA"),
                    array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                ]
            ).select_from(all_stack_symbols),
            "return": select(
                [
                    literal("INTRA"),
                    callsite_stack_symbols.c.stack_symbol,
                    func.concat(
                        literal("return"),
                        ":",
                        callsite_stack_symbols.c.stack_symbol,
                    ),
                    literal("INTRA"),
                    array([]).cast(ARRAY(String)),
                ],
            ).select_from(callsite_stack_symbols),
            "empty_return": select(
                [
                    literal("INTRA"),
                    literal(BOT),
                    func.concat(
                        literal("return"),
                        ":",
                        callsite_stack_symbols.c.stack_symbol,
                    ),
                    literal("INTRA"),
                    array([callsite_stack_symbols.c.caller_context, literal(BOT)]).cast(
                        ARRAY(String)
                    ),
                ],
            ).select_from(callsite_stack_symbols),
            "context_return": select(
                [
                    literal("INTRA"),
                    callsite_stack_symbols.c.callee_context,
                    func.concat(
                        literal("return"),
                        ":",
                        callsite_stack_symbols.c.stack_symbol,
                    ),
                    literal("INTRA"),
                    array([callsite_stack_symbols.c.caller_context]).cast(ARRAY(String)),
                ],
            ).select_from(callsite_stack_symbols),
        }

        graph.session.execute(
            insert(cls.transition_table).from_select(
                ["old_state", "old_stack", "input", "new_state", "new_stack"],
                union(*[rules[i] for i in rules]),
            )
        )
        cls.update_transition_table_statistics(graph)
        graph.session.commit()


def ConfigureDFGPath(*, thin: bool = True) -> Type[Path]:
    class CSDataflowPath(ContextSensitiveCFLPath):
        """Thin dataflow paths that use context-sensitivity (CS) from the points-to analysis.

        The PDA encoded by this class has:

        * States:
            * ``DATAFLOW``
        * Edge symbols (variables appear ``<in angle brackets>``, tokens are
          separated by spaces for clarity):

            * Symbol:
                * ``value_definition_to_use``
                * Edge kinds: ``EdgeKind.VALUE_DEFINITION_TO_USE``
                * Condition: The target node is an instruction which is not a
                  ``call``, ``invoke`` or ``load``; **and** the use is not as the
                  first operand of a ``store``.

            * Symbol:
                * ``dataflow_from_memory : <context>``
                * Edge kinds: ``EdgeKind.DATAFLOW_SIGNATURE``,
                  ``EdgeKind.DIRECT_DATAFLOW_SIGNATURE``, plus
                  ``EdgeKind.INDIRECT_DATAFLOW_SIGNATURE`` if ``thin`` is
                  ``False``.
                * Condition: The target node is a dataflow, input, or output
                  signature, and the source node is a memory location.

            * Symbol:
                * ``dataflow_from_value : <context>``
                * Edge kinds: ``EdgeKind.DATAFLOW_SIGNATURE``,
                  ``EdgeKind.DIRECT_DATAFLOW_SIGNATURE``, plus
                  ``EdgeKind.INDIRECT_DATAFLOW_SIGNATURE`` if ``thin`` is
                  ``False``.
                * Condition: The target node is a dataflow, input, or output
                  signature, and the source node is *not* a memory location (i.e.,
                  it is an LLVM value).

            * Symbol:
                * ``dataflow_from_value : <context>``
                * Edge kinds: ``EdgeKind.DATAFLOW_SIGNATURE``,
                  ``EdgeKind.DIRECT_DATAFLOW_SIGNATURE``, plus
                  ``EdgeKind.INDIRECT_DATAFLOW_SIGNATURE`` if ``thin`` is
                  ``False``.
                * Condition: The target node is a dataflow, input, or output
                  signature, and the source node is *not* a memory location (i.e.,
                  it is an LLVM value).

            * Symbol:
                * ``dataflow_to_memory : <context>``
                * Edge kinds: ``EdgeKind.DATAFLOW_SIGNATURE``,
                  ``EdgeKind.DIRECT_DATAFLOW_SIGNATURE``, plus
                  ``EdgeKind.INDIRECT_DATAFLOW_SIGNATURE`` if ``thin`` is
                  ``False``.
                * Condition: The target node is a memory location.

            * Symbol:
                * ``dataflow_to_value : <context>``
                * Edge kinds: ``EdgeKind.DATAFLOW_SIGNATURE``,
                  ``EdgeKind.DIRECT_DATAFLOW_SIGNATURE``, plus
                  ``EdgeKind.INDIRECT_DATAFLOW_SIGNATURE`` if ``thin`` is
                  ``False``.
                * Condition: The target node is *not* a memory location (i.e., it
                  is an LLVM value).

            * Symbol:
                * ``load : <context>``
                * Edge kinds: ``EdgeKind.LOAD_MEMORY``
                * Condition: None

            * Symbol:
                * ``store : <context>``
                * Edge kinds: ``EdgeKind.STORE_MEMORY``
                * Condition: None

            * Symbol:
                * ``operand_to_param_binding``
                * Edge kinds: ``EdgeKind.OPERAND_TO_PARAM_BINDING``
                * Condition: None

            * Symbol:
                * ``call : <call instruction> : <caller context> --> <callee context>``
                * Edge kinds: ``EdgeKind.PARAM_BINDING_TO_ARG``
                * Condition: The parameter was bound by this call in this calling
                  context

            * Symbol:
                * ``return_value_to_call_return``
                * Edge kinds: ``EdgeKind.RETURN_VALUE_TO_CALL_RETURN``
                * Condition: None

            * Symbol:
                * ``return : <call instruction> : <caller context> --> <callee context>``
                * Edge kinds: ``EdgeKind.CALL_RETURN_TO_CALLER``
                * Condition: This return is from a (potential) call in context
                  ``<caller context>``, resulting in callee context ``<callee
                  context>``.
        * Stack symbol templates/formats:
        * ``<call instruction> : <caller context> --> <callee context>``
        * ``<context>``
        * Transitions (variables appear ``<in angle brackets>``, ``push`` is the
          cons constructor for the stack type, ``bot`` is the bottom of the stack,
          all input and output states are ``DATAFLOW``):
            * Transition:
                * Input stack: ``<s>``
                * Edge symbol: ``value_definition_to_use``
                * New stack: ``<s>``
            * Transition:
                * Input stack: ``<s>``
                * Edge symbol: ``operand_to_param_binding``
                * New stack: ``<s>``
            * Transition:
                * Input stack: ``<s>``
                * Edge symbol: ``return_value_to_call_return``
                * New stack: ``<s>``
            * Transition:
                * Description: TODO(lb)
                * Input stack: ``push(call : <call instruction 0> : <caller context 0> --> <callee context 0>)``
                * Edge symbol: ``call : <call instruction> : <caller context> --> <callee context>``
                * New stack: ``push(call : <call instruction> : <caller context> --> <callee context>, push(call : <call instruction 0> : <caller context 0> : <callee context 0>))``
                * Where: ``<callee context 0> = <caller context>`` and the callee
                  function of the existing stack frame is the caller context of the
                  new stack frame.
                * TODO(lb): how does that relate to ``<call instruction>``?
            * Transition:
                * Input stack: ``push(<caller context>, <s>)``
                * Edge symbol: ``call : <call instruction> : <caller context> --> <callee context>``
                * New stack: ``push(<call instruction> : <caller context> --> <callee context>, push(<context>, bot))``
            * Transition:
                * Input stack: ``push(call : <call instruction> : <caller context> --> <callee context>, <s>)``
                * Edge symbol: ``return : <call instruction> : <caller context> --> <callee context>``
                * New stack: ``<s>``
            * Transition:
                * Description: Return with an empty stack
                * Input stack: ``bot``
                * Edge symbol: ``return : <call instruction> : <caller context> --> <callee context>``
                * New stack: ``push(<caller context>, bot)``
            * Transition:
                * Input stack: ``push(<callee context>, <s>)``
                * Edge symbol: ``return : <call instruction> : <caller context> : <callee context>``
                * New stack: ``push(<caller context>, <s>)``
            * Transition:
                * Input stack: ``bot``
                * Edge symbol: ``load : <context>``
                * New stack: ``push(<context>, <s>)``
            * Transition:
                * Input stack: ``push(<call instruction> : <caller context> --> <callee context>, <s>)``
                * Edge symbol: ``store : <callee context>``
                * New stack: ``bot``
            * Transition:
                * Input stack: ``bot``
                * Edge symbol: ``store : <context>``
                * New stack: ``bot``
            * Transition:
                * Input stack: ``push(<context>, <s>)``
                * Edge symbol: ``store : <context>``
                * New stack: ``bot``
            * Similar rules where ``dataflow_from_memory`` is to
              ``dataflow_to_memory`` as ``load`` is to ``store``...
            * Transition:
                * Input stack: ``push(<context>, <s>)``
                * Edge symbol: ``dataflow_from_value : <context>``
                * New stack: ``push(<context>, <s>)``
            * Transition:
                * Input stack: ``bot``
                * Edge symbol: ``dataflow_from_value : <context>``
                * New stack: ``push(<context>, bot)``
            * Transition:
                * Input stack: ``push(<call instruction> : <caller context> --> <callee context>, bot)``
                * Edge symbol: ``dataflow_from_value : <callee context>``
                * New stack: ``push(<call instruction> : <caller context> --> <callee context>, bot)``
            * Transition:
                * Input stack: ``push(<context>, <s>)``
                * Edge symbol: ``dataflow_to_value : <context>``
                * New stack: ``push(<context>, <s>)``
            * Transition:
                * Input stack: ``bot``
                * Edge symbol: ``dataflow_to_value : <context>``
                * New stack: ``push(<context>, bot)``
            * Transition:
                * Input stack: ``push(<call instruction> : <caller context> --> <callee context>, bot)``
                * Edge symbol: ``dataflow_to_value : <callee context>``
                * New stack: ``push(<call instruction> : <caller context> --> <callee context>, bot)``


        Transitions for a reversed automaton are dual in some sense...
        """

        @classmethod
        def table_name_prefix(cls) -> str:
            # The PDA tables are the same for all instances
            return "cs" + ("thin" if thin else "") + "dataflow"

        @classmethod
        def initial_state(cls) -> ClauseElement:
            return literal("DATAFLOW").cast(String)

        @classmethod
        def initial_stack(cls) -> ClauseElement:
            return array([BOT]).cast(ARRAY(String))

        @classmethod
        def populate_edge_symbol_table(cls, graph: CPG) -> None:
            """Preprocess the graph's edge table and give each edge a symbol to be used during
            during CFL-based path extension."""

            if not cls._create_edge_symbol_table(graph):
                return

            current_edge = graph.Edge
            source_node = aliased(graph.Node)
            target_node = aliased(graph.Node)
            current_call = aliased(graph.Node)
            current_call_edge = aliased(graph.Edge)

            # NOTE(lb): Any update to this query should be reflected in the class
            # docstring.
            edge_symbol_query = (
                select(
                    [
                        current_edge.uuid,
                        current_edge.source,
                        current_edge.target,
                        case(
                            [
                                (
                                    (current_edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE)
                                    & (
                                        (
                                            (
                                                ~(
                                                    target_node.attributes["opcode"].astext.in_(
                                                        [
                                                            Opcode.CALL.value,
                                                            Opcode.INVOKE.value,
                                                            Opcode.LOAD.value,
                                                        ]
                                                    )
                                                )
                                            )
                                            if thin
                                            else true()
                                        )
                                    )
                                    & (
                                        (
                                            (
                                                (
                                                    target_node.attributes["opcode"].astext
                                                    != Opcode.STORE.value
                                                )
                                                | (
                                                    current_edge.attributes[
                                                        "operand_number"
                                                    ].as_integer()
                                                    != 1
                                                )
                                            )
                                            if thin
                                            else true()
                                        )
                                    ),
                                    literal("value_definition_to_use"),
                                ),
                                # Edges to dataflow signature nodes from memory
                                (
                                    (
                                        current_edge.kind.in_(
                                            [
                                                EdgeKind.DATAFLOW_SIGNATURE,
                                                EdgeKind.DIRECT_DATAFLOW_SIGNATURE,
                                            ]
                                            + (
                                                []
                                                if thin
                                                else [EdgeKind.INDIRECT_DATAFLOW_SIGNATURE]
                                            )
                                        )
                                        & target_node.kind.in_(
                                            [
                                                NodeKind.DATAFLOW_SIGNATURE,
                                                NodeKind.INPUT_SIGNATURE,
                                                NodeKind.OUTPUT_SIGNATURE,
                                            ]
                                        )
                                        & source_node.kind.in_(
                                            [
                                                NodeKind.MEMORY_LOCATION,
                                            ]
                                        )
                                    ),
                                    func.concat(
                                        literal("dataflow_from_memory"),
                                        ":",
                                        current_edge.attributes["context"].astext,
                                    ),
                                ),
                                # Edges to dataflow signature nodes from values
                                (
                                    (
                                        current_edge.kind.in_(
                                            [
                                                EdgeKind.DATAFLOW_SIGNATURE,
                                                EdgeKind.DIRECT_DATAFLOW_SIGNATURE,
                                            ]
                                            + (
                                                []
                                                if thin
                                                else [EdgeKind.INDIRECT_DATAFLOW_SIGNATURE]
                                            )
                                        )
                                        & target_node.kind.in_(
                                            [
                                                NodeKind.DATAFLOW_SIGNATURE,
                                                NodeKind.INPUT_SIGNATURE,
                                                NodeKind.OUTPUT_SIGNATURE,
                                            ]
                                        )
                                    ),
                                    func.concat(
                                        literal("dataflow_from_value"),
                                        ":",
                                        current_edge.attributes["context"].astext,
                                    ),
                                ),
                                # Edges from dataflow signature nodes to memory
                                (
                                    (
                                        current_edge.kind.in_(
                                            [
                                                EdgeKind.DATAFLOW_SIGNATURE,
                                                EdgeKind.DIRECT_DATAFLOW_SIGNATURE,
                                            ]
                                            + (
                                                []
                                                if thin
                                                else [EdgeKind.INDIRECT_DATAFLOW_SIGNATURE]
                                            )
                                        )
                                        & (target_node.kind == NodeKind.MEMORY_LOCATION)
                                    ),
                                    func.concat(
                                        literal("dataflow_to_memory"),
                                        ":",
                                        current_edge.attributes["context"].astext,
                                    ),
                                ),
                                # Edges from dataflow signature nodes to values
                                (
                                    (
                                        current_edge.kind.in_(
                                            [
                                                EdgeKind.DATAFLOW_SIGNATURE,
                                                EdgeKind.DIRECT_DATAFLOW_SIGNATURE,
                                            ]
                                            + (
                                                []
                                                if thin
                                                else [EdgeKind.INDIRECT_DATAFLOW_SIGNATURE]
                                            )
                                        )
                                    ),
                                    func.concat(
                                        literal("dataflow_to_value"),
                                        ":",
                                        current_edge.attributes["context"].astext,
                                    ),
                                ),
                                (
                                    current_edge.kind == EdgeKind.LOAD_MEMORY,
                                    func.concat(
                                        literal("load"),
                                        ":",
                                        current_edge.attributes["context"].astext,
                                    ),
                                ),
                                (
                                    current_edge.kind == EdgeKind.STORE_MEMORY,
                                    func.concat(
                                        literal("store"),
                                        ":",
                                        current_edge.attributes["context"].astext,
                                    ),
                                ),
                                (
                                    current_edge.kind == EdgeKind.OPERAND_TO_PARAM_BINDING,
                                    literal("operand_to_param_binding"),
                                ),
                                (
                                    current_edge.kind == EdgeKind.PARAM_BINDING_TO_ARG,
                                    func.concat(
                                        literal("call"),
                                        ":",
                                        current_call.uuid,
                                        ":",
                                        current_edge.attributes["caller_context"].astext,
                                        "-->",
                                        current_edge.attributes["callee_context"].astext,
                                    ),
                                ),
                                (
                                    current_edge.kind == EdgeKind.RETURN_VALUE_TO_CALL_RETURN,
                                    literal("return_value_to_call_return"),
                                ),
                                (
                                    current_edge.kind == EdgeKind.CALL_RETURN_TO_CALLER,
                                    func.concat(
                                        literal("return"),
                                        ":",
                                        current_call.uuid,
                                        ":",
                                        current_edge.attributes["caller_context"].astext,
                                        "-->",
                                        current_edge.attributes["callee_context"].astext,
                                    ),
                                ),
                            ],
                        ).label("symbol"),
                    ]
                )
                .select_from(
                    join(
                        join(
                            join(
                                join(
                                    current_edge,
                                    target_node,
                                    (current_edge.target == target_node.uuid),
                                ),
                                source_node,
                                (current_edge.source == source_node.uuid),
                            ),
                            current_call_edge,
                            (
                                (current_edge.kind == EdgeKind.PARAM_BINDING_TO_ARG)
                                & (current_edge.source == current_call_edge.target)
                                & (current_call_edge.kind == EdgeKind.CALL_TO_PARAM_BINDING)
                            ),
                            isouter=True,
                        ),
                        current_call,
                        (
                            (
                                (current_call_edge.uuid != None)
                                & (current_call_edge.source == current_call.uuid)
                            )
                            | (
                                (current_call_edge.uuid == None)
                                & (current_edge.target == current_call.uuid)
                            )
                        ),
                    )
                )
                .alias()
            )

            graph.session.execute(
                insert(cls.edge_symbol_table).from_select(
                    ["uuid", "source", "target", "symbol"],
                    select(
                        [
                            edge_symbol_query.c.uuid,
                            edge_symbol_query.c.source,
                            edge_symbol_query.c.target,
                            edge_symbol_query.c.symbol,
                        ]
                    ).where(edge_symbol_query.c.symbol != None),
                )
            )
            cls.update_edge_symbol_table_statistics(graph)
            graph.session.commit()

        @classmethod
        def populate_transition_table(cls, graph: CPG) -> None:
            if not cls._create_transition_table(graph):
                return

            callsite_stack_symbols = cls.select_callsite_stack_symbols(graph)
            callsite_stack_symbols2 = aliased(callsite_stack_symbols)
            context_stack_symbols = cls.select_context_stack_symbols(graph)

            all_stack_symbols = union(
                select([callsite_stack_symbols.c.stack_symbol]).select_from(callsite_stack_symbols),
                select([context_stack_symbols.c.stack_symbol]).select_from(context_stack_symbols),
                select([literal(BOT).label("stack_symbol")]),
            ).alias()

            # NOTE(lb): Any update to this query should be reflected in the class
            # docstring.
            rules = {
                "intraprocedural": select(
                    [
                        literal("DATAFLOW"),
                        all_stack_symbols.c.stack_symbol,
                        literal("value_definition_to_use"),
                        literal("DATAFLOW"),
                        array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                    ],
                ).select_from(all_stack_symbols),
                "operand_to_param_binding": select(
                    [
                        literal("DATAFLOW"),
                        all_stack_symbols.c.stack_symbol,
                        literal("operand_to_param_binding"),
                        literal("DATAFLOW"),
                        array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                    ],
                ).select_from(all_stack_symbols),
                "return_value_to_call_return": select(
                    [
                        literal("DATAFLOW"),
                        all_stack_symbols.c.stack_symbol,
                        literal("return_value_to_call_return"),
                        literal("DATAFLOW"),
                        array([all_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                    ],
                ).select_from(all_stack_symbols),
                "param_binding_to_arg": (
                    select(
                        [
                            literal("DATAFLOW"),
                            callsite_stack_symbols.c.stack_symbol,
                            func.concat(
                                literal("call"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([]).cast(ARRAY(String)),
                        ],
                    ).select_from(callsite_stack_symbols)
                    if cls.is_reversed
                    else select(
                        [
                            literal("DATAFLOW"),
                            callsite_stack_symbols2.c.stack_symbol,
                            func.concat(
                                literal("call"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array(
                                [
                                    callsite_stack_symbols.c.stack_symbol,
                                    callsite_stack_symbols2.c.stack_symbol,
                                ]
                            ).cast(ARRAY(String)),
                        ],
                    ).select_from(
                        join(
                            callsite_stack_symbols,
                            callsite_stack_symbols2,
                            (callsite_stack_symbols2.c.callee == callsite_stack_symbols.c.caller)
                            & (
                                callsite_stack_symbols2.c.callee_context
                                == callsite_stack_symbols.c.caller_context
                            ),
                        )
                    )
                ),
                "empty_param_binding_to_arg": (
                    select(
                        [
                            literal("DATAFLOW"),
                            literal(BOT),
                            func.concat(
                                literal("call"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([callsite_stack_symbols.c.caller_context, BOT]).cast(
                                ARRAY(String)
                            ),
                        ],
                    ).select_from(callsite_stack_symbols)
                    if cls.is_reversed
                    else select(
                        [
                            literal("DATAFLOW"),
                            literal(BOT),
                            func.concat(
                                literal("call"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([callsite_stack_symbols.c.stack_symbol, BOT]).cast(ARRAY(String)),
                        ],
                    ).select_from(callsite_stack_symbols)
                ),
                "context_param_binding_to_arg": (
                    select(
                        [
                            literal("DATAFLOW"),
                            callsite_stack_symbols.c.callee_context,
                            func.concat(
                                literal("call"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([callsite_stack_symbols.c.caller_context]).cast(ARRAY(String)),
                        ],
                    ).select_from(callsite_stack_symbols)
                    if cls.is_reversed
                    else select(
                        [
                            literal("DATAFLOW"),
                            context_stack_symbols.c.stack_symbol,
                            func.concat(
                                literal("call"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array(
                                [
                                    callsite_stack_symbols.c.stack_symbol,
                                    context_stack_symbols.c.stack_symbol,
                                ]
                            ).cast(ARRAY(String)),
                        ],
                    ).select_from(
                        join(
                            context_stack_symbols,
                            callsite_stack_symbols,
                            (
                                context_stack_symbols.c.stack_symbol
                                == callsite_stack_symbols.c.caller_context
                            )
                            & (context_stack_symbols.c.function == callsite_stack_symbols.c.caller),
                        )
                    )
                ),
                "call_return_to_caller": (
                    select(
                        [
                            literal("DATAFLOW"),
                            callsite_stack_symbols2.c.stack_symbol,
                            func.concat(
                                literal("return"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array(
                                [
                                    callsite_stack_symbols.c.stack_symbol,
                                    callsite_stack_symbols2.c.stack_symbol,
                                ]
                            ).cast(ARRAY(String)),
                        ],
                    ).select_from(
                        join(
                            callsite_stack_symbols,
                            callsite_stack_symbols2,
                            (callsite_stack_symbols2.c.callee == callsite_stack_symbols.c.caller)
                            & (
                                callsite_stack_symbols2.c.callee_context
                                == callsite_stack_symbols.c.caller_context
                            ),
                        )
                    )
                    if cls.is_reversed
                    else select(
                        [
                            literal("DATAFLOW"),
                            callsite_stack_symbols.c.stack_symbol,
                            func.concat(
                                literal("return"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([]).cast(ARRAY(String)),
                        ],
                    ).select_from(callsite_stack_symbols)
                ),
                "empty_call_return_to_caller": (
                    select(
                        [
                            literal("DATAFLOW"),
                            literal(BOT),
                            func.concat(
                                literal("return"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([callsite_stack_symbols.c.stack_symbol, literal(BOT)]).cast(
                                ARRAY(String)
                            ),
                        ],
                    ).select_from(callsite_stack_symbols)
                    if cls.is_reversed
                    else select(
                        [
                            literal("DATAFLOW"),
                            literal(BOT),
                            func.concat(
                                literal("return"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([callsite_stack_symbols.c.caller_context, literal(BOT)]).cast(
                                ARRAY(String)
                            ),
                        ],
                    ).select_from(callsite_stack_symbols)
                ),
                "context_call_return_to_caller": (
                    select(
                        [
                            literal("DATAFLOW"),
                            context_stack_symbols.c.stack_symbol,
                            func.concat(
                                literal("return"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array(
                                [
                                    callsite_stack_symbols.c.callee_context,
                                    context_stack_symbols.c.stack_symbol,
                                ]
                            ).cast(ARRAY(String)),
                        ],
                    ).select_from(
                        join(
                            context_stack_symbols,
                            callsite_stack_symbols,
                            (
                                context_stack_symbols.c.stack_symbol
                                == callsite_stack_symbols.c.caller_context
                            )
                            & (context_stack_symbols.c.function == callsite_stack_symbols.c.caller),
                        )
                    )
                    if cls.is_reversed
                    else select(
                        [
                            literal("DATAFLOW"),
                            callsite_stack_symbols.c.callee_context,
                            func.concat(
                                literal("return"),
                                ":",
                                callsite_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([callsite_stack_symbols.c.caller_context]).cast(ARRAY(String)),
                        ],
                    ).select_from(callsite_stack_symbols)
                ),
                "load_memory": (
                    union(
                        select(
                            [
                                literal("DATAFLOW"),
                                callsite_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("load"), ":", callsite_stack_symbols.c.callee_context
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(callsite_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                literal(BOT),
                                func.concat(
                                    literal("load"), ":", context_stack_symbols.c.stack_symbol
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                context_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("load"), ":", context_stack_symbols.c.stack_symbol
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                    )
                    if cls.is_reversed
                    else select(
                        [
                            literal("DATAFLOW"),
                            literal(BOT),
                            func.concat(literal("load"), ":", context_stack_symbols.c.stack_symbol),
                            literal("DATAFLOW"),
                            array([context_stack_symbols.c.stack_symbol, literal(BOT)]).cast(
                                ARRAY(String)
                            ),
                        ],
                    ).select_from(context_stack_symbols)
                ),
                "store_memory": (
                    select(
                        [
                            literal("DATAFLOW"),
                            literal(BOT),
                            func.concat(
                                literal("store"), ":", context_stack_symbols.c.stack_symbol
                            ),
                            literal("DATAFLOW"),
                            array([context_stack_symbols.c.stack_symbol, literal(BOT)]).cast(
                                ARRAY(String)
                            ),
                        ],
                    ).select_from(context_stack_symbols)
                    if cls.is_reversed
                    else union(
                        select(
                            [
                                literal("DATAFLOW"),
                                callsite_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("store"), ":", callsite_stack_symbols.c.callee_context
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(callsite_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                literal(BOT),
                                func.concat(
                                    literal("store"), ":", context_stack_symbols.c.stack_symbol
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                context_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("store"), ":", context_stack_symbols.c.stack_symbol
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                    )
                ),
                "dataflow_from_memory": (
                    union(
                        select(
                            [
                                literal("DATAFLOW"),
                                context_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_from_memory"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                literal(BOT),
                                func.concat(
                                    literal("dataflow_from_memory"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                callsite_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_from_memory"),
                                    ":",
                                    callsite_stack_symbols.c.callee_context,
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(callsite_stack_symbols),
                    )
                    if cls.is_reversed
                    else select(
                        [
                            literal("DATAFLOW"),
                            literal(BOT),
                            func.concat(
                                literal("dataflow_from_memory"),
                                ":",
                                context_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([context_stack_symbols.c.stack_symbol, literal(BOT)]).cast(
                                ARRAY(String)
                            ),
                        ],
                    ).select_from(context_stack_symbols)
                ),
                "dataflow_to_memory": (
                    select(
                        [
                            literal("DATAFLOW"),
                            literal(BOT),
                            func.concat(
                                literal("dataflow_to_memory"),
                                ":",
                                context_stack_symbols.c.stack_symbol,
                            ),
                            literal("DATAFLOW"),
                            array([context_stack_symbols.c.stack_symbol, literal(BOT)]).cast(
                                ARRAY(String)
                            ),
                        ],
                    ).select_from(context_stack_symbols)
                    if cls.is_reversed
                    else union(
                        select(
                            [
                                literal("DATAFLOW"),
                                context_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_to_memory"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                literal(BOT),
                                func.concat(
                                    literal("dataflow_to_memory"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                callsite_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_to_memory"),
                                    ":",
                                    callsite_stack_symbols.c.callee_context,
                                ),
                                literal("DATAFLOW"),
                                array([literal(BOT)]).cast(ARRAY(String)),
                            ],
                        ).select_from(callsite_stack_symbols),
                    )
                ),
                "dataflow_from_value": (
                    union(
                        select(
                            [
                                literal("DATAFLOW"),
                                context_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_from_value"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([context_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                literal(BOT),
                                func.concat(
                                    literal("dataflow_from_value"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([context_stack_symbols.c.stack_symbol, literal(BOT)]).cast(
                                    ARRAY(String)
                                ),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                callsite_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_from_value"),
                                    ":",
                                    callsite_stack_symbols.c.callee_context,
                                ),
                                literal("DATAFLOW"),
                                array([callsite_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                            ],
                        ).select_from(callsite_stack_symbols),
                    )
                    if cls.is_reversed
                    else union(
                        select(
                            [
                                literal("DATAFLOW"),
                                callsite_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_from_value"),
                                    ":",
                                    callsite_stack_symbols.c.callee_context,
                                ),
                                literal("DATAFLOW"),
                                array([callsite_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                            ],
                        ).select_from(callsite_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                literal(BOT),
                                func.concat(
                                    literal("dataflow_from_value"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([context_stack_symbols.c.stack_symbol, BOT]).cast(
                                    ARRAY(String)
                                ),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                context_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_from_value"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([context_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                    )
                ),
                "dataflow_to_value": (
                    union(
                        select(
                            [
                                literal("DATAFLOW"),
                                callsite_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_to_value"),
                                    ":",
                                    callsite_stack_symbols.c.callee_context,
                                ),
                                literal("DATAFLOW"),
                                array([callsite_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                            ],
                        ).select_from(callsite_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                literal(BOT),
                                func.concat(
                                    literal("dataflow_to_value"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([context_stack_symbols.c.stack_symbol, BOT]).cast(
                                    ARRAY(String)
                                ),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                context_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_to_value"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([context_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                    )
                    if cls.is_reversed
                    else union(
                        select(
                            [
                                literal("DATAFLOW"),
                                context_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_to_value"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([context_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                literal(BOT),
                                func.concat(
                                    literal("dataflow_to_value"),
                                    ":",
                                    context_stack_symbols.c.stack_symbol,
                                ),
                                literal("DATAFLOW"),
                                array([context_stack_symbols.c.stack_symbol, literal(BOT)]).cast(
                                    ARRAY(String)
                                ),
                            ],
                        ).select_from(context_stack_symbols),
                        select(
                            [
                                literal("DATAFLOW"),
                                callsite_stack_symbols.c.stack_symbol,
                                func.concat(
                                    literal("dataflow_to_value"),
                                    ":",
                                    callsite_stack_symbols.c.callee_context,
                                ),
                                literal("DATAFLOW"),
                                array([callsite_stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                            ],
                        ).select_from(callsite_stack_symbols),
                    )
                ),
            }

            graph.session.execute(
                insert(cls.transition_table).from_select(
                    ["old_state", "old_stack", "input", "new_state", "new_stack"],
                    union(*[rules[i] for i in rules]),
                )
            )
            cls.update_transition_table_statistics(graph)
            graph.session.commit()

    return CSDataflowPath


CSThinDataflowPath: Type[Path] = ConfigureDFGPath(thin=True)

CSDataflowPath: Type[Path] = ConfigureDFGPath(thin=False)


class CallGraphPath(CFLPath):
    @classmethod
    def table_name_prefix(cls) -> str:
        # The PDA tables are the same for all instances
        return "callgraph"

    @classmethod
    def initial_state(cls) -> ClauseElement:
        return literal("EMPTY").cast(String)

    @classmethod
    def initial_stack(cls) -> ClauseElement:
        return array([BOT]).cast(ARRAY(String))

    @classmethod
    def populate_edge_symbol_table(cls, graph: CPG) -> None:
        """Preprocess the graph's edge table and give each edge a symbol to be used during during
        CFL-based path extension."""

        if not cls._create_edge_symbol_table(graph):
            return

        # NOTE(lb): Any update to this query should be reflected in the class
        # docstring.
        edge_symbol_query = (
            select(
                [
                    graph.Edge.uuid,
                    graph.Edge.source,
                    graph.Edge.target,
                    func.concat(
                        graph.Edge.attributes["caller_context"].astext,
                        literal("-->"),
                        graph.Edge.attributes["callee_context"].astext,
                    ).label("symbol"),
                ]
            )
            .where(graph.Edge.kind == EdgeKind.CALLGRAPH)
            .alias()
        )

        graph.session.execute(
            insert(cls.edge_symbol_table).from_select(
                ["uuid", "source", "target", "symbol"],
                select(
                    [
                        edge_symbol_query.c.uuid,
                        edge_symbol_query.c.source,
                        edge_symbol_query.c.target,
                        edge_symbol_query.c.symbol,
                    ]
                ),
            )
        )
        cls.update_edge_symbol_table_statistics(graph)
        graph.session.commit()

    @classmethod
    def populate_transition_table(cls, graph: CPG) -> None:
        if not cls._create_transition_table(graph):
            return

        callgraph_edge_symbols = (
            select(
                [
                    graph.Edge.attributes["caller_context"].astext.label("caller"),
                    graph.Edge.attributes["callee_context"].astext.label("callee"),
                    func.concat(
                        graph.Edge.attributes["caller_context"].astext,
                        literal("-->"),
                        graph.Edge.attributes["callee_context"].astext,
                    ).label("symbol"),
                ]
            )
            .where(graph.Edge.kind == EdgeKind.CALLGRAPH)
            .alias()
        )

        # NOTE(lb): Any update to this query should be reflected in the class
        # docstring.
        rules = {
            "empty": select(
                [
                    literal("EMPTY"),
                    literal(BOT),
                    callgraph_edge_symbols.c.symbol,
                    literal("CONTEXT"),
                    (
                        array([callgraph_edge_symbols.c.caller]).cast(ARRAY(String))
                        if cls.is_reversed
                        else array([callgraph_edge_symbols.c.callee]).cast(ARRAY(String))
                    ),
                ]
            ).select_from(callgraph_edge_symbols),
            "context": select(
                [
                    literal("CONTEXT"),
                    (
                        callgraph_edge_symbols.c.callee
                        if cls.is_reversed
                        else callgraph_edge_symbols.c.caller
                    ),
                    callgraph_edge_symbols.c.symbol,
                    literal("CONTEXT"),
                    (
                        array([callgraph_edge_symbols.c.caller]).cast(ARRAY(String))
                        if cls.is_reversed
                        else array([callgraph_edge_symbols.c.callee]).cast(ARRAY(String))
                    ),
                ]
            ).select_from(callgraph_edge_symbols),
        }

        graph.session.execute(
            insert(cls.transition_table).from_select(
                ["old_state", "old_stack", "input", "new_state", "new_stack"],
                union(*[rules[i] for i in rules]),
            )
        )
        cls.update_transition_table_statistics(graph)
        graph.session.commit()
