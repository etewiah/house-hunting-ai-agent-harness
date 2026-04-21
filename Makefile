.PHONY: demo test lint harness-check

demo:
	python -m src.ui.cli demo

test:
	pytest

lint:
	ruff check src evals

harness-check:
	pytest evals/tests/test_guardrails.py evals/tests/test_architecture_boundaries.py
