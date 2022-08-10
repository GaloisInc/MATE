import dataclasses
import enum
from enum import Enum
from typing import Dict, Iterable, List, Literal, Optional, Tuple, Union

from pydantic import PositiveInt
from pydantic.dataclasses import dataclass


class ORMConfig:
    orm_mode = True


@dataclass(frozen=True, config=ORMConfig)
class Target:
    event: str
    id: str
    type: str = "target"


@dataclass(frozen=True, config=ORMConfig)
class Decl:
    """An initial declaration for symbolic variables."""

    name: str = dataclasses.field(metadata=dict(description="Name of the symbolic declaration"))
    # "????" is 4 bytes unconstrained
    # "AB??" is 4 bytes: 2 concrete and 2 unconstrained
    value: str = dataclasses.field(
        metadata=dict(description="Symbolic value (Manticore-encoded symbolic notation)")
    )
    # TODO: Should be SMT-like instead of str
    expr: str = dataclasses.field(
        metadata=dict(description="Expression for constraint on identifier (SMT formula)")
    )


@dataclass(frozen=True, config=ORMConfig)
class Addr:
    """A binary address."""

    va: PositiveInt = dataclasses.field(
        metadata=dict(description="Manticore binary virtual address")
    )


@dataclass(frozen=True, config=ORMConfig)
class Model:
    """Replacement Model for a piece of native code, like a function."""

    # TODO: There should be a more generic way to do this
    python_code: str = dataclasses.field(
        metadata=dict(
            description="Not implemented. A well-formed Python code to execute for modeling",
        )
    )


@dataclass(frozen=True, config=ORMConfig)
class Replacement:
    """A replacement for a function call. A "replacement" will intercept control-flow to replace the
    logic at the specified location. If it will replace a function call, then the location should
    appear at the very first instruction within the function that is being replaced (to catch all
    calls). The model will then need to return control-flow back to the caller using standard
    calling convention rules.

    NOTE: This has yet to be implemented or tested.

    These are added _before_ the execution of location
    """

    location: Addr = dataclasses.field(
        metadata=dict(description="Not Implemented. Location of where to replace.")
    )
    model: Model = dataclasses.field(
        metadata=dict(description="Not Implemented. The model to use for replacement.")
    )


@enum.unique
class Register(str, Enum):
    """Registers for machine-code. Must match up with what appears in the binary.

    NOTE: If there is a better way of normalizing the register names,
    we might not need this.
    """

    RIP = "RIP"


@dataclass(frozen=True, config=ORMConfig)
class SMTIdentifier:
    """Identifier for SMT expressions."""

    identifier: Union[Register, str] = dataclasses.field(
        metadata=dict(
            description="The Register should match a machine register; ``str`` should match a ``Decl.name``"
        )
    )


@dataclass(frozen=True, config=ORMConfig)
class Constraint:
    """Constraint to apply to identifier."""

    # TODO: Where to define special string?
    expr: str = dataclasses.field(
        metadata=dict(
            description="""Expression for constraint on identifier.
Will use special string to replace SMTIdentifiers in the order they appear.

Special string: ``$replace#`` is constant and then an index number into ``id`` (``$replace#0`` - 0th index of ``id``)"""
        )
    )

    id: List[SMTIdentifier] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="Ordered SMT identifiers to be placed into the expression"),
    )


@dataclass(frozen=True, config=ORMConfig)
class Assertion:
    """Assertions are used to add constraints during the execution of a program.

    These constraints only apply to symbolic values and must be true _after_ the execution of the
    location.
    """

    location: Addr = dataclasses.field(
        metadata=dict(description="Location of where to place the assertion.")
    )
    constraint: List[Constraint] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(
            description="These constraints only apply to symbolic values and must be true *after* the execution of the location."
        ),
    )


@dataclass(frozen=True, config=ORMConfig)
class Waypoint:
    """Waypoint message relates to a specific area of code and contains relevant information for
    that area."""

    start: Addr = dataclasses.field(
        metadata=dict(description="Location of where the Waypoint starts.")
    )
    end: Addr = dataclasses.field(metadata=dict(description="Location of where the Waypoint ends."))
    asserts: List[Assertion] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(
            description="Assertions are used to add constraints during the execution of a program."
        ),
    )
    replacements: List[Replacement] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="Replacement Model for a piece of native code, like a function."),
    )


@dataclass(frozen=True, config=ORMConfig)
class ReachingValue:
    """A symbolic representation of the reaching input and a single, concrete, base64-encoded
    value."""

    symbolic_value: str
    concrete_value_base64: str = dataclasses.field(
        metadata=dict(description="Concrete value encoded as base64 string for more portability")
    )


@dataclass(frozen=True, config=ORMConfig)
class ReachingInput:
    """Information about symbolic input that has reached a destination of importance within the
    program during execution.

    Each input has an associated name in Manticore that gives some insight on its origin.
    """

    name: str = dataclasses.field(
        metadata=dict(description="Identifier name of the symbolic variable")
    )

    symbolic_values: List[ReachingValue] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(
            description="Value(s) associated with this input that reach the last Waypoint"
        ),
    )


@enum.unique
class Detector(str, Enum):
    """Supported detectors for Manticore.

    See the `dwarfcore` module for more info.
    """

    DetectAllPaths = "DetectAllPaths"
    VariableBoundsAccess = "VariableBoundsAccess"
    UninitializedVar = "UninitializedVariable"
    UseAfterFree = "UseAfterFree"
    UnderconstrainedOOB = "UnderconstrainedOOB"
    ConcreteHeapOOB = "ConcreteHeapOOB"


@dataclass(frozen=True, config=ORMConfig)
class DetectorOptionsBase:
    """Common fields for detector options."""

    fast: bool = dataclasses.field(
        default=True,
        metadata=dict(
            description="Whether to return after the first detection or wait until another event stop Manticore---"
            "which could include reaching the last waypoint in a reachability or Manticore exploring all paths. "
            "It is highly recommended to keep this True."
        ),
    )


@dataclass(frozen=True, config=ORMConfig)
class DetectAllPathsOptions(DetectorOptionsBase):
    """A testing detector that fires when each state terminates."""

    detector: Literal[Detector.DetectAllPaths] = dataclasses.field(
        default=Detector.DetectAllPaths,
        metadata=dict(
            description="The detector to enable within Manticore that, upon detection, will return with a "
            "message containing an input that exercises the detected feature. If None, runs "
            "Manticore with default detection mechanisms (like detecting fatal OS errors)"
        ),
    )


@dataclass(frozen=True, config=ORMConfig)
class UnderconstrainedOOBOptions(DetectorOptionsBase):
    """A testing detector that creates a case for every OOB access in underconstrained symex."""

    detector: Literal[Detector.UnderconstrainedOOB] = dataclasses.field(
        default=Detector.UnderconstrainedOOB,
        metadata=dict(description="Underconstrained out-of-bounds memory access detector"),
    )


@dataclass(frozen=True, config=ORMConfig)
class ConcreteHeapOOBOptions(DetectorOptionsBase):
    """A testing detector that creates a case for every OOB access in the heap."""

    detector: Literal[Detector.ConcreteHeapOOB] = dataclasses.field(
        default=Detector.ConcreteHeapOOB,
        metadata=dict(description="Heap out-of-bounds memory access detector"),
    )


@dataclass(frozen=True, config=ORMConfig)
class VariableBoundsAccessOptions(DetectorOptionsBase):
    detector: Literal[Detector.VariableBoundsAccess] = dataclasses.field(
        default=Detector.VariableBoundsAccess,
        metadata=dict(
            description="The detector to enable within Manticore that, upon detection, will return with a "
            "message containing an input that exercises the detected feature. If None, runs "
            "Manticore with default detection mechanisms (like detecting fatal OS errors)"
        ),
    )

    poi_info: List[str] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(
            description="Only these POI functions will be considered for valid detections. "
            "This helps to limit the number of lookups the detector performs. It "
            "is highly suggested that if you know this information, you should "
            "include it."
        ),
    )


@dataclass(frozen=True, eq=True, config=ORMConfig)
class FunctionVariableInfo:
    """Targeted function and variable name for input to uninitialized stack-variable use
    detection."""

    function_name: str = dataclasses.field(
        metadata=dict(description="The target function to look at, as given in a CPG.")
    )
    variable_name: str = dataclasses.field(
        metadata=dict(
            description="The target variable to look at within the function, as given by the CPG."
        )
    )


@dataclass(frozen=True, config=ORMConfig)
class UninitializedVarOptions(DetectorOptionsBase):
    detector: Literal[Detector.UninitializedVar] = dataclasses.field(
        default=Detector.UninitializedVar,
        metadata=dict(
            description="The detector to enable within Manticore that, upon detection, will return with a "
            "message containing an input that exercises the detected feature. If None, runs "
            "Manticore with default detection mechanisms (like detecting fatal OS errors)"
        ),
    )
    poi_info: List[FunctionVariableInfo] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(
            description="Only these POI functions and variables will be considered for valid detections. "
            "This helps to limit the number of lookups the detector performs. It "
            "is highly suggested that if you know this information, you should "
            "include it."
        ),
    )


@dataclass(frozen=True, eq=True, config=ORMConfig)
class FreeUseInfo:
    """Use and free filename(s) and line numbers for input into use after free detection."""

    use_file: str
    use_line: int
    free_file: str
    free_line: int


@dataclass(frozen=True, config=ORMConfig)
class UseAfterFreeOptions(DetectorOptionsBase):
    detector: Literal[Detector.UseAfterFree] = dataclasses.field(
        default=Detector.UseAfterFree,
        metadata=dict(
            description="The detector to enable within Manticore that, upon detection, will return with a "
            "message containing an input that exercises the detected feature. If None, runs "
            "Manticore with default detection mechanisms (like detecting fatal OS errors)"
        ),
    )
    poi_info: List[FreeUseInfo] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(
            description="Only these POI locations will be considered for valid detections. "
            "This helps the detector ignore results that are not the primary focus for validation. "
            "It is highly suggested that if you know this information, you should include it."
        ),
    )


DetectorOptions = Union[
    DetectAllPathsOptions,
    VariableBoundsAccessOptions,
    UninitializedVarOptions,
    UseAfterFreeOptions,
    UnderconstrainedOOBOptions,
    ConcreteHeapOOBOptions,
]


@dataclass(frozen=True, config=ORMConfig)
class ReachingTestCase:
    """A summary of a set of inputs and description that have been saved for replay on a binary.

    ``description`` is human-readable free-form text that gives insight on what Manticore detected.
    """

    description: str = dataclasses.field(
        metadata=dict(description="A description of why there are inputs for this case")
    )

    detector_triggered: Optional[Detector] = dataclasses.field(
        default=None,
        metadata=dict(description="The detector that triggered and relates to the symbolic_inputs"),
    )

    symbolic_inputs: List[ReachingInput] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="The input that was found to trigger a detector or test case"),
    )


@dataclass(frozen=True, config=ORMConfig)
class UnderconstrainedTestCase(ReachingTestCase):
    """A test case generated by under-constrained Manticore."""

    uid: int = dataclasses.field(
        default=-1,
        metadata=dict(description="Unique identifier for the test case"),
    )

    va: int = dataclasses.field(
        default=-1,
        metadata=dict(
            description="The virtual address of the faulty instruction that generated the test case"
        ),
    )

    va_mapping: Optional[str] = dataclasses.field(
        default=None,
        metadata=dict(description="The mapping and offset corresponding to the 'va' field"),
    )

    condition: Optional[str] = dataclasses.field(
        default=None,
        metadata=dict(description="The symbolic condition that causes the faulty behaviour"),
    )

    constraints: List[str] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="The state constraints when recording the test case"),
    )


### Top-level Messages
@dataclass(frozen=False, config=ORMConfig)
class ExplorationTree:
    """A tree representing exploration choices and containing potential errors detected during
    program exploration."""

    state_id: int = dataclasses.field(
        metadata=dict(description="ID of the manticore state corresponding to this tree node")
    )

    cases: List[ReachingTestCase] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="Test cases found during exploration for this state"),
    )

    choices: List[Tuple[str, int]] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(
            description="""Fork choices that resulted in this state. It consists in a list of tuples
(expr, value) where 'expr' is the symbolic expression on which manticore forked and 'value'
the concrete value assigned to the expression after forking"""
        ),
    )

    children: List["ExplorationTree"] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="List of states forked from this state"),
    )

    error_msg: Optional[str] = dataclasses.field(
        default=None,
        metadata=dict(
            description="Optional error message if the state was terminated due to an internal error"
        ),
    )

    def get_state(self, state_id: int) -> Optional["ExplorationTree"]:
        """Get a state in the exploration tree."""
        if self.state_id == state_id:
            return self
        for child in self.children:
            tmp = child.get_state(state_id)
            if tmp:
                return tmp
        return None

    def add_state(self, parent_id: int, state_id: int, choice: Tuple[str, int]) -> bool:
        """Add a state to the exploration tree.

        Return true on success
        """
        parent_state = self.get_state(parent_id)
        if parent_state:
            parent_state.children.append(ExplorationTree(state_id=state_id, choices=[choice]))
            return True
        else:
            return False

    def iter_cases(self) -> Iterable[ReachingTestCase]:
        yield from self.cases
        for child in self.children:
            yield from child.iter_cases()


@dataclass(frozen=True, config=ORMConfig)
class ExploreRet:
    """Results message after processing of an `Explore` message."""

    path: str = dataclasses.field(metadata=dict(title="Location of the binary under analysis"))

    exploration_tree: Optional[ExplorationTree] = dataclasses.field(
        default=None,
        metadata=dict(description="State tree resulting from the exploration task"),
    )

    cases: List[ReachingTestCase] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="Test cases generated by the enabled detectors"),
    )

    warnings: List[str] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="Relevant warnings raised during the exploration task"),
    )


@dataclass(frozen=True, config=ORMConfig)
class ReachabilityRet(ExploreRet):
    """Results message after processing of the `Reachability` message."""

    success: bool = dataclasses.field(
        default=False, metadata=dict(description="Whether we could follow all Waypoints")
    )


@dataclass(frozen=True, config=ORMConfig)
class Explore:
    """A message that will configure Manticore to explore with an optionally enabled detector
    without much direction."""

    command_line_flags: List[str] = dataclasses.field(default_factory=lambda: [])
    concrete_start: str = dataclasses.field(
        default="",
        metadata=dict(
            description="A string of concrete bytes manticore will read from stdin before any purely "
            "symbolic bytes are read"
        ),
    )
    stdin_size: Optional[int] = dataclasses.field(
        default=256,
        metadata=dict(
            description="Maximum number of purely symbolic bytes Manticore can read from stdin"
        ),
    )
    env: Dict[str, str] = dataclasses.field(
        default_factory=lambda: {},
        metadata=dict(description="Dictionary of environment variables: {env_var : value}"),
    )
    detector_options: List[DetectorOptions] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="Enable Manticore detectors to find different kinds of bugs"),
    )
    timeout: Optional[int] = dataclasses.field(
        default=None, metadata=dict(description="Timeout in seconds for the exploration task")
    )


@dataclass(frozen=True, config=ORMConfig)
class Reachability(Explore):
    """Reachability message is the top-level message that represents constraints for POIs."""

    waypoints: List[Waypoint] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(
            description="Waypoint message relates to a specific area of code and contains relevant information for that area."
        ),
    )
    constraint_vars: List[Decl] = dataclasses.field(
        default_factory=lambda: [],
        metadata=dict(description="An initial declaration for symbolic variables."),
    )


@enum.unique
class UnboundedPtrPolicyType(str, Enum):
    """Strategy for handling unbounded pointers."""

    DEFAULT = "default"
    CUSTOM = "custom"
    # TODO(#1586) CPG = "CPG"
    # TODO(#1586) ADJUST_ON_ACCESS = "AdjustOnAccess"


@dataclass(frozen=True, config=ORMConfig)
class UnboundedPtrPolicy:
    """Policy for handling unbounded pointers in under-constrained Manticore."""

    policy_type: UnboundedPtrPolicyType = dataclasses.field(
        default=UnboundedPtrPolicyType.DEFAULT,
        metadata=dict(description="The strategy to use to handle unbounded pointers"),
    )

    max_alternatives: int = dataclasses.field(
        default=3,
        metadata=dict(
            description="The maximum number of alternatives for the number of elements pointed by unbounded pointers. Manticore forks on each alternative"
        ),
    )

    custom_values: Optional[List[int]] = dataclasses.field(
        default=None,
        metadata=dict(description="Custom values to use for the CUSTOM policy type"),
    )


@dataclass(frozen=True, config=ORMConfig)
class ExploreFunction(Explore):
    """A message that configures Manticore to explore a single function using underconstrained
    symbolic execution."""

    target_function: Optional[str] = dataclasses.field(
        default=None,
        metadata=dict(
            description="Describes the function in the current execution environment that should be targeted"
        ),
    )

    input_constraints: Optional[List[str]] = dataclasses.field(
        default=None,
        metadata=dict(description="Additional user-defined constraints on the symbolic state"),
    )

    primitive_ptr_policy: Optional[UnboundedPtrPolicy] = dataclasses.field(
        default=UnboundedPtrPolicy(),
        metadata=dict(
            description="Policy for handling underconstrained unbounded pointers to primitive types (char, int, etc)"
        ),
    )

    complex_ptr_policy: Optional[UnboundedPtrPolicy] = dataclasses.field(
        default=UnboundedPtrPolicy(),
        metadata=dict(
            description="Policy for handling underconstrained unbounded pointers to complex types (structs, objects, etc)"
        ),
    )
