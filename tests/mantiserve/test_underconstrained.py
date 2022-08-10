import manticore.utils.log
import pytest

from dwarfcore.helper import manticore_explore
from mantiserve.logging import logger
from mate_common.models.integration import DetectAllPathsOptions, Detector, ExploreFunction


def test_underconstrained_symbex_no_fork(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "hello.c", "foo")

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 1
    )


def test_underconstrained_symbex_three_forks(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "ex_simple.c", "foo")

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 4
    )


def test_underconstrained_symbex_struct_ptr(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "struct-by-ptr.c", "func")

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 2
    )


def test_underconstrained_symbex_symbolic_offset_read(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2, session, tmp_path, "underconstrained_symbolic_offset_read.c", "func"
    )

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 2
    )


def test_underconstrained_symbex_symbolic_offset_write(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2, session, tmp_path, "underconstrained_symbolic_offset_write.c", "func"
    )

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 2
    )


def test_underconstrained_symbex_virtual_method(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2, session, tmp_path, "underconstrained_virtual_method.cpp", "_Z4funcP5Value"
    )

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 2
    )


def test_underconstrained_symbex_complex_inheritance(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2, session, tmp_path, "underconstrained_complex_inheritance.cpp", "_Z4funcP5Value"
    )

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 2
    )


def test_underconstrained_symbex_complex_inheritance2(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2, session, tmp_path, "underconstrained_complex_inheritance2.cpp", "_Z4funcP5Value"
    )

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 2
    )


def test_underconstrained_symbex_complex_inheritance3(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2, session, tmp_path, "underconstrained_complex_inheritance3.cpp", "_Z4funcP5Value"
    )

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 3
    )


def test_underconstrained_oob_read(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "underconstrained_oob_read.c", "func")

    assert _count_unique_oob_errors(ret_msg.exploration_tree) == 1


def test_underconstrained_oob_write(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "underconstrained_oob_write.c", "func")

    assert _count_unique_oob_errors(ret_msg.exploration_tree) == 1


def test_underconstrained_minimised_garfield_setchr(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2,
        session,
        tmp_path,
        "garfield_minimised_setchr.cpp",
        "_Z14setchr_builtinP5ValueS0_i",
    )

    assert _count_unique_oob_errors(ret_msg.exploration_tree) == 1


def test_underconstrained_garfield_setchr_user_constraint(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2,
        session,
        tmp_path,
        "garfield_minimised_setchr.cpp",
        "_Z14setchr_builtinP5ValueS0_i",
        constraints=["a->s.length == $LEN(a->s.s)", "loc > 0", "loc < $LEN(a->s.s)"],
    )

    assert _count_unique_oob_errors(ret_msg.exploration_tree) == 0


@pytest.mark.xfail(reason="Probably failing because of FXRSTOR with too much symbolic data")
def test_underconstrained_minimised_garfield_substr(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2, session, tmp_path, "garfield_minimised_substr.cpp", "_Z14substr_builtinP5Valueii"
    )

    assert _count_unique_oob_errors(ret_msg.exploration_tree) == 1


def test_underconstrained_cpp_vector(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2,
        session,
        tmp_path,
        "underconstrained_cpp_vector.cpp",
        "_Z4funcRSt6vectorIiSaIiEE",
        constraints=[
            # For this test only, constrain the initial vector size to be two elements
            "vector<#,#>: $SIZE($OBJ) == 2",
            "vector<#,#>: $OBJ._M_impl._M_finish - $OBJ._M_impl._M_start == $SIZE($OBJ)*$TYPESIZE(#0)",
            "vector<#,#>: $OBJ._M_impl._M_end_of_storage == $OBJ._M_impl._M_start + ($CAPACITY($OBJ)*$TYPESIZE(#0))",
            "vector<#,#>: $LEN($OBJ._M_impl._M_start) == $CAPACITY($OBJ)",
            "vector<#,#>: $CAPACITY($OBJ) == 100",
            # Sanity constraints on internal pointers
            "vector<#,#>: $POINTS_WITHIN($OBJ._M_impl._M_finish, $OBJ._M_impl._M_start)",
            "vector<#,#>: $POINTS_WITHIN($OBJ._M_impl._M_end_of_storage, $OBJ._M_impl._M_start)",
        ],
    )

    assert _count_unique_oob_errors(ret_msg.exploration_tree) == 0

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.DetectAllPaths])
        == 1
    )


def test_underconstrained_timeout(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(
        dc_cpg_v2,
        session,
        tmp_path,
        "underconstrained_cpp_vector.cpp",
        "_Z4funcRSt6vectorIiSaIiEE",
        timeout=1,  # timeout after 1 second, not enough to reach the bug
    )

    assert _count_unique_oob_errors(ret_msg.exploration_tree) == 0


def test_underconstrained_concrete_heap_oob(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "heap_oob.cpp", "_Z4funcv")

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.ConcreteHeapOOB])
        == 1
    )


def test_underconstrained_concrete_heap_oob_2(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "heap_oob.cpp", "_Z5func3v")

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.ConcreteHeapOOB])
        == 1
    )


def test_underconstrained_concrete_heap_oob_3(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "heap_oob.cpp", "_Z5func4v")

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.ConcreteHeapOOB])
        == 1
    )


def test_underconstrained_concrete_heap_oob_4(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "heap_oob.cpp", "_Z5func2v")

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.ConcreteHeapOOB])
        == 1
    )


def test_underconstrained_concrete_heap_oob_malloc(session, dc_cpg_v2, tmp_path):
    ret_msg = _explore(dc_cpg_v2, session, tmp_path, "heap_oob_malloc.c", "func")

    assert (
        len([case for case in ret_msg.cases if case.detector_triggered is Detector.ConcreteHeapOOB])
        == 1
    )


def _explore(dc_cpg_v2, session, tmp_path, filename, function_name, constraints=None, timeout=None):
    compile_options = (
        dict(extra_compiler_flags=["-std=c++17"]) if filename.endswith(".cpp") else dict()
    )
    (cpg, bin_name) = dc_cpg_v2(filename, compile_options=compile_options)

    detector_options = [DetectAllPathsOptions(detector=Detector.DetectAllPaths)]

    msg = ExploreFunction(
        command_line_flags=[],
        target_function=function_name,
        input_constraints=[] if constraints is None else constraints,
        detector_options=detector_options,
        timeout=timeout,
    )
    manticore.utils.log.init_logging()
    return manticore_explore(bin_name, session, cpg, msg, logger, manticore_workspace=str(tmp_path))


def _count_unique_oob_errors(tree) -> int:
    """Count OOB errors and discard duplicates by using the faulty instruction address as a key."""
    error_addresses = set()
    res = 0
    if tree is None:
        return 0
    for case in tree.iter_cases():
        if (
            case.detector_triggered is Detector.UnderconstrainedOOB
            and case.va not in error_addresses
        ):
            res += 1
            error_addresses.add(case.va)
    return res
