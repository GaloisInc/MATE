"""Test that we're able to unambiguously access function parameters that come from expanded variadic
templates."""

import pytest


# TODO(ww): Re-write this without the MachineFunction indirection
# once we fix Argument -> DWARFArgument relationships.
# See: https://gitlab-ext.galois.com/mate/MATE/-/issues/1053
@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        # TODO(ww): The tests fail at these optimization levels,
        # probably because of inlining.
        # ("-O2",),
        # ("-O3",),
    ],
)
def test_expanded_variadic_parameters(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2(
        "variadictemplatemultiple.cpp", compile_options=dict(extra_compiler_flags=cflags)
    )

    foo_name = (
        "double foo<double, double, double, int, int, int>"
        "(std::tuple<double, double, double>, std::tuple<int, int, int>)"
    )
    foo = session.query(cpg.Function).filter_by(demangled_name=foo_name).one()
    foo_mf = foo.machine_functions[0]

    # foo has two formal parameters, each of which is a variadically expanded tuple
    foo_args = sorted(foo_mf.arguments, key=lambda node: node.arg)
    assert len(foo_args) == 2

    assert foo_args[0].name == "args1"
    assert foo_args[1].name == "args2"

    # bar has 13 formal parameters, all of which are expanded from a single variadic
    # parameter pack
    bar_name = (
        "unsigned long bar<int, int, int, int, int, int, int, int, int, int, int, int, int>"
        "(int, int, int, int, int, int, int, int, int, int, int, int, int)"
    )
    bar = session.query(cpg.Function).filter_by(demangled_name=bar_name).one()
    bar_mf = bar.machine_functions[0]

    bar_args = sorted(bar_mf.arguments, key=lambda node: node.arg)
    assert len(bar_args) == 13

    for idx, bar_arg in enumerate(bar_args):
        assert bar_arg.from_variadic_template is True
        assert bar_arg.original_name == bar_arg.name == "args"

        # For a single variadic template expansion with no other parameters at all,
        # variadic_index will always be 0, template_index will always match the current
        # index (and thus parameter_index).
        assert bar_arg.variadic_index == 0
        assert idx == bar_arg.parameter_index == bar_arg.template_index

    # baz has 4 formal parameters: one from a template type parameter, and three from
    # a single variadic parameter pack
    baz_name = "unsigned long baz<int, int, int, int>(int, int, int, int)"
    baz = session.query(cpg.Function).filter_by(demangled_name=baz_name).one()
    baz_mf = baz.machine_functions[0]

    baz_args = sorted(baz_mf.arguments, key=lambda node: node.arg)
    assert len(baz_args) == 4

    baz_x_arg = baz_args[0]
    assert baz_x_arg.name == "x"

    for idx, baz_arg in enumerate(baz_args[1:], start=1):
        assert baz_arg.from_variadic_template is True
        assert baz_arg.original_name == baz_arg.name == "args"

        # For a single variadic template expansion with a single leading parameter
        # variadic_index will always be 1, parameter_index will always match the current
        # index, and template_index will be the current index - 1 (since we're starting at 1)
        assert baz_arg.variadic_index == 1
        assert idx == baz_arg.parameter_index
        assert baz_arg.template_index == idx - 1
