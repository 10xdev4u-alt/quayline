"""Every rejection path of the commit message rule.

These exist because the rule is enforced at commit time. A hook that rejects the
wrong thing, or accepts something it should not, teaches agents to reach for
--no-verify, and once that happens the hook is worse than useless.
"""

from __future__ import annotations

import importlib.util
import re as _re
import subprocess
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


# ------------------------------------------------------------------ issue 129
# The address, not just the name.


def test_rejects_a_wrong_co_author_address() -> None:
    """The exact mistake I made and the hook accepted.

    A Gmail address in place of the account address does not fail the commit, does
    not warn, and does not affect the gate. It records an unlinked contributor, which
    is indistinguishable from no co-author at all.
    """
    problems = check(
        message(
            GOOD_SUBJECT,
            "Co-Authored-By: the-ai-developer <the-ai-developer@users.noreply@gmail.com>",
        )
    )
    assert len(problems) == 1
    assert "the-ai-developer@users.noreply@gmail.com" in problems[0]
    assert "users.noreply.github.com" in problems[0], "the message must name the required address"
    assert "unlinked contributor" in problems[0], "the message must say why it matters"


@pytest.mark.parametrize(
    "address",
    [
        "the-ai-developer@users.noreply.github.com",
        "THE-AI-DEVELOPER@USERS.NOREPLY.GITHUB.COM",
        "The-Ai-Developer@Users.NoReply.GitHub.com",
    ],
)
def test_the_address_is_case_insensitive(address: str) -> None:
    """Email local parts are technically case sensitive and domains are not, but
    GitHub matches case insensitively, so a case variant must not be a false
    positive that trains people to disable the check."""
    assert check(message(GOOD_SUBJECT, f"Co-Authored-By: the-ai-developer <{address}>")) == []


@pytest.mark.parametrize(
    "address",
    [
        "the-ai-developer@users.noreply.gmail.com",
        "the-ai-developer@gmail.com",
        "someone-else@users.noreply.github.com",
        "the-ai-developer",
    ],
)
def test_a_near_miss_address_is_rejected(address: str) -> None:
    for problems in (
        check(message(GOOD_SUBJECT, f"Co-Authored-By: the-ai-developer <{address}>")),
    ):
        assert problems, address


def test_a_correct_address_with_a_wrong_name_is_still_rejected() -> None:
    """Name and address are checked together. Either alone is not the rule."""
    problems = check(
        message(
            GOOD_SUBJECT, "Co-Authored-By: someone-else <the-ai-developer@users.noreply.github.com>"
        )
    )
    assert problems
    assert "sole co-author" in problems[0]


def test_a_wrong_name_with_a_wrong_address_reports_both() -> None:
    problems = check(message(GOOD_SUBJECT, "Co-Authored-By: someone <someone@example.com>"))
    joined = " ".join(problems)
    assert "sole co-author" in joined
    assert "someone@example.com" in joined


def test_two_co_authors_are_rejected_even_with_correct_addresses() -> None:
    """The count rule, now that a bad address is no longer the usual way to trip it."""
    problems = check(
        message(
            GOOD_SUBJECT,
            "Co-Authored-By: the-ai-developer <the-ai-developer@users.noreply.github.com>",
            "Co-Authored-By: someone-else <someone@example.com>",
        )
    )
    joined = " ".join(problems)
    assert "sole co-author" in joined
    assert "exactly one Co-Authored-By trailer" in joined


def test_the_repository_history_carries_the_address_the_rule_requires() -> None:
    """Guards against a bad address already being in history.

    The rule is only worth anything if the history it is supposed to describe
    actually satisfies it, and a bad address in a merged commit is not visible from
    the diff of the change that added the check.
    """
    subject_rule = r"^Co-Authored-By:\s*[^<]+?\s*<[^>]+>\s*$"
    log = subprocess.run(
        ["git", "log", "--format=%B"], capture_output=True, text=True, check=True
    ).stdout
    trailers = [ln for ln in log.splitlines() if ln.lower().startswith("co-authored-by:")]
    assert trailers, "history must carry co-author trailers"
    for trailer in trailers:
        assert _re.match(subject_rule, trailer), f"malformed trailer in history: {trailer!r}"
        email = trailer.rsplit("<", 1)[1].rstrip(">").strip()
        assert email.lower() == GOOD_TRAILER.rsplit("<", 1)[1].rstrip(">"), trailer


def message(subject: str = GOOD_SUBJECT, *body: str) -> str:
    return "\n".join([subject, *body, ""])


# ------------------------------------------------------------------ accepts
def test_accepts_a_conforming_message() -> None:
    assert check(message(GOOD_SUBJECT, GOOD_TRAILER)) == []


def test_accepts_a_scoped_type() -> None:
    subject = "fix(calendars): exclude scheduled closures from policy"
    assert check(message(subject, GOOD_TRAILER)) == []


def test_rejects_a_trailer_without_an_email() -> None:
    """Replaces a test that accepted this, written before the rule existed.

    GitHub resolves a co-author by email. A trailer with no address attributes nobody,
    so it is a commit that appears to carry the co-author and does not.
    """
    problems = check(message(GOOD_SUBJECT, "Co-Authored-By: the-ai-developer"))
    assert problems
    assert "no Co-Authored-By trailer" in problems[0]


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
    problems = check(
        message(
            GOOD_SUBJECT,
            "Co-Authored-By: The-AI-Developer <the-ai-developer@users.noreply.github.com>",
        )
    )
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


# ---------------------------------------------------------------- issue 121
# .githooks must be usable as a core.hooksPath, or overriding it silently
# disables every check in it.


def _hooks_dir() -> Path:
    return ROOT / ".githooks"


@pytest.mark.parametrize("hook", ["commit-msg", "pre-commit", "pre-push"])
def test_every_hook_this_project_relies_on_exists(hook: str) -> None:
    """A named list rather than a directory listing, so deleting a hook is a test
    failure instead of a silent loss of enforcement."""
    assert (_hooks_dir() / hook).exists(), hook


@pytest.mark.parametrize("hook", ["commit-msg"])
def test_the_shim_is_executable(hook: str) -> None:
    """If the execute bit is lost git skips the hook and we are back to issue 121.

    The failure is invisible: git does not warn, it just does not run the hook.
    """
    mode = (_hooks_dir() / hook).stat().st_mode
    assert mode & 0o111, f".githooks/{hook} is not executable; git will skip it"


def test_the_shim_delegates_to_the_tested_checker() -> None:
    """The logic lives in the importable module, not in the shell.

    A hook with logic in it is a hook nobody tests, and this one is the only thing
    standing between a bad commit and main.
    """
    shim = (_hooks_dir() / "commit-msg").read_text()
    assert "check_commit_msg.py" in shim
    assert "awk" not in shim and "sed " not in shim, "rule logic must not live in the shim"


def test_pointing_hooks_path_at_githooks_still_enforces_the_rule(tmp_path: Path) -> None:
    """The regression, end to end, through a real git commit.

    This is the test issue 121 asked for. Everything else here checks the parts;
    this one reproduces the actual bypass, in a throwaway repository, by making
    the same mistake again and asserting it no longer works.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
    }

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=repo, env=env, capture_output=True, text=True, check=True)

    run("git", "init", "-q")
    run("git", "config", "user.name", "t")
    run("git", "config", "user.email", "t@example.com")
    (repo / "f").write_text("x")
    run("git", "add", "f")
    # Exactly the override that caused the incident.
    run("git", "config", "core.hooksPath", str(_hooks_dir()))

    bad = subprocess.run(
        ["git", "commit", "-m", "feat: render packets grouped by ground"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode != 0, "the override disabled the commit-msg check"
    assert "6 words" in bad.stdout + bad.stderr, bad.stdout + bad.stderr

    good = subprocess.run(
        [
            "git",
            "commit",
            "-m",
            "build: add toolchain with validation gate",
            "-m",
            GOOD_TRAILER,
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert good.returncode == 0, good.stdout + good.stderr


def test_the_default_hooks_path_is_not_githooks() -> None:
    """Guards the documentation. If make hooks ever starts setting
    core.hooksPath, the shim above is what runs, and this test should be
    reconsidered rather than quietly deleted."""
    hooks = ROOT / "Makefile"
    assert hooks.exists()
