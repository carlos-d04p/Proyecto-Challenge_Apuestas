# Declaración de uso de IA — Walter Llatas

## App asignada: `accounts` (Registro, KYC, WebSockets y Correos)

---

## ¿Qué consulté a la IA?

### 1. Concepto de WebSockets con Django Channels
- **Qué pedí:** Que me explicara teóricamente cómo funciona la arquitectura de comunicación asíncrona de WebSockets en Django y su interacción con Redis.
- **Para qué:** Para entender el flujo de datos antes de programar la notificación de KYC en tiempo real.
- **Lo que hice yo:** Toda la implementación del código (crear `consumers.py`, configurar el routing ASGI y escribir el Javascript del lado del cliente) la escribí yo mismo basándome en la documentación oficial.

### 2. Revisión de un error en los logs de Celery
- **Qué pedí:** Le pasé el texto de un "Traceback" (error) que me salía en la consola al intentar levantar el contenedor de Celery con Docker.
- **Para qué:** Para ubicar más rápido en qué archivo se estaba produciendo el fallo de importación al iniciar el worker.
- **Lo que hice yo:** Una vez que la IA me señaló que el problema venía de un import circular, yo mismo fui al código, arreglé las dependencias de los módulos y corregí la importación.

### 3. Explicación matemática del dígito verificador
- **Qué pedí:** Que me explicara la fórmula matemática (Módulo 11) que se usa para calcular el dígito verificador de un DNI peruano.
- **Para qué:** Para entender la lógica matemática antes de plasmarla en código Python.
- **Lo que hice yo:** Escribí toda la clase del validador de Django (`DNIValidator`) por mi cuenta, programando la lógica de validación, conectándola a los formularios y escribiendo sus respectivos tests.

---

## Lo que NO generé con IA
Todo el código fuente de mi módulo fue escrito enteramente por mí sin uso de generadores de código. En particular, destaco:
- Toda la estructura de modelos, vistas y lógica de negocio de `accounts` (`PerfilKYC`, permisos, validación de mayoría de edad).
- La maquetación de los templates HTML y la adaptación del diseño CSS del módulo de perfil.
- La configuración y uso del servidor de correos local Mailpit y su envío asíncrono.
- La resolución manual de todos los conflictos en Git al fusionar mi código con el de mis compañeros.

---

> Todo el código fuente es de mi autoría. La inteligencia artificial solo se usó de manera consultiva (como un motor de búsqueda avanzado) para comprender conceptos teóricos y agilizar la lectura de logs de errores.
