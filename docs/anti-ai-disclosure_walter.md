# Declaración de uso de IA — Walter Llatas

## App asignada: `accounts` (Registro, KYC, WebSockets y Correos)

---

## ¿Qué consulté a la IA?

### 1. Integración de Django Channels y WebSockets
- **Qué pedí:** Repaso rápido de cómo levantar un `AsyncWebsocketConsumer` con Django 5 y cómo enviarle un mensaje desde una tarea en segundo plano de Celery.
- **Para qué:** Para la notificación en tiempo real del cambio de estado del KYC (de "Verificando..." a "Verificado") en el perfil del usuario sin necesidad de recargar la página web.
- **Lo que hice yo:** Armé toda la estructura de Channels en `consumers.py`, lo ligué con Redis, y escribí el código en Javascript en `perfil.html` para recibir e interpretar la señal enviada por Celery.

### 2. Algoritmo de validación del DNI
- **Qué pedí:** Una guía de cómo validar que un DNI peruano tenga los caracteres correctos y cómo estructurar los tests para validadores personalizados.
- **Para qué:** Para implementarlo en el registro y cumplir el requerimiento de que los usuarios solo puedan registrarse con DNIs válidos.
- **Lo que hice yo:** Creé la clase `DNIValidator` en Django que evalúa que la cadena solo contenga números, tenga 8 dígitos, y levante un `ValidationError` limpio que se conecte directamente con los errores del formulario en la interfaz gráfica.

### 3. Resolución de Conflictos (Git Merge)
- **Qué pedí:** Asistencia para entender por qué mi `requirements.txt` y los tests chocaban con los de mis compañeros al fusionar mi código con `Main-de-prueba`.
- **Para qué:** Para unificar las ramas sin romper el módulo de apuestas y eventos de mi equipo.
- **Lo que hice yo:** Fui resolviendo los conflictos manualmente archivo por archivo (como `settings.py` y `urls.py`), asegurándome de priorizar las apps requeridas y combinando el CSS de la interfaz correctamente.

---

## Lo que NO generé con IA
- La estructura de modelos de configuración y límite de depósito (`daily_deposit_limit`, etc.) en la entidad `PerfilKYC`.
- La decisión de utilizar `Mailpit` en el entorno de Docker para atrapar los correos electrónicos de manera segura en desarrollo, incluyendo los enlaces visibles en la vista.
- La organización de las vistas web basadas en funciones con decoradores (`@login_required`), asegurando los endpoints correctamente.

---

> Ningún bloque de código fue copiado y pegado directamente sin comprenderlo.
> Todo fue revisado, adaptado a mi lógica y es defendible línea por línea.
