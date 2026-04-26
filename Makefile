# spiderfarmer-ha — developer shortcuts
#
#   make deploy [HA_HOST=root@homeassistant.local HA_PORT=22]
#                                       Push custom_components/spiderfarmer
#                                       (including the spiderwire submodule)
#                                       to a HA instance over SSH.
#   make deploy-restart                 Same as deploy, then `ha core restart`.
#
# Override any variable on the command line, e.g.:
#   make deploy HA_HOST=root@homeassistant.local HA_PORT=22222

HA_HOST   ?= root@10.10.10.10
HA_PORT   ?= 22
HA_CONFIG ?= /homeassistant

DEPLOY_ENV = HA_HOST='$(HA_HOST)' HA_PORT='$(HA_PORT)' HA_CONFIG='$(HA_CONFIG)'

.PHONY: help deploy deploy-restart

help:
	@echo "Usage:"
	@echo "  make deploy           Deploy custom_components/spiderfarmer/ over SSH"
	@echo "  make deploy-restart   Deploy then 'ha core restart'"
	@echo ""
	@echo "Variables (override on command line):"
	@echo "  HA_HOST=$(HA_HOST)"
	@echo "  HA_PORT=$(HA_PORT)"
	@echo "  HA_CONFIG=$(HA_CONFIG)"

deploy:
	$(DEPLOY_ENV) RESTART=0 bash scripts/deploy.sh

deploy-restart:
	$(DEPLOY_ENV) RESTART=1 bash scripts/deploy.sh
