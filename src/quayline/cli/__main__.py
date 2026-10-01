"""``python -m quayline.cli`` entry point.

Issue 79. The console script in ``pyproject.toml`` is the supported invocation and
this is here so the package is runnable without being installed.
"""

from __future__ import annotations

import sys

from quayline.cli.audit_cmd import main

if __name__ == "__main__":
    sys.exit(main())
