.PHONY: launch install bridge start stop health check backup restore clean hook ui-install ui-build ui-dev ui-test test test-all test-engine test-server lint

launch:
	bash scripts/launch.sh

install:
	bash scripts/install.sh

bridge:
	bash scripts/install-gh-bridge.sh

start:
	bash scripts/start.sh

stop:
	bash scripts/stop.sh

health:
	bash scripts/healthcheck.sh

backup:
	bash scripts/backup.sh

restore:
	@echo "Usage: make restore ARCHIVE=backups/<file>.tar.gz"
	@test -n "$(ARCHIVE)" && bash scripts/restore.sh "$(ARCHIVE)" || true

test:
	python3 -m pytest tests/ -v --tb=short

test-all: test

test-engine:
	python3 -m pytest tests/test_state_machine.py tests/test_review_gate.py \
		tests/test_orchestrator.py tests/test_file_lock.py tests/test_dispatch.py \
		tests/test_roles.py tests/test_role_architecture.py tests/test_review_workflow.py \
		tests/test_cron_adapter.py tests/test_skill_manager.py \
		tests/test_engine_integration.py -v --tb=short

test-server:
	python3 -m pytest tests/test_control_server.py tests/test_smoke_control_api.py \
		tests/test_frontend_routes.py -v --tb=short

lint:
	ruff check --select=E,F engine/ server/ scripts/control_server.py \
		dashboard/rd-dashboard/dashboard_data.py --ignore=E501,E402

check:
	@echo "=== Python compile check ==="
	for f in engine/*.py; do python3 -m py_compile "$$f"; done
	find server -name '*.py' -exec python3 -m py_compile {} +
	python3 -m py_compile dashboard/rd-dashboard/dashboard_data.py
	python3 -m py_compile scripts/control_server.py
	@echo "=== Ruff lint ==="
	ruff check --select=E,F engine/ server/ scripts/control_server.py \
		dashboard/rd-dashboard/dashboard_data.py --ignore=E501,E402
	@echo "=== JSON validation ==="
	jq -e . templates/jobs.template.json >/dev/null
	jq -e . templates/company-project.template.json >/dev/null
	jq -e . templates/exec-approvals.template.json >/dev/null
	for f in templates/workflow-jobs.*.json; do jq -e . "$$f" >/dev/null; done
	jq -e . engine/role_config.json >/dev/null
	jq -e . engine/review_rules.json >/dev/null
	for f in templates/agents/*/manifest.json; do jq -e . "$$f" >/dev/null; done
	jq -e . docker/demo_data/dashboard-data.json >/dev/null
	jq -e . docker/demo_data/business-metrics.json >/dev/null
	@echo "[OK] all checks passed"

hook:
	cp scripts/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "pre-commit hook installed"

clean:
	bash scripts/stop.sh 2>/dev/null || true
	rm -rf backups/

ui-install:
	cd frontend/console-vue && npm install

ui-build:
	cd frontend/console-vue && npm run build

ui-dev:
	cd frontend/console-vue && npm run dev

ui-test:
	python3 -m pytest tests/test_frontend_routes.py -v --tb=short
