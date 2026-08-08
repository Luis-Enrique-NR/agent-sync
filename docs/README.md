# Acuerdo de documentación del proyecto

> **Mensaje para personas y agentes:** esta carpeta es parte permanente del proyecto y debe conservarse activa en `main`. Antes de modificar un dominio, lee este archivo y las decisiones existentes de la categoría correspondiente.

## Regla de ubicación

Cada documento de avance o decisión debe vivir dentro de una carpeta de categoría:

```text
docs/
├── README.md
├── arquitectura/
├── planificacion/
├── seguridad/
├── seguimiento/
└── pruebas/
```

Se pueden agregar categorías cuando sean necesarias, pero no se deben colocar decisiones sueltas en la raíz de `docs/`. Este `README.md` es la única excepción porque funciona como cartel de entrada.

## Regla de nombre

Dentro de cada categoría se usa el siguiente formato:

```text
N. Título de la decisión.md
```

Ejemplo:

```text
docs/planificacion/1. Plan de acción generado.md
```

El número es consecutivo **dentro de cada categoría**. Antes de crear un archivo, usa el siguiente número libre y evita renombrar documentos ya referenciados por otras ramas.

## Consolidación de ramas

Cuando se integran documentos históricos desde otra rama, se conserva su ruta y
número original para no romper referencias. Por eso una categoría puede mostrar
huecos temporales: el hueco identifica documentación que pertenece a otra línea
de trabajo todavía no consolidada, no un documento que deba inventarse o
renumerarse. Los documentos con el mismo nombre que ya tengan una versión más
reciente en `main` no se duplican ni se reemplazan automáticamente.

## Contenido mínimo

Cada documento debe indicar:

- Estado: `Propuesta`, `Aceptada`, `En progreso`, `Completada` o `Reemplazada`.
- Fecha y rama donde se tomó la decisión.
- Contexto o problema.
- Decisión o avance concreto.
- Consecuencias, riesgos y trabajo pendiente.
- Archivos o pruebas relacionados cuando existan.

## Flujo de trabajo

1. Todo desarrollo ocurre en una rama distinta de `main`.
2. La misma rama actualiza los documentos de las categorías afectadas.
3. El pull request incluye código y su documentación asociada.
4. Al integrar el pull request, `docs/` queda actualizado y activo en `main`.
5. Una decisión histórica no se borra: se marca como `Reemplazada` y se enlaza la nueva decisión.

No guardes tokens, llaves, teléfonos, direcciones ni otros secretos en esta carpeta.
