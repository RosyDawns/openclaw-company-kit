.PHONY: launch install bridge start stop health check backup restore clean hook ui-install ui-build ui-dev

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

check:
	bash scripts/release-check.sh

backup:
	bash scripts/backup.sh

restore:
	@echo "Usage: make restore ARCHIVE=backups/<file>.tar.gz"
	@test -n "$(ARCHIVE)" && bash scripts/restore.sh "$(ARCHIVE)" || true

test:
	python3 -m unittest discover -s tests -p 'test_*.py' -v

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
