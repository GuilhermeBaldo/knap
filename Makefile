.PHONY: install install-dev run cli test test-v test-x lint lint-fix format clean

# Install dependencies
install:
	uv sync

# Install with dev dependencies
install-dev:
	uv sync --extra dev

# Run the Telegram bot
run:
	uv run python -m knap

# Run the CLI
cli:
	uv run knap-cli

# Run tests
test:
	uv run pytest

# Run tests with verbose output
test-v:
	uv run pytest -v

# Run tests and stop on first failure
test-x:
	uv run pytest -x

# Lint code
lint:
	uv run ruff check knap tests

# Lint and fix
lint-fix:
	uv run ruff check --fix knap tests

# Format code
format:
	uv run ruff format knap tests

# Check formatting (CI)
format-check:
	uv run ruff format --check knap tests

# Clean up cache files
clean:
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
