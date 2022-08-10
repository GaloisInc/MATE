"""This module contains all of the handling for orchestrating the contents of a Reachability message
into a symbolic execution plan for Manticore to execute."""
import argparse
import base64
import re
from collections import deque
from dataclasses import dataclass
from functools import lru_cache, partial
from pathlib import Path
from typing import Callable, Deque, FrozenSet, Iterable, List, Optional, Tuple, TypeVar, Union

from manticore import set_verbosity
from manticore.core.smtlib import Bool, Expression
from manticore.native.state import State
from manticore.utils import config

from dwarfcore.dwarfcore import DwarfCore
from dwarfcore.helper import enable_detectors, setup_generic_manticore
from mate_common.models.integration import (
    Assertion,
    Constraint,
    Reachability,
    ReachabilityRet,
    ReachingInput,
    ReachingTestCase,
    ReachingValue,
    SMTIdentifier,
    Waypoint,
)
from mate_query.db import Graph, Session

from .liftsmt2 import lift_smt2_to_python, validate_smt2
from .logging import logger

StatefulAssertion = Callable[[State], Bool]
StatefulIdReplacement = Callable[[State], Tuple[str, Expression]]
HookCall = Callable[[State], None]


def manticore_reach(
    bin_path: Path,
    session: Session,
    graph: Graph,
    ctxt: argparse.Namespace,
    msg: Reachability,
    *,
    manticore_workspace: Optional[str] = None,
) -> ReachabilityRet:
    """Determine whether Manticore can follow the given Reachability message.

    :param bin_path: The program to run
    :param ctxt: Global context for settings and options
    :param msg: Reachability message to process
    :param manticore_workspace: Location where Manticore will place execution artifacts
    :return: Reachability Return message with details of Manticore run
    """
    logger.info(f"Received Reachability message:\n{msg}")
    logger.debug(f"Program path: {bin_path}")
    # Params to give to executable
    params = list(msg.command_line_flags)
    logger.debug(f"Program params: {params}")

    # Initialization stuff
    # ------------------------
    consts = config.get_group("core")
    consts.mprocessing = consts.mprocessing.single
    # Set verbosity based on what was passed
    set_verbosity(ctxt.m_verbose)
    logger.debug(f"Set manticore verbosity: {ctxt.m_verbose}")

    # Get dwarfcore information
    dwarfcore = DwarfCore(session, graph, bin_path)

    # Need environment variable information to accurately reproduce execution
    # environment of a normal user
    m = setup_generic_manticore(
        bin_path,
        params,
        env=msg.env,
        workspace_path=manticore_workspace,
        concrete_start=msg.concrete_start,
        stdin_size=msg.stdin_size,
        dwarfcore=dwarfcore,
    )
    logger.debug("Setup Manticore")

    # Generate hooks for all waypoint messages and their assertion statements
    waypoint_infos = deque(
        generate_hook_waypoint_assertions(waypoint) for waypoint in msg.waypoints
    )

    # Add our custom hook at the end and combine it with the deinit hook
    last_waypoint = waypoint_infos[-1]
    assert last_waypoint is not None
    new_deinit_hook = combine_hooks(
        [last_block_solve, last_waypoint.deinit_hook.callback]  # type: ignore
    )
    deinit_hook_info = HookInfo(
        last_waypoint.deinit_hook.pc, new_deinit_hook, last_waypoint.deinit_hook.after
    )
    waypoint_infos[-1] = WaypointInfo(
        last_waypoint.va_start,
        last_waypoint.va_end,
        last_waypoint.init_hook,
        last_waypoint.hooks,
        deinit_hook_info,
    )

    # Setup our waypoints for the initial states
    for state in m.all_states:
        # Add the waypoints to the state
        state.context["waypoints"] = waypoint_infos
        # Setup the Waypoints for the state
        setup_next_waypoint(state)

    logger.debug(f"Setup dwarfcore")

    detectors = enable_detectors(m, dwarfcore, msg.detector_options)
    logger.debug(f"Setup detectors: {detectors}")

    # Finally run
    m.run()

    with m.locked_context() as context:
        testcases: List[ReachingTestCase] = []

        solved_list = context.get("solved", list())
        if len(solved_list) > 0:
            testcases.append(
                ReachingTestCase(description="Followed all waypoints", symbolic_inputs=solved_list)
            )
        for detector in detectors:
            testcases.extend(detector.results)
        if len(testcases) > 0:
            ret_msg = ReachabilityRet(path=str(bin_path), success=True, cases=testcases)
        else:
            ret_msg = ReachabilityRet(path=str(bin_path), success=False)

    return ret_msg


@dataclass(frozen=True, eq=True)
class HookInfo:
    """Information required to keep track of hooks added.

    These are also the order in which the arguments appear to add_hook and remove_hook
    """

    pc: int
    callback: HookCall
    after: bool


@dataclass(frozen=True, eq=True)
class WaypointInfo:
    """Information that Manticore should know about Waypoints to add and remove assertion hooks as
    they are encountered."""

    va_start: int
    va_end: int
    init_hook: HookInfo
    hooks: FrozenSet[HookInfo]
    deinit_hook: HookInfo

    @property  # type: ignore
    @lru_cache(maxsize=None)
    def all_hooks(self) -> FrozenSet[HookInfo]:
        return frozenset([self.init_hook] + list(self.hooks) + [self.deinit_hook])


def setup_next_waypoint(state: State) -> None:
    """Grab the next waypoint and setup a hook to initialize it when the start address is hit.

    :param state: The state we want to setup the next waypoint on
    """
    state_waypoints: Deque[WaypointInfo] = state.context["waypoints"]
    if len(state_waypoints) == 0:
        logger.debug(f" [{state.id}] Trying to set up next waypoint, but no waypoints left!")
        return
    next_waypoint: WaypointInfo = state_waypoints[0]
    init_hook_info = next_waypoint.init_hook
    logger.debug(f" [{state.id}] Setting up next waypoint at 0x{next_waypoint.va_start:x}")
    assert init_hook_info.pc == next_waypoint.va_start
    state.add_hook(init_hook_info.pc, init_hook_info.callback, init_hook_info.after)


def deinit_hook(state: State) -> None:
    """Hook at the end address of the waypoint. Removes all hooks from this waypoint.

    :param state: The state we want to deinitialize the hook
    """
    logger.debug(
        f" [{state.id}] Reached 0x{state.cpu.instruction.address:x}. Removing all waypoint hooks"
    )
    waypoint = state.context["waypoints"].popleft()
    hook: HookInfo
    # Remove all waypoint hooks
    for hook in waypoint.all_hooks:
        state.remove_hook(hook.pc, hook.callback, hook.after)
    setup_next_waypoint(state)


def init_hook(state: State) -> None:
    """Hook at the beginning address of the waypoint. Initializes all other hooks in the waypoint.

    :param state: The state we want to initialize the hook
    """
    logger.debug(f" [{state.id}] Reached 0x{state.cpu.PC:x}. Adding all waypoint hooks")
    # Get the waypoint we're initiating
    waypoint: WaypointInfo = state.context["waypoints"][0]
    for hook in list(waypoint.hooks) + [waypoint.deinit_hook]:
        state.add_hook(hook.pc, hook.callback, hook.after)


T = TypeVar("T")


def call_funcs(arg: T, funcs: List[Callable[[T], None]]) -> None:
    """Call all functions given and pass arg to each one. Ignores output of functions.

    :param arg: Argument to pass to functions
    :param funcs: List of functions to call
    """
    for func in funcs:
        func(arg)


def combine_hooks(hooks: Iterable[HookCall]) -> HookCall:
    """Combine hooks by calling them one after another in the order provided.

    :param hooks: The hooks to combine
    :return: A function that will call all hooks
    """
    return partial(call_funcs, funcs=hooks)


def stateful_id_expr(identifier: SMTIdentifier, state: State) -> Tuple[str, Expression]:
    """Use run-time information from Manticore state to retrieve value of the SMT identifier.

    :param identifier_p: Identifier that will have value retrieved
    :param state: Manticore state for context of value for identifier
    :return: The identifier and its value
    """
    # Get the name of the register
    reg_name = identifier.identifier.value
    assert reg_name in state.cpu.all_registers
    reg_val = state.cpu.read_register(reg_name)
    return (reg_name, reg_val)


def convert_identifier(identifier_p: SMTIdentifier) -> StatefulIdReplacement:
    """Build a function that will obtain an identifier's value using a Manticore State.

    :param identifier_p: Identifier that will have its value retrieved
    :return: Partial function that can be used to get the run-time value of the
        identifier given a Manticore state
    """
    return partial(stateful_id_expr, identifier_p)


def do_expr_replace(smt_replacements, constraint_msg: Constraint, state: State) -> Bool:
    """Match up our replacement identifiers $replace#0, $replace#1, ... with our actual
    replacements, and form a Python expression, which we can then return.

    :param smt_replacements: The values we want to insert the constraint
    :param constraint_msg_p: The constraint to place on the Manticore state
    :param state: The Manticore State this replacement relates to
    :return: An assertion expression placed on the Manticore state with
        replacements
    """
    replacements = [replacement(state) for replacement in smt_replacements]
    logger.debug(f" [{state.id}] Expression: {constraint_msg.expr}")
    logger.debug(f" [{state.id}] Replacements: {replacements}")
    manti_expr = lift_smt2_to_python(
        constraint_msg.expr, decls=[value for (name, value) in replacements]
    )
    return manti_expr


def build_assertion_expr(constraint_msg: Constraint) -> StatefulAssertion:
    """Build a Manticore-compatible StatefulAssertion.

    :param constraint_msg: The constraint message that will be placed on
        Manticore
    :return: An assertion expression that can be used with a Manticore state
    """
    # Convert SMT expression identifiers to their Manticore identifiers for
    # replacement in the SMT expression
    smt_replacements = [convert_identifier(replacement) for replacement in constraint_msg.id]
    return partial(do_expr_replace, smt_replacements, constraint_msg)


def add_assertion(assertions: List[StatefulAssertion], state: State) -> None:
    """Add all assertions in the list to the Manticore State.

    :param assertions: Assertions to be added to the State
    :param state: The Manticore State that will take the assertions
    """
    logger.debug(f" [{state.id}] ******* ADDING ASSERTIONS")
    for assertion in assertions:
        _assertion = assertion(state)
        logger.debug(f" [{state.id}] Assertion: {_assertion}")
        if state.can_be_true(_assertion):
            state.constrain(_assertion)
        else:
            logger.debug(f" [{state.id}] Abandoning on unsatisfiable assertion")
            state.abandon()


def assertion_hook_callback_factory(assertions: List[StatefulAssertion]) -> HookCall:
    """Given a stateful assertion, create a callback that will add that assertion to Manticore's
    state.

    :param assertions: Assertions to be added to a Manticore State
    :return: A function that can be used with a Manticore state to add the assertions
    """
    return partial(add_assertion, assertions)


def generate_hook_waypoint_assertions(waypoint: Waypoint) -> WaypointInfo:
    """Given a list of assertions, create a hook for manticore that will apply the constraints
    _after_ the instruction has executed.

    :param waypoint: The Waypoint message to extract the assertions
    :return: Information about the waypoint and hooks to add to Manticore
    """
    asserts: List[Assertion] = waypoint.asserts
    hook_infos: Deque[HookInfo] = deque()
    init_hooks: List[HookCall] = [init_hook]
    # stack for hooks at the very end, the same as waypoint deinit call. Will be combined
    deinit_hooks: List[HookCall] = []

    # Build hooks for each assertion
    for assertion_msg in asserts:
        assert_pc = assertion_msg.location.va
        assertion_exprs = [
            build_assertion_expr(constraint) for constraint in assertion_msg.constraint
        ]
        assert_hook = assertion_hook_callback_factory(assertion_exprs)
        if assert_pc == waypoint.end.va:
            # TODO: Asserts are always after assert_pc executes. This logic will change for replacements
            deinit_hooks.append(assert_hook)
            # Continue in case multiple hooks/asserts at very end
            continue
        logger.info(f"manticore will hook assertion {assert_pc}")
        hook_infos.append(HookInfo(assert_pc, assert_hook, True))

    # Add our deinit waypoint hook
    deinit_hooks.append(deinit_hook)

    # Combine (de)init hook lists
    init_hook_info = HookInfo(waypoint.start.va, combine_hooks(init_hooks), False)
    deinit_hook_info = HookInfo(waypoint.end.va, combine_hooks(deinit_hooks), True)

    return WaypointInfo(
        waypoint.start.va,
        waypoint.end.va,
        init_hook_info,
        frozenset(hook_infos),
        deinit_hook_info,
    )


def natural_sort_key(s, _nsre=re.compile("([0-9]+)")):
    """String natural sort for strings that include numbers.

    https://stackoverflow.com/a/16090640
    """
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


def last_block_solve(state: State) -> None:
    """Hook for the last basic block/Waypoint on the list used to generate ReachingInput message
    that is saved in Manticore context.

    :param state: Manticore state for context
    """
    logger.info(f" [{state.id}] Reached our final destination! 0x{state.cpu._last_pc:x}")
    reaching_inputs: List[ReachingInput] = []
    for declaration in sorted(
        state.constraints.declarations, key=lambda d: natural_sort_key(d.name)
    ):
        res = state.constraints.get_variable(declaration.name)
        conc_val = state.solve_one(res)
        logger.debug(f" [{state.id}] Generated reaching input!")
        logger.debug(f" [{state.id}] \t{declaration.name}:\n [{state.id}] {conc_val!r}")

        # TODO(ek): Get the full SMT formula for constraints on our symbolic variable
        # symb_smt = state.constraints.to_string()

        if not isinstance(conc_val, (bytes, bytearray)):
            conc_val = repr(conc_val).encode("utf-8")

        symbolic_value = ReachingValue(
            symbolic_value="Skipped",
            concrete_value_base64=base64.b64encode(conc_val).decode("utf-8"),
        )
        reaching_inputs.append(
            ReachingInput(name=declaration.name, symbolic_values=[symbolic_value])
        )

    with state.manticore.locked_context() as context:
        solved_list = context.get("solved", list())
        solved_list.extend(reaching_inputs)
        # Need to check if we even had symbolic inputs and insert a fake one if
        # there are no symbolic variables
        if len(solved_list) == 0:
            solved_list.append(ReachingInput(name="Everything_Concrete"))
        context["solved"] = solved_list

    # Kill Manticore so that we can send our result right away
    # We might want to remove this to gather more reaching inputs and send
    # results as they're generated.
    state.manticore.kill()


# TODO: Add this to Mantiserve response message
# https://gitlab-ext.galois.com/mate/MATE/-/issues/651
@dataclass(frozen=True)
class ValidationErrorInfo:
    """General validation error information."""

    err_msg: Union[str, List[str]]


@dataclass(frozen=True)
class ConstraintValidationErrorInfo(ValidationErrorInfo):
    """Validation error information for constraints."""

    # Expression with error
    expr: str


def validate_reachability_msg(reach_msg: Reachability) -> List[ValidationErrorInfo]:
    """Validate the well-formed-ness of the Reachability message before Manticore processes it.

    :param reach_msg: Reachability message to validate
    :return: a list of errors if there are any.
    """
    ret: List[ValidationErrorInfo] = []

    waypoint: Waypoint
    for waypoint in reach_msg.waypoints:
        assertion: Assertion
        for assertion in waypoint.asserts:
            constraint: Constraint
            for constraint in assertion.constraint:
                # Fill the replacement identifiers with just 0s to make sure the lifting works
                errs = validate_smt2(constraint.expr, [0 for _ in constraint.id])
                if errs:
                    ret.append(ConstraintValidationErrorInfo(err_msg=errs, expr=constraint.expr))

    return ret
