from mate_common.models.cpg_types import EdgeKind, Opcode
from mate_query import db


def test_stack_type_backpropagation(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "test-dataflow-small.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    sext = (
        session.query(cpg.Instruction)
        .filter(
            cpg.Instruction.opcode == Opcode.SEXT,
            cpg.Instruction.parent_block.has(
                cpg.Block.parent_function.has(cpg.Function.name == "stack")
            ),
        )
        .one()
    )

    neighborhood = (
        db.PathBuilder()
        .stopping_at(lambda Node: Node.uuid == sext.uuid)
        .continuing_while(
            lambda _, Edge: Edge.source_node.has(
                cpg.Instruction.parent_block.has(
                    cpg.Block.parent_function.has(cpg.Function.name == "stack")
                )
            )
        )
        .reverse()
        .build(cpg.dfg, keep_start=False)
    )
    loads = (
        session.query(neighborhood)
        .join(cpg.Instruction, cpg.Instruction.uuid == neighborhood.source)
        .filter(cpg.Instruction.opcode == Opcode.LOAD)
        .with_entities(cpg.Instruction)
        .all()
    )
    assert len(loads) > 0
    for load in loads:
        assert (
            session.query(cpg.Edge)
            .filter(cpg.Edge.target == load.uuid, cpg.Edge.kind == EdgeKind.LOAD_MEMORY)
            .count()
        ) > 0
