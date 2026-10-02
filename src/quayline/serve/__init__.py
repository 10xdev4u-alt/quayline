"""A local HTTP intake, so a client is not emailing us a PDF to run a CLI.

Issue 191. Loopback only, nothing stored, no accounts. Read ``security.py`` before
changing anything here.
"""

from __future__ import annotations

__all__ = ["app", "security"]
