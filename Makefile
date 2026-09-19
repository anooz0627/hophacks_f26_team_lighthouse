# AidGraph developer tasks. Run `make help` for the list.
# Paths stay relative: make cannot handle the space in this repo's absolute path.
SHELL := /bin/bash

VENV := backend/.venv
PY := $(VENV)/bin/python
UVICORN := $(VENV)/bin/uvicorn
NODE_MODULES := frontend/node_modules

# uv when it is on PATH, otherwise stdlib venv + pip.
HAVE_UV := $(shell command -v uv 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help dev backend frontend install install-backend install-frontend test lint build clean

help: ## Show available targets
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install backend and frontend dependencies

install-backend: $(PY) ## Create backend venv and install Python deps
$(PY):
	@echo "[make] creating backend venv..."
ifdef HAVE_UV
	cd backend && uv venv -q .venv && uv pip install -q -e '.[dev]'
else
	cd backend && python3 -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -q -e '.[dev]'
endif

install-frontend: $(NODE_MODULES) ## Install frontend npm deps
$(NODE_MODULES): frontend/package.json
	@echo "[make] installing frontend deps..."
	cd frontend && npm install
	@touch $(NODE_MODULES)

dev: install ## Run backend (:8000) and frontend (:3000) together; Ctrl-C stops both
	@echo "[make] backend  -> http://localhost:8000/docs"
	@echo "[make] frontend -> http://localhost:3000"
	@( cd backend && ../$(UVICORN) app.main:app --reload --port 8000 ) & BACK=$$!; \
	( cd frontend && npm run dev ) & FRONT=$$!; \
	trap 'kill $$BACK $$FRONT 2>/dev/null' EXIT INT TERM; \
	wait

backend: install-backend ## Run only the backend API on :8000
	cd backend && ../$(UVICORN) app.main:app --reload --port 8000

frontend: install-frontend ## Run only the Next.js dev server on :3000
	cd frontend && npm run dev

test: install-backend ## Run backend tests
	cd backend && ../$(PY) -m pytest -q

lint: install-frontend ## Lint the frontend
	cd frontend && npm run lint

build: install-frontend ## Production build of the frontend
	cd frontend && npm run build

clean: ## Remove venv, node_modules and build caches
	rm -rf $(VENV) $(NODE_MODULES) frontend/.next backend/.pytest_cache
	find backend -name '__pycache__' -type d -prune -exec rm -rf {} +
