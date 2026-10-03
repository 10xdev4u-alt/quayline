"""The README against the code, because they disagree silently.

`README.md` said "There is no entry point: no function takes a document and returns an
audit result" while `engine/audit.py` had exported `audit()` since issue 167, and
`quayline serve` had been in the CLI since issue 79. Nothing failed, because a
document contradicting the code is not a state any test could see.

This is the same defect as the stale figures in `docs/ONBOARDING.md` in issue 203 and
the machine path in the specimen in issue 208, at the level of a sentence. A README is
the first thing a new contributor reads and the first thing a prospective user reads,
and a false claim in either is worth more than a missing one.
"""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from quayline.cli import audit_cmd, serve_cmd
from quayline.engine.audit import audit

README = Path(__file__).resolve().parent.parent / "README.md"


def _cli_help() -> str:
    """The command line's own ``--help``, captured from stdout.

    ``main`` prints help and exits, so SystemExit is the documented outcome rather than
    a failure.
    """
    buffer = io.StringIO()
    with redirect_stdout(buffer), pytest.raises(SystemExit):
        audit_cmd.main(["--help"])
    return buffer.getvalue()


#: Subcommands the CLI advertises, read from `--help` at import so a rename shows up
#: here rather than in a list somebody maintains by hand.
_SUBCOMMANDS: set[str] = set(re.findall(r"^\s{2,}([a-z][a-z-]+)\s", _cli_help(), re.M))


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def test_the_readme_exists_and_is_not_empty() -> None:
    assert _readme().strip()


@pytest.mark.parametrize(
    "claim",
    [
        "there is no entry point",
        "no function takes a document",
        "nothing joins them",
        "the engine recomputes and there is no product",
    ],
)
def test_the_readme_makes_no_claim_that_is_now_false(claim: str) -> None:
    """Each of these was true once and is not now.

    Listed rather than pattern-matched, because a general "no stale claims" check is a
    sentiment and this is a list. When the next sentence goes false it gets added here
    with the issue that made it false.
    """
    assert claim not in _readme().lower(), (
        f"the README still says {claim!r}. Check whether it became true again, and if so "
        f"delete this entry rather than the sentence in the README."
    )


def test_the_entry_point_the_readme_names_exists() -> None:
    """`quayline audit` and `quayline serve` are named in Running it. Both must exist."""
    assert callable(audit)
    assert hasattr(audit_cmd, "main")
    assert hasattr(serve_cmd, "add_parser")


def test_the_readme_states_one_carrier_and_the_readme_matches_coverage() -> None:
    """The single most load-bearing number in the README.

    A reader deciding whether to install needs to know the money check covers one
    carrier, not nine. If the coverage improves this test should be updated with it, in
    the same pull request that improves it.
    """
    readme = _readme()
    match = re.search(r"money recomputation runs for \*\*(\w+)\*\*", readme)
    assert match, "the README no longer states which carriers the money check covers"
    assert match.group(1).lower() == "one", (
        "coverage changed. Update this test and the README in the same pull request."
    )


def test_the_running_instructions_name_real_subcommands() -> None:
    """Every `quayline <word>` in Running it must be a subcommand the CLI has.

    Read from the command line's own ``--help`` rather than a hand-kept list, so a
    subcommand added to the CLI is accepted and one the README invents is not.

    An earlier version reached into ``argparse``'s private ``_subparsers``, which is an
    ``_ArgumentGroup`` and exposes no choices at all. Running ``--help`` is what a
    reader would do, and it has no private anything in it.
    """

    block = _readme().split("## Running it", 1)[-1].split("## Building", 1)[0]
    commands = set(re.findall(r"\bquayline ([a-z-]+)", block))
    assert commands, "the Running it section names no quayline command"
    known = set(_SUBCOMMANDS)
    unknown = commands - known
    assert not unknown, (
        f"the README tells a reader to run {sorted(unknown)}, which are not subcommands. "
        f"The CLI has {sorted(known)}."
    )
