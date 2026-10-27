# Diagrama de contexto: <nombre del sistema>

> Plantilla de ADR-EQ-001. Muestra el sistema, quién lo usa y con qué sistemas externos se
> comunica. No muestra componentes internos: eso va en el diagrama de contenedores.

```mermaid
C4Context
    title Contexto de <nombre del sistema>

    Person(usuario, "<Rol de usuario>", "<Qué hace con el sistema>")

    System(sistema, "<Nombre del sistema>", "<Qué hace, en una frase>")

    System_Ext(externo1, "<Sistema externo>", "<Qué provee>")
    System_Ext(externo2, "<Sistema externo>", "<Qué provee>")

    Rel(usuario, sistema, "<Qué hace>", "<Protocolo, por ejemplo HTTPS>")
    Rel(sistema, externo1, "<Qué intercambia>", "<Protocolo, por ejemplo HTTPS/JSON>")
    Rel(sistema, externo2, "<Qué intercambia>", "<Protocolo, por ejemplo Kafka>")
```

## Elementos

| Elemento | Tipo | Descripción |
|---|---|---|
| <nombre> | Persona / Sistema / Sistema externo | <descripción> |
