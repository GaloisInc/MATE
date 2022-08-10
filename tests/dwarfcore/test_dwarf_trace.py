import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest
from manticore.native import Manticore

from dwarfcore.examples.example_trace_general import setup_generic_dwarf_tracer
from dwarfcore.plugins.dwarf_trace import DwarfTrace


def _extract_manti_traces(manticore: Manticore) -> List[List[str]]:
    """Searches for DWARF trace files in Manticores workspace.

    :param manticore: An instance of manticore to extract trace files from workspace
    :return: A list of traces (a trace is a list itself)
    """
    trace_paths = list(Path(manticore.workspace).glob(f"{DwarfTrace.trace_file}*"))
    all_traces = []
    for trace_path in trace_paths:
        with trace_path.open() as f:
            trace_reader = csv.reader(f)
            # Get rid of header
            trace_content = list(trace_reader)[1:]
            trace = []
            for row in trace_content:
                # Only grab function
                trace.append(row[0].strip())
            all_traces.append(trace)
    return all_traces


DWARFCORE_BIN_PATH = Path(__file__).resolve().parent / "binaries"


@dataclass(frozen=True)
class GoldInfo:
    prog_name: str
    # The command line used to run the program with respective output
    prog_invocation: List[str]
    # A list of all outputs (which are lists of strings)
    expected_outs: List[List[str]]


# Delimiter for multiple outputs in a gold file
GOLD_MULTI_OUT_DELIM: str = "=" * 20


def parse_gold_file(gold_path: Path) -> GoldInfo:
    with gold_path.open() as f:
        prog_invocation = f.readline().strip().split()
        prog_name = prog_invocation[0]
        output = f.readlines()
        outputs: List[List[str]] = [[]]
        num_outputs = 0
        for line in output:
            line = line.strip()
            if line == GOLD_MULTI_OUT_DELIM:
                outputs.append([])
                num_outputs += 1
            else:
                outputs[num_outputs].append(line)
        return GoldInfo(prog_name=prog_name, prog_invocation=prog_invocation, expected_outs=outputs)


GOLD_FILES = ["ex_simple.conc.O1.gold", "ex_simple.symb.O1.gold"]


@pytest.mark.parametrize("gold_file", GOLD_FILES)
def test_func_tracer(session, dc_cpg_v2, gold_file: str, tmp_path):
    gold_info = parse_gold_file(Path(DWARFCORE_BIN_PATH / gold_file))

    (cpg, test_bin) = dc_cpg_v2(
        gold_info.prog_name, compile_options=dict(extra_compiler_flags=("-O1",))
    )
    m = setup_generic_dwarf_tracer(
        session, cpg, test_bin, gold_info.prog_invocation[1:], workspace_path=str(tmp_path)
    )
    m.run()
    traces = _extract_manti_traces(m)

    # Apparently, Mypy can't tell that "tuple" is both a Type and a Callable.
    assert set(map(tuple, traces)) == set(map(tuple, gold_info.expected_outs))  # type: ignore
