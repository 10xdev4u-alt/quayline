# Every agent runs the same gate. One command, non-zero on any failure.
#
#   make install    create the venv, install the dev group, wire the git hooks
#   make hooks      re-wire the git hooks after a fresh clone
#   make validate   the gate: pytest, ruff check, ruff format check, mypy
#   make format     apply ruff formatting and the autofixable lint rules
#   make hooks      install the commit-msg and pre-push hooks
#   make clean      remove build and cache artifacts

PY      := .venv/bin/python
PIP     := .venv/bin/python -m pip
RUFF    := .venv/bin/ruff
MYPY    := .venv/bin/mypy
PYTEST  := .venv/bin/pytest
PRECOMMIT := .venv/bin/pre-commit

.PHONY: install validate format hooks clean

# The dev group is declared in pyproject.toml and installed from there. Naming
# the tools on the command line instead would let any older version already on
# the machine satisfy the install and silently ignore the declared minimums.
install:
	python3 -m venv .venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -e . --group dev
	for stage in pre-commit commit-msg pre-push; do \
		$(PRECOMMIT) install --hook-type $$stage; \
	done

# The gate. Order is cheapest and most-likely-to-fail first.
validate:
	$(PYTEST)
	$(RUFF) check .
	$(RUFF) format --check .
	$(MYPY)

format:
	$(RUFF) check --fix .
	$(RUFF) format .

# Wire the git hooks. Needed after a fresh clone, and after anyone changes
# core.hooksPath. Idempotent.
hooks:
	for stage in pre-commit commit-msg pre-push; do \
		$(PRECOMMIT) install --hook-type $$stage; \
	done

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
