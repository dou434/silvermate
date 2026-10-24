
.PHONY: up up-lite down logs lint format test test-unit test-integration test-e2e seed seed-kb reset

PYTEST_ARGS ?=
BACKEND_PYTHON ?= $(shell cat backend/.python-version)

up:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Please create it from .env.template"; \
		exit 1; \
	fi
	docker compose up -d

down:
	docker compose down

reset:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Please create it from .env.template"; \
		exit 1; \
	fi
	docker compose down
	rm -rf docker/volumes
	docker compose up -d
	@echo "Waiting for api to be ready..."
	@until docker compose exec -T api true >/dev/null 2>&1; do sleep 2; done
	$(MAKE) seed

up-lite:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Please create it from .env.template"; \
		exit 1; \
	fi
	LITE_MODE=true VITE_USE_RUNS_API=false docker compose up -d postgres redis minio api web

logs:
	@docker logs --tail=50 api-dev
	@echo "\n\nBranch: $$(git branch --show-current)"
	@echo "Commit ID: $$(git rev-parse HEAD)"
	@echo "System: $$(uname -a)"

seed:
	docker compose exec api uv run python scripts/seed_initial_users.py

seed-kb:
	docker compose exec api uv run python scripts/seed_knowledge_base.py

######################
# LINTING AND FORMATTING
######################

lint:
	cd backend && UV_PYTHON=$(BACKEND_PYTHON) uv run ruff check package
	cd backend && UV_PYTHON=$(BACKEND_PYTHON) uv run ruff check --select I package
	cd web && pnpm run lint

format:
	cd backend && UV_PYTHON=$(BACKEND_PYTHON) uv run ruff format package
	cd backend && UV_PYTHON=$(BACKEND_PYTHON) uv run ruff check package --fix
	cd backend && UV_PYTHON=$(BACKEND_PYTHON) uv run ruff check --select I package --fix
	cd web && pnpm run format
	cd web && pnpm run lint

######################
# TESTING
######################

test:
	docker compose exec api uv run --group test pytest test $(PYTEST_ARGS)

test-unit:
	docker compose exec api uv run --group test pytest test/unit -m "not slow" $(PYTEST_ARGS)

test-integration:
	docker compose exec api uv run --group test pytest test/integration $(PYTEST_ARGS)

test-e2e:
	docker compose exec api uv run --group test pytest test/e2e -m e2e $(PYTEST_ARGS)
