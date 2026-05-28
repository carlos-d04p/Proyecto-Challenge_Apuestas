# ADR 0005: Estrategia de Concurrencia (select_for_update)

## Contexto
En escenarios de alta carga, un usuario podría emitir múltiples peticiones HTTP simultáneas para apostar o retirar dinero, excediendo su balance actual (Double-Spending). O bien, múltiples administradores podrían intentar liquidar el mismo evento simultáneamente.

## Decisión
Implementamos bloqueos de base de datos pesimistas utilizando el método `select_for_update()` de Django (dentro de un bloque `transaction.atomic()`) en todas las operaciones que modifiquen el estado de la billetera o el estado de un evento deportivo. Descartamos la estrategia optimista (versioning) para evitar el retrabajo de código cliente al manejar excepciones `OptimisticLockError`.

## Consecuencias
- **Positivas**: Evita condiciones de carrera (Race Conditions) y garantiza absolutamente la consistencia de los balances.
- **Negativas**: Mayor contención de bloqueos en la base de datos que puede resultar en `TimeoutErrors` o `Deadlocks` si las transacciones son muy largas, lo que obliga a mantener la lógica transaccional lo más concisa y rápida posible.
