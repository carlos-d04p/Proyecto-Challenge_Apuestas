# ADR 0006: Idempotencia en Endpoints de Apuesta y Pagos

## Estado
Aceptado

## Contexto
Las caídas de red, los timeouts en los clientes móviles o los reintentos automáticos del navegador pueden causar que un usuario envíe la misma solicitud de "Crear Apuesta" o "Depositar" más de una vez. Sin un control, esto resultaría en apuestas o cargos duplicados que afectarían negativamente la experiencia y las finanzas del usuario.

## Decisión
Todo endpoint que modifique estados financieros o de apuestas en `betting` y `payments` debe ser idempotente.

Se implementará el uso obligatorio de una cabecera `Idempotency-Key` (UUIDv4 generado por el cliente frontend) para la creación de apuestas y transacciones de pago.
- El servidor buscará esta clave en una caché rápida (ej. Redis) o base de datos.
- Si la clave ya existe y el proceso terminó con éxito, se devuelve la respuesta guardada previamente.
- Si el proceso está en curso, se bloquea o retorna un código de estado específico (ej. HTTP 409 Conflict o 425 Too Early).
- Si la clave no existe, se procesa y se registra el resultado asociado a esa clave.

## Consecuencias
### Positivas:
- **Fiabilidad y confianza:** Los usuarios no sufrirán cargos dobles por presionar un botón varias veces o por mala conectividad.
- **Simplicidad para el cliente:** El frontend puede reintentar solicitudes POST sin miedo a efectos secundarios.

### Negativas:
- **Estado adicional:** Se requiere infraestructura (Redis) o espacio en DB para almacenar las claves de idempotencia junto con la respuesta generada.
- **Sobrecarga de validación:** Cada petición requiere un chequeo previo en la capa de persistencia de claves.

## Fecha y Autor
* **Fecha:** 27 de Mayo de 2026
* **Autor:** Arnold Quiroz
