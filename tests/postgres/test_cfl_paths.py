from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.sql.expression import case, insert, literal, select, union
from sqlalchemy.types import String

from mate_query.cfl import CFLPath
from mate_query.db import BOT, PathBuilder

if TYPE_CHECKING:
    from typing import Tuple, Type

    from sqlalchemy.sql.expression import ClauseElement

    from mate_query.db import Graph as CPG


def MakeParens(opens: Tuple[str, ...], closes: Tuple[str, ...]) -> Type[CFLPath]:
    class Parens(CFLPath):
        @classmethod
        def table_name_prefix(cls) -> str:
            return f"parens_{str(abs(hash(opens)))[:8]}_{str(abs(hash(closes)))[:8]}"

        @classmethod
        def initial_state(cls) -> ClauseElement:
            return literal("UNIT").cast(String)

        @classmethod
        def initial_stack(cls) -> ClauseElement:
            return array([BOT]).cast(ARRAY(String))

        @classmethod
        def populate_edge_symbol_table(cls, graph: CPG) -> None:
            if not cls._create_edge_symbol_table(graph):
                return

            graph.session.execute(
                insert(cls.edge_symbol_table).from_select(
                    ["uuid", "source", "target", "symbol"],
                    select(
                        [
                            graph.Edge.uuid,
                            graph.Edge.source,
                            graph.Edge.target,
                            case(
                                [
                                    (graph.Edge.uuid.in_(opens), "("),
                                    (graph.Edge.uuid.in_(closes), ")"),
                                ]
                            ).label("symbol"),
                        ]
                    ),
                )
            )
            graph.session.commit()

        @classmethod
        def populate_transition_table(cls, graph: CPG) -> None:
            if not cls._create_transition_table(graph):
                return

            stack_symbols = union(
                select([literal("(").label("stack_symbol")]),
                select([literal(")").label("stack_symbol")]),
                select([literal(BOT).label("stack_symbol")]),
            ).alias()

            rules = {
                "open": select(
                    [
                        literal("UNIT"),
                        stack_symbols.c.stack_symbol,
                        literal("("),
                        literal("UNIT"),
                        array([literal("("), stack_symbols.c.stack_symbol]).cast(ARRAY(String)),
                    ]
                ).select_from(stack_symbols),
                "close": select(
                    [
                        literal("UNIT"),
                        literal("("),
                        literal(")"),
                        literal("UNIT"),
                        array([]).cast(ARRAY(String)),
                    ]
                ).select_from(stack_symbols),
            }

            graph.session.execute(
                insert(cls.transition_table).from_select(
                    ["old_state", "old_stack", "input", "new_state", "new_stack"],
                    union(*[rules[i] for i in rules]),
                )
            )
            graph.session.commit()

    return Parens


def test_diamond_no_cfl_paths(session, diamond_graph):
    p = PathBuilder(MakeParens(tuple(), ("AB", "AC", "BD", "CD"))).build(
        diamond_graph, keep_edge=True, keep_trace=True
    )
    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {tuple()}


def test_diamond_one_cfl_path(session, diamond_graph):
    p = PathBuilder(MakeParens(("AB",), ("AC", "BD", "CD"))).build(
        diamond_graph, keep_edge=True, keep_trace=True
    )
    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {
        (),
        ("AB",),
        ("AB", "BD"),
    }


def test_diamond_two_cfl_paths(session, diamond_graph):
    p = PathBuilder(MakeParens(("AB", "AC"), ("BD", "CD"))).build(
        diamond_graph, keep_edge=True, keep_trace=True
    )
    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {
        (),
        ("AB",),
        ("AC",),
        ("AB", "BD"),
        ("AC", "CD"),
    }
