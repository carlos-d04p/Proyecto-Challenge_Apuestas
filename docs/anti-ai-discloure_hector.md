# Declaracion de uso de IA - Hector

**Autor:** Hector  
**Modulo trabajado:** `wallet`  
**Proyecto:** FairBet Lab

## Uso declarado

Durante el desarrollo del modulo `wallet` se utilizo asistencia de IA de forma general como apoyo tecnico para consultar funciones, modelos, metodos y patrones importantes relacionados con la logica financiera del wallet.

La IA no reemplazo la revision humana del codigo ni la toma de decisiones del proyecto. Su uso principal fue apoyar la comprension, estructuracion y validacion de partes criticas del modulo, especialmente en reglas de negocio relacionadas con saldo derivado, ledger de partida doble, idempotencia, concurrencia y presentacion visual.

## Actividades con apoyo relevante de IA

| Actividad | Uso de IA | Motivo |
| --- | --- | --- |
| 9 - Servicios wallet | Si | Se consultaron patrones para estructurar operaciones financieras con `transaction.atomic()`, doble asiento ledger y validacion de saldo. |
| 11 - Implementar idempotencia | Si | Se uso apoyo para revisar el flujo de `Idempotency-Key`, hash de payload y prevencion de transacciones duplicadas. |
| 14 - Ajuste de concurrencia | Si | Se consulto el uso correcto de `select_for_update()` y recalculo de saldo dentro de transacciones atomicas para prevenir doble gasto. |
| 15 - Interfaz visual wallet | Si | Se uso apoyo para organizar la pantalla de billetera, formularios simulados, mensajes de error y estructura visual orientada al usuario. |

## Alcance del apoyo

La asistencia de IA fue usada para:

- Consultar buenas practicas de Django y PostgreSQL aplicadas al wallet.
- Revisar alternativas para servicios financieros con partida doble.
- Mejorar la consistencia de validaciones y mensajes de usuario.
- Ordenar la interfaz visual de la billetera.
- Detectar riesgos de concurrencia, duplicidad e inconsistencias de saldo.

## Responsabilidad

El codigo final fue revisado y adaptado al contexto del proyecto FairBet Lab. Las decisiones de negocio se mantuvieron alineadas con las reglas del simulador educativo:

- Uso de moneda virtual.
- Sin dinero real.
- Sin pasarelas reales.
- Saldo derivado desde ledger.
- Operaciones atomicas.
- Trazabilidad y pruebas.

Por tanto, el uso de IA se considera una asistencia tecnica y no una sustitucion de autoria o responsabilidad sobre el modulo desarrollado.
