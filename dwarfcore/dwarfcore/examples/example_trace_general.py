from pathlib import Path
from typing import List, Optional

import manticore.utils.log
from sqlalchemy.orm import Session

from dwarfcore.dwarfcore import DwarfCore
from dwarfcore.helper import setup_generic_manticore
from dwarfcore.plugins.dwarf_trace import DwarfTrace
from mate_query.db import Graph as CPG


def setup_generic_dwarf_tracer(
    session: Session,
    cpg: CPG,
    prog: Path,
    prog_args: List[str],
    workspace_path: Optional[str] = None,
):
    """Set up a generic instance of Manticore to record a trace of function calls using DWARF debug
    info.

    :param prog: Program file stream
    :param prog_args: Arguments to program
    :param workspace_path: Where to store Manticore output. Default is current directory
    :return: An instance of Manticore ready to run()
    """
    dwarfcore = DwarfCore(session, cpg, prog)
    manticore.utils.log.init_logging()
    m = setup_generic_manticore(prog, prog_args, workspace_path=workspace_path, dwarfcore=dwarfcore)

    # Default plugins
    m.register_plugin(DwarfTrace(dwarfcore))

    return m
