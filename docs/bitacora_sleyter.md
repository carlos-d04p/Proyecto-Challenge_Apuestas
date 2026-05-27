# Bitácora Semanal — Sleyter Correa
**Proyecto:** FairBet Lab | **App asignada:** `markets`

---

## Semana 1 — 26 al 31 de Mayo 2026

### ¿Qué hice esta semana?

- Cloné el repositorio y leí el PDF del reto completo para entender el alcance
- Analicé el esquema de base de datos (DBML) y ubiqué las tablas que me corresponden:
  `evento`, `mercado`, `seleccion`
- Creé mi rama `Sleyter_Correa` y la publiqué en GitHub
- Diseñé e implementé los tres modelos con UUID como clave primaria
- Configuré los estados del evento como choices de Django (FSM simple)
- Implementé los serializers anidados con DRF para devolver el árbol
  Event → Market → Selection en un solo response
- Agregué filtros por deporte, estado y búsqueda por nombre
- Configuré el admin de Django con inlines para gestionar eventos fácilmente
- Creé el comando `seed_markets` para poblar la BD con datos de prueba reales
  (4 eventos, 10 mercados, 24 selecciones con margen del 5%)
- Apliqué el margen del operador con la función `apply_margin()` al crear selecciones
- Escribí los tests con pytest y fixtures
- Documenté el ADR-0001 con la decisión de usar 3 modelos separados vs JSON
- Completé `lecciones.md` con 4 intentos fallidos del sprint
- Completé `anti-ai-disclosure.md` con lo que consulté y lo que hice yo

### ¿Qué aprendí?

- Cómo funciona el margen del operador ("vigorish") en apuestas deportivas
  y por qué los odds nunca suman exactamente 1 dividido entre probabilidades
- Diferencia práctica entre `select_related` (FK/OneToOne) y
  `prefetch_related` (relaciones inversas/M2M) para optimizar queries
- Que `editable=False` en UUIDField es necesario para que no aparezca
  como campo editable en formularios del admin
- Los serializers anidados de DRF son solo lectura por defecto —
  para escritura hay que separar los endpoints

### Problemas que encontré

- Error `UnicodeEncodeError` al usar el símbolo ✓ en Windows (cp1252).
  Lo resolví reemplazándolo por `[OK]` en el output del comando
- El `prefetch_related` del queryset principal no se reutiliza dentro
  de acciones `@action`, hay que aplicarlo de nuevo al queryset local

### Coordinación con el equipo

- Los endpoints de `markets` están listos para que Carlos (betting)
  los consuma cuando implemente `linea_apuesta`
- Avisé a Arnold (realtime) que cada `Selection` tiene UUID propio,
  que es lo que necesita para actualizar un odds específico vía WebSocket
- Compartí la distribución de partes con el grupo

### Para la próxima semana

- Revisar si el equipo necesita algún endpoint adicional de markets
- Apoyar con la configuración del `docker-compose` si se necesita
- Verificar que mis tests corren bien junto con los del resto del equipo
