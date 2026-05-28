# ADR 0005: Estrategia de Concurrencia (Select for Update vs Optimista)

## Estado
Aceptado

## Contexto
En eventos populares (ej. la final de la Champions League o un partido en vivo importante), miles de usuarios podrían intentar realizar apuestas simultáneas sobre los mismos mercados, o un mismo usuario podría intentar abusar del sistema lanzando múltiples peticiones concurrentes para agotar su balance antes de que se actualice.

## Decisión
Se implementará un enfoque híbrido dependiendo del dominio:

1. **Gestión de Saldos y Wallet (`select_for_update` / Pesimista):** 
Para debitar dinero de la cuenta del usuario, se bloqueará la fila correspondiente del balance utilizando bloqueo a nivel de base de datos (`SELECT ... FOR UPDATE`). Esto previene el problema del "doble gasto" de forma absoluta.

2. **Actualización de Cuotas y Mercados (Control de Concurrencia Optimista):**
Dado que las cuotas (odds) cambian rápidamente en apuestas en vivo (`markets`), bloquear el mercado detendría todas las lecturas. En lugar de ello, utilizaremos bloqueo optimista basado en versiones (`version_id`). Si al confirmar una apuesta, la versión del mercado ha cambiado, la base de datos rechazará la transacción y se aplicará la política de re-cotización.

## Consecuencias
### Positivas:
- **Seguridad financiera:** Previene fallas de doble gasto garantizando consistencia fuerte en `wallet`.
- **Rendimiento en mercados:** Permite altas tasas de lectura/escritura en cuotas sin bloqueos de DB costosos en `markets`.

### Negativas:
- **Deadlocks potenciales:** Riesgo de bloqueos cruzados en `select_for_update` si no se ordenan las sentencias consistentemente (siempre ordenar por ID de cuenta antes de bloquear).
- **Complejidad UI:** Requiere manejar el flujo de "Error por cambio de cuota" en el frontend cuando falla el bloqueo optimista de la apuesta.

## Fecha y Autor
* **Fecha:** 27 de Mayo de 2026
* **Autor:** Arnold Quiroz
