.DEFAULT_GOAL := help
.PHONY: help start stop restart reset-data status logs infra-start infra-stop infra-restart infra-reset-data
.PHONY: mvp-start mvp-stop mvp-restart mvp-status

help:
	@printf '%s\n' \
	  'start       Start PostgreSQL, wait, migrate and seed local data' \
	  'stop        Stop PostgreSQL; retain its data' \
	  'restart     Restart PostgreSQL; retain its data' \
	  'reset-data  DELETE local PostgreSQL data, then migrate and reseed' \
	  'status      Show local infrastructure state' \
	  'logs        Follow PostgreSQL logs' \
	  'mvp-start   Start the portal, real ADK voice and offline Laya' \
	  'mvp-stop    Stop application services; retain PostgreSQL' \
	  'mvp-restart Restart application services with current configuration' \
	  'mvp-status  Check portal, ADK and Laya readiness'

start stop restart reset-data status logs infra-start infra-stop infra-restart infra-reset-data:
	@rtk proxy sh scripts/infra.sh "$@"

mvp-start mvp-stop mvp-restart mvp-status:
	@rtk proxy uv run --project agent --frozen --python 3.11 python scripts/mvp.py "$@"
