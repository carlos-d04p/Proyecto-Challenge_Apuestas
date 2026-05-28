# Declaración de uso de IA — Sleyter Correa

## App asignada: `markets`

---

## ¿Qué hice yo vs qué asistió la IA?

### Lo que hice yo:
- Leer y entender el PDF del reto varias veces
- Decidir qué parte del equipo me correspondía (catálogo de mercados)
- Entender el esquema de base de datos y cómo encajaban las tablas
- Decidir que los 3 modelos necesitaban UUID como PK para que `linea_apuesta` pueda referenciarlos
- Coordinar con el equipo la distribución de partes y crear `Main-de-prueba`
- Revisar que el output del servidor fuera correcto y probar los endpoints manualmente
- Entender los errores que surgieron (encoding en Windows, prefetch_related en @action)
- Redactar la bitácora semanal con mis palabras

### Donde usé IA significativamente (generación de código):
- `models.py` — la IA generó la estructura base de los modelos. Yo revisé y validé que coincidía con el esquema del PDF
- `serializers.py` — generado con asistencia de IA
- `views.py` — los ViewSets fueron generados con IA. Yo entendí la lógica de filtros y los probé
- `views_web.py` — generado con IA
- `admin.py` — generado con IA
- `seed_markets.py` — generado con IA, yo ajusté los datos de prueba y corregí el error de encoding
- `templates/` — los tres templates HTML fueron generados con IA
- `static/css/main.css` — generado con IA
- `urls.py` — generado con IA
- `tests.py` — estructura generada con IA, yo revisé que los casos tengan sentido
- `ADR-0001` — redactado con asistencia de IA basado en decisiones reales que tomé
- `lecciones.md` — los problemas son reales, la redacción tuvo asistencia de IA

### Donde usé IA solo para consultar conceptos (no generación):
- Entender qué es el "vigorish" o margen del operador en apuestas
- Diferencia entre `select_related` y `prefetch_related`
- Cómo funciona `DEFAULT_ROUTER` en DRF

---

## ¿Puedo defender el código en walkthrough?

Sí. Entiendo:
- Por qué los modelos usan UUID como PK
- Cómo funciona el prefetch_related en los ViewSets
- Qué hace el apply_margin y por qué se aplica al crear selecciones
- La diferencia entre las vistas de API (ViewSets) y las vistas web (views_web.py)
- El flujo completo: URL → Vista → Modelo → Template

Lo que no podría explicar en detalle sin revisar antes:
- La implementación interna exacta del CSS (animaciones específicas)
- Los detalles de configuración del DefaultRouter de DRF
