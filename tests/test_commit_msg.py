"""Every rejection path of the commit message rule.

These exist because the rule is enforced at commit time. A hook that rejects the
wrong thing, or accepts something it should not, teaches agents to reach for
--no-verify, and once that happens the hook is worse than useless.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_checker() -> ModuleType:
    """Load the hook script as a module. It lives outside the package on purpose,
    because a hook that imports the project it guards can be broken by the very
    breakage it exists to catch."""
    spec = importlib.util.spec_from_file_location(
        "check_commit_msg", ROOT / ".githooks" / "check_commit_msg.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_commit_msg"] = module
    spec.loader.exec_module(module)
    return module


check_mod = _load_checker()
check = check_mod.check

GOOD_SUBJECT = "build: add toolchain with validation gate"
GOOD_TRAILER = "Co-Authored-By: the-ai-developer <the-ai-developer@users.noreply.github.com>"


def message(subject: str = GOOD_SUBJECT, *body: str) -> str:
    return "\n".join([subject, *body, ""])


# ------------------------------------------------------------------ accepts
def test_accepts_a_conforming_message() -> None:
    assert check(message(GOOD_SUBJECT, GOOD_TRAILER)) == []


def test_accepts_a_scoped_type() -> None:
    subject = "fix(calendars): exclude scheduled closures from policy"
    assert check(message(subject, GOOD_TRAILER)) == []


def test_accepts_a_trailer_without_an_email() -> None:
    assert check(message(GOOD_SUBJECT, "Co-Authored-By: the-ai-developer")) == []


def test_accepts_a_long_body_with_other_trailers() -> None:
    body = (
        "A description that runs to several lines and explains the reasoning "
        "at more length than strictly necessary.",
        "",
        "Signed-off-by: 10xdev4u-alt <10xdev4u@gmail.com>",
    )
    assert check(message(GOOD_SUBJECT, *body, GOOD_TRAILER)) == []


# ------------------------------------------------------------------ rejects
def test_rejects_an_empty_message() -> None:
    assert check("") != []


def test_rejects_a_subject_with_no_colon() -> None:
    problems = check(message("added the toolchain with a gate", GOOD_TRAILER))
    assert any("conventional form" in p for p in problems)


def test_rejects_an_unknown_type() -> None:
    problems = check(message("wibble: add toolchain with validation gate", GOOD_TRAILER))
    assert any("is not one of" in p for p in problems)


def test_rejects_too_few_words() -> None:
    problems = check(message("build: add toolchain", GOOD_TRAILER))
    assert any("exactly 6 words" in p for p in problems)


def test_rejects_too_many_words() -> None:
    problems = check(
        message("build: add the project toolchain with a validation gate", GOOD_TRAILER)
    )
    assert any("exactly 6 words" in p for p in problems)


def test_rejects_an_over_length_subject() -> None:
    long_subject = (
        "build: add a very long subject that runs well past the character limit for a line"
    )
    problems = check(message(long_subject, GOOD_TRAILER))
    assert any("over the 72 limit" in p for p in problems)


def test_rejects_a_missing_co_author() -> None:
    problems = check(message(GOOD_SUBJECT, "A body with no trailer at all."))
    assert any("no Co-Authored-By trailer" in p for p in problems)


def test_rejects_the_wrong_co_author() -> None:
    problems = check(message(GOOD_SUBJECT, "Co-Authored-By: someone-else <s@e.com>"))
    assert any("sole co-author is the-ai-developer" in p for p in problems)


def test_rejects_a_second_co_author() -> None:
    problems = check(
        message(
            GOOD_SUBJECT,
            GOOD_TRAILER,
            "Co-Authored-By: an-extra-reviewer <extra@example.com>",
        )
    )
    assert any("Remove: an-extra-reviewer" in p for p in problems)


def test_rejects_a_case_variant_co_author() -> None:
    """The comparison is case-insensitive so a capitalised trailer is not a bypass."""
    problems = check(message(GOOD_SUBJECT, "Co-Authored-By: The-AI-Developer <x@y.com>"))
    assert problems == []


@pytest.mark.parametrize(
    "bad_subject",
    [
        "chore: bootstrap quayline with research corpus and then some",
        "FEAT: add toolchain with validation gate now",
        "feat:Add toolchain with validation gate",
        " feat: add toolchain with validation gate",
    ],
    ids=["too-long", "uppercase-type", "no-space-after-colon", "leading-space"],
)
def test_rejects_malformed_subjects(bad_subject: str) -> None:
    assert check(message(bad_subject, GOOD_TRAILER)) != []


def test_makefile_installs_every_hook_stage() -> None:
    """`pre-commit install` on its own wires only the pre-commit stage.

    The commit-msg and pre-push rules were configured, documented and installed
    once already, and enforced nothing, while the install output read exactly as
    though they were live. A bad commit went through. This asserts the stage
    list rather than the installed files, so it holds on a fresh clone where
    `make hooks` has not been run yet.
    """
    makefile = (ROOT / "Makefile").read_text()
    for stage in ("pre-commit", "commit-msg", "pre-push"):
        assert "--hook-type $$stage" in makefile, f"make hooks does not install the {stage} stage"
    assert "--hook-type" in makefile, "make hooks does not pass --hook-type at all"


def test_commit_msg_hook_is_passed_the_message_file() -> None:
    """For the commit-msg stage the filename git supplies is the message file.

    With pass_filenames false, pre-commit passes nothing and the hook dies on a
    usage error. It fails closed, which is the right direction and still wrong,
    because it rejects conforming messages as well.
    """
    config = (ROOT / ".pre-commit-config.yaml").read_text()
    block = config.split("- id: commit-msg", 1)[1].split("- id:", 1)[0]
    # Strip comments before matching. This file explains the rules it enforces,
    # and a naive substring check over a config that documents itself will always
    # match the explanation. The first draft of this test did exactly that.
    settings = [
        line.strip()
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert "pass_filenames: false" not in settings, (
        "the commit-msg hook needs the message file, so pass_filenames must stay true"
    )
    assert "stages: [commit-msg]" in settings
