.PHONY: up down run chat eval markup test logs

up:
	docker compose up --build

down:
	docker compose down

run:
	@echo "make run — not implemented yet"

chat:
	@echo "make chat — not implemented yet"

eval:
	docker compose exec backend python -m eval.run_eval

markup:
	@echo "not implemented yet — see Phase 11 / README"

test:
	docker compose exec backend python -m pytest tests/ -v

logs:
	docker compose logs -f
