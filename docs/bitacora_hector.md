# Bitacora de desarrollo - Modulo Wallet

**Autor:** Hector  
**App:** `wallet`  
**Proyecto:** FairBet Lab

## Objetivo del modulo

El modulo `wallet` permite administrar fichas virtuales dentro de FairBet Lab. Su importancia para el negocio es central porque controla el saldo del usuario, las recargas simuladas, los retiros simulados, los bonos y los movimientos internos que luego se relacionan con apuestas.

Al tratarse de un simulador educativo, el wallet debe dejar claro que no procesa dinero real. A nivel tecnico, el modulo se construyo con partida doble para asegurar trazabilidad, evitar saldos manipulados y permitir auditoria de cada movimiento.

## Secuencia de trabajo

| Actividad | Que se realizo | Importancia para el negocio | Parte tecnica principal |
| --- | --- | --- | --- |
| 0 - Diagnostico | Se revisaron archivos existentes, modelos vacios y configuracion inicial. | Permitio identificar brechas antes de implementar dinero virtual. | Revision de `apps/wallet`, `core/money.py`, idempotencia y tests. |
| 0.2 - Reglas de negocio | Se definieron reglas obligatorias para saldo, ledger, Decimal e idempotencia. | Aseguro que el wallet no funcione como dinero real y respete el enfoque educativo. | Reglas RB-WAL para partida doble y validaciones financieras. |
| 0.3 - Configuracion PostgreSQL | Se alineo Django con PostgreSQL y apps del dominio. | PostgreSQL permite probar concurrencia real y bloqueos pesimistas. | Variables de entorno, `DATABASES`, `INSTALLED_APPS`. |
| 1 - ADR wallet | Se documento la decision de usar partida doble con saldo derivado. | Da respaldo tecnico a la decision de no guardar saldos directos. | ADR sobre ledger y consecuencias. |
| 2 - Tests de dinero | Se agregaron pruebas para normalizacion de montos. | Evita errores financieros por floats o montos invalidos. | Tests de Decimal, cero, negativos y precision. |
| 3 - Implementar `core/money.py` | Se implemento normalizacion de dinero. | Unifica la forma en que el sistema trata montos de fichas. | `Decimal`, 4 decimales, rechazo de `float`. |
| 4 - Tests de modelos | Se definieron pruebas para `Transaction` y `LedgerEntry`. | Asegura que la base contable tenga campos correctos. | Choices, constraints y `DecimalField(18,4)`. |
| 5 - Modelos + migracion | Se implementaron modelos financieros del wallet. | Permite registrar movimientos auditables y balanceados. | `Transaction`, `LedgerEntry`, indices y constraints. |
| 6 - Tests de saldo | Se probaron escenarios de saldo inicial, creditos, debitos y multiples movimientos. | Garantiza que el saldo visible no dependa de un campo manipulable. | Agregaciones sobre `LedgerEntry`. |
| 7 - Selector de saldo | Se implemento calculo de saldo derivado. | Permite mostrar saldo real segun ledger. | `SUM(CREDIT) - SUM(DEBIT)` por cuenta y usuario. |
| 8 - Tests de servicios | Se probaron deposito, retiro y transferencia interna. | Cubre operaciones principales del usuario. | Transacciones balanceadas y rollback ante fallos. |
| 9 - Servicios wallet | Se implementaron operaciones financieras centrales. | Es el nucleo del wallet: recargar, retirar y mover fichas. | `transaction.atomic()`, ledger doble, validacion de saldo. |
| 10 - Tests de idempotencia | Se probaron claves repetidas y conflictos de payload. | Evita cobros o movimientos duplicados por doble clic o reintentos. | Hash de request y unicidad por usuario/key. |
| 11 - Implementar idempotencia | Se integro idempotencia en servicios del wallet. | Aumenta confiabilidad de operaciones criticas. | Registro de idempotencia dentro de transacciones atomicas. |
| 12 - Property-based tests | Se agregaron pruebas de invariantes financieras. | Detecta errores en casos variados de montos y secuencias. | Hypothesis para balance, no negativos y precision. |
| 13 - Tests de concurrencia | Se probo doble gasto con retiros simultaneos. | Protege el saldo ante operaciones concurrentes. | Threads y pruebas transaccionales contra PostgreSQL. |
| 14 - Ajuste de concurrencia | Se reforzo bloqueo con `select_for_update`. | Evita que dos retiros gasten el mismo saldo. | Bloqueo pesimista y recalculo dentro de `atomic`. |
| 15 - Endpoints DRF | Se expusieron endpoints de balance, recarga y retiro. | Permite que frontend consuma operaciones del wallet. | Serializers, views y rutas API. |
| 15.1 - Interfaz visual wallet | Se implemento la pantalla de billetera. | Hace usable el modulo para el cliente/apostador. | Template, CSS, JS, formularios simulados y mensajes. |
| 16 - Auditoria | Se integraron eventos auditables del wallet. | Permite rastrear operaciones exitosas sin datos sensibles. | Eventos de auditoria con `transaction_id`, usuario, monto y tipo. |
| 17 - Bonos promocionales | Se agrego logica real de bonos en cuenta `BONUS`. | Mejora experiencia comercial sin comprometer dinero real. | Campanias, redencion, ledger balanceado y restriccion de retiro. |
| 18 - Ajustes visuales finales | Se refino la UI de wallet, formularios y validaciones. | Da una experiencia mas clara, profesional y confiable. | Formato de montos, validacion de tarjeta simulada y layout responsive. |

## Importancia para FairBet Lab

El wallet es importante porque conecta la experiencia del usuario con la seguridad financiera del simulador. Aunque las fichas no tienen valor monetario real, el sistema debe comportarse como una plataforma seria: cada movimiento debe quedar registrado, balanceado y auditado.

La decision de usar partida doble ayuda a:

- Evitar saldos almacenados y faciles de alterar.
- Reconstruir el saldo desde movimientos reales.
- Prevenir inconsistencias por errores o concurrencia.
- Preparar el sistema para apuestas, devoluciones, cash-out y bonos.
- Mantener transparencia frente a auditoria y cumplimiento.

## Resumen tecnico simple

El modulo usa `Transaction` como cabecera de cada operacion y `LedgerEntry` como asiento contable. Para que una operacion sea valida, debe tener al menos dos asientos y quedar balanceada.

El saldo disponible se calcula desde la cuenta `USER_WALLET`. Las fichas pendientes se separan en `PENDING_BETS` y los beneficios promocionales en `BONUS`. La cuenta `HOUSE` representa el sistema.

Las operaciones criticas usan:

- `Decimal` para montos.
- `transaction.atomic()` para evitar operaciones parciales.
- `select_for_update()` para prevenir doble gasto.
- Idempotencia para evitar duplicados.
- Tests unitarios, property-based y de concurrencia.

## Relacion con commits `[ai-assisted]`

La siguiente tabla resume que actividades podrian justificar el sufijo `[ai-assisted]` en commits, tomando como base el nivel de asistencia y complejidad tecnica.

| Actividad                       |     Conviene `[ai-assisted]`? | Motivo                                                              |
| ------------------------------- | -----------------------------: | ------------------------------------------------------------------- |
| 0 - Diagnostico                 |                             No | No hay commit. Solo analisis.                                       |
| 0.2 - Reglas de negocio         |                             No | Es contexto, no implementacion.                                     |
| 0.3 - Configuracion PostgreSQL  | Opcional, pero diria **No**    | Es configuracion tecnica simple.                                    |
| 1 - ADR wallet                  |              No necesariamente | Es documentacion.                                                   |
| 2 - Tests de dinero             |                             No | Tests simples de validacion Decimal.                                |
| 3 - Implementar `core/money.py` |                       Opcional | Solo si la funcion fue generada principalmente con IA.              |
| 4 - Tests de modelos            |                             No | Son pruebas estructurales relativamente simples.                    |
| 5 - Modelos + migracion         |                  **Si viable** | Define modelos financieros, constraints, choices e indices.         |
| 6 - Tests de saldo              |                             No | Son pruebas directas.                                               |
| 7 - Selector de saldo           |                  No / opcional | Es una agregacion simple si fue revisada manualmente.               |
| 8 - Tests de servicios          |                  **Si viable** | Define escenarios criticos del wallet.                              |
| 9 - Servicios wallet            |                  **Si viable** | Es logica financiera central.                                       |
| 10 - Tests de idempotencia      |                       Opcional | Viable si la IA diseno casos complejos.                             |
| 11 - Implementar idempotencia   |                  **Si viable** | Es logica critica contra duplicidad.                                |
| 12 - Property-based tests       |                  **Si viable** | Hypothesis e invariantes financieras son complejos.                 |
| 13 - Tests de concurrencia      |                  **Si viable** | Concurrencia real y doble gasto son parte critica.                  |
| 14 - Ajuste de concurrencia     |                  **Si viable** | `select_for_update` y atomicidad son delicados.                     |
| 15 - Endpoints DRF              |                       Opcional | Solo si la IA implemento serializers, views y rutas completas.      |
| 15.1 - Interfaz visual wallet   |                       Opcional | Viable si se genero bastante frontend con asistencia.               |
| 16 - Auditoria                  |                  **Si viable** | Integra wallet con trazabilidad y audit log.                        |
| 17 - Documentacion              |                             No | Es mejor redactarla y defenderla personalmente.                     |

## Cierre

El desarrollo del wallet aporta una base confiable para FairBet Lab porque separa claramente la experiencia educativa del usuario de la integridad contable interna. El modulo queda preparado para crecer hacia apuestas, bonos, devoluciones y auditoria sin abandonar la regla principal: todo movimiento de fichas debe ser trazable, balanceado y seguro.
