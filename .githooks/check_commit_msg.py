#!/usr/bin/env python3
"""Validate a commit message against the project rules.

Two rules, both hard. A six word conventional subject, and the-ai-developer as
the sole co-author. Both are enforced here rather than at review because a
malformed commit is cheaper to prevent than to rewrite, and because the co-author
trailer is the one piece of metadata that has to be right before the commit
exists at all.

The rules live in this file. Nothing is configurable by environment variable,
because a rule that can be switched off per shell is not a rule.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SUBJECT_WORD_COUNT = 6
MAX_SUBJECT_CHARS = 72
USAGE_EXIT = 2

ALLOWED_TYPES = frozenset(
    {
        "feat",  # a new capability
        "fix",  # a defect fix
        "refactor",  # behaviour unchanged, structure changed
        "docs",  # documentation only
        "test",  # tests only
        "chore",  # tooling, dependencies, housekeeping
        "perf",  # a performance change
        "build",  # build system and packaging
        "ci",  # continuous integration
        "data",  # fixtures and transcribed source data
    }
)

REQUIRED_CO_AUTHOR = "the-ai-developer"

# The address the trailer must carry, not just the name.
#
# GitHub resolves a co-author by email. A wrong address does not fail the commit, does
# not warn, and does not affect the gate, and the result is an unlinked contributor
# rather than the account. An unlinked co-author is indistinguishable from no
# co-author, so validating the name alone means the rule this file exists to enforce
# is satisfiable in a form nothing downstream can read.
REQUIRED_CO_AUTHOR_EMAIL = "the-ai-developer@users.noreply.github.com"

# type(scope): the scope is optional and binds to the type with no space.
SUBJECT_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?: (?P<rest>.+)$")
# The email is no longer optional. A trailer without one produces no co-author on
# GitHub, so accepting it is accepting a commit that appears to carry the attribution
# and does not.
CO_AUTHOR_RE = re.compile(
    r"^Co-Authored-By:\s*(?P<who>[^<]+?)\s*<(?P<email>[^>]+)>\s*$", re.IGNORECASE
)
TRAILER_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z-]*:")


def check_subject(raw: str) -> list[str]:
    """Validate the first line of the message."""
    problems: list[str] = []

    # Do not strip before validating. Leading or trailing whitespace on the
    # subject line means something wrote the message wrong, and silently
    # normalising it hides that and leaves a one character bypass.
    if raw != raw.strip():
        problems.append("the subject line has leading or trailing whitespace")

    subject = raw.strip()
    if not subject:
        return [*problems, "the subject is empty"]

    match = SUBJECT_RE.match(subject)
    if match is None:
        problems.append(
            f"the subject is not in conventional form. Expected "
            f"'type: description' or 'type(scope): description', got {subject!r}"
        )
    elif match.group("type") not in ALLOWED_TYPES:
        problems.append(
            f"the type {match.group('type')!r} is not one of {', '.join(sorted(ALLOWED_TYPES))}"
        )

    word_count = len(subject.split())
    if word_count != SUBJECT_WORD_COUNT:
        problems.append(
            f"the subject must be exactly {SUBJECT_WORD_COUNT} words, got {word_count}: {subject!r}"
        )

    if len(subject) > MAX_SUBJECT_CHARS:
        problems.append(
            f"the subject is {len(subject)} characters, over the "
            f"{MAX_SUBJECT_CHARS} limit: {subject!r}"
        )

    return problems


def check_co_authors(body: list[str]) -> list[str]:
    """Validate the trailers. the-ai-developer must appear, alone, with the right address.

    Name and address are checked together. Checking the name alone once let a Gmail
    address through, and the commit was authored and merged, and the only reason it
    was noticed was that I made the same mistake and read my own message back.
    """
    co_authors: list[tuple[str, str | None]] = []
    for line in body:
        if not TRAILER_LINE_RE.match(line):
            continue
        trailer = CO_AUTHOR_RE.match(line)
        if trailer:
            co_authors.append((trailer.group("who").strip(), trailer.group("email")))

    if not co_authors:
        return [
            f"the message has no Co-Authored-By trailer naming "
            f"{REQUIRED_CO_AUTHOR} <{REQUIRED_CO_AUTHOR_EMAIL}>."
        ]

    problems: list[str] = []

    unexpected = sorted(who for who, _ in co_authors if who.lower() != REQUIRED_CO_AUTHOR)
    if unexpected:
        problems.append(
            f"the sole co-author is {REQUIRED_CO_AUTHOR}. Remove: {', '.join(unexpected)}"
        )

    if len(co_authors) > 1:
        problems.append(
            f"there must be exactly one Co-Authored-By trailer, found {len(co_authors)}."
        )

    for who, email in co_authors:
        if email is None:
            problems.append(
                f"{who} has no email address. GitHub resolves a co-author by email, so a "
                f"trailer without one attributes nobody. The required trailer is "
                f"'Co-Authored-By: {REQUIRED_CO_AUTHOR} <{REQUIRED_CO_AUTHOR_EMAIL}>'."
            )
        elif email.lower() != REQUIRED_CO_AUTHOR_EMAIL:
            problems.append(
                f"the co-author address is {email!r}. The required address is "
                f"{REQUIRED_CO_AUTHOR_EMAIL!r}. A wrong address records an unlinked "
                f"contributor rather than the account."
            )

    return problems


def check(message: str) -> list[str]:
    """Return a list of problems. Empty means the message is acceptable."""
    if not message:
        return ["the commit message is empty"]

    lines = message.splitlines()
    return [*check_subject(lines[0]), *check_co_authors(lines[1:])]


def main(argv: list[str]) -> int:
    if len(argv) != USAGE_EXIT:
        print("usage: check_commit_msg.py <path-to-message-file>", file=sys.stderr)
        return USAGE_EXIT

    problems = check(Path(argv[1]).read_text())
    if not problems:
        return 0

    print("commit message rejected:\n", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        f"Rules: {SUBJECT_WORD_COUNT} words in '<type>: <description>' form, "
        f"types from {', '.join(sorted(ALLOWED_TYPES))}, "
        f"under {MAX_SUBJECT_CHARS} characters, no surrounding whitespace, and "
        f"exactly one Co-Authored-By trailer naming "
        f"{REQUIRED_CO_AUTHOR} <{REQUIRED_CO_AUTHOR_EMAIL}>.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
