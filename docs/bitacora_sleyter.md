# Bitácora — Sleyter Correa

## Semana 1 (26/05/2026)

Esta semana arrancamos con el proyecto. Lo primero que hice fue leer el PDF varias veces porque la verdad no entendía bien de qué iba lo del "catálogo de mercados". Tuve que buscar qué significa exactamente un mercado de apuestas porque nunca había trabajado con eso.

Me tocó la app de `markets` que maneja los eventos deportivos, los tipos de apuesta (1X2, over/under, etc.) y las cuotas. En teoría es la parte más "sencilla" del sistema pero igual me tomó tiempo entender cómo encajaba con el resto.

Lo que hice:
- Monté los modelos Event, Market y Selection. El UUID como PK me confundió al inicio, estaba acostumbrado a usar el id numérico de Django
- Estuve un buen rato peleando con los serializers anidados porque quería que un POST creara el evento con sus mercados al mismo tiempo y DRF no lo permite así de fácil
- Hice el comando para meter datos de prueba. Me dio error en Windows por un símbolo de check (✓) que no soporta el encoding. Lo tuve que cambiar por [OK]
- Configuré el admin para que se vean los mercados dentro del evento directamente

Lo que no salió bien:
- Intenté hacer un filtro `?activo=true` que devolviera SCHEDULED y LIVE juntos pero no supe cómo mapearlo en django-filter, quedé con los filtros por separado
- El prefetch_related no funciona como yo creía dentro de los `@action`, me tardé en darme cuenta de eso

Coordiné con el grupo la distribución de partes y creé la rama Sleyter_Correa.

Para la próxima semana toca ver si Carlos o Arnold necesitan algo de los endpoints de markets para continuar con sus partes.
