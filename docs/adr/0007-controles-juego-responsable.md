# ADR 0007: Controles de Juego Responsable

## Contexto
El juego compulsivo es un riesgo regulatorio y ético de la plataforma. El sistema debe ser capaz de limitar el daño financiero a los apostadores impulsivos o ludópatas.

## Decisión
Hemos implementado un modelo mixto de Juego Responsable:
1. **Límites Configurables**: Cada usuario tiene límites auto-impuestos de depósito y apuesta diaria/semanal. Un intento de sobrepasar estos límites lanza un error HTTP 400. Subir el límite toma 24 horas (cooldown), mientras que bajarlo es instantáneo.
2. **Autoexclusión**: El usuario puede bloquear su propia cuenta por 30 días, 1 año o indefinidamente. Las vistas en Django filtran las peticiones de usuarios bloqueados a nivel de Middleware.
3. **Monitoreo Automático**: Mediante Celery se detectan patrones de "Depósito rápido y Retiro Inmediato" (DEP_WD), bloqueando transacciones sospechosas y derivándolas a revisión humana.

## Consecuencias
- **Positivas**: Alineamiento ético total y cumplimiento prospectivo con las regulaciones de la Ley Peruana de Apuestas (Ley 31557). Reduce la responsabilidad civil de la casa de apuestas.
- **Negativas**: Posible fricción para los apostadores de alto riesgo (VIPs o "ballenas") que deseen aumentar sus apuestas rápidamente, afectando las métricas de ingresos brutos (GGR).
