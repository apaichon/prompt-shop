.DEFAULT_GOAL := help
.PHONY: help start stop restart reset-data status logs infra-start infra-stop infra-restart infra-reset-data

help:
	@printf '%s\n' \
	  'start       Start PostgreSQL, wait, migrate and seed local data' \
	  'stop        Stop PostgreSQL; retain its data' \
	  'restart     Restart PostgreSQL; retain its data' \
	  'reset-data  DELETE local PostgreSQL data, then migrate and reseed' \
	  'status      Show local infrastructure state' \
	  'logs        Follow PostgreSQL logs'

start stop restart reset-data status logs infra-start infra-stop infra-restart infra-reset-data:
	@rtk proxy sh scripts/infra.sh "$@"
