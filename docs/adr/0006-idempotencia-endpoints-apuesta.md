# ADR 0006: Idempotencia en Endpoints de Apuesta

## Contexto
Las caídas de red, interrupciones de clientes móviles o reintentos automáticos de navegadores pueden provocar que un "POST /api/betting/bets/" (colocar una apuesta) llegue al servidor varias veces. Cobrarle la misma apuesta dos veces al usuario por un fallo de red es un error crítico.

## Decisión
Hemos implementado un middleware/mixin de Idempotencia. Todos los endpoints financieros (incluyendo depósitos, retiros y apuestas) exigen una cabecera HTTP personalizada `Idempotency-Key` generada por el cliente. El backend guarda la respuesta de cada clave; si detecta una clave repetida con un payload idéntico, retorna la misma respuesta sin procesar la transacción contable por segunda vez.

## Consecuencias
- **Positivas**: Protege contra "double-charging" en fallos de red (retries de la red). 
- **Negativas**: Aumenta la complejidad del almacenamiento (se requiere registrar y limpiar claves de idempotencia antiguas) y fuerza a los clientes web/móvil a implementar lógica de generación de UUIDs para las cabeceras HTTP.
