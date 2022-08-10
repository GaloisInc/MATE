"""This module provides dict manipulation functions."""

from typing import Any, Dict, TypeVar

T = TypeVar("T")


def recursive_merge(d1: Dict[T, Any], d2: Dict[T, Any]) -> Dict[T, Any]:
    """Merge two dictionaries, merging any sub-dictionaries at the same key.

    If the two dictionaries have the same key (path) but different values, the
    values in the second dictionary will be used.

    Returns a freshly-allocated dict.

    >>> recursive_merge({'foo': {'bar': 'baz'}}, {})
    {'foo': {'bar': 'baz'}}

    >>> recursive_merge({}, {'foo': {'bar': 'baz'}})
    {'foo': {'bar': 'baz'}}

    >>> recursive_merge({'foo': {'bar': 'baz'}}, {'foo': {'quux': 'asdf'}})
    {'foo': {'bar': 'baz', 'quux': 'asdf'}}

    >>> recursive_merge({'foo': {'bar': 'baz'}}, {'foo': {'bar': 'asdf'}})
    {'foo': {'bar': 'asdf'}}
    """
    ret = dict(d1)  # copy
    for (key, d2_value) in d2.items():
        if key not in ret or not isinstance(d2_value, dict):
            ret[key] = d2_value
            continue
        ret[key] = recursive_merge(d1[key], d2_value)
    return ret
