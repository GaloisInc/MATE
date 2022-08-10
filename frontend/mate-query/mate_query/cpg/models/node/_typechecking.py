"""This module contains a class ``NodeMixin`` which is equal to ``mate_query.cpg.models.core.Node``
at type-checking time, but is just ``object`` at runtime.

This is used as a base class for all the node mix-ins, because they are only mixed into subclasses
of ``Node``. Mypy can't use that information without a little bit of help.
"""

from typing import TYPE_CHECKING

from mate_common.utils import SPHINX_BUILD

if TYPE_CHECKING or SPHINX_BUILD:
    from mate_query.cpg.models.core.node import Node

    class NodeMixin(Node):
        pass

else:

    class NodeMixin:
        pass
