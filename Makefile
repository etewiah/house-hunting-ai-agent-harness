.PHONY: demo test lint

demo:
	python -m src.ui.cli demo

test:
	pytest

lint:
	ruff check src evals

