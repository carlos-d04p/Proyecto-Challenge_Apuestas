# Bitácora — Walter Llatas

## Semana 1 (26/05/2026)

Esta semana arranqué con el proyecto enfocado en la parte de `accounts`. Lo primero fue leer el PDF para entender bien los requerimientos legales, sobre todo el tema de validación de mayoría de edad y la autoexclusión, que es un requerimiento vital según la Ley 31557 para el simulador.

Me tocó toda la app de `accounts` que maneja el registro, la autenticación, el KYC (conozca a su cliente), la gestión de límites y el tema de correos. Era bastante lógica de negocio y permisos, así que me enfoqué en que funcione bien y sea fácil de probar para el evaluador.

Lo que hice:
- Creé el modelo `PerfilKYC` ligado al usuario de Django usando Signals para que se cree automáticamente tras el registro y gestione todos sus estados (PENDING, VERIFIED, BLOCKED, SELF_EXCLUDED).
- Implementé la lógica para validar el DNI y la edad en el formulario de registro. Al principio el dígito verificador del DNI fallaba porque usaba un cálculo incorrecto, pero lo ajusté a los parámetros peruanos.
- Configuré Celery y Redis para que los correos de verificación y la "verificación RENIEC" asíncrona no bloqueen la vista principal del usuario.
- Integré WebSockets con Django Channels para que el frontend (`perfil.html`) se actualice en tiempo real de "Pendiente" a "Verificado" apenas Celery termine de procesar en el fondo.
- Puse Mailpit para interceptar correos localmente, dejando el enlace al puerto 8025 a la vista en el perfil para que los evaluadores lo puedan probar sin usar sus correos reales.

Lo que no salió bien:
- Tuve serios dolores de cabeza con los conflictos de Git al hacer merge con el equipo, sobre todo en `settings.py`, `urls.py` y `base.html`. Al unir mi rama con la del equipo, las configuraciones chocaban.
- Me pasé un buen rato intentando entender por qué Celery fallaba al iniciar; resultó ser por unos imports circulares y funciones faltantes (`cash_out_bet`) en los otros módulos que afectaban la carga inicial.

Coordiné la integración de mi rama `Walter_Llatas` hacia la principal `Main-de-prueba`, logrando unificar WebSockets con los endpoints de los chicos.

Para la próxima semana tocaría ver detalles de UI si sobra tiempo, o refinar las validaciones de los límites si el evaluador tiene algún comentario.
