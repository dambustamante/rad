# Diagrama de contenedores: <nombre del sistema>

> Plantilla de ADR-EQ-006. Muestra las aplicaciones, bases de datos y colas que componen el
> sistema, con su tecnología y sus relaciones. Cada contenedor declara su tecnología y cada
> relación su protocolo.

```mermaid
C4Container
    title Contenedores de <nombre del sistema>

    Person(usuario, "<Rol de usuario>", "<Qué hace con el sistema>")

    System_Boundary(limite, "<Nombre del sistema>") {
        Container(api, "<Nombre de la API>", "<Tecnología, por ejemplo Java 21, Spring Boot 3>", "<Responsabilidad>")
        ContainerDb(bd, "<Nombre de la base de datos>", "<Tecnología, por ejemplo PostgreSQL 16>", "<Qué guarda>")
        ContainerQueue(cola, "<Nombre del tópico o cola>", "<Tecnología, por ejemplo Kafka>", "<Qué eventos transporta>")
    }

    System_Ext(externo, "<Sistema externo>", "<Qué provee>")

    Rel(usuario, api, "<Qué hace>", "<HTTPS/JSON>")
    Rel(api, bd, "<Lee y escribe>", "<JDBC>")
    Rel(api, cola, "<Publica eventos de …>", "<Kafka>")
    Rel(api, externo, "<Consulta …>", "<HTTPS/JSON>")
```

## Contenedores

| Contenedor | Tecnología | Responsabilidad |
|---|---|---|
| <nombre> | <tecnología> | <responsabilidad> |
