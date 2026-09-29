API_DIR=apps/api
WEB_DIR=apps/web

.PHONY: api-lint api-typecheck api-migrate api-test web-typecheck web-build web-test web-e2e frontend-security-audit production-smoke chaos-recovery provider-activation final-audit release-gate

api-lint:
	cd $(API_DIR) && ruff check app tests

api-typecheck:
	cd $(API_DIR) && mypy app

api-migrate:
	cd $(API_DIR) && alembic upgrade head && alembic heads

api-test:
	cd $(API_DIR) && pytest tests -q

web-typecheck:
	cd $(WEB_DIR) && npm run typecheck

web-build:
	cd $(WEB_DIR) && npm run build

web-test:
	cd $(WEB_DIR) && npm run test:unit

web-e2e:
	cd $(WEB_DIR) && npm run test:e2e

frontend-security-audit:
	python scripts/frontend_security_audit.py

production-smoke:
	python scripts/production_smoke.py

chaos-recovery:
	python scripts/chaos_recovery.py

provider-activation:
	python scripts/provider_activation.py

final-audit:
	python scripts/final_audit.py

release-gate:
	$(MAKE) api-lint
	$(MAKE) api-typecheck
	$(MAKE) api-migrate
	$(MAKE) api-test
	$(MAKE) web-typecheck
	$(MAKE) web-build
	$(MAKE) web-test
	$(MAKE) web-e2e
	$(MAKE) frontend-security-audit
	$(MAKE) final-audit
