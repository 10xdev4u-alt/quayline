# Every agent runs the same gate. One command, non-zero on any failure.
#
#   make install    create the venv and install the dev group
#   make validate   the gate: pytest, ruff check, ruff format check, mypy
#   make format     apply ruff formatting and the autofixable lint rules
#   make clean      remove build and cache artifacts

PY      := .venv/bin/python
PIP     := .venv/bin/python -m pip
RUFF    := .venv/bin/ruff
MYPY    := .venv/bin/mypy
PYTEST  := .venv/bin/pytest

.PHONY: install validate format clean

install:
	python3 -m venv .venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -e .
	$(PIP) install --quiet ruff mypy pytest

# The gate. Order is cheapest and most-likely-to-fail first.
validate:
	$(PYTEST)
	$(RUFF) check .
	$(RUFF) format --check .
	$(MYPY)

format:
	$(RUFF) check --fix .
	$(RUFF) format .

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
