import base64
from pathlib import Path
from typing import List

import pytest
from manticore.core.plugin import Plugin
from manticore.core.smtlib import BitVecVariable, Operators
from manticore.native.state import State

from dwarfcore.detectors.dwarf_variables import DwarfVariables
from dwarfcore.examples.example_variable_general import setup_generic_dwarf_variable
from mate.build.tob_chess_utils.dwarf import FieldOffset, cpg_dwarf_unroll_type_info


def _normalize_unrolled_struct_fields(fields: List[FieldOffset]):
    return [(field.offset, field.field.name.full_name) for field in fields]


# 3-tuple of (program, type_name, struct_fields)
STRUCT_TEST_PARAMS = [
    (
        "struct_bounds.c",
        "authentication",
        [
            (0, "authentication.buffer"),
            (9, "authentication.<pad>"),
            (12, "authentication.authenticated"),
            (16, "authentication.catch_buffer"),
        ],
    ),
    (
        "nested_structs.c",
        "authentication",
        [
            (0, "authentication.buffer"),
            (9, "authentication.<pad>"),
            (12, "authentication.authenticated"),
            (16, "authentication.nest.buf"),
            (36, "authentication.nest.large"),
        ],
    ),
    (
        "triple_nested_structs.c",
        "authentication",
        [
            (0, "authentication.buffer"),
            (9, "authentication.<pad>"),
            (12, "authentication.authenticated"),
            (16, "authentication.nest.buf"),
            (36, "authentication.nest.<pad>"),
            (40, "authentication.nest.second.hello"),
            (48, "authentication.nest.second.third.buf"),
            (53, "authentication.nest.second.third.large"),
            (71, "authentication.nest.second.<pad>"),
            (72, "authentication.nest.second.why"),
            (76, "authentication.nest.second.<pad>"),
            (80, "authentication.end"),
        ],
    ),
]


@pytest.mark.parametrize("program,type_name,struct_fields", STRUCT_TEST_PARAMS)
def test_struct_unroller(session, dc_cpg_v2, program, type_name, struct_fields):
    (cpg, _) = dc_cpg_v2(program, compile_options=dict(extra_compiler_flags=("-O1",)))
    type_node = session.query(cpg.DWARFType).filter_by(name=type_name).one()
    unrolled_type_info = cpg_dwarf_unroll_type_info(session, cpg, type_node)
    assert _normalize_unrolled_struct_fields(unrolled_type_info.field_offsets) == struct_fields


class ConcretePlugin(Plugin):
    """Manticore concrete plugin that uses Unicorn to concretely execute the beginning of the
    program."""

    def __init__(self, stop_va: int):
        """Initialize the plugin with where to stop emulation.

        :param stop_va:
        """
        super().__init__()
        self.stop_va = stop_va

    def will_run_callback(self, *_args):
        for state in self.manticore.ready_states:
            state.cpu.emulate_until(self.stop_va)


def test_nested_overflow_detection(session, dc_cpg_v2, tmp_path):
    """Test the ability for Manticore to detect overflow of struct fields."""
    (cpg, test_bin) = dc_cpg_v2(
        "triple_nested_structs.c", compile_options=dict(extra_compiler_flags=("-O1",))
    )
    poi_func = "overflow_field"

    symb_var_name = "ARGV_index"

    m = setup_generic_dwarf_variable(
        session, cpg, test_bin, prog_args=["10"], poi_funcs=[poi_func], workspace_path=str(tmp_path)
    )

    # Not the nicest way, but should do for now
    dwarfvar_plugin = next(
        inst for plug_name, inst in m.plugins.items() if isinstance(inst, DwarfVariables)
    )
    poi_func_addr = dwarfvar_plugin.dwarfcore.start_va_of_function_m(poi_func)

    # Fast concrete unicorn run until start of poi_func
    m.register_plugin(ConcretePlugin(poi_func_addr))

    # We've used a concrete argv, but now we want to make the argv symbolic
    @m.hook(poi_func_addr)
    def _unconstrain_arg(state: State):
        if state.constraints.get_variable(symb_var_name):
            return
        # New symbolic 4-byte integer value
        symb_argv: BitVecVariable = state.new_symbolic_value(4 * 8, symb_var_name)
        # EDI is the first argument (an integer)
        state.cpu.write_register("EDI", symb_argv)
        # Clone a few more states to test other constraints
        # Constrain to interesting values
        with state as new_state:
            # Way out of bounds
            new_state.constrain(Operators.AND(0 <= symb_argv, symb_argv <= 200))
            m._put_state(new_state)
        with state as new_state:
            # In-bounds of struct, but not a particular field
            new_state.constrain(Operators.AND(0 <= symb_argv, symb_argv <= 50))
            m._put_state(new_state)
        # In-bounds of struct and a particular field
        state.constrain(Operators.AND(0 <= symb_argv, symb_argv <= 3))

    m.run()
    m.kill()

    results = dwarfvar_plugin.results

    # We expect to see the case where 0 <= index <= 50 and 0 <= index <= 200 generate test cases because
    # it's an overflow, but # 0 <= index <= 3 case is within bounds
    expected_vals = [0, 0, 50, 200, 200]
    # Should detect 5 test cases, two 0 and 50 and two 200, but not 0 and 3 because they're in the same field
    # Two 200 because it is out of bounds of all variables as well as MIN-MAX pointing to different variables
    # assert len(argv_outs) == 5
    seen_vals = []
    # Where the detector saw it in the source code
    locations = []
    for result in results:
        locations.append(result.description)
        for sym_input in result.symbolic_inputs:
            if sym_input.name.startswith("ARGV_"):
                for sym_val in sym_input.symbolic_values:
                    seen_vals.append(int(base64.b64decode(sym_val.concrete_value_base64)))
    seen_vals = sorted(seen_vals)

    # Check that we've seen our expected values
    assert expected_vals == seen_vals

    # Check the line number is correct
    assert all("triple_nested_structs.c:32" in loc for loc in list(locations))


def test_simple_overunderflow_detection(session, dc_cpg_v2, tmp_path):
    """Test a simple unbound symbolic index variable to detect lower and upper bounds of the index
    and determine if accesses are outside of any variable size bounds.

    See the C source code for the binary in
    its respective directory.
    :return:
    """
    (cpg, bin_name) = dc_cpg_v2(
        "ex_symb_index.c", compile_options=dict(extra_compiler_flags=("-O1",))
    )
    # Send two symbolic bytes, which should be enough for intervals (-9,-1), (0,9), (10,99) when using
    # the atoi function, but the (0,9) won't be listed because those are actually within variable size
    # bounds. However, index 10 is still in bounds, but the upper bound is not, so it's interesting
    # We only test the bounds, since Manticore solves for min and max
    expected_vals = {"-9", "-1", "10", "99"}

    m = setup_generic_dwarf_variable(
        session, cpg, bin_name, prog_args=["++"], poi_funcs=["oob"], workspace_path=str(tmp_path)
    )
    m.run()
    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))

    assert len(argv_outs) > 0
    seen_vals = set()
    for argv_out in argv_outs:
        with argv_out.open() as f:
            argv_str = f.readline().strip()
            seen_vals.add(argv_str)
    # Check that we've seen everything
    assert seen_vals == expected_vals


def test_explore_simple_overunderflow_detection(session, dc_cpg_v2, tmp_path):
    """Test a simple unbound symbolic index variable to detect lower and upper bounds of the index
    and determine if accesses are outside of any variable size bounds.

    Uses exploration mode with no specific function to look at.

    See the C source code for the binary in
    its respective directory.
    :return:
    """
    (cpg, bin_name) = dc_cpg_v2(
        "ex_symb_index.c", compile_options=dict(extra_compiler_flags=("-O1",))
    )
    # Send two symbolic bytes, which should be enough for intervals (-9,-1), (0,9), (10,99) when using
    # the atoi function, but the (0,9) won't be listed because those are actually within variable size
    # bounds. However, index 10 is still in bounds, but the upper bound is not, so it's interesting
    # We only test the bounds, since Manticore solves for min and max
    expected_vals = {"-9", "-1", "10", "99"}

    m = setup_generic_dwarf_variable(
        session, cpg, bin_name, prog_args=["++"], poi_funcs=None, workspace_path=str(tmp_path)
    )
    m.run()
    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))

    assert len(argv_outs) > 0
    seen_vals = set()
    for argv_out in argv_outs:
        with argv_out.open() as f:
            argv_str = f.readline().strip()
            seen_vals.add(argv_str)
    # Check that we've seen everything
    assert seen_vals == expected_vals


def test_explore_oob_detection_kernel_cve(session, dc_cpg_v2, tmp_path):
    """Test to make sure we don't find anything in the kernel cve.

    Uses exploration mode with no specific function to look at.

    See the C source code for the binary in
    its respective directory.
    :return:
    """
    (cpg, bin_name) = dc_cpg_v2(
        "poi-kernel-cve-uninit.c", compile_options=dict(extra_compiler_flags=("-O0",))
    )

    m = setup_generic_dwarf_variable(
        session, cpg, bin_name, prog_args=[], poi_funcs=None, workspace_path=str(tmp_path)
    )
    m.run()
    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))

    assert len(argv_outs) == 0


# Debugging test case. Doesn't actually stop running because there's nothing to
# find and the program is a 'while True'
# def test_explore_oob_detection_example_1(session, dc_cpg_v2, tmp_path):
#     """Test to make sure we don't find anything in the kernel cve.
#
#     Uses exploration mode with no specific function to look at.
#
#     See the C source code for the binary in
#     its respective directory.
#     :return:
#     """
#     (cpg, bin_name) = dc_cpg_v2("example_1.c")
#
#     m = setup_generic_dwarf_variable(
#         session,
#         cpg,
#         bin_name,
#         prog_args=["HELLO", "GOODBYE"],
#         poi_funcs=None,
#         workspace_path=str(tmp_path),
#     )
#     try:
#         m.run()
#     except Exception as e:
#         pytest.fail(f"Got an error during Manticore run: {e}")
#     # Get the workspace directory and check test cases for generated `argv` values
#     argv_outs = list(Path(m.workspace).glob("test_*.argv"))
#
#     assert len(argv_outs) == 0
