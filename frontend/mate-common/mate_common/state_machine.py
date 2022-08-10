"""Typing protocols and mixins for using Python enums as state machines."""

from typing import Dict, FrozenSet, Protocol, TypeVar

_TransitionableSelf = TypeVar("_TransitionableSelf", bound="_Transitionable")


class _Transitionable(Protocol):
    def _valid_transitions(
        self: _TransitionableSelf,
    ) -> Dict[_TransitionableSelf, FrozenSet[_TransitionableSelf]]:
        ...


class StateMachineMixin:
    def can_transition_to(self: _Transitionable, other: _Transitionable) -> bool:
        """Returns whether the current state can transition to the given ``other`` state."""
        return other in self._valid_transitions()[self]

    def is_terminal(self: _Transitionable) -> bool:
        """Returns whether this state is terminal, i.e. has no transitions."""
        return len(self._valid_transitions()[self]) == 0

    def start(self: _Transitionable) -> _Transitionable:
        return next(iter(self._valid_transitions().keys()))
