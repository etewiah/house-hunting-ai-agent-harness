.PHONY: search test lint harness-check

search:
	python -m src.ui.cli search

test:
	pytest

lint:
	ruff check src evals

harness-check:
	pytest evals/tests/test_guardrails.py evals/tests/test_architecture_boundaries.py
