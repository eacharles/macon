SHELL := /bin/bash
GIT_BRANCH := $(shell git branch --show-current)
PY_VENV := .venv/
UV_LOCKFILE := uv.lock

#------------------------------------------------------------------------------
# Default help target (thanks ChatGPT)
#------------------------------------------------------------------------------

help:
	@echo "Available targets:"
	@awk -F':' '/^[a-zA-Z0-9\._-]+:/ && !/^[ \t]*\.PHONY/ {print $$1}' $(MAKEFILE_LIST) | sort -u | column


#------------------------------------------------------------------------------
# DX: Use uv to bootstrap project
#------------------------------------------------------------------------------

$(UV_LOCKFILE):
	uv lock --build-isolation

$(PY_VENV): $(UV_LOCKFILE)
	uv sync --frozen

.PHONY: clean
clean:
	rm -rf $(PY_VENV)
	rm -f test_macon.db
	rm -rf ./archive
	find src -type d -name '__pycache__' | xargs rm -rf
	find tests -type d -name '__pycache__' | xargs rm -rf

.PHONY: init
init: $(PY_VENV)
	uv run pre-commit install

.PHONY: update-deps
update-deps: init
	uv lock --upgrade --build-isolation

.PHONY: update
update: update-deps init


#------------------------------------------------------------------------------
# Convenience targets to run pre-commit hooks ("lint") and mypy ("typing")
#------------------------------------------------------------------------------

.PHONY: lint
lint:
	pre-commit run --all-files

.PHONY: typing
typing:
	mypy src tests



#------------------------------------------------------------------------------
# Targets for developers to debug running against local sqlite.  Can be used on
# local machines or USDF dev nodes.
#------------------------------------------------------------------------------

.PHONY: test-sqlite
test-sqlite: export DB__URL=sqlite+aiosqlite:////${PWD}/tests/test_macon.db
test-sqlite:
	pytest -vvv --asyncio-mode=auto --cov=macon --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: test-github-ci
test-github-ci: export DB__URL=sqlite+aiosqlite:////${PWD}/tests/test_macon.db
test-github-ci:
	pytest -vvv --asyncio-mode=auto --cov=macon --cov-branch --cov-report=term --cov-report=xml ${PYTEST_ARGS}

.PHONY: run-sqlite-local
run-sqlite: export DB__URL=sqlite+aiosqlite:////${PWD}/tests/test_macon.db
run-sqlite:
	macon-local
