DOCKER_COMPOSE ?= docker compose
COMPOSE_FILE ?= docker-compose.yml
# Для сборки linux/amd64 на macOS без флага --platform (старые версии compose)
DOCKER_DEFAULT_PLATFORM ?= linux/amd64

.PHONY: local-build local-up local-down local-logs

local-build:
	DOCKER_DEFAULT_PLATFORM=$(DOCKER_DEFAULT_PLATFORM) $(DOCKER_COMPOSE) -f $(COMPOSE_FILE) build --pull

local-up:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d

local-down:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down -v

local-logs:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) logs -f
