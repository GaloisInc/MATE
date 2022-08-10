from __future__ import annotations

import enum
from functools import lru_cache
from typing import Any, Dict, FrozenSet, List, Optional

from pydantic import BaseModel

from mate_common.models.bytes import Gibibytes, Mebibytes, gb_to_mb
from mate_common.models.integration import (
    Explore,
    ExploreFunction,
    Reachability,
    UnboundedPtrPolicy,
)
from mate_common.state_machine import StateMachineMixin

_DEFAULT_DOCKER_MEMORY_LIMIT_GB = Gibibytes(64)


@enum.unique
class MantiserveTaskState(StateMachineMixin, str, enum.Enum):
    """An enumeration of the different states that a ``MantiserveTask`` can be in."""

    Created = "created"
    Running = "running"
    Completed = "completed"
    Failed = "failed"

    @lru_cache
    def _valid_transitions(self) -> Dict[MantiserveTaskState, FrozenSet[MantiserveTaskState]]:
        return {
            MantiserveTaskState.Created: frozenset(
                {MantiserveTaskState.Running, MantiserveTaskState.Failed}
            ),
            MantiserveTaskState.Running: frozenset(
                {MantiserveTaskState.Completed, MantiserveTaskState.Failed}
            ),
            MantiserveTaskState.Completed: frozenset(),
            MantiserveTaskState.Failed: frozenset(),
        }

    def __str__(self) -> str:
        return self.value


@enum.unique
class MantiserveTaskKind(str, enum.Enum):
    """Supported Mantiserve tasks."""

    Reachability = "Reachability"
    Explore = "Explore"
    ExploreFunction = "ExploreFunction"


class _MantiserveTaskOptions(BaseModel):
    docker_image: Optional[str] = None
    """
    The docker image that will be pulled where Mantiserve will
    insert a Manticore instance. This image must be valid with a ``docker
    pull <docker_image>``. It is HIGHLY recommended to use a Docker image to
    isolate Manticore's side-effects.

    If no image is configured, Mantiserve will attempt to use the same
    image used with the Mantiserve task's associated build.
    """

    docker_memory_limit_mb: Mebibytes = gb_to_mb(_DEFAULT_DOCKER_MEMORY_LIMIT_GB)
    """
    A memory limit, in MB, to impose when using Manticore within a Docker container.
    """


class ReachabilityOptions(_MantiserveTaskOptions):
    reach_msg: Reachability
    """
    A Reachability message that directs Manticore along a path.
    """


class ExploreOptions(_MantiserveTaskOptions):
    explore_msg: Explore
    """
    An Explore message that allows Manticore to explore the
    executable without much direction. See the schema model for more
    information.
    """


class ExploreFunctionOptions(_MantiserveTaskOptions):
    explore_msg: ExploreFunction
    """
    An Explore message that directs Manticore to explore one function
    using underconstrained symbolic execution.
    """


class MantiserveTaskInformation(BaseModel):
    """Metadata about a Mantiserve task."""

    task_id: str
    """The unique ID for this Mantiserve task."""

    build_id: str
    """The associated MATE build's ID."""

    artifact_ids: List[str]
    """The IDs of any artifacts associated with this Mantiserve task."""

    kind: MantiserveTaskKind
    """The kind of Mantiserve task."""

    request: Dict[str, Any]
    """The request that kicked off this Mantiserve task."""

    result: Optional[Dict[str, Any]]
    """The task's result, if any."""

    state: MantiserveTaskState
    """The task's state."""

    docker_image: Optional[str]
    """The Docker image that the task was configured with, if any."""


####### Under-constrained mode ########


class UserDefinedConstraint(str):
    """A symbolic constraint defined by the user.

    It consists simply in a string that will later be translated into actual Constraint objects by
    manticore itself
    """

    pass


class UnderConstrainedOptions(BaseModel):
    """Input to the under-constrained plugin."""

    target_function: str
    """Function to execute in under-constrained mode"""

    init_until: Optional[int] = None
    """Address until which to run the program before jumping to the
    target function. If not specified, program will be initialised
    until it reaches main()"""

    native_array_size_policy: UnboundedPtrPolicy
    """Policy used to handle under-constrained raw pointers
    to native types (int*, char*, ...)"""

    complex_array_size_policy: UnboundedPtrPolicy
    """Policy used to handle under-constrained raw pointers
    to complex types (SomeClass*, vector<SomeClass>*, ...)"""

    auto_fix_errors: bool = False
    """Automatically fix out-of-bounds errors:
    - When False, manticore will terminate a state as soon as it results
    in a possible OOB error
    - When True, if manticore detects a possible OOB error, it will try
    to harden the state constraints to enforce the OOB to become a correct
    memory access, and then resume exploring the state"""

    input_constraints: List[UserDefinedConstraint] = []
    """Additional symbolic constraints to initialise manticore with"""
