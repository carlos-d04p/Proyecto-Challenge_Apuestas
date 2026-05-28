# Declaración de Uso de IA - Arnold Quiroz

En cumplimiento con la rúbrica del proyecto, declaro de manera honesta y transparente el uso de Inteligencia Artificial como herramienta de asistencia durante el desarrollo de este proyecto.

## Herramientas Utilizadas
- **Modelos**: GPT-4, Claude 3, Gemini (Vía asistentes IDE y chat).
- **Herramientas**: GitHub Copilot, Agentes Autónomos de IDE.

## Áreas de Aplicación
1. **Generación de Boilerplate**: Se utilizó IA para inicializar las estructuras de Django, archivos de configuración (Dockerfile, docker-compose) y esqueletos de los tests.
2. **Refactorización y Resolución de Conflictos**: Se utilizó asistencia de IA (específicamente Antigravity) para resolver conflictos severos de Git durante la fase final de integración (Merge conflicts en `urls.py`, `views.py`), así como para detectar la falta de la dependencia `celery` y el error de sintaxis en `idempotency.py` originados al unir las ramas.
3. **Diagramas**: Los diagramas de Mermaid (Entity-Relationship, Secuencias y State Machine) fueron generados con instrucciones asistidas por IA para agilizar la documentación técnica.
4. **Traducción y Documentación**: Asistencia en la estructuración de la documentación OpenAPI y redacción gramatical del ensayo.

## Decisiones Humanas (No IA)
La lógica principal del negocio, las decisiones arquitectónicas de emplear Partida Doble (Double-Entry Ledger), el esquema de concurrencia pesimista (`select_for_update`) y la integración del juego responsable fueron decisiones tomadas por el equipo humano basándose en la Ley 31557 y en principios contables; la IA fue utilizada como un programador par (pair-programmer) para ejecutar nuestra visión arquitectónica, no como la mente maestra del negocio.
