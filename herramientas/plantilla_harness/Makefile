PYTHON ?= python3

.DEFAULT_GOAL := help

.PHONY: help doctor actualizar foco

help: ## Lista los comandos disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | grep -v '^help:' | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-12s %s\n", $$1, $$2}'

doctor: ## Verifica git, Python y gitleaks
	@$(PYTHON) herramientas/harness.py doctor

foco: ## Deja visibles en Cursor solo REPOS=a,b (sin REPOS: todos)
	@$(PYTHON) herramientas/harness.py foco $(if $(REPOS),--repos $(REPOS))

actualizar: ## Trae la última versión del harness y clona o actualiza code/ (ENLAZAR=<carpeta> reutiliza clones existentes)
	git pull --ff-only
	@$(PYTHON) herramientas/harness.py code $(if $(ENLAZAR),--enlazar $(ENLAZAR))
