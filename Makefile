.PHONY: dev dev-down prod prod-down logs ps

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build --remove-orphans

dev-down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

prod:
	docker compose up -d --build --remove-orphans

prod-down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps
