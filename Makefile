SHELL := /bin/bash

.PHONY: check test demo-up demo-down

check:
	bash scripts/release-check.sh

test:
	python3 -m unittest discover -s tests -p 'test_*.py' -v

demo-up:
	docker compose up --build -d

demo-down:
	docker compose down
