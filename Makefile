.PHONY: up down logs build restart ps github-sync scan-all scan-docker scan-network setup clean

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

restart:
	docker compose restart

ps:
	docker compose ps

github-sync:
	curl -s -X POST http://localhost:$${BRIDGE_PORT:-8090}/api/github/sync | python3 -m json.tool

scan-all:
	curl -s -X POST http://localhost:$${AUTODOC_PORT:-8091}/api/scan/all | python3 -m json.tool

scan-docker:
	curl -s -X POST http://localhost:$${AUTODOC_PORT:-8091}/api/scan/docker | python3 -m json.tool

scan-network:
	curl -s -X POST http://localhost:$${AUTODOC_PORT:-8091}/api/scan/network | python3 -m json.tool

setup:
	bash scripts/setup.sh

clean:
	docker compose down -v
	rm -rf data/postgres data/xwiki data/anythingllm
