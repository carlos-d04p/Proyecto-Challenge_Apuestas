# ADR-0002: Máquina de estados para el ciclo de vida de una apuesta

## Contexto
Necesitamos controlar de manera estricta las transiciones de estado de una apuesta (PENDING, PLACED, WON, LOST, VOID, CASHED_OUT) para evitar que un boleto sea liquidado dos veces o modificado una vez cerrado.

## Opciones Consideradas
### Opción 1: Validaciones condicionales simples en el modelo
* **Descripción:** Comprobar mediante estructuras `if/else` en cualquier método si el estado actual permite el cambio.
* **Pros:** Rápido de escribir inicialmente.
* **Contras:** Código disperso y propenso a errores si se añade un nuevo estado en el futuro.

### Opción 2: Máquina de estados transaccional centralizada (Elegida)
* **Descripción:** Validar centralizadamente en `settle_bet` y `cash_out_bet` que el estado origen sea estrictamente `PLACED` antes de mutar a un estado terminal.
* **Pros:** Sigue el principio de única responsabilidad y bloquea transiciones ilegales directamente bajo transacciones atómicas.
* **Contras:** Requiere controlar las excepciones manualmente en las pruebas unitarias.

## Decisión
Se implementa la **Opción 2** para asegurar la integridad del negocio de apuestas simples y combinadas.

## Consecuencias
* **Lo que se vuelve más fácil:** Es imposible re-liquidar un boleto que ya fue cobrado o anulado.
* **Lo que se vuelve más difícil:** Las pruebas unitarias deben simular estados específicos preexistentes en la base de datos.
* **Deudas técnicas asumidas:** No se utiliza una librería externa de FSM (como django-fsm) para mantener el proyecto ligero.

## Fecha y Autor
* **Fecha:** 27 de Mayo de 2026
* **Autor:** Carlos Cancino