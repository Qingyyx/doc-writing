PYTHON ?= python3

.PHONY: check test-gates list

check:
	$(PYTHON) scripts/check.py --all

list:
	$(PYTHON) scripts/check.py --list

test-gates:
	$(PYTHON) scripts/test_gates.py
