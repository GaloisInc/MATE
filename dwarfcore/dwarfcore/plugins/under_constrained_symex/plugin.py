import struct
import traceback
from typing import Final

from manticore.core.plugin import Plugin
from manticore.core.smtlib import BitVecConstant, ConstraintSet, pretty_print, simplify
from manticore.native.state import State, TerminateState

import mate_query.db as db
from mate_common.models.integration import ExplorationTree
from mate_common.models.manticore import UnderConstrainedOptions

from . import dwarf_helper, uc_platform
from .errors import AccessKind, ErrorManager
from .exceptions import *
from .logging import logger
from .smt import uc_pretty_print
from .user_constraints import UserConstraintManager


class UCSE(Plugin):
    return_addr_magic: Final[int] = 0x1234567812345678
    ctx_exploration_tree: Final[str] = "UCSE_result_tree"
    ctx_warnings: Final[str] = "UCSE_warnings"

    def __init__(
        self,
        session: db.Session,
        graph: db.Graph,
        init_state: State,
        options: UnderConstrainedOptions,
    ):
        """Under-constrained symbolic execution plugin. Responsible for executing a target function
        and handling access to uninitialised memory through symbolic pointers.

        :param session: The DB session to query the CPG
        :param graph: The code property graph associated to the binary to run
        :param options: Settings for the plugin
        """

        super().__init__()
        logger.info("Instanciating UCSE plugin...")
        self.session = session
        self.graph = graph
        uc_platform._UCSE_session = session
        uc_platform._UCSE_graph = graph
        dwarf_helper.init_db_session(session, graph)
        self.options = options

        # Setup target function
        target_func = (
            session.query(graph.MachineFunction).filter_by(name=options.target_function).first()
        )
        if target_func is None:
            raise InputError(f"Could not find target function '{options.target_function}'")
        self.func_start = target_func.va_start
        self.func_end = target_func.va_end
        logger.debug(f"Target function bounds: {self.func_start}-{self.func_end}")

        # Prepare concrete program initialisation before UC exec
        self.init_until = (
            init_state.platform._find_symbol("main")
            if options.init_until is None
            else options.init_until
        )
        if self.init_until is None:
            raise Exception("Couldn't find address of main(), aborting...")
        self.cxa_allocate_exception_addr = init_state.platform._find_symbol(
            "__cxa_allocate_exception"
        )

        # Create error manager
        self.error_manager = ErrorManager()

        # Add user-defined constraints
        self.user_constraints = UserConstraintManager()
        for constraint in options.input_constraints:
            self.user_constraints.add(constraint)

    @property
    def name(self) -> str:
        return "UCSEPlugin"

    def will_run_callback(self, ready_states):
        # Concretely emulate the program loading and initialisation
        # from _start to main
        for state in ready_states:
            state.cpu.emulate_until(self.init_until)

    def did_load_state_callback(self, state):
        # Link the error manager in memory to the main one in the plugin
        state.cpu.memory.error_manager = self.error_manager
        state.cpu.memory.user_constraints = self.user_constraints
        # Set dynamic array policies
        state.cpu.memory.native_array_size_policy = self.options.native_array_size_policy
        state.cpu.memory.complex_array_size_policy = self.options.complex_array_size_policy

    def will_execute_instruction_callback(self, state, pc, _insn):
        if pc >= self.func_start and pc <= self.func_end:
            logger.debug(f"State {state.id}: {_insn}")

        # Check if we are throwing an exception from the target function
        # We check that we are executing __cxa__allocate_exception and that
        # it was called from the target function by looking at the return
        # address on the stack.
        if pc == self.cxa_allocate_exception_addr:
            ret_addr = state.cpu.read_int(state.cpu.RSP, 8)
            if ret_addr >= self.func_start and ret_addr <= self.func_end:
                logger.debug("Throwing exception from target function")
                state.abandon()

    def will_fork_state_callback(self, _state, expression, solutions, _policy):
        logger.debug(f"State {_state.id}: forking on {pretty_print(simplify(expression))}")
        # logger.debug(f"Fork constraints are {state.constraints}")
        logger.debug(f"State {_state.id}: fork solutions are: {solutions}")

    def will_decode_instruction_callback(self, state, pc):
        # TODO(boyan): handle functions that exit by throwing an exception
        if pc == UCSE.return_addr_magic:
            logger.info("Reached end of target function")
            state.abandon()

        if pc == self.init_until:
            logger.info("Program initialisation complete, jumping directly to target function")
            self.setup_uc_state(state)

    def will_terminate_state_callback(self, _current_state, exception):
        logger.debug(f"State {_current_state.id}: terminating with exception: {exception}")
        if isinstance(exception, UCException):
            with self.manticore.locked_context() as ctx:
                tree = ctx[UCSE.ctx_exploration_tree]
                tree.get_state(_current_state.id).error_msg = traceback.format_exc()

    def will_kill_state_callback(self, _current_state, exception):
        logger.debug(f"State {_current_state.id}: killing with exception: {exception}")
        with self.manticore.locked_context() as ctx:
            tree = ctx[UCSE.ctx_exploration_tree]
            tree.get_state(_current_state.id).error_msg = traceback.format_exc()

    def did_fork_state_callback(self, parent_state, expression, new_values, _policy, children):
        expression = simplify(expression)

        # Abstact expressions without any symbolic variables are not considered
        # exploration choices. In that case, the expression is actually a constant
        if isinstance(expression, BitVecConstant):
            # Sanity check. Forking on a constant shouldn't create more states
            if children:
                raise UCException("Forking on constant shouldn't create child states")
            else:
                # Everything OK, just ignore this fork and return
                return

        with self.manticore.locked_context() as ctx:
            tree = ctx[UCSE.ctx_exploration_tree]
            expression_str: str = uc_pretty_print(expression)
            # If there is only 1 new value and no child states, it means that manticore
            # made an optimised fork on 1 unique fork solution, so we don't need to record
            # a choice here
            if len(new_values) == 1 and not children:
                tree.get_state(parent_state.id).choices.append(
                    (
                        expression_str,
                        new_values[0],
                    )
                )
                return
            # Sanity check
            if len(new_values) != len(children):
                raise UCException(
                    "Fork callback: new values list doesn't match children states list"
                )
            # NOTE: the code below relies on the fact that the `new_values` and `children`
            # lists match (i.e new_values[i] is the value of `expression` in children[i]).
            # Hence the sanity check before
            for i in range(len(new_values)):
                tree.add_state(
                    parent_state.id,
                    children[i],
                    (
                        expression_str,
                        new_values[i],
                    ),
                )

    def did_run_callback(self):
        # Finished to run, record potential unused constraints
        with self.manticore.locked_context() as ctx:
            for constraint in self.user_constraints.get_unused_constraints():
                ctx[UCSE.ctx_warnings].append(f"Unused constraint: '{constraint}'")

    def setup_uc_state(self, state):
        """Modify a manticore state to perform under constrained symbolic execution. It consists in
        pointing the PC to the target address, making most of the registers symbolic, and initialise
        the UC memory with the function argument objects if there are any.

        :param state: The state to setup for under constrained symbolic execution
        """
        state.cpu.PC = self.func_start

        # Make a fake stack in an arbitrary location
        stack_size = 0x210000
        stack_top = 0xAAA000000
        state.cpu.memory.mmap(stack_top, stack_size, "rw")
        state.cpu.RBP = stack_top + (stack_size // 2)
        state.cpu.RSP = state.cpu.RBP - 8
        # Fake return address
        state.cpu.memory.write(state.cpu.RSP, struct.pack("<Q", UCSE.return_addr_magic))

        # Initialize function arguments
        machine_func = (
            self.session.query(self.graph.MachineFunction).filter_by(va_start=self.func_start).one()
        )
        self.setup_func_args(state, machine_func)

        # Initialize context
        with self.manticore.locked_context() as ctx:
            ctx[UCSE.ctx_exploration_tree] = ExplorationTree(state.id)
            ctx[UCSE.ctx_warnings] = []

        logger.info(
            f"Successfully setup under constrained state for function at: {hex(self.func_start)}"
        )
        return state

    def setup_func_args(self, state: State, func):
        arg_regs = ["RDI", "RSI", "RDX", "RCX", "R8", "R9"]
        try:
            for i, arg in enumerate(func.arguments):
                expr = state.cpu.memory.uc_func_arg_to_expr(arg)
                if i <= 6:
                    setattr(state.cpu, arg_regs[i], expr)
                else:
                    state.cpu.STACK -= 8
                    state.cpu.memory.write(state.cpu.STACK, expr)
        except Exception as e:
            raise Exception(f"Error setting up target function arguments: {e}")

    def will_read_memory_callback(self, state: State, address, size):
        try:
            state.cpu.memory.check_oob_access(address, size // 8, AccessKind.READ, False)
        except FatalSymexError as e:
            raise TerminateState(str(e))

    def will_write_memory_callback(self, state: State, address, _value, size):
        try:
            state.cpu.memory.check_oob_access(address, size // 8, AccessKind.WRITE, False)
        except FatalSymexError as e:
            raise TerminateState(str(e))


def make_initial_state(program_path):
    """Create the initial program state, using the custom platform."""
    platform = uc_platform.UCLinux(
        str(program_path), argv=[], envp={"LD_BIND_NOW": "1"}, symbolic_files=None
    )
    return State(ConstraintSet(), platform)
