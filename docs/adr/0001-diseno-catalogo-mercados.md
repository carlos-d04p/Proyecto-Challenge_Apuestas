# ADR-0001: Diseño del catálogo de eventos y mercados

## Contexto

El sistema necesita representar eventos deportivos con sus mercados de apuesta y
las selecciones (opciones apostables) correspondientes. La estructura debe ser lo
suficientemente flexible para soportar distintos tipos de mercado (resultado final,
over/under, ambos anotan, handicap) y estados de ciclo de vida para el evento.

El reto principal es decidir cómo modelar la jerarquía Event → Market → Selection
y cómo manejar el margen del operador en las cuotas.

## Opciones Consideradas

### Opción 1: Un solo modelo con campo JSON para selecciones
* **Descripción:** Guardar el evento con sus cuotas en un único modelo usando
  un campo `JSONField` para las selecciones y sus odds.
* **Pros:**
    * Menos tablas, más simple de leer de un vistazo.
    * Un solo query para obtener todo el evento.
* **Contras:**
    * Imposible filtrar, ordenar o actualizar selecciones individuales.
    * Los odds no son un `Decimal` tipado, se pierde precisión.
    * No se puede referenciar una selección individualmente desde `linea_apuesta`.

### Opción 2: Tres modelos separados Event → Market → Selection (elegida)
* **Descripción:** Cada entidad tiene su propia tabla con UUID como PK. Las
  selecciones referencian su mercado y los mercados referencian su evento.
* **Pros:**
    * Cada selección tiene un UUID propio, necesario para `linea_apuesta`.
    * Los odds se guardan como `Decimal(10,4)`, sin pérdida de precisión.
    * Se pueden actualizar cuotas individuales sin tocar el resto (para tiempo real).
    * Filtros y búsquedas eficientes por deporte, estado, tipo de mercado.
* **Contras:**
    * Requiere JOINs para obtener el árbol completo.
    * Serializers anidados en DRF son algo más verbosos.

## Decisión

Se implementa la **Opción 2**: tres modelos separados con UUID como clave primaria.
Los `odds` se definen como `DecimalField(max_digits=10, decimal_places=4)` para
respetar el requisito de precisión del proyecto.

El margen del operador se aplica como una función utilitaria `apply_margin()` al
momento de crear selecciones, no se almacena en la base de datos. Así los odds
guardados ya incluyen el margen y pueden consultarse directamente.

## Consecuencias

* **Lo que se vuelve más fácil:** Arnold puede conectar `realtime` y actualizar
  cuotas de una sola `Selection` via WebSocket sin tocar el resto del evento.
  Walter (betting) puede referenciar una `Selection` directamente desde `linea_apuesta`.
* **Lo que se vuelve más difícil:** Para mostrar el evento completo en un solo
  response hay que usar `prefetch_related`, lo que se hizo en los ViewSets.
* **Deudas técnicas asumidas:** El margen del operador es fijo (5%) definido en
  el comando `seed_markets`. En producción debería ser configurable por mercado
  o evento desde el admin, lo cual se deja como mejora futura.

## Fecha y Autor
* **Fecha:** 27 de Mayo de 2026
* **Autor:** Sleyter Correa
