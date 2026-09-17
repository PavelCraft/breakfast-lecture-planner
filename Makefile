DEPLOY_BRANCH ?= markdown-integration
DEPLOY_HOST ?= 193.30.123.232
DEPLOY_USER ?= pavel
DEPLOY_DIR ?= /home/pavel/app

.PHONY: deploy rollback rollback-with-database

deploy:
	@test "$$(git branch --show-current)" = "$(DEPLOY_BRANCH)" || \
		(echo "Ошибка: деплой разрешён только из ветки $(DEPLOY_BRANCH)."; exit 1)
	@test -z "$$(git status --porcelain)" || \
		(echo "Ошибка: сначала закоммитьте все локальные изменения."; git status --short; exit 1)
	git push origin $(DEPLOY_BRANCH)
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) 'cd $(DEPLOY_DIR) && git pull --ff-only origin $(DEPLOY_BRANCH) && ./deploy.sh'

rollback:
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) 'cd $(DEPLOY_DIR) && ./rollback.sh'

rollback-with-database:
	@echo "ВНИМАНИЕ: будут потеряны данные, появившиеся после последнего деплоя."
	@printf "Для продолжения введите RESTORE: "; read answer; \
		test "$$answer" = "RESTORE" || (echo "Отменено."; exit 1)
	ssh $(DEPLOY_USER)@$(DEPLOY_HOST) \
		'cd $(DEPLOY_DIR) && ./rollback.sh --restore-database'
