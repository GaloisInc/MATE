import enum
from typing import Final, List, Union

from manticore import Plugin
from manticore.core.smtlib import ConstraintSet, Expression, SelectedSolver, pretty_print, simplify
from manticore.native import Manticore
from manticore.native.state import State

from dwarfcore.utils import addr_to_map_and_offset, pp_map_and_offset
from mate_common.models.integration import Detector, UnderconstrainedTestCase

from .exceptions import FatalSymexError
from .smt import uc_pretty_print
from .user_constraints import Metavar


class ExecError:
    """A base class representing an error during execution."""

    @property
    def is_oob(self) -> bool:
        return False


class OOBError(ExecError):
    """A base class representing an out of bounds memory access error."""

    def __init__(self, pc: int, cond: Expression, constraints: ConstraintSet):
        self.pc = pc
        self.cond = cond
        self.constraints = constraints

    def __str__(self):
        res = "Out-of-bounds error:\n"
        res += f"\tPC: {self.pc}\n\tCondition: {pretty_print(self.cond)}\n\tState constraints: {self.constraints}"
        return res

    @property
    def is_oob(self) -> bool:
        return True


class OOBReadError(OOBError):
    pass


class OOBWriteError(OOBError):
    pass


class AccessKind(str, enum.Enum):
    READ = "read"
    WRITE = "write"


class ErrorManager:
    """A class used to check and handle for memory access errors during underconstrained symbolic
    execution."""

    def __init__(self):
        self.errors = list()  #  Errors detected during execution

    def record_error(self, error):
        self.errors.append(error)

    def check_oob_access(
        self,
        access: AccessKind,
        obj,
        offset: Union[Expression, int],
        size: int,
        memory,
        pc: int,
        fix_oob: bool = False,
    ):
        """Check whether a memory access can exceed the bounds of a memory object. If the offset can
        be out of bounds, create an error case.

        :param access: type of memory access (read or write)
        :param obj: memory object to access
        :param offset: offset at which to read/write in 'obj'
        :param size: number of bytes to read/write
        :param memory: the current UC memory
        :param pc: the address of the instruction reading memory
        :param fix_error: if set to True and if offset can be out of bounds, try to add a constraint to the
         constraint set such that to enforce 'offset' to be in within the bounds of 'obj'
        """
        # Create out-of-bounds condition
        # OOB if last byte accessed exceeds the size of the object
        # - last byte accessed is offset+size
        # - size of the object is #elements * sizeof(element)
        obj_base = str(obj.uid)
        if isinstance(offset, Expression):
            oob_cond = (offset + size).ugt(
                obj.content_type_size * memory.base_to_metavars[obj_base][Metavar.LEN]
            )
        else:
            oob_cond = offset + size > obj.size
        oob_cond = simplify(oob_cond)
        #  Check if OOB is possible
        if SelectedSolver.instance().can_be_true(memory.constraints.related_to(oob_cond), oob_cond):
            # Possible OOB
            # TODO(boyan): maybe we could split constraints related to 'oob_cond' and
            # other constraints (which would be simple path constraints)
            simplified_constraints = [simplify(c) for c in memory.constraints]
            error = (
                OOBReadError(pc=pc, cond=oob_cond, constraints=simplified_constraints)
                if access is AccessKind.READ
                else OOBWriteError(pc=pc, cond=oob_cond, constraints=simplified_constraints)
            )
            # Record the error
            self.record_error(error)
            # Try to fix the access by adding constraints
            if fix_oob:
                valid_cond = not oob_cond
                # If the access 'can' be valid, add the constraint
                if SelectedSolver.instance().can_be_true(
                    memory.constraints.related_to(valid_cond), valid_cond
                ):
                    memory.constraints.add(valid_cond)
                    return
                # If the access is always invalid, pass (we raise exception at the end of the method)
                else:
                    pass
        else:
            return  # No OOB access

        raise FatalSymexError(f"[UC] Out of bounds memory {access.value}")


class UnderconstrainedOOB(Plugin):
    """Detector for under-constrained OOB errors."""

    MCORE_TESTCASE_LIST: Final[str] = "UnderconstrainedOOBDetector_test_cases"
    __testcase_uid_cnt: int = 0

    def __init__(self, manticore: Manticore):
        super().__init__()
        # Get the underconstrained plugin
        ucse_plugin = [p for p in manticore.plugins.values() if p.name == "UCSEPlugin"][0]
        self.error_manager: ErrorManager = ucse_plugin.error_manager

    @property
    def results(self) -> List[UnderconstrainedTestCase]:
        """Any test case results found during execution."""
        with self.manticore.locked_context() as context:
            return context.get(self.MCORE_TESTCASE_LIST, list())

    @classmethod
    def new_testcase_uid(cls):
        cls.__testcase_uid_cnt += 1
        return cls.__testcase_uid_cnt - 1

    def record_testcases(self, state: State) -> None:
        # Record new errors for this state
        with state as tmp:
            with tmp.manticore.locked_context() as context:
                cases = context.get(self.MCORE_TESTCASE_LIST, list())
                for error in self.error_manager.errors:
                    # Keep only one OOB error per instruction address
                    if error.is_oob:
                        test_case = UnderconstrainedTestCase(
                            description="Out-of-bounds memory access",
                            uid=UnderconstrainedOOB.new_testcase_uid(),
                            va=error.pc,
                            va_mapping=pp_map_and_offset(
                                addr_to_map_and_offset(error.pc, state.cpu.memory)
                            ),
                            condition=uc_pretty_print(error.cond),
                            constraints=[uc_pretty_print(e) for e in error.constraints],
                            detector_triggered=Detector.UnderconstrainedOOB,
                            symbolic_inputs=[],  # TODO(boyan): this must be computed on-the-fly
                        )
                        cases.append(test_case)
                        # Also add the error in the exploration tree
                        from .plugin import UCSE

                        context[UCSE.ctx_exploration_tree].get_state(state.id).cases.append(
                            test_case
                        )
                        # Remove the pending error so it's recorded only once
                        self.error_manager.errors.remove(error)
                context[self.MCORE_TESTCASE_LIST] = cases

        # Generate a testcase using Manticore's internal machinery
        # self.manticore.generate_testcase(state, message)

    def will_terminate_state_callback(self, state, _reason):

        self.record_testcases(state)
