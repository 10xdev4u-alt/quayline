"""The exit contract, in a leaf module.

Two callers need these numbers and neither may import the other. The command line
starts the intake, and the intake renders an audit with the command line's own
formatters. Putting the constants here gives both a dependency that points nowhere,
which is the only way to let two modules need each other's contract without needing
each other's code.

The values are the contract. They are asserted in ``tests/test_cli.py`` and asserted
again over HTTP in ``tests/test_serve.py``, because a client reads the number and a
shell reads the number and they must agree.
"""

from __future__ import annotations

#: The document is clean. Nothing to dispute.
EXIT_CLEAN = 0

#: The document is worth a dispute. The human went looking and found something, or
#: the carrier admitted it. Distinct from clean because a batch of invoices needs to
#: separate the two without reading them.
EXIT_FILE_WORTHY = 1

#: The engine could not reach a verdict. A bad PDF, an unparseable rate rule, an
#: internal failure. Never a silent zero: a caller that treats a failure as a clean
#: bill is how a disputed invoice gets paid.
EXIT_ENGINE_ERROR = 2

EXIT_CODES = (EXIT_CLEAN, EXIT_FILE_WORTHY, EXIT_ENGINE_ERROR)

__all__ = ["EXIT_CLEAN", "EXIT_CODES", "EXIT_ENGINE_ERROR", "EXIT_FILE_WORTHY"]
