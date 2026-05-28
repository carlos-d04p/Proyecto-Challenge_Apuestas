# Uso de IA — Sleyter Correa / markets

Voy a ser honesto porque el PDF lo pide y porque igual se nota si uno miente en el walkthrough.

## Cómo usé la IA

La usé principalmente para generar el código de la app. Le explicaba qué necesitaba (por ejemplo "necesito un modelo Django para un evento deportivo con UUID como PK y 5 estados posibles") y la IA me daba el código. Yo lo revisaba, lo comparaba con el esquema del PDF, y ajustaba lo que no cuadraba.

Los archivos donde la asistencia fue mayor: `models.py`, `serializers.py`, `views.py`, `admin.py`, `urls.py`, `tests.py`, los templates y el CSS. En todos esos casos yo no escribí el código desde cero pero sí lo revisé y entiendo para qué sirve cada parte.

Donde sí participé más directamente:
- Definir que los modelos necesitaban UUID como clave primaria para que Carlos (betting) pudiera referenciar selecciones desde `linea_apuesta`. Eso lo decidí yo al leer el esquema de BD.
- Corregir el error de encoding en Windows cuando el seed crasheaba por el símbolo ✓. Encontré el error yo, supe qué era y lo corregí cambiándolo por [OK].
- Los datos de prueba del seed los ajusté yo (qué eventos, qué deportes, qué cuotas base).
- La coordinación con el equipo, la creación de la rama `Main-de-prueba` y avisarle a Arnold sobre los endpoints.
- La bitácora y este documento los escribí yo (con algo de ayuda para la estructura inicial).

También usé la IA para entender conceptos antes de escribir: me explicó qué es el margen del operador en apuestas (vigorish) y la diferencia entre `select_related` y `prefetch_related`. Eso me ayudó a entender el código que después revisé.

## Lo que puedo defender

En el walkthrough puedo explicar:
- Por qué tres modelos separados y no JSON estático
- Por qué UUID como PK
- Cómo funciona el margen del 5% al crear una selección
- La diferencia entre los ViewSets (API) y las vistas web (HTML)
- Por qué el prefetch_related va en el queryset local dentro de @action

Lo que no podría detallar sin revisar: los detalles internos del CSS o la configuración exacta del DefaultRouter.
