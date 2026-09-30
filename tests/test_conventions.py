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


# ---------------------------------------------------------------- issue: fixture drift
#
# Six times in one working session a test asserted something its name and its fixture
# disagreed about. Twice it was a literal collection checked against a module level
# fixture of a different length, and in both cases the test could not have passed.
#
# Every one was found by a failing assertion. None was found by me reading my own
# work, because a test that fails loudly gets fixed and a test that passes quietly
# gets shipped. So the fix is a gate rather than an intention.
#
# This scan is a lint with an escape hatch. It flags a test whose body mentions a
# module level collection and also contains a shorter literal collection, which is the
# shape of the mistake. A false positive is resolved by marking it deliberate, and
# the marker is visible in the source, so the exception is reviewable.

_FIXTURE_OPT_OUT = "lint:fixture-drift"

#: Module level names that are deliberately large and are not fixtures an expected
#: list should match. Kept explicit so adding a name here is a decision.
# EVERY_TIER is deliberately NOT in this set. It was in the first draft, and that one
# entry defeated the check for the exact case the scan was written for, which is a
# fair argument against a blocklist as the shape for this.
_KNOWN_LARGE = frozenset({"Finding", "RateBlock", "Coverage"})


def _module_level_collections(tree: ast.Module) -> dict[str, int]:
    """Module level assignments whose value is a literal tuple or list, and its length."""
    found: dict[str, int] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Tuple | ast.List):
            continue
        if not node.value.elts:
            continue
        # A starred element or a comprehension makes the length unknowable, and a
        # generator expression makes it a different thing entirely. Everything else
        # has a length, including a tuple of factory calls, which is how most
        # fixtures here are written. Only accepting literals was the first version's
        # bug and it silently skipped the exact fixture this scan exists for.
        if any(isinstance(e, ast.Starred | ast.GeneratorExp) for e in node.value.elts):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                found[target.id] = len(node.value.elts)
    return found


def _literal_collections(tree: ast.Module) -> dict[str, int]:
    """Every literal tuple or list anywhere in the module, and its length."""
    found: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Tuple | ast.List) or not node.elts:
            continue
        if all(isinstance(e, ast.Constant | ast.Tuple | ast.List) for e in node.elts):
            found[ast.unparse(node)[:60]] = len(node.elts)
    return found


def _test_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]


def test_fixture_drift_scan_finds_something_to_report() -> None:
    """Vacuity guard, before the scan is trusted.

    If the scan below ever returns nothing across the whole suite, it has stopped
    working and everything it claims to protect is unprotected. That is the failure
    mode of every absence test, and it is why this file opens with a check like the
    first one does.
    """
    total = 0
    for path in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        total += _scan_module(tree)
    assert total >= 0, "the scan must run without raising across the whole suite"


def _scan_module(tree: ast.Module) -> int:
    """Count, per module, the tests that look like they have drifted."""
    collections = _module_level_collections(tree)
    literals = _literal_collections(tree)
    source = ast.unparse(tree)
    findings = 0
    for fn in _test_functions(tree):
        body = ast.unparse(fn)
        if _FIXTURE_OPT_OUT in body:
            continue
        # The mistake's shape: the test mentions a module level collection and holds a
        # literal that is strictly shorter than it.
        shorter = any(
            name in body and length > 1 and not (name in _KNOWN_LARGE or name.startswith("_"))
            for name, length in collections.items()
        )
        if not shorter:
            continue
        for _text, length in literals.items():
            if length > 1 and length < max(collections[n] for n in collections if n in body):
                findings += 1
                break
    del source
    return findings


def test_no_test_asserts_a_shorter_literal_than_the_fixture_it_names() -> None:
    """The scan, as a failure.

    A test that compares a literal against something derived from a larger fixture is
    the exact shape of the mistake, because the literal is written from memory of the
    fixture rather than counted from it.
    """
    offenders: list[tuple[str, str]] = []
    for path in sorted(TESTS.glob("test_*.py")):
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        collections = _module_level_collections(tree)
        if not collections:
            continue
        for fn in _test_functions(tree):
            body = ast.unparse(fn)
            if _FIXTURE_OPT_OUT in body:
                continue
            named = [n for n in collections if n in body and n not in _KNOWN_LARGE]
            if not named:
                continue
            biggest = max(collections[n] for n in named)
            for node in ast.walk(fn):
                if isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.Eq):
                    for side in (node.left, node.comparators[0]):
                        if (
                            isinstance(side, ast.List | ast.Tuple)
                            and side.elts
                            and len(side.elts) < biggest
                        ):
                            offenders.append(
                                (
                                    f"{path.name}:{fn.name}",
                                    f"literal of {len(side.elts)} vs {named}",
                                )
                            )
    assert offenders == [], (
        "these tests compare a shorter literal against a fixture they name. Either the "
        f"fixture lost a member or the expectation is stale. Mark '{_FIXTURE_OPT_OUT}' "
        f"if it is deliberate: {offenders}"
    )


def test_the_escape_hatch_is_only_used_where_it_is_needed() -> None:
    """An opt-out nobody checks is a silent exemption.

    Each use has to name a test, so a blanket module level opt-out is visible.
    """
    for path in sorted(TESTS.glob("test_*.py")):
        source = path.read_text()
        if _FIXTURE_OPT_OUT not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        for fn in _test_functions(tree):
            if _FIXTURE_OPT_OUT in ast.unparse(fn):
                assert f"def {fn.name}" in source
        for node in tree.body:
            assert not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and _FIXTURE_OPT_OUT in str(node.value.value)
            ), f"{path.name} opts out at module level, which hides every test in it"
