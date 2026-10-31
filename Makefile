PYTHON := .venv/bin/python
ENTORNO := .venv/.instalado

.DEFAULT_GOAL := help

.PHONY: help venv estado doctor sync-arquitectura harness-traer coherencia repos terceros historias harness-generar indices actualizar revisar semanal test

help: ## Lista los comandos disponibles
	@echo "Uso habitual:"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | grep -v '^help:' | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-18s %s\n", $$1, $$2}'
	@echo ""
	@echo "Pasos internos (los ejecuta make actualizar):"
	@grep -E '^[a-zA-Z_-]+:.*?#- ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?#- "}; {printf "  make %-18s %s\n", $$1, $$2}'

$(ENTORNO): requirements.txt
	python3 -m venv .venv
	$(PYTHON) -m pip install --quiet --upgrade pip
	$(PYTHON) -m pip install --quiet -r requirements.txt
	@touch $(ENTORNO)

venv: $(ENTORNO) ## Crea o actualiza el entorno de Python

estado: $(ENTORNO) ## Muestra el estado general y qué sigue (sin red ni IA)
	@$(PYTHON) herramientas/estado.py

doctor: $(ENTORNO) #- Verifica herramientas, configuración y variables (sin mostrar valores)
	@$(PYTHON) herramientas/doctor.py

sync-arquitectura: $(ENTORNO) #- Descarga arquitectura y genera arquitectura/INDICE.md
	@$(PYTHON) herramientas/sync_arquitectura.py

coherencia: $(ENTORNO) #- Actualiza equipo/COHERENCIA.md y lista los pares por evaluar
	@$(PYTHON) herramientas/coherencia.py generar
	@$(PYTHON) herramientas/coherencia.py preparar

repos: $(ENTORNO) #- Descarga o actualiza los repositorios activos de todos los productos
	@$(PYTHON) herramientas/productos.py sincronizar

terceros: $(ENTORNO) #- Indexa la documentación de los terceros de todos los productos
	@$(PYTHON) herramientas/terceros.py indexar

historias: $(ENTORNO) #- Sincroniza las historias de usuario de los productos que las tienen configuradas
	-@$(PYTHON) herramientas/jira.py sincronizar

harness-traer: $(ENTORNO) #- Trae la última versión de cada harness de producto (git pull de la copia local)
	-@$(PYTHON) herramientas/harness.py traer

harness-generar: $(ENTORNO) #- Regenera lo generado en cada harness y hace commit local si cambió (el push es manual)
	-@$(PYTHON) herramientas/harness.py generar

indices: $(ENTORNO) #- Regenera equipo/INDICE.md y los índices de los productos
	@$(PYTHON) herramientas/indices.py

actualizar: doctor sync-arquitectura harness-traer coherencia repos terceros historias harness-generar indices ## Ejecuta la parte automática de /actualizar

revisar: $(ENTORNO) ## Parte automática de /revisar: make revisar P=<producto> [R=<repo>] [SIN_SONAR=1] [COMPLETA=1]
	@test -n "$(P)" || (echo "Uso: make revisar P=<producto> [R=<repo>] [SIN_SONAR=1]"; exit 1)
	@$(PYTHON) herramientas/revisar.py $(P) $(if $(R),--repo $(R)) $(if $(SIN_SONAR),--sin-sonar) $(if $(COMPLETA),--completa)

semanal: repos ## Reporte semanal de cada producto (actualiza antes las copias de los repositorios)
	@$(PYTHON) herramientas/estado.py semanal

test: $(ENTORNO) ## Ejecuta las pruebas de las herramientas
	@$(PYTHON) -m unittest discover -s herramientas/pruebas -t herramientas/pruebas -v
