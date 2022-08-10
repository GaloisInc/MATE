from typing import Final, List

from manticore import Plugin
from manticore.native.state import State

from dwarfcore.detectors.common import record_concretize_state_vars
from mate_common.models.integration import Detector, ReachingTestCase


class DetectAllPaths(Plugin):
    MCORE_TESTCASE_LIST: Final[str] = "TestDetector"

    @property
    def results(self) -> List[ReachingTestCase]:
        """Any test case results found during execution."""
        with self.manticore.locked_context() as context:
            return context.get(self.MCORE_TESTCASE_LIST, list())

    def record_testcase(self, state: State, message: str):
        with state as tmp:
            testcase = ReachingTestCase(
                description=message,
                detector_triggered=Detector.DetectAllPaths,
                symbolic_inputs=record_concretize_state_vars(tmp, state.id),
            )
            with tmp.manticore.locked_context() as context:
                case_list = context.get(self.MCORE_TESTCASE_LIST, list())
                case_list.append(testcase)
                context[self.MCORE_TESTCASE_LIST] = case_list

        # Generate a testcase using Manticore's internal machinery
        self.manticore.generate_testcase(state, message)

    def will_terminate_state_callback(self, state, reason):
        self.record_testcase(state, str(reason))
