# Bitácora Semanal - Arnold Quiroz

## Semana 1
- **Actividades**: Configuración inicial del repositorio, definición del modelo base de eventos deportivos y estructura del frontend en Django Templates.
- **Retos**: Entender la estructura de Channels para el futuro realtime.
- **Logros**: Docker-compose funcionando y modelos de base de datos definidos.

## Semana 2
- **Actividades**: Implementación del sistema de WebSockets para actualizar las cuotas en tiempo real en la página principal (`dashboard.html`).
- **Retos**: Configuración del `RedisChannelLayer` y evitar que el frontend colapse con demasiados eventos.
- **Logros**: Conexión bidireccional estable, las cuotas titilan en rojo/verde cuando cambian en el backend.

## Semana 3
- **Actividades**: Integración del módulo de la Billetera (Partida Doble) con el motor de Apuestas. 
- **Retos**: Lidiar con problemas de dependencias (ej. crash de Celery al integrar cambios del equipo) y compatibilidad de Python 3.9 con type hints nuevos (`str | None`).
- **Logros**: Panel de control OPS (Backoffice) creado, permitiendo liquidar eventos con un botón y pagar a los usuarios automáticamente.

## Semana 4 (Cierre)
- **Actividades**: Resolución de conflictos severos en Git (`urls.py`, `views.py`) tras la integración final con el equipo de Compliance. Redacción de documentación técnica y diagramas.
- **Retos**: Unir dos dashboards completamente diferentes en el mismo backoffice sin romper el trabajo de Sleyter/Walter.
- **Logros**: Entrega final lista, servidor corriendo estable sin `Connection Reset`, y cobertura de código generada.
