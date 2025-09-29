# AI Agent Platform - Development Makefile

.PHONY: help install install-dev test test-unit test-integration lint format type-check security-check clean setup-dev run demo interactive

# Default target
help:
	@echo "AI Agent Platform Development Commands"
	@echo "====================================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  install       Install production dependencies"
	@echo "  install-dev   Install development dependencies"
	@echo "  setup-dev     Full development environment setup"
	@echo ""
	@echo "Code Quality:"
	@echo "  format        Format code with black and isort"
	@echo "  lint          Run flake8 linting"
	@echo "  type-check    Run mypy type checking"
	@echo "  security-check Run bandit security checks"
	@echo ""
	@echo "Testing:"
	@echo "  test          Run all tests"
	@echo "  test-unit     Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo ""
	@echo "Application:"
	@echo "  run           Run the application (demo mode)"
	@echo "  demo          Run comprehensive demo"
	@echo "  interactive   Run interactive mode"
	@echo ""
	@echo "Utilities:"
	@echo "  clean         Clean up generated files"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -e ".[dev]"

setup-dev: install-dev
	pre-commit install
	@echo "Development environment setup complete!"

# Code Quality
format:
	black src/ examples/ tests/ *.py
	isort src/ examples/ tests/ *.py

lint:
	flake8 src/ examples/ tests/ *.py

type-check:
	mypy src/

security-check:
	bandit -r src/ -f json -o bandit-report.json || true
	bandit -r src/

# Testing
test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v -m integration

test-coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term --cov-fail-under=80

# Application
run: demo

demo:
	python main.py --mode demo

interactive:
	python main.py --mode interactive

debug:
	python main.py --mode demo --log-level DEBUG

# Utilities
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -f bandit-report.json

# Development workflow shortcuts
check: format lint type-check security-check test-unit
	@echo "All checks passed!"

ci: lint type-check security-check test
	@echo "CI checks complete!"

# Pre-commit hooks
pre-commit-run:
	pre-commit run --all-files

pre-commit-update:
	pre-commit autoupdate