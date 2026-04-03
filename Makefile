.PHONY: all help format lint fix typecheck test abi abi-all install setup clean

all: format lint typecheck test ## Run full quality pipeline

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

format: ## Format code with ruff
	uv run ruff format src tests

lint: ## Check for lint errors (no auto-fix)
	uv run ruff check src tests

fix: ## Auto-fix lint and format issues
	uv run ruff check --fix src tests
	uv run ruff format src tests

typecheck: ## Run type checking with pyright
	uv run pyright

test: ## Run tests
	uv run pytest

NETWORK ?= mainnet
abi: ## Generate ABIs for a network (default NETWORK=mainnet; override with NETWORK=testnet)
	uv run python -m decibel.abi $(NETWORK)

abi-all: ## Generate ABIs for all networks
	uv run python -m decibel.abi all

install: ## Install dependencies
	uv sync --all-extras

setup: install ## Install dependencies + pre-commit hooks
	uv run pre-commit install

clean: ## Remove build artifacts and caches
	rm -rf dist build .pytest_cache .ruff_cache
	find src -type d -name __pycache__ -exec rm -rf {} +
