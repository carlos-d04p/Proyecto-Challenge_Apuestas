# ADR 0009: Controles de Juego Responsable en Middleware y Lógica Central

## Estado
Aceptado

## Contexto
Por cumplimiento legal y ético, la plataforma de apuestas debe asegurar mecanismos para evitar el juego problemático. Esto requiere integrar límites de depósito, límites de pérdidas, recordatorios de tiempo de sesión y mecanismos de autoexclusión. No centralizar estas validaciones podría permitir el bypass de los controles.

## Decisión
Se centralizará toda la lógica de reglas en la aplicación `compliance`. La verificación de estos controles se implementará interceptando las acciones correspondientes antes de llegar al procesamiento core en `betting` o `payments`.

Controles mínimos a implementar y validar:
- **Límite de Depósito:** Acumulado de la cuenta en frecuencia diaria/semanal/mensual. Evaluado al intentar depositar.
- **Límite de Pérdida o Apuesta Máxima:** Evaluado antes de aceptar el ticket.
- **Autoexclusión (Self-Exclusion):** Bloqueo total de la cuenta por un tiempo determinado (ej. 6 meses, permanente). Verificado a nivel de login y middleware de autenticación.

## Consecuencias
### Positivas:
- **Cumplimiento regulatorio y ético:** Prepara el terreno para operar legalmente en jurisdicciones fuertemente reguladas y protege al jugador.
- **Seguridad en la plataforma:** El diseño garantiza que ningún endpoint escape accidentalmente a las reglas si se usa un enfoque transversal (middleware/decorators).

### Negativas:
- **Performance overhead:** Cada intento de apuesta, depósito o login debe consultar los límites actuales y el estado del usuario en BD o Caché antes de proceder.
- **Mayor acoplamiento de Compliance:** Módulos de billetera y apuestas ahora dependen del estado devuelto por `compliance`.

## Fecha y Autor
* **Fecha:** 27 de Mayo de 2026
* **Autor:** nombre