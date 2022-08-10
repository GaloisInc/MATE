import pytest

from mantiserve.liftsmt2 import validate_smt2

smt2_tst_exprs = [
    ("Hello", [], 1),
    ("(assert ())", [], 2),
    ("(assert (= $replace#0 4197882))", [0], 0),
    ("(assert (= $replace#0 4197882))", [], 1),
]


@pytest.mark.parametrize("expr,replace,num_errs", smt2_tst_exprs)
def test_validation(expr, replace, num_errs):
    assert len(validate_smt2(expr, replace)) == num_errs
