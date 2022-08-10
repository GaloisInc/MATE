#!/usr/bin/env python3

# migraine.py: Generate a patch of assembler directives based on Wedlock's output
# for retrieving the addresses of basic blocks and functions.

import argparse
import json
import sys

from mate.build.tob_chess_utils.logging import make_logger

logger = make_logger(__name__)


def emit_preamble():
    return '.section .migraine_addrs,"",@progbits'


def migraine_record(name, expr=None):
    """Emits (the assembler directives for) a single migraine record to the output.

    The directives used by migraine correspond to three fields:

    1. A length prefix for the migraine identifier (size = 8 bytes)
    2. The migraine identifier (size = length prefix)
    3. The corresponding VA (size = 8 bytes)
    """
    if expr is None:
        expr = 0

    logger.debug(f"Marked {expr} as {name}")
    return f"""
    \t.quad {len(name)}
    \t.ascii "{name}"
    \t.quad {expr}
    """


def generate_addresses(wed):
    """Emits directives for the function and every constituent basic block to the output."""
    mod_stem = wed["module"]["source_stem"]
    func_name = wed["function"]["name"]
    logger.debug(f"Writing address anchors for {func_name}")

    # NOTE(ww): Emitting the migraine::func directive before its constituent BBs
    # is VERY important: aspirin relies on this to appropriately cache line entries
    # by function for faster lookup when pairing BBs to their source lines.
    name = f"migraine::func::{mod_stem}::{func_name}"
    yield migraine_record(name, func_name)

    # NOTE(ww): In addition to its name anchor, every function has three other groups
    # of anchors:
    #  * Basic block anchors: each basic block in the function is tracked
    #    via migraine::bb and migraine::bb_end.
    #  * Prologue anchors: each basic block corresponding to a function prologue
    #    is tracked via migraine::func_prologue_begin and migraine::func_prologue_end
    #  * Epilogue anchors: each basic block correspond to a function epilogue
    #    is tracked via migraine::func_epilogue_begin and migraine::func_epilogue_end
    #
    # Observe that the prologue and epilogue anchors are co-extensive with their basic
    # blocks, i.e. that one or more basic blocks with overlap exactly with any
    # prologue/epilogue information. Observe also that the presence of prologues
    # and epilogues is not guaranteed -- a function may have only one or neither,
    # depending on optimizations, stack use, CSR use, and so forth.
    for bb in wed["function"]["bbs"]:
        if "ir" in bb:
            bb_stem = bb["ir"]["operand"]
        else:
            logger.debug(f"No matching IR BB for {bb['mi']['symbol']}, marking as such")
            bb_stem = f"ex_{bb['mi']['symbol']}"

        # If a basic block contains a function prologue, emit the appropriate
        # func_prologue_begin and func_prologue_end anchors for it.
        if bb["mi"]["is_prologue_insertion_block"]:
            name = f"migraine::func_prologue_begin::{mod_stem}::{func_name}::{bb_stem}"
            yield migraine_record(name, f"{bb['mi']['symbol']}")

            name = f"migraine::func_prologue_end::{mod_stem}::{func_name}::{bb_stem}"
            yield migraine_record(name, f"{bb['mi']['symbol']}_end")

        # If a basic block contains a function epilogue, emit the appropriate
        # func_epilogue_begin and func_epilogue_end anchors for it.
        if bb["mi"]["is_epilogue_insertion_block"]:
            name = f"migraine::func_epilogue_begin::{mod_stem}::{func_name}::{bb_stem}"
            yield migraine_record(name, f"{bb['mi']['symbol']}")

            name = f"migraine::func_epilogue_end::{mod_stem}::{func_name}::{bb_stem}"
            yield migraine_record(name, f"{bb['mi']['symbol']}_end")

        name = f"migraine::bb::{mod_stem}::{func_name}::{bb_stem}"
        yield migraine_record(name, bb["mi"]["symbol"])

        # NOTE(ww): Similarly to the requirement that migraine::func appear before
        # its constituent BBs, it's important that migraine::bb_end directives DIRECTLY
        # follow their corresponding migraine::bb directives. Aspirin assumes this
        # behavior in order to avoid iterating over every basic block visited when
        # performing VA/end-VA pairing.
        name = f"migraine::bb_end::{mod_stem}::{func_name}::{bb_stem}"
        yield migraine_record(name, f"{bb['mi']['symbol']}_end")

    # NOTE(ww): We generate a dummy func_end anchor at the end of each function.
    # This anchor does **not** contain a real VA; it exists simply to make our lives
    # easier in aspirin: it gives us a clear stopping point for emitting the function
    # record, after all epilogue anchors (which may be none) have been accounted for.
    name = f"migraine::func_end::{mod_stem}::{func_name}"
    yield migraine_record(name)


parser = argparse.ArgumentParser(
    description="Generate an assembly patch for storing program feature addresses in a section"
)
parser.add_argument(
    "-w", "--wedlock", type=argparse.FileType("r"), required=True, help="Wedlock input"
)
parser.add_argument(
    "-o", "--output", type=argparse.FileType("w"), default=sys.stdout, help="Output file"
)


def migraine(wed_dicts):
    yield emit_preamble()
    for wed in wed_dicts:
        for addr_record in generate_addresses(wed):
            yield addr_record


def main():
    args = parser.parse_args()

    wed_dicts = [json.loads(jsonl) for jsonl in args.wedlock]

    for line in migraine(wed_dicts):
        print(line, file=args.output)


if __name__ == "__main__":
    main()
