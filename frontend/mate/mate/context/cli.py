import argparse
import enum
import os
from pathlib import Path
from typing import List

import mate.logging


@enum.unique
class Command(enum.Enum):
    serve: str = "serve"
    pgshell: str = "pgshell"


parser = argparse.ArgumentParser()
parser.add_argument(
    "-v", "--verbose", action="count", default=0, help="print verbose logging information"
)
parser.add_argument(
    "-b",
    "--bdist-root",
    type=Path,
    default=os.environ.get("MATE_BDIST_ROOT", "."),
    help="path to the root of the MATE binary distribution",
)

# =================================================================

subparsers = parser.add_subparsers(dest="command", required=True)

# =================================================================

serve_parser = subparsers.add_parser(Command.serve.value, help="Start the REST API.")

serve_parser.add_argument(
    "--internal-port",
    action="store",
    dest="internal_port",
    default=20221,
    type=int,
    help="Port to listen on for internal messages.",
)

serve_parser.add_argument("--db-uri", action="store", dest="db_uri", default="mate-db:5432")

pgshell_parser = subparsers.add_parser(Command.pgshell.value, help="Start a Postgres-based shell.")

pgshell_parser.add_argument(
    "--db",
    action="store",
    dest="db",
    default="postgresql://mate@db/mate",
    type=str,
    help="Connection string to MATE database host.",
)

# =================================================================


def make_context(argv: List[str]) -> argparse.Namespace:
    ctxt = parser.parse_args(argv)
    mate.logging.configure(ctxt)

    return ctxt
