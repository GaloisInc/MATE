import argparse
from typing import List

from mantiserve import logging

parser = argparse.ArgumentParser()
parser.add_argument(
    "-v",
    "--verbose",
    action="count",
    dest="verbose",
    default=0,
    help="print verbose logging information",
)

subparsers = parser.add_subparsers(dest="command")

serve_parser = subparsers.add_parser("serve", help="Start a MantiServe server in the foreground.")

server_args = serve_parser.add_argument_group("server")

server_args.add_argument(
    "--port",
    action="store",
    dest="port",
    default=8001,
    type=int,
    help="Port to serve REST API.",
)

manticore_args = serve_parser.add_argument_group("manticore")

manticore_args.add_argument(
    "--m.verbose",
    action="store",
    dest="m_verbose",
    type=int,
    default=0,  # Show only the highest level information
)


def make_context(argv: List[str]) -> argparse.Namespace:
    """Parse the server's command line arguments and create a context."""
    ctxt = parser.parse_args(argv)

    ctxt.verbose = min(ctxt.verbose, len(logging.VERBOSITY) - 1)

    return ctxt
