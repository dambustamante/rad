PYTHON ?= python3

.DEFAULT_GOAL := help

.PHONY: help doctor code actualizar foco

help: ## Lista los comandos disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | grep -v '^help:' | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-12s %s\n", $$1, $$2}'

doctor: ## Verifica git, Python y gitleaks
	@$(PYTHON) herramientas/harness.py doctor

code: ## Clona o actualiza los repositorios en code/ (ENLAZAR=<carpeta> reutiliza clones existentes)
	@$(PYTHON) herramientas/harness.py code $(if $(ENLAZAR),--enlazar $(ENLAZAR))

foco: ## Deja visibles en Cursor solo REPOS=a,b (sin REPOS: todos)
	@$(PYTHON) herramientas/harness.py foco $(if $(REPOS),--repos $(REPOS))

actualizar: ## Trae la última versión del harness y actualiza code/
	git pull --ff-only
	@$(PYTHON) herramientas/harness.py code
