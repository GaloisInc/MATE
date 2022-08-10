from pathlib import Path
from typing import List

from dwarfcore.detectors.uaf import DetectUseAfterFree
from dwarfcore.examples.example_heap_detect import setup_generic_uaf_detector_use
from mate_common.models.integration import FreeUseInfo, ReachingTestCase

_PROGRAMS_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent / "frontend" / "test" / "programs"
)


def test_simple_uaf_read(session, dc_cpg_v2, tmp_path):
    """Test a simple use after free reading from a freed node within a linked list."""
    (cpg, bin_name) = dc_cpg_v2("simple-uaf-read.c")

    m = setup_generic_uaf_detector_use(
        session,
        cpg,
        bin_name,
        prog_args=[],
        workspace_path=str(tmp_path),
    )
    m.run()

    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))
    assert len(argv_outs) == 1

    results: List[ReachingTestCase] = m.context.get(DetectUseAfterFree.MCORE_TESTCASE_LIST)
    assert len(results) == 1
    assert "reading" in results[0].description
    assert "24" in results[0].description
    assert "20" in results[0].description


def test_simple_uaf_write(session, dc_cpg_v2, tmp_path):
    """Test a simple use after free writing to a freed node within a linked list."""
    (cpg, bin_name) = dc_cpg_v2("simple-uaf-write.c")

    m = setup_generic_uaf_detector_use(
        session,
        cpg,
        bin_name,
        prog_args=[],
        workspace_path=str(tmp_path),
    )
    m.run()

    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))
    assert len(argv_outs) == 1

    results: List[ReachingTestCase] = m.context.get(DetectUseAfterFree.MCORE_TESTCASE_LIST)
    assert len(results) == 1
    assert "writing" in results[0].description
    assert "27" in results[0].description
    assert "23" in results[0].description


def test_simple_uaf_read_poi(session, dc_cpg_v2, tmp_path):
    """Test a simple use after free reading from a freed node within a linked list."""
    (cpg, bin_name) = dc_cpg_v2("simple-uaf-read.c")

    free_use_path = _PROGRAMS_PATH / "simple-uaf-read.c"
    assert free_use_path.exists()

    # Look for the the second UAF on the path
    poi_info = [FreeUseInfo(str(free_use_path.name), 25, str(free_use_path.name), 20)]

    m = setup_generic_uaf_detector_use(
        session, cpg, bin_name, prog_args=[], workspace_path=str(tmp_path), poi_info=poi_info
    )
    m.run()

    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))
    assert len(argv_outs) == 1

    results: List[ReachingTestCase] = m.context.get(DetectUseAfterFree.MCORE_TESTCASE_LIST)
    assert len(results) == 1
    assert "reading" in results[0].description
    assert "25" in results[0].description
    assert "20" in results[0].description


def test_simple_uaf_write_poi(session, dc_cpg_v2, tmp_path):
    """Test a simple use after free writing to a freed node within a linked list."""
    (cpg, bin_name) = dc_cpg_v2("simple-uaf-write.c")

    free_use_path = _PROGRAMS_PATH / "simple-uaf-write.c"
    assert free_use_path.exists()

    poi_info = [FreeUseInfo(str(free_use_path.name), 27, str(free_use_path.name), 23)]

    m = setup_generic_uaf_detector_use(
        session, cpg, bin_name, prog_args=[], workspace_path=str(tmp_path), poi_info=poi_info
    )
    m.run()

    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))
    assert len(argv_outs) == 1

    results: List[ReachingTestCase] = m.context.get(DetectUseAfterFree.MCORE_TESTCASE_LIST)
    assert len(results) == 1
    assert "writing" in results[0].description
    assert "27" in results[0].description
    assert "23" in results[0].description


def test_poi_incorrect_line_num(session, dc_cpg_v2, tmp_path):
    """Test a simple use after free writing to a freed node within a linked list."""
    (cpg, bin_name) = dc_cpg_v2("simple-uaf-write.c")

    free_use_path = _PROGRAMS_PATH / "simple-uaf-read.c"
    assert free_use_path.exists()

    poi_info = [FreeUseInfo(str(free_use_path.name), 12, str(free_use_path.name), 100)]

    m = setup_generic_uaf_detector_use(
        session, cpg, bin_name, prog_args=[], workspace_path=str(tmp_path), poi_info=poi_info
    )
    m.run()

    # Get the workspace directory and check test cases for generated `argv` values
    argv_outs = list(Path(m.workspace).glob("test_*.argv"))

    # This binary contains a UAF but it is not the one of interest
    assert not len(argv_outs)


def test_mini_fenway_uaf_detect(session, dc_cpg_v2, tmp_path):
    """Test detecting mini-feway uaf with concrete stdin."""
    (cpg, bin_name) = dc_cpg_v2("mini-fenway-uaf.c")
    concrete_start = "A00000000ABCDEFGH.ppm\nB00000000ABCDEFGH.ppm\n"

    m = setup_generic_uaf_detector_use(
        session,
        cpg,
        bin_name,
        prog_args=[],
        workspace_path=str(tmp_path),
        concrete_start=concrete_start,
        stdin_size=0,
        fast=True,
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

    results: List[ReachingTestCase] = m.context.get(DetectUseAfterFree.MCORE_TESTCASE_LIST)
    assert len(results) == 1
    assert "reading" in results[0].description
    assert "188" in results[0].description
    assert "76" in results[0].description
