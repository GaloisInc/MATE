from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import manticore.utils.log
from sqlalchemy.orm import Session

from dwarfcore.detectors.uaf import DetectUseAfterFree
from dwarfcore.dwarfcore import DwarfCore
from dwarfcore.helper import setup_generic_manticore
from mate_common.models.integration import FreeUseInfo

if TYPE_CHECKING:
    from typing import List, Optional

    from mate_query.cpg.models.core.cpg import CPG


def setup_generic_uaf_detector_use(
    session: Session,
    cpg: CPG,
    prog: Path,
    prog_args: List[str],
    poi_info: Optional[List[FreeUseInfo]] = None,
    workspace_path: Optional[str] = None,
    concrete_start: str = "",
    stdin_size: Optional[int] = None,
    fast=False,
):
    """Set up a generic instance of Manticore to examine a program's heap and detect when memory is
    being used after freed.

    :param cpg: CPG handle
    :param prog: Program file path
    :param prog_args: Arguments to program
    :param poi_info: POI information to use
    :param workspace_path: Where to store Manticore output. Default is current directory
    :param concrete_start: String of concrete bytes to append to the beginning of stdin
    :param stdin_size: Number of symbolic bytes after concrete_start available in stdin
    :return: An instance of Manticore ready to run()
    """
    manticore.utils.log.init_logging()
    dwarfcore = DwarfCore(session, cpg, prog)
    m = setup_generic_manticore(
        prog,
        prog_args,
        workspace_path=workspace_path,
        concrete_start=concrete_start,
        stdin_size=stdin_size,
        dwarfcore=dwarfcore,
    )

    # Plugins
    m.register_plugin(DetectUseAfterFree(dwarfcore, m, poi_info, fast=fast))

    return m
