"""Common exception classes and utilities for MATE."""

import subprocess
from signal import Signals
from textwrap import dedent


class MateError(Exception):
    """A common superclass for all MATE-related errors.

    Prefer throwing a more specific subclass rather than this exception.
    """

    pass


def process_error_to_message(cpe: subprocess.CalledProcessError) -> str:
    exit_code_text = dedent(
        f"""
        {cpe.cmd} exited with {cpe.returncode};
        """
    ).strip()

    # "If the process exited due to a signal, this will be the negative
    # signal number."
    if cpe.returncode < 0:
        code = abs(cpe.returncode)
        try:
            exit_code_text = dedent(
                f"""
                {cpe.cmd} exited due to signal {Signals(code).name} ({str(code)});
                """
            ).strip()
        except ValueError:
            exit_code_text = dedent(
                f"""
                {cpe.cmd} exited due to unknown/invalid signal {str(code)};
                """
            ).strip()

    message = dedent(
        f"""
        {exit_code_text}

        STDOUT:
        {cpe.stdout}

        STDERR:
        {cpe.stderr}
        """
    ).strip()

    return message
