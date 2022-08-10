from typing import Any, List

from elftools.dwarf.dwarf_expr import DWARFExprParser

from .ast import DwarfInstr
from .enums import lookup_DW_OP


class Decoder(DWARFExprParser):
    """A decoder for the DWARF binary expression format.

    Expressions in the DWARF expression language are usually embedded in a binary format. This class
    uses pyelftools' ``DWARFExprParser`` functionality to decode these into a meaningful Python
    datastructure.
    """

    def __init__(self, structs: Any) -> None:
        super().__init__(structs)
        self._parsed: List[Any] = []
        self._result: List[DwarfInstr] = []

    def _convert_parsed(self) -> List[DwarfInstr]:
        result = []
        for expr_op in self._parsed:
            op = lookup_DW_OP(expr_op.op_name)
            assert op is not None
            result.append(DwarfInstr(op, expr_op.args))
        return result

    def process_expr(self, expr: List[int]) -> None:
        # print(f"Processing {describe_DWARF_expr(expr, self.structs)}")
        self._parsed = super().parse_expr(expr)
        self._result = self._convert_parsed()

    def get_result(self) -> List[DwarfInstr]:
        return self._result
