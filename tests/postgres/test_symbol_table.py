def check_symbol(symbol, binding, typ):
    assert symbol["binding"] == binding
    assert symbol["type"] == typ


def test_symbol_table(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "symbol-menagerie.c", compile_options=dict(extra_compiler_flags=optimization_flags)
    )

    module = session.query(cpg.Module).one()

    # "foo" is a weakly bound function.
    foo = [s for s in module.symbols if s["name"] == "foo"]
    assert len(foo) == 1
    foo = next(iter(foo))
    check_symbol(foo, "STB_WEAK", "STT_FUNC")

    # "bar" is a locally bound (i.e., static) function.
    bar = [s for s in module.symbols if s["name"] == "bar"]
    assert len(bar) == 1
    bar = next(iter(bar))
    check_symbol(bar, "STB_LOCAL", "STT_FUNC")

    # "barp" is a locally bound (i.e., static) global variable (i.e., object)
    barp = [s for s in module.symbols if s["name"] == "barp"]
    assert len(barp) == 1
    barp = next(iter(barp))
    check_symbol(barp, "STB_LOCAL", "STT_OBJECT")

    # "barp_result" is an globally bound (i.e., non-static) global variable (i.e., object)
    barp_result = [s for s in module.symbols if s["name"] == "barp_result"]
    assert len(barp_result) == 1
    barp_result = next(iter(barp_result))
    check_symbol(barp_result, "STB_GLOBAL", "STT_OBJECT")

    # "baz" is a globally bound (i.e., non-static) function
    baz = [s for s in module.symbols if s["name"] == "baz"]
    assert len(baz) == 1
    baz = next(iter(baz))
    check_symbol(baz, "STB_GLOBAL", "STT_FUNC")

    # "baz_alias" is a globally bound alias of "baz"
    baz_alias = [s for s in module.symbols if s["name"] == "baz_alias"]
    assert len(baz_alias) == 1
    baz_alias = next(iter(baz_alias))
    check_symbol(baz_alias, "STB_GLOBAL", "STT_FUNC")

    # "baz_weak_alias" is a weakly bound alias of "baz"
    baz_weak_alias = [s for s in module.symbols if s["name"] == "baz_weak_alias"]
    assert len(baz_weak_alias) == 1
    baz_weak_alias = next(iter(baz_weak_alias))
    check_symbol(baz_weak_alias, "STB_WEAK", "STT_FUNC")

    # "quux" is a globally bound thread-local variable
    quux = [s for s in module.symbols if s["name"] == "quux"]
    assert len(quux) == 1
    quux = next(iter(quux))
    check_symbol(quux, "STB_GLOBAL", "STT_TLS")

    # "quux2" is a locally bound (i.e., static) thread-local variable
    quux2 = [s for s in module.symbols if s["name"] == "quux2"]
    assert len(quux2) == 1
    quux2 = next(iter(quux2))
    check_symbol(quux2, "STB_LOCAL", "STT_TLS")
