.PHONY: launch install start stop health check backup restore clean

launch:
	bash scripts/launch.sh

install:
	bash scripts/install.sh

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

clean:
	bash scripts/stop.sh 2>/dev/null || true
	rm -rf backups/
