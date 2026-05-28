# ADR-0009: Política de Re-cotización en Cuotas de Apuesta

## Contexto
Las cuotas cambian constantemente en tiempo real (especialmente in-play). Debemos asegurar que el usuario juegue bajo el valor exacto que visualizó y aceptó en su interfaz.

## Opciones Consideradas
### Opción 1: Aceptar la cuota final vigente en el sistema automáticamente
* **Descripción:** El backend toma la cuota actual disponible en el momento exacto de procesar la transacción sin importar lo que vio el usuario.
* **Pros:** La apuesta nunca se rechaza.
* **Contras:** Perjudica la transparencia y rompe las expectativas del usuario si la cuota disminuye de golpe.

### Opción 2: Validación estricta con expected_odds (Elegida)
* **Descripción:** El cliente envía la cuota esperada (`expected_odds`). El backend la compara contra la base de datos bajo un bloqueo pesimista y rechaza la operación con una excepción si no coinciden.
* **Pros:** Cumplimiento normativo riguroso y protección del usuario.
* **Contras:** Incrementa la tasa de rechazo de transacciones en momentos de alta volatilidad de cuotas.

## Decisión
Se implementa la **Opción 2** levantando un error `ValidationError` si `selection.odds != expected_odds`.

## Consecuencias
* **Lo que se vuelve más fácil:** Garantía total de transparencia en apuestas simples y combinadas.
* **Lo que se vuelve más difícil:** El frontend debe implementar flujos de reconfirmación rápidos cuando el backend rechaza un boleto.
* **Deudas técnicas asumidas:** No se definió un umbral de tolerancia mínimo (ej. +/- 0.01) para mitigar rechazos por micro-cambios insignificantes.

## Fecha y Autor
* **Fecha:** 27 de Mayo de 2026
* **Autor:** Arnold Quiroz
