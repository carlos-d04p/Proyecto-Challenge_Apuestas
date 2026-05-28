# ADR-0001: Wallet con partida doble y saldo derivado

## Contexto

FairBet Lab es un simulador educativo de apuestas deportivas con moneda virtual. El modulo wallet debe registrar recargas, retiros simulados y futuras transferencias internas sin representar dinero real ni integrarse con pasarelas de pago.

El wallet requiere trazabilidad contable, control de concurrencia, idempotencia y compatibilidad con PostgreSQL para soportar operaciones atomicas y bloqueos pesimistas. Ademas, los montos financieros deben manejarse con `Decimal(18,4)`, sin usar `float`.

## Opciones consideradas

### Opcion 1: Guardar saldo directamente en usuario/perfil

**Descripcion:** Agregar un campo `balance`, `saldo` o similar en el usuario, perfil KYC o una tabla de wallet, y actualizarlo en cada operacion.

**Ventajas:**

- Consultas de saldo simples y rapidas.
- Menor complejidad inicial de implementacion.

**Desventajas:**

- Riesgo de inconsistencias si una operacion falla parcialmente.
- Menor trazabilidad de los cambios de saldo.
- Mayor dificultad para auditar movimientos financieros.
- Contradice la regla de no almacenar balance.

### Opcion 2: Calcular saldo desde movimientos ledger

**Descripcion:** Registrar cada movimiento como una `Transaction` con al menos dos `LedgerEntry` balanceados, y calcular el saldo desde los asientos del ledger usando `SUM(CREDIT) - SUM(DEBIT)` para la cuenta `USER_WALLET` del usuario.

**Ventajas:**

- Mayor trazabilidad y auditabilidad.
- El saldo se puede reconstruir desde los movimientos.
- Facilita validar invariantes contables.
- Permite correcciones futuras mediante transacciones compensatorias.

**Desventajas:**

- Consultas de saldo mas complejas.
- Requiere transacciones atomicas para evitar movimientos parciales.
- Requiere pruebas de invariantes y concurrencia.

## Decision

Se usara partida doble con saldo derivado desde el ledger.

Cada operacion financiera exitosa debera crear una `Transaction` como cabecera logica y un minimo de dos `LedgerEntry` asociados. La suma financiera de cada transaccion debera quedar balanceada, es decir, `SUM(CREDIT) - SUM(DEBIT) = 0`.

El saldo del usuario no se almacenara en columnas como `balance`, `saldo` o `current_balance`. Siempre se calculara desde los asientos del ledger filtrando por `account=USER_WALLET` y `account_owner=user`.

## Consecuencias

- Mayor trazabilidad de recargas, retiros simulados y transferencias internas.
- Mayor complejidad en consultas de saldo e historial.
- Necesidad de ejecutar movimientos financieros dentro de transacciones atomicas.
- Necesidad de usar bloqueos pesimistas en debitos para prevenir doble gasto.
- Necesidad de pruebas de invariantes contables, precision decimal y concurrencia.

## Relacion con reglas del wallet

- No se debe usar `float` para dinero, saldos, movimientos o montos financieros.
- No se debe almacenar balance en usuario, perfil ni wallet.
- Todo monto financiero debe manejarse como `Decimal(18,4)`.
- Toda operacion financiera debe generar una `Transaction`.
- Toda `Transaction` debe tener al menos dos asientos `LedgerEntry`.
- Toda `Transaction` debe quedar balanceada.

## Fecha y autor

- **Fecha:** 27 de mayo de 2026
- **Autor:** Equipo FairBet Lab
