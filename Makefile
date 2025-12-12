DOCKER_COMPOSE ?= docker compose
COMPOSE_FILE ?= docker-compose.yml

# Включаем BuildKit и не форсим архитектуру: можно задать PLATFORM=linux/amd64 при необходимости
export DOCKER_BUILDKIT ?= 1
PLATFORM ?=

# Тянуть свежие базы образов только по запросу: PULL=true make local-build
PULL ?= false
PULL_FLAG := $(if $(filter true,$(PULL)),--pull,)

.PHONY: local-build local-up local-down local-logs

local-build:
	DOCKER_DEFAULT_PLATFORM=$(PLATFORM) $(DOCKER_COMPOSE) -f $(COMPOSE_FILE) build $(PULL_FLAG)

local-up:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d

local-down:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down -v

local-logs:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) logs -f

.PHONY: test-architecture test-schemas-snapshots

test-architecture:
	PYTHONPATH=$(PWD) pytest tests/architecture

test-schemas-snapshots:
	PYTHONPATH=$(PWD) pytest tests/contracts/test_schema_snapshots.py
