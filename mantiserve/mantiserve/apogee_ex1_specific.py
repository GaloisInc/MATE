"""This module is purely for testing purposes for Apogee Example 1 to make sure this package can
find all of its dependencies and complete a run of Manticore trace following."""
import socket
from typing import List

from mate_common.models.integration import (
    Addr,
    Assertion,
    Constraint,
    Reachability,
    Register,
    SMTIdentifier,
    Waypoint,
)

from .logging import logger


def build_fake_reachability_msg(bin_path: str) -> Reachability:
    reach_msg = Reachability(
        path=bin_path,
        command_line_flags=["HELLO", "GOODBYE"],
        waypoints=get_waypoints(),
        constraint_vars=[],
    )

    return reach_msg


def get_waypoints() -> List[Waypoint]:
    waypoints: List[Waypoint] = []

    # Real trace
    trace_lst = [
        (0x400CC2, 0x400D9B),
        (0x400DA4, 0x400DA8),
        (0x400DAE, 0x400DD2),
        # One-instruction waypoint for making sure we get here but don't do anything else
        # Start of `call authenticatedFunction` bb
        # We can't assert on the call unless we know the RVA of the call instruction
        (0x400DD4, 0x400DD4),
        # Next waypoint at start of authenticatedFunction bb and end at ret
        # We can't assert on the ret, unless we know the instruction address after the call
        (0x400B70, 0x400BC1),
        # Next we need to end up at the end of the BB at 0x400DD4
        # Add assertion to jump to 0x400DFA
        (0x400DF4, 0x400DF4),
        (0x400DFA, 0x400E43),
    ]

    next_starts = [0x400DA4, 0x400DAE, 0x400DD4, None, None, 0x400DFA, None]

    for next_start, (start, end) in zip(next_starts, trace_lst):
        addr_start = Addr(va=start)
        addr_end = Addr(va=end)
        asserts = (
            []
            if not next_start
            else [
                Assertion(
                    location=addr_end,
                    constraint=[
                        Constraint(
                            id=[SMTIdentifier(identifier=Register.RIP)],
                            expr=f"(assert (= $replace#0 {next_start}))",
                        )
                    ],
                )
            ]
        )
        w = Waypoint(start=addr_start, end=addr_end, asserts=asserts, replacements=[])
        waypoints.append(w)

    return waypoints


def try_exploit(payload: bytes) -> bool:
    """Tries to send the exploit payload across the network to the Apogee example 1 server. Also
    checks that we receive back some correct messages.

    Returns whether or not the exploit worked.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("challenge_container", 8081))
        # Get the opening prompt
        _ = s.recv(4096)
        # Send our "password"
        s.send(payload)
        # Receive the result
        result_bytes = s.recv(4096)
        s.close()
        result = result_bytes.decode("utf-8")
        flag = "EXAMPLE_1_FLAG"
        logger.info("Result from challenge binary:")
        logger.info("*" * 80)
        logger.info(result)
        logger.info("*" * 80)
        logger.info("Need to see expected string:")
        logger.info(flag)
        if flag in result:
            logger.info("Found expected string!")
            return True
        return False
    except socket.gaierror as e:
        logger.warning(f"Address-related error connecting to Apogee Example 1 server: {e}")
        logger.warning("Continuing anyway...")
        return False


if __name__ == "__main__":
    gen_reach = build_fake_reachability_msg("example_1.instrumented")
    print(gen_reach)
    gen_file = "gen_message.pbs"
    # Machine-readable message
    with open(gen_file, "wb") as fb:
        fb.write(gen_reach.SerializeToString())

    # Write out human-readable message
    with open(f"{gen_file}.txt", "w") as f:
        f.write(str(gen_reach))
    import os

    # Translate decimal RVAs into human readable hexadecimal RVAs, inplace
    os.system("perl -p -i -e 's/\\b\\d{4,}\\b/sprintf \"%#x\", $&/ge' " + f"{gen_file}.txt")
