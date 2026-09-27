"""Invariants about the continuous integration workflow.

The gate is defined once, in the Makefile. A workflow that re-lists the checks
drifts from it, and the drift is invisible until the day the two disagree about
what passed. These tests hold the single definition in place.

The same drift guard runs inside the workflow itself. Having it in both places
is deliberate: the test catches it before review, the workflow step catches it
for anyone who edits the workflow without running the suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "gate.yml"


def _workflow() -> str:
    assert WORKFLOW.exists(), "the gate workflow is missing"
    return WORKFLOW.read_text()


def _strip_comments(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_workflow_calls_the_shared_gate() -> None:
    body = _strip_comments(_workflow())
    assert "run: make validate" in body, (
        "the workflow must call make validate, which is the single definition"
    )


@pytest.mark.parametrize("tool", ["pytest", "ruff", "mypy"])
def test_workflow_does_not_relist_the_gate(tool: str) -> None:
    """A second list of checks is how the two definitions diverge.

    Matched on the YAML list-item form, so the shell string inside the guard step
    does not match itself.
    """
    body = _strip_comments(_workflow())
    offenders = re.findall(rf"^\s*(?:-\s+)?run:\s*{tool}\b", body, re.MULTILINE)
    assert not offenders, (
        f"the workflow invokes {tool} directly. Call make validate instead so there "
        f"is one definition of the gate."
    )


def test_workflow_triggers_on_pull_request_and_main() -> None:
    body = _workflow()
    assert "pull_request:" in body
    assert "push:" in body
    assert "branches: [main]" in body


def test_workflow_cancels_superseded_runs() -> None:
    """A five commit branch should not take twenty five minutes to learn it is
    broken. Every earlier run on the same ref is already known to be obsolete."""
    body = _workflow()
    assert "concurrency:" in body
    assert "cancel-in-progress: true" in body


def test_workflow_uses_only_local_actions() -> None:
    """Third party actions can change what CI runs. Pin the two we use and
    nothing else, so a new action has to be a deliberate diff."""
    body = _workflow()
    used = re.findall(r"uses:\s*(\S+)", body)
    allowed_prefixes = ("actions/checkout@", "actions/setup-python@")
    for action in used:
        assert action.startswith(allowed_prefixes), f"unexpected action {action}"


def test_workflow_has_a_timeout() -> None:
    """A hung gate blocks a merge indefinitely. Ten minutes is generous for a
    project this size and bounded regardless."""
    assert "timeout-minutes:" in _workflow()


def test_readme_badge_points_at_the_gate_workflow() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "actions/workflows/gate.yml/badge.svg" in readme, (
        "the readme badge should point at the gate workflow so its state is visible"
    )
