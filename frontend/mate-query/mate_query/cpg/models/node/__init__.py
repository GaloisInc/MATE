"""This package contains specializations of the ``Node`` class.

The query interface automatically instantiates these classes when the
appropriate type of node is retrieved from the database. For instance,
if a query returns a set of instructions, the result will be an iterable
of objects of the ``Instruction`` class, rather than the bare ``Node``
class.

In addition to accessing the attributes of these classes after a query is
executed, the attributes and relationships can also be used as SQLAlchemy
expressions in a filter, and the classes themselves can be used as if they were
tables.
"""
from .analysis import *
from .ast import *
from .dwarf import *
from .translation_unit import *
