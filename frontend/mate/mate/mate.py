"""This module contains the logic for the entrypoint to the mate executable."""

import logging
from typing import Final, List

import IPython
from traitlets.config import Config

from mate import context, server
from mate.context import Command
from mate_common.models.cpg_types import Namespace
from mate_query import db

logger = logging.getLogger(__name__)

_MATE_BANNER: Final[
    str
] = """
Welcome to MATE's interactive (IPython) shell!

This shell environment has been pre-loaded with some useful state:

- `db`: A reference to `mate.db`
- `session`: A live database connection that can be used to connect to CPGs
"""


def main(ctxt: Namespace) -> None:
    ctxt.callback(ctxt)


def dispatch_serve(_ctxt: Namespace) -> None:
    server.Server().run()


def dispatch_pgshell(ctxt: Namespace) -> None:
    c = Config()
    c.TerminalInteractiveShell.banner2 = _MATE_BANNER

    db.initialize(ctxt.db, create=False)
    session = db.new_session()
    IPython.start_ipython(argv=[], config=c, user_ns={"db": db, "session": session})


def run_mate(args: List[str]) -> None:
    """Call ``mate`` as from CLI, providing a list of arguments."""
    ctxt = context.make_context(args)

    if ctxt.command == Command.serve.value:
        ctxt.callback = dispatch_serve
    elif ctxt.command == Command.pgshell.value:
        ctxt.callback = dispatch_pgshell
    else:
        logger.error("Weird: Unreachable case!")
    main(ctxt)
