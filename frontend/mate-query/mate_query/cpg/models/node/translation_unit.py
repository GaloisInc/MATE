"""Nodes corresponding to translation units in the compilation process.

At runtime, the models here are accessed via attributes on a CPG, not directly.
"""

from mate_common.models.cpg_types import NodeKind
from mate_query.cpg.models.node._typechecking import NodeMixin


class TranslationUnit(NodeMixin):
    _kind = NodeKind.TRANSLATION_UNIT
