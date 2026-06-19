VENV := .venv
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff

.PHONY: install test lint fmt check

install:
	python3.12 -m venv $(VENV)
	$(PYTHON) -m pip install -q --upgrade pip
	$(PYTHON) -m pip install -q -r requirements.txt

test:
	$(PYTEST) tests/ -v

lint:
	$(RUFF) check .

fmt:
	$(RUFF) format .

check: lint test
