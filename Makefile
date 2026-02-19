.PHONY: dev down prod

dev:
	docker compose -f docker-compose.dev.yml up --build

down:
	docker compose -f docker-compose.dev.yml down

prod:
	docker compose up --build -d
