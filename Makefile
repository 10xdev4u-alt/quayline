# Every agent runs the same gate. One command, non-zero on any failure.
#
#   make install    create the venv, install the dev group, wire the git hooks
#   make hooks      re-wire the git hooks after a fresh clone
#   make validate   the gate: pytest, ruff check, ruff format check, mypy, index
#   make format     apply ruff formatting and the autofixable lint rules
#   make repo-state report live collaborator and branch protection state, change nothing
#   make specimen   regenerate the public specimen page from the fixture corpus
#   make fixtures-checksum
#     recompute every tariff fixture checksum after a deliberate transcription edit
#   make clean      remove build and cache artifacts

PY      := .venv/bin/python
PIP     := .venv/bin/python -m pip
RUFF    := .venv/bin/ruff
MYPY    := .venv/bin/mypy
PYTEST  := .venv/bin/pytest
PRECOMMIT := .venv/bin/pre-commit

.PHONY: install validate format hooks clean index repo-state specimen

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
	$(MAKE) index

# Issue 126. Nothing from a tool's machine local state may be staged.
#
# This lives in the gate and not in pytest on purpose. A test suite runs *during*
# the commit that creates the state it is asserting about, so a pytest assertion
# about a clean index fires on the commit that adds the test, and a test that fails
# on correct work gets switched off. The gate runs in pre-push and in CI, where
# the index is settled, which is the only place a claim about the index is true.
#
# It is a separate target as well as a gate step so a contributor can run exactly
# this check and nothing else.
TOOL_DIRS := .freebuff .codex .agents .continue .cursor .cline

index:
	@fail=0; \
	for d in $(TOOL_DIRS); do \
		staged=$$(git diff --cached --name-only | grep -c "^$$d/" || true); \
		if [ "$$staged" != "0" ]; then \
			echo "staged tool artifact(s) under $$d/:"; \
			git diff --cached --name-only | grep "^$$d/"; \
			fail=1; \
		fi; \
	done; \
	for f in $$($(PYTEST) --collect-only -q 2>/dev/null >/dev/null; echo .gitignore); do :; done; \
	if [ $$fail != "0" ]; then exit 1; fi; \
	echo "index clean of tool artifacts"

format:
	$(RUFF) check --fix .
	$(RUFF) format .

# Wire the git hooks. Needed after a fresh clone, and after anyone changes
# core.hooksPath. Idempotent.
hooks:
	for stage in pre-commit commit-msg pre-push; do \
		$(PRECOMMIT) install --hook-type $$stage; \
	done

# Issue 92. Report the live repository state so the collaborator ordering trap is
# found by running a command rather than by being blocked by a merge. Reports only.
# Applying the policy is scripts/configure_branch_protection.sh, which is separate
# on purpose: a setup step that silently grants access is a different risk.
repo-state:
	scripts/verify_repository_state.sh

# Issue 39. Recompute every fixture checksum after a deliberate transcription edit.
# This is a write operation, so it is not part of validate. Run it, read the diff,
# and only then commit.
fixtures-checksum:
	$(PY) scripts/recompute_fixture_checksums.py

# The specimen page is generated, never written. `make specimen` is the only way it
# comes into existence, so a hand edited page in web/specimen.html is a change with no
# pull request behind it, which the repository hygiene test refuses.
specimen:
	@mkdir -p web
	$(PY) -c "from quayline.web.render import generate; \
		open('web/specimen.html','w',encoding='utf-8').write(generate())"
	@echo "wrote web/specimen.html"

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
