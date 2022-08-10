from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import manticore.utils.log
from sqlalchemy.orm import Session

from dwarfcore.detectors.dwarf_variables import DwarfVariables
from dwarfcore.dwarfcore import DwarfCore
from dwarfcore.helper import setup_generic_manticore

if TYPE_CHECKING:
    from mate_query.cpg.models.core.cpg import CPG


def setup_generic_dwarf_variable(
    session: Session,
    cpg: CPG,
    prog: Path,
    prog_args: List[str],
    poi_funcs: Optional[List[str]],
    workspace_path: Optional[str] = None,
    fast=False,
):
    """Set up a generic instance of Manticore to look at functions' variables for object bounds.

    :param prog: Program file stream
    :param prog_args: Arguments to program
    :param poi_funcs: List of functions to look at the variables
    :param workspace_path: Where to store Manticore output. Default is current directory
    :return: An instance of Manticore ready to run()
    """
    dwarfcore = DwarfCore(session, cpg, prog)
    manticore.utils.log.init_logging()
    m = setup_generic_manticore(prog, prog_args, workspace_path=workspace_path, dwarfcore=dwarfcore)

    # Default plugins
    m.register_plugin(DwarfVariables(dwarfcore, poi_funcs, fast=fast))

    return m
