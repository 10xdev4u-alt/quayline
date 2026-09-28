"""Conventions that can only be checked by reading the tests, not by running them.

Issue 112 generalised the 541.6(b)(6) escaping fix. The original was a one line
correction in a single test: ``pytest.raises`` takes a regex, and ``541.6(b)(6)``
read as one compiles to ``541.6b6``, which matches nothing. The test then passed
for the wrong reason and would have gone on passing after the message changed,
which is the worst possible state for a test: green, and checking nothing.

Hand escaping a citation in every place it appears does not hold, because the next
person adds a test and does not know. So the rule is checked here instead, by
reading the source of every test rather than by running any of them.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent

#: A bare CFR citation. Deliberately loose, it only has to notice a citation.
CITATION = re.compile(r"\b\d+\.\d+(\(\w+\))+\b")

#: Argument names whose value is compiled as a pattern rather than compared.
PATTERN_ARGS = {"match", "pattern"}


def _match_argument_sources() -> list[tuple[Path, int, str]]:
    """Every ``match=`` or ``pattern=`` argument in the test suite, as source text."""
    found = []
    for path in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg not in PATTERN_ARGS:
                    continue
                segment = ast.get_source_segment(path.read_text(), keyword.value) or ""
                found.append((path, keyword.value.lineno, segment))
    return found


def test_the_suite_actually_contains_pattern_arguments() -> None:
    """So that the checks below cannot pass by finding nothing.

    An empty result set would make every other test in this file vacuously true,
    which is the same failure as a green test checking nothing.
    """
    assert len(_match_argument_sources()) >= 3, "the scan found no pattern arguments at all"


def test_no_citation_is_used_as_a_regex_without_escaping() -> None:
    """The generalised form of the 541.6(b)(6) fix.

    Any citation reaching a pattern argument must go through ``re.escape``, because
    the parentheses in ``541.6(b)(6)`` are a capture group and the dot matches any
    character, so the unescaped form matches strings that are not the citation and
    the assertion silently stops meaning anything.
    """
    offenders = [
        (path.name, lineno, segment)
        for path, lineno, segment in _match_argument_sources()
        if CITATION.search(segment) and "re.escape" not in segment
    ]
    assert offenders == [], f"unescaped citations in pattern arguments: {offenders}"


def test_no_cite_constant_is_used_as_a_regex_without_escaping() -> None:
    """The same rule for the constants, which is how the sites are actually written."""
    offenders = [
        (path.name, lineno, segment)
        for path, lineno, segment in _match_argument_sources()
        if re.search(r"\bCITE_[A-Z_]+", segment) and "re.escape" not in segment
    ]
    assert offenders == [], f"unescaped CITE_ constants in pattern arguments: {offenders}"


def test_the_escape_helper_is_the_only_way_in() -> None:
    """No test invents its own escaping by hand, which is how the rule forks.

    A hand written ``541\\.6\\(b\\)\\(6\\)`` is correct today and is a fourth
    spelling tomorrow. The constants plus ``re.escape`` is the whole vocabulary.
    """
    hand_escaped = []
    for path, lineno, segment in _match_argument_sources():
        if "re.escape" in segment:
            continue
        if CITATION.search(segment) or re.search(r"\bCITE_[A-Z_]+", segment):
            hand_escaped.append((path.name, lineno, segment))
    assert hand_escaped == [], hand_escaped


def test_the_original_offence_is_still_pinned() -> None:
    """Named, so a future reader knows why this file exists."""
    source = (TESTS / "test_daycount.py").read_text()
    assert "re.escape(CITE_AVAILABILITY)" in source
    assert "541.6(b)(6) read as one" in source
