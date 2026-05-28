# Declaración de uso de IA — Carlos Cancino

## App asignada: `betting` (Apuestas simples/combinadas, Máquina de estados, Liquidación y Cash-out)

---

## ¿Qué consulté a la IA?

### 1. Formulación matemática para Cash-out y precisión decimal
- **Qué pedí:** Que me validara la fórmula financiera estándar para calcular el valor de un cierre anticipado (Cash-out) y cómo aplicar correctamente un factor de retención (margen de la casa).
- **Para qué:** Para asegurar que los cálculos de mi módulo reflejaran el comportamiento matemático real sin generar fugas de dinero en la plataforma.
- **Lo que hice yo:** Implementé toda la lógica en código Python dentro de `services.py`, asegurando el uso del tipo de dato `Decimal` con precisión de 4 dígitos en el backend y limitando la visualización a 2 dígitos en el frontend mediante filtros de plantillas.

### 2. Estructuración de reglas de negocio y gestión de riesgo (Liability)
- **Qué pedí:** Ejemplos de la industria sobre cómo limitar las apuestas para no quebrar la casa de apuestas (cálculo de límite máximo dinámico) y reglas de anti-arbitraje.
- **Para qué:** Para definir un manifiesto sólido de reglas de negocio antes de programar las validaciones.
- **Lo que hice yo:** Traduje estas directrices teóricas a código real, escribiendo las validaciones para bloquear tickets con cuotas alteradas, limitar las combinadas a 5 eventos, y crear las excepciones (`ValidationError`) correspondientes.

### 3. Diagnóstico de errores en Git y Docker
- **Qué pedí:** Ayuda para interpretar mensajes de error específicos de la terminal, como bloqueos de fusión (`MERGE_HEAD exists`), archivos temporales de Vim (`.swp`), y fallos de autenticación de PostgreSQL en los logs de Docker.
- **Para qué:** Para comprender qué estaba fallando en mi entorno local al intentar integrar el trabajo de las ramas de mis compañeros con la mía.
- **Lo que hice yo:** Ejecuté la limpieza del repositorio, resolví los conflictos de código de manera manual línea por línea en VS Code, y reconstruí mi base de datos aislando los problemas de configuración.

---

## Lo que NO generé con IA
Todo el código fuente de mi módulo fue escrito enteramente por mí sin uso de generadores de código. En particular, destaco:
- La creación de la capa transaccional en `services.py` para el procesamiento seguro de apuestas simples y combinadas (ACCA).
- La implementación estricta de la **Máquina de Estados (FSM)**, garantizando mediante código que los tickets en estado terminal (`WON`, `LOST`, `VOID`, `CASHED_OUT`) sean inmutables.
- La integración de partida doble con el módulo `wallet`, asegurando el bloqueo concurrente (`select_for_update`) y el manejo de fondos entre `USER_WALLET` y `PENDING_BETS` bajo `transaction.atomic()`.
- La maquetación de los templates HTML (vistas MVT) para la interfaz de mis apuestas, aplicando la separación de la lógica de backend y la capa de presentación.

---

> Todo el código fuente es de mi autoría. La inteligencia artificial solo se usó de manera consultiva (como un motor de búsqueda avanzado y mentor técnico) para comprender fórmulas financieras, definir parámetros de negocio y agilizar el diagnóstico de errores de infraestructura y control de versiones.