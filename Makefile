PYTHON := .venv/bin/python
ENTORNO := .venv/.instalado

.DEFAULT_GOAL := help

.PHONY: help venv estado doctor sync-arquitectura coherencia repos proveedor historias indices actualizar revisar test

help: ## Lista los comandos disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-18s %s\n", $$1, $$2}'

$(ENTORNO): requirements.txt
	python3 -m venv .venv
	$(PYTHON) -m pip install --quiet --upgrade pip
	$(PYTHON) -m pip install --quiet -r requirements.txt
	@touch $(ENTORNO)

venv: $(ENTORNO) ## Crea o actualiza el entorno de Python

estado: $(ENTORNO) ## Muestra el estado general y qué sigue (sin red ni IA)
	@$(PYTHON) herramientas/estado.py

doctor: $(ENTORNO) ## Verifica herramientas, configuración y variables (sin mostrar valores)
	@$(PYTHON) herramientas/doctor.py

sync-arquitectura: $(ENTORNO) ## Descarga arquitectura y genera arquitectura/INDICE.md
	@$(PYTHON) herramientas/sync_arquitectura.py

coherencia: $(ENTORNO) ## Actualiza equipo/COHERENCIA.md y lista los pares por evaluar
	@$(PYTHON) herramientas/coherencia.py generar
	@$(PYTHON) herramientas/coherencia.py preparar

repos: $(ENTORNO) ## Descarga o actualiza los repositorios activos de todos los productos
	@$(PYTHON) herramientas/productos.py sincronizar

proveedor: $(ENTORNO) ## Indexa la documentación del proveedor y de las integraciones de todos los productos
	@$(PYTHON) herramientas/proveedor.py indexar

historias: $(ENTORNO) ## Sincroniza las historias de usuario de los productos que las tienen configuradas
	-@$(PYTHON) herramientas/historias.py sincronizar

indices: $(ENTORNO) ## Regenera equipo/INDICE.md y los índices de los productos
	@$(PYTHON) herramientas/indices.py

actualizar: doctor sync-arquitectura coherencia repos proveedor historias indices ## Ejecuta la parte automática de /actualizar

revisar: $(ENTORNO) ## Parte automática de /revisar: make revisar P=<producto> [R=<repo>] [SIN_SONAR=1]
	@test -n "$(P)" || (echo "Uso: make revisar P=<producto> [R=<repo>] [SIN_SONAR=1]"; exit 1)
	@$(PYTHON) herramientas/revisar.py $(P) $(if $(R),--repo $(R)) $(if $(SIN_SONAR),--sin-sonar)

test: $(ENTORNO) ## Ejecuta las pruebas de las herramientas
	@$(PYTHON) -m unittest discover -s herramientas/pruebas -t herramientas/pruebas -v
