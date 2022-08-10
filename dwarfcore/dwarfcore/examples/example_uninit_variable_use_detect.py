from pathlib import Path
from typing import List, Optional

import manticore.utils.log

from dwarfcore.detectors.uninitialized_stack_variable import DetectUninitializedStackVariable
from dwarfcore.dwarfcore import DwarfCore
from dwarfcore.helper import setup_generic_manticore
from mate_common.models.integration import FunctionVariableInfo
from mate_query import db


def setup_generic_uninit_stack_var_use(
    session: db.Session,
    cpg: db.Graph,
    prog: Path,
    prog_args: List[str],
    poi_info: Optional[List[FunctionVariableInfo]] = None,
    workspace_path: Optional[str] = None,
    fast=False,
):
    """Set up a generic instance of Manticore to look at functions' stack variables and detect use
    before initialization.

    :param cpg: CPG handle
    :param prog: Program file path
    :param prog_args: Arguments to program
    :param poi_info: POI information to use
    :param workspace_path: Where to store Manticore output. Default is current directory
    :return: An instance of Manticore ready to run()
    """
    dwarfcore = DwarfCore(session, cpg, prog)
    manticore.utils.log.init_logging()
    m = setup_generic_manticore(prog, prog_args, workspace_path=workspace_path, dwarfcore=dwarfcore)

    # Plugins
    m.register_plugin(DetectUninitializedStackVariable(dwarfcore, poi_info, fast=fast))

    return m
