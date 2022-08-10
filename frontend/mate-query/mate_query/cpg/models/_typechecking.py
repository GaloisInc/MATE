"""This module exports a class that can be used as a base class for any class that is used in such a
way that Mypy can't figure out if/how it's attributes are defined. The two canonical examples are:

- Classes with a custom implementation of ``__getattr__``.
- Subclasses of Node, which have many attributes that are set dynamically by
  ``setattr``.

See https://mypy.readthedocs.io/en/latest/cheat_sheet_py3.html.
"""

from typing import TYPE_CHECKING, Any


class _HasDynamicAttributes:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)


class _ClassHasDynamicAttributes(type, _HasDynamicAttributes):
    """This is a metaclass version of ``HasDynamicAttributes``.

    It's effect is to convince Mypy that a class has dynamically set *class variables* rather than
    dynamic *instance variables*.
    """

    pass


if TYPE_CHECKING:

    HasDynamicAttributes = _HasDynamicAttributes
    ClassHasDynamicAttributes = _ClassHasDynamicAttributes

else:

    HasDynamicAttributes = object
    ClassHasDynamicAttributes = type
