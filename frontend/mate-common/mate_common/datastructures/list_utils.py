"""This module provides list manipulation functions."""

from typing import List, Tuple, TypeVar

T = TypeVar("T")


def partition_on_common_prefix(
    list_a: List[T], list_b: List[T]
) -> Tuple[List[T], List[T], List[T]]:
    """Takes two lists a and b, and returns three lists: their common prefix, the remainder of list
    a, the remainder of list b."""
    if list_a == []:
        return ([], [], list_b)
    if list_b == []:
        return ([], list_a, [])
    if len(list_a) > len(list_b):
        shorter_list = list_b
        longer_list = list_a
    else:
        shorter_list = list_a
        longer_list = list_b

    mutual: List[T] = []
    remaining_a: List[T] = []
    remaining_b: List[T] = []
    # iterate through the shorter list to avoid OOB accesses
    for shorter_index, element in enumerate(shorter_list):
        if (
            longer_list[shorter_index] == element
        ):  # we iterate through the shorter list, so compare against that position in the longer list
            mutual.append(element)
        else:
            remaining_a = list_a[shorter_index:]
            remaining_b = list_b[shorter_index:]
            return (mutual, remaining_a, remaining_b)
    # if execution gets here it means we've exhausted the shorter list
    return (
        (mutual, [], list_b[shorter_index + 1 :])
        if (list_a == shorter_list)
        else (mutual, list_a[shorter_index + 1 :], [])
    )
