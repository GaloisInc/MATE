from pathlib import Path
from typing import List

from dwarfcore.detectors.uninitialized_stack_variable import DetectUninitializedStackVariable
from dwarfcore.examples.example_uninit_variable_use_detect import setup_generic_uninit_stack_var_use
from mate_common.models.integration import FunctionVariableInfo, ReachingTestCase


def test_uninit_stack_var_use(session, dc_cpg_v2, tmp_path):
    """Test a simple use before assignment for a stack variable."""
    # NOTE(ek): Will not work using default flags because our program is unsafe
    # and -Werror makes it fail. Also, optimization of -O1 will make this test
    # fail due to optimizations foregoing a call to our vulnerable function
    (cpg, bin_name) = dc_cpg_v2(
        "uninit-stack-var-use.c", compile_options=dict(extra_compiler_flags=("-O0",))
    )

    m = setup_generic_uninit_stack_var_use(
        session,
        cpg,
        bin_name,
        prog_args=[],
        poi_info=[FunctionVariableInfo("vuln", "res")],
        workspace_path=str(tmp_path),
    )
    m.run()
    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))

    assert len(argv_outs) == 1
    seen_vals = set()
    for argv_out in argv_outs:
        with argv_out.open() as f:
            argv_str = f.readline().strip()
            seen_vals.add(argv_str)


def test_uninit_stack_array_use(session, dc_cpg_v2, tmp_path):
    """Test a simple stack array element use before assignment."""
    # NOTE(ek): Will not work using default flags because our program is unsafe
    # and -Werror makes it fail. Also, optimization of -O1 will make this test
    # fail due to optimizations foregoing a call to our vulnerable function
    (cpg, bin_name) = dc_cpg_v2(
        "uninit-stack-array-use.c", compile_options=dict(extra_compiler_flags=("-O0",))
    )

    m = setup_generic_uninit_stack_var_use(
        session,
        cpg,
        bin_name,
        prog_args=[],
        poi_info=[FunctionVariableInfo("vuln", "res")],
        workspace_path=str(tmp_path),
    )
    m.run()
    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))

    assert len(argv_outs) == 1
    seen_vals = set()
    for argv_out in argv_outs:
        with argv_out.open() as f:
            argv_str = f.readline().strip()
            seen_vals.add(argv_str)


def test_init_stack_struct_array_use(session, dc_cpg_v2, tmp_path):
    """Test a simple stack struct array member use before assignment."""
    (cpg, bin_name) = dc_cpg_v2("triple_nested_structs.c")

    m = setup_generic_uninit_stack_var_use(
        session,
        cpg,
        bin_name,
        prog_args=["4"],
        poi_info=[FunctionVariableInfo("overflow_field", "auth")],
        workspace_path=str(tmp_path),
    )
    m.run()
    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))

    assert len(argv_outs) == 0
    seen_vals = set()
    for argv_out in argv_outs:
        with argv_out.open() as f:
            argv_str = f.readline().strip()
            seen_vals.add(argv_str)


def test_uninit_stack_struct_array_use(session, dc_cpg_v2, tmp_path):
    """Test a simple stack struct array member use before assignment."""
    (cpg, bin_name) = dc_cpg_v2("triple_nested_structs.c")

    m = setup_generic_uninit_stack_var_use(
        session,
        cpg,
        bin_name,
        prog_args=["24"],
        poi_info=[FunctionVariableInfo("overflow_field", "auth")],
        workspace_path=str(tmp_path),
    )
    m.run()
    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))

    assert len(argv_outs) == 1
    seen_vals = set()
    for argv_out in argv_outs:
        with argv_out.open() as f:
            argv_str = f.readline().strip()
            seen_vals.add(argv_str)


def test_uninit_explore_kernel_cve_dwarfcore(session, dc_cpg_v2, tmp_path):
    """Test that Manticore is able to find the uninitialized stack variable use by just exploring
    through the program with nothing specific to look for."""
    (cpg, bin_name) = dc_cpg_v2(
        "poi-kernel-cve-uninit.c", compile_options=dict(extra_compiler_flags=("-O0",))
    )

    m = setup_generic_uninit_stack_var_use(
        session,
        cpg,
        bin_name,
        prog_args=[],
        poi_info=None,
        workspace_path=str(tmp_path),
        fast=True,
    )
    m.run()

    results: List[ReachingTestCase] = m.context.get(
        DetectUninitializedStackVariable.MCORE_TESTCASE_LIST
    )
    assert len(results) == 1

    assert "txc.tai" in results[0].description


def test_uninit_kernel_cve_dwarfcore(session, dc_cpg_v2, tmp_path):
    """Test that Manticore is able to find the uninitialized stack variable use in the specified
    function with the specified variable."""
    (cpg, bin_name) = dc_cpg_v2(
        "poi-kernel-cve-uninit.c", compile_options=dict(extra_compiler_flags=("-O0",))
    )

    m = setup_generic_uninit_stack_var_use(
        session,
        cpg,
        bin_name,
        prog_args=[],
        poi_info=[FunctionVariableInfo("syscall_adjtimex", "txc")],
        workspace_path=str(tmp_path),
        fast=True,
    )
    m.run()

    results: List[ReachingTestCase] = m.context.get(
        DetectUninitializedStackVariable.MCORE_TESTCASE_LIST
    )
    assert len(results) == 1

    assert "txc.tai" in results[0].description


# Debugging test case. Doesn't actually stop running because there's nothing to
# find and the program is a 'while True'
# def test_uninit_example_1(session, dc_cpg_v2, tmp_path):
#    """Test that Manticore is able to find the uninitialized stack variable use in the specified
#    function with the specified variable."""
#    (cpg, bin_name) = dc_cpg_v2("example_1.c", compile_options=dict(extra_compiler_flags=("-O0",)))
#
#    m = setup_generic_uninit_stack_var_use(
#        session,
#        cpg,
#        bin_name,
#        prog_args=['HELLO', 'GOODBYE'],
#        poi_info=None,
#        workspace_path=str(tmp_path),
#        fast=True,
#    )
#    try:
#        m.run()
#    except Exception as e:
#        pytest.fail(f"Got an error during Manticore run: {e}")
#
#    results: List[ReachingTestCase] = m.context.get(
#        DetectUninitializedStackVariable.MCORE_TESTCASE_LIST
#    )
#    assert len(results) == 0
