from collections import deque
from typing import Callable, Collection, Deque, Dict, Generic, Iterable, Set, Type, TypeVar

T = TypeVar("T")
R = TypeVar("R", bound="Digraph")


class Digraph(Generic[T]):
    def __init__(self, nodes: Iterable[T], successors: Callable[[T], Iterable[T]]):
        self.nodes = list(nodes)
        self.successors = successors

    @classmethod
    def from_successor_function(
        cls: Type[R], nodes: Iterable[T], successors: Callable[[T], Iterable[T]]
    ) -> R:
        return cls(nodes, successors)

    @classmethod
    def from_adjacency_list(cls: Type[R], adjacency_list: Dict[T, Iterable[T]]) -> R:
        return cls(adjacency_list.keys(), lambda k: adjacency_list[k])

    def _topological_helper(self, node: T, visited: Set[T], deck: Deque[T]) -> None:
        visited.add(node)
        for succ in self.successors(node):
            if succ not in visited:
                self._topological_helper(succ, visited, deck)
        deck.appendleft(node)

    def topological_sort(self) -> Collection[T]:
        visited: Set[T] = set()
        deck: Deque[T] = deque()
        for node in self.nodes:
            if node not in visited:
                self._topological_helper(node, visited, deck)
        return deck
