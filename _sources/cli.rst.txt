############################
Command-Line Tools Reference
############################

.. TIP::
  See :doc:`mate-cli-overview` for an overview of these tools.

.. autoprogram:: mate_cli.cli:parser
  :prog: mate-cli

.. NOTE::
  The ``mate.build.tob_chess_utils.tools`` CLIs are legacy interfaces that should not be
  used directly. They are in the process of being removed. MATE does not use
  these CLIs and does not test their functionality.

.. autoprogram:: mate.build.tob_chess_utils.tools.margin:parser
  :prog: python3 -m mate.build.tob_chess_utils.tools.margin

.. autoprogram:: mate.build.tob_chess_utils.tools.aspirin:parser
  :prog: python3 -m mate.build.tob_chess_utils.tools.aspirin

.. autoprogram:: mate.build.tob_chess_utils.tools.migraine:parser
  :prog: python3 -m mate.build.tob_chess_utils.tools.migraine
