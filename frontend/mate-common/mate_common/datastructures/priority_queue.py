"""This module provides a max-heap wrapper over Python's min-heap."""

from heapq import heappop, heappush
from typing import Generic, List, Tuple, TypeVar

T = TypeVar("T")


class PriorityQueue(Generic[T]):
    """Wrapper to enforce heap invariants by hiding underlying list.

    Unfortunately python provides a standard min-heap but not a max-heap;
    this class ranks by maximum priority by inverting the priority before pushing
    to the standard min-heap. This makes me sad but seems to be the goto solution.

    Elements of the priority queue are a 3-tuple of
        (priority, insertion counter index, data)
    """

    def __init__(self) -> None:
        self._data: List[Tuple[float, int, T]] = list()
        # The heapq lib recommends keeping a counter to use as a tie-breaker
        self._counter = 0

    def push(self, elem: T, priority: float) -> None:
        """Push the negation of the priority to max-heapify our min-heap."""
        heappush(self._data, (-1 * priority, self._counter, elem))
        self._counter += 1

    def pop(self) -> T:
        """Returns just the data of the tuple with the highest priority."""
        if len(self._data) == 0:
            raise Exception("Attempted to pop off the PQ after it was empty")
        return heappop(self._data)[2]

    def empty(self) -> bool:
        """Reports whether the PQ is empty."""
        return len(self._data) == 0

    def pop_all(self) -> List[T]:
        """Removes and returns all data in priority order."""
        accum: List[T] = []
        while not self.empty():
            accum.append(self.pop())
        return accum
