###########
MATE Traces
###########

.. NOTE::
    The CLIs documented below are part of the **legacy** ``mate`` CLI, which is
    in the process of being removed. Everything below is kept for posterity,
    but may no longer be functional.

MATE has the ability to collect block-level execution traces. This is useful because this enables
some analyses that aren't otherwise possible.

Mate first compiles an instrumented binary. In the instrumented binary each basic block has an extra
function call to a logging function, so that when that basic block is executed, it logs its uuid to
``stdout``. Mate can then run this instrumented binary and log the collected traces.

*****************
Collecting Traces
*****************

You can collect traces by running ``mate trace collect``::

    mate trace collect --source [-s] <Path to .ll file> --label [-l] <label> --output-filename [-o] <output.trace> --target-args [-a] "<arg0> <arg1> ..."

This will build an instrumented binary, save it to a workspace (it uses the same default workspace
behavior as ``mate build``), and then run it. If there's already an instrumented binary in that
workspace it will use it instead of rebuilding (yay, workspaces!).

The ``--label`` command line argument gets saved along with the collected trace. The label is
intended to describe the execution trace, and may be specific to a given analysis. For instance, an
analysis may wish to process traces which are labeled as either ``authenticated`` or
``unauthenticated``.

The ``--target-args`` command line argument takes a string containing arguments for the instrumented
binary, and passes them to the instrumented binary.

Example: tracing example_1
--------------------------

Collect traces for ``example_1``::

    mate -v trace collect -s <path_to_example_1.ll>/example_1.ll -l authenticated -o test.trace -a "hello world"

To generate an interesting trace, you'll need to send inputs to the running binary. First start the
instrumented binary running by executing the above command.

To interact with ``example_1``, and likely all other programs, you need to open another
shell into the same docker image and use ``netcat``. You can do this by doing ``docker ps``,
finding the image name (ie, it'll be something like ``musing-jackson``), and then doing ``docker
exec -it <NAME> /bin/bash``. Once in the docker image, use ``netcat``::

    root@28bed379fb65:/builds/mate/MATE/# netcat -v localhost 8081
    localhost [127.0.0.1] 8081 (tproxy) open
    Enter Information: <-- netcat wrote that
    hello there <-- I typed that and hit enter; it's the input that example_1 expects
    world <-- example_1 server wrote that; it's what happens when you authenticate

Once you've finished interacting with the running binary, you can stop it by typing control+c in the
shell running ``mate traces``. This will stop the running binary and write the collected trace to
the specified output file.

The output file produced from running ``example_1`` has a JSON object and looks like::

    $ cat submodules/mate-tests/tests/example_1/challenge_bin/example_1.bin.workspace/test.trace
    {"label": "example_label", "trace": ["<block>:@main:%i0", "<block>:@main:%i2", "<block>:@main:%i3", "<block>:@main:%i5", "<block>:@setupServer:%i0", "<block>:@setupServer:%i2", "<block>:@setupServer:%i4", "Listening on port 8081...", "<block>:@setupServer:%i5", "<block>:@main:%i7", "<block>:@runServer:%i0", "<block>:@runServer:%i1"]}


**********************
Instrumenting Binaries
**********************

It's also possible to build an instrumented binary without running it
with ``mate trace instrument``.

To build an instrumented binary of ``example_1`` but not collect traces, run::

    mate trace instrument submodules/mate-tests/tests/example_1/challenge_bin/example_1.bin.ll
