# Testing

We will use golden tests[1] to ensure consistent behavior. This document aims to keep track of how to properly format a golden test file so that others may read, write, and understand the information accurately.

All _golden_ tests MUST end with the `.gold` suffix, to help organize this directory, and filename should also include the stem of the binary being tested. The following shows an example file listing for the stem file `ex_simple` that is used in testing:
```bash
ex_simple.conc.gold  # golden file for simple concrete case (one output trace)
ex_simple.symb.gold  # godlen file for symbolic multi-output case
ex_simple.bin        # Generic compiled binary (derivation #1)
ex_simple.pie.bin    # PIE compiled binary (derivation #2)
ex_simple.c          # Source file
```

## Simple concrete input/output

The most golden test file is of the following form, where brackets indicate variables
```text
<prog_stem> <arg1> <arg2> ...
<out1>
<out2>
...
```
The first line is almost identical to how you would run the program on the command line, however `<prog_stem>` should only indicate the most base name of the program binary under test, e.g. `ex_simple` if there are both binaries `ex_simple.bin` and `ex_simple.pie.bin`. It is important that all derivative binaries produce the same relevant output. However, which binaries you actually test is up to the test function.

The second line and the rest of the file should consist of the expected output that should be interpretable by both humans and machines. For instance, if there is a program trace of functions, each function visited will have its own line.

An example of this is [./ex_simple.conc.gold](./ex_simple.conc.gold)

## One input, multiple output

Since these tests target Manticore and Manticore tries to explore _all_ paths in one execution, there may be multiple outputs to check for correctness. In this case, we combine the simple concrete format, with the first line staying the same, but use a consistent separator for the multiple outputs. The outputs do not have to be ordered.

The first line follows Manticore's symbolic variable semantics when passing input on the command-line. The `+` symbol stands for 1 byte of symbolic input, and this must be listed in the golden file to pass symbolic input by the command line.


```text
<prog_stem> +++ +++++ <conc_inp> ...
<out1_1>
<out1_2>
...
<out1_n>
====================
<out2_1>
...
```

An example of this is [./ex_simple.symb.gold](./ex_simple.symb.gold)

## Notes

* Currently, there are no golden file semantics for describing how much or what kind of data to use for any other method of user-input to the binary.
* Whitespace matters in golden files

[1]: https://en.wikipedia.org/wiki/Characterization_test
