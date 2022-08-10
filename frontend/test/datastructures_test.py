from collections import defaultdict
from typing import Collection, DefaultDict, Dict, Iterable, List

import hypothesis.strategies as st
import pytest
from hypothesis import given

from mate_common.datastructures.dict_utils import recursive_merge
from mate_common.datastructures.digraph import Digraph
from mate_common.datastructures.list_utils import partition_on_common_prefix
from mate_common.datastructures.priority_queue import PriorityQueue


@pytest.mark.parametrize(
    "inp, outp",
    [
        ({0: {1, 2}, 2: {3, 4}}, [0, 2, 4, 3, 1]),
        (dict(), []),
        ({4: {3}, 3: {2}, 2: {1}}, [4, 3, 2, 1]),
    ],
)
def test_topological_sort(inp, outp):
    d: Dict[int, Iterable[int]] = defaultdict(set)
    d.update(inp)
    assert list(Digraph.from_adjacency_list(d).topological_sort()) == outp


@given(st.dictionaries(st.integers(), st.sets(st.integers())))
def test_topological_sort_properties(rand):
    adjacency_list: DefaultDict = defaultdict(set)
    adjacency_list.update(rand)
    sorted_list: Collection = Digraph.from_adjacency_list(adjacency_list).topological_sort()

    # No superfluous items
    assert set(sorted_list) <= set(adjacency_list.keys())

    # No item appears twice
    assert len(sorted_list) == len(set(sorted_list))

    # Removing a key/value pair can only shrink the resulting list
    if len(adjacency_list) > 0:
        del adjacency_list[next(iter(adjacency_list.keys()))]
        assert len(sorted_list) >= len(
            Digraph.from_adjacency_list(adjacency_list).topological_sort()
        )


def test_priority_queue():
    pq = PriorityQueue[str]()
    assert pq.empty()
    pq.push("one", priority=1)
    assert not pq.empty()
    pq.push("two", priority=2)
    pq.push("neg_one", priority=-1)
    pq.push("zero", priority=0)
    assert not pq.empty()
    assert pq.pop() == "two"
    pq.push("one_and_a_half", priority=1.5)
    assert pq.pop_all() == ["one_and_a_half", "one", "zero", "neg_one"]
    assert pq.empty()


def test_partition_on_common_prefix():
    empty: List[int] = []  # to help Mypy
    assert partition_on_common_prefix([1, 2, 3], [1, 3, 4]) == ([1], [2, 3], [3, 4])
    assert partition_on_common_prefix([2, 3], [3, 4]) == (empty, [2, 3], [3, 4])
    assert partition_on_common_prefix(empty, [3, 4]) == (empty, empty, [3, 4])
    assert partition_on_common_prefix([1, 2], empty) == (empty, [1, 2], empty)
    assert partition_on_common_prefix(empty, empty) == (empty, empty, empty)
    assert partition_on_common_prefix([1], [1, 3]) == ([1], empty, [3])
    assert partition_on_common_prefix([1, 3], [1]) == ([1], [3], empty)


@given(st.dictionaries(st.integers(), st.integers()), st.dictionaries(st.integers(), st.integers()))
def test_recursive_merge(d1, d2):
    d1_copy = dict(d1)
    d2_copy = dict(d2)
    merged = recursive_merge(d1, d2)
    assert d1_copy == d1  # unmodified
    assert d2_copy == d2  # unmodified
    assert set(d1.keys()) | set(d2.keys()) <= set(merged.keys())
    assert set(d2.values()) <= set(merged.values())
