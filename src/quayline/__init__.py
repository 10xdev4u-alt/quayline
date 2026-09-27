"""Quayline: an invoice-self-auditing engine for 46 CFR Part 541 demurrage and detention disputes."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("quayline")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+uninstalled"

__all__ = ["__version__"]
