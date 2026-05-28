# Lecciones aprendidas — Sprint 1 (Markets)
**Autor:** Sleyter Correa | **App:** `markets`

---

## Intento fallido 1: UUID con `auto` en PostgreSQL

**Qué intenté:** Definir el campo `id` como `UUIDField(default=uuid.uuid4)` sin
especificar `editable=False`, esperando que Django lo manejara automáticamente.

**Qué pasó:** Django mostraba el campo `id` editable en el admin, lo que permitía
cambiarlo accidentalmente. Además, al ejecutar `makemigrations`, Django generaba
una migración con `default=uuid.uuid4` pero no marcaba el campo como no editable.

**Cómo lo resolví:** Agregué `editable=False` al `UUIDField`. Aprendí que esto es
estándar en Django cuando usas UUID como PK — `editable=False` evita que aparezca
en formularios del admin y señaliza la intención claramente.

---

## Intento fallido 2: Serializer anidado con escritura

**Qué intenté:** Hacer que `EventSerializer` con `markets` anidado fuera de
lectura y escritura (crear un evento con sus mercados en un solo POST).

**Qué pasó:** DRF no soporta escritura en serializers anidados por defecto.
Al enviar un POST con `markets: [...]`, DRF simplemente ignoraba el campo o
lanzaba un error de validación.

**Cómo lo resolví:** Separé las responsabilidades: crear el evento con un POST a
`/events/`, y luego crear los mercados con POST a `/markets/`. Es más RESTful.
Dejé los serializers anidados solo para lectura (`read_only=True`).

---

## Intento fallido 3: Filtrar eventos activos vs. terminados

**Qué intenté:** Agregar un filtro `?activo=true` personalizado que devolviera
solo eventos cuyo `status` sea `SCHEDULED` o `LIVE`.

**Qué pasó:** `django-filter` no soporta directamente un filtro booleano que mapee
a múltiples valores de un campo de texto. Intenté con `FilterSet` personalizado
pero tuve un error de configuración con `DjangoFilterBackend`.

**Cómo lo resolví:** Usé dos filtros separados (`?status=LIVE`, `?status=SCHEDULED`)
que el usuario puede combinar. Para el frontend sería más cómodo el filtro custom,
pero queda como mejora futura cuando se necesite.

---

## Intento fallido 4: `prefetch_related` en acción personalizada

**Qué intenté:** En la acción `events/{id}/markets/`, quería usar el queryset
ya prefetcheado del EventViewSet para no hacer un segundo query.

**Qué pasó:** `self.get_object()` no reutiliza el prefetch del queryset principal.
Cada llamada a `get_object()` hace su propio query sin prefetch a menos que se
especifique explícitamente.

**Cómo lo resolví:** Agregué `.prefetch_related("selections")` directamente sobre
el queryset dentro de la acción: `event.markets.filter(...).prefetch_related(...)`.
Aprendí que el prefetch hay que aplicarlo al queryset final que se va a iterar.

---

## Observaciones generales del sprint

- El esquema con UUID como PK en todas las tablas facilita la integración entre
  apps (p.ej. `linea_apuesta` puede referenciar cualquier `Selection` por UUID).
- El margen del operador debería configurarse por evento o mercado en una versión
  productiva. Dejarlo fijo en el seed es suficiente para el simulador educativo.
- Los tests con `pytest-django` y fixtures son mucho más limpios que el
  `TestCase` de Django por defecto. Vale la pena aprenderlos bien.


# Lecciones aprendidas — Sprint 1 (Betting)
**Autor:** Carlos Cancino | **App:** `betting`

## Intento fallido 1: Validación de estado in-memory en liquidación de apuestas
* **Qué intenté:** Validar si una apuesta ya estaba resuelta inspeccionando el atributo `.status` de la instancia de Python antes de abrir la transacción con bloqueo.
* **Qué pasó:** El test de doble liquidación falló porque los cambios en la base de datos no se reflejaban automáticamente en el objeto de memoria del test, permitiendo re-liquidar un ticket.
* **Cómo lo resolví:** Moví la validación `if bet_lock.status != Bet.Status.PLACED:` adentro del bloque `transaction.atomic()` inmediatamente después del `select_for_update()`. Esto blinda el flujo transaccional contra doble gasto e inconsistencias concurrentes.


## Intento fallido: Desincronización de estado de fixtures en pytest
* **Qué intenté:** Ejecutar múltiples aserciones consecutivas sobre un mismo objeto de prueba (`placed_bet`) mutando su estado directamente en memoria.
* **Qué pasó:** Provocó fallos de recolección y errores sintácticos (`fixture not found` / `IndentationError`) debido al anidamiento incorrecto de funciones utilitarias dentro de clases colectoras independientes.
* **Cómo lo resolví:** Extraje el fixture a nivel global del módulo y forcé recargas limpias desde el motor de persistencia de Django mediante transacciones atómicas.

# Lecciones aprendidas — Sprint Final (WebSockets & OPS)
**Autor:** Arnold Quiroz | **App:** `realtime` / `backoffice`

## Intento fallido 1: WebSockets bloqueando el servidor
* **Qué intenté:** Configurar Channels usando el enrutador sincrónico por defecto y haciendo llamadas directas a la base de datos dentro del consumer de WebSockets.
* **Qué pasó:** El servidor Daphne se bloqueaba al procesar peticiones HTTP normales porque el Event Loop de asincronía de Python quedaba atascado en operaciones I/O de base de datos.
* **Cómo lo resolví:** Refactoricé el `LiveOddsConsumer` para heredar de `AsyncWebsocketConsumer` y usé el decorador `@database_sync_to_async` en cada llamada al ORM de Django.

## Intento fallido 2: Broadcast redundante en Redis
* **Qué intenté:** Emitir un mensaje WebSocket a cada usuario individual iterando sobre todas las conexiones cuando una cuota cambiaba.
* **Qué pasó:** El servidor Redis colapsaba por exceso de mensajes (OOM) y el rendimiento era logarítmico.
* **Cómo lo resolví:** Utilicé grupos de Channels (`async_to_sync(channel_layer.group_send)`). Ahora emito un solo mensaje al grupo `live_events` y Channels se encarga eficientemente del fan-out.

## Intento fallido 3: Crash de Celery en Merge
* **Qué intenté:** Ejecutar el servidor después de integrar (merge) la rama de mi compañero (Compliance), asumiendo que mi entorno local era suficiente.
* **Qué pasó:** El servidor `manage.py runserver` arrojó `ModuleNotFoundError: No module named 'celery'` rompiendo el entorno de desarrollo y retornando `ERR_CONNECTION_RESET` en el frontend.
* **Cómo lo resolví:** Entendí que los cambios de rama incluyen cambios en dependencias. Instalé `celery` vía pip y actualicé mi `requirements.txt`.

## Intento fallido 4: Type Hints incompatibles en Python 3.9
* **Qué intenté:** Ejecutar el proyecto integrado con código que utilizaba la sintaxis `str | None`.
* **Qué pasó:** Arrojó un `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` porque mi Mac utiliza Python 3.9 y esa sintaxis fue introducida en Python 3.10.
* **Cómo lo resolví:** Modifiqué `core/idempotency.py` para usar `from typing import Optional` y la sintaxis clásica `Optional[str]`, garantizando retrocompatibilidad del proyecto.
