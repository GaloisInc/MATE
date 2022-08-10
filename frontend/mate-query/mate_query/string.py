"""Module implementing an enhanced string column type for SQLAlchemy with a support for regular
expression operators in Postgres and SQLite.

http://xion.io/post/code/sqlalchemy-regex-filters.html
https://gist.github.com/Xion/204ddbd020f1a4275a53
"""
from __future__ import annotations

from re import Pattern
from typing import Any

from sqlalchemy.ext.hybrid import Comparator
from sqlalchemy.sql.expression import BinaryExpression, literal
from sqlalchemy.sql.operators import custom_op

__all__ = ["StringComparator"]


class StringComparator(Comparator):
    """A custom comparator for strings supporting a ``re_match`` operation."""

    def re_match(self, other: Pattern) -> _RegexMatchExpression:
        other0: Any = other
        if isinstance(other, Pattern):
            other0 = other.pattern
        return _RegexMatchExpression(self.__clause_element__(), literal(other0), custom_op("~"))

    def operate(self, op: Any, other: Any, **_kwargs: Any) -> Any:
        return op(self.__clause_element__(), other)


class _RegexMatchExpression(BinaryExpression):
    """Represents matching of a column againsts a regular expression."""
