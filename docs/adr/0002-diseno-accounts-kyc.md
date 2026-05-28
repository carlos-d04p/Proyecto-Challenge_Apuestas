# ADR-0002: Diseño de Cuentas, KYC y Juego Responsable

## Contexto

El sistema de apuestas requiere un módulo robusto para gestionar la identidad
de los usuarios (KYC) y aplicar controles estrictos de juego responsable,
conforme a la normativa vigente. El desafío es cómo modelar el usuario,
verificar la edad (≥ 18 años) y DNI, gestionar los límites de depósito con reglas
de enfriamiento (cooldown), y manejar la concurrencia/duplicación de requests.

## Opciones Consideradas

### Modelo de Usuario

- **Opción A:** Usar `django.contrib.auth.models.User` y extenderlo con un perfil
  uno-a-uno (`OneToOneField`).
- **Opción B (Elegida):** Crear un `CustomUser` extendiendo `AbstractBaseUser`
  con UUID como clave primaria, y usar un `OneToOneField` a `PerfilKYC`
  para los atributos específicos de identidad y juego responsable.
  - *Razonamiento:* El proyecto requiere explícitamente que los ID sean UUID
    y que la tabla se llame `usuario`. `AbstractBaseUser` da control total
    sobre la autenticación y la estructura de la base de datos sin
    campos heredados innecesarios.

### Máquina de Estados (FSM) para KYC

Para gestionar el ciclo de vida de la cuenta se implementa una FSM en `PerfilKYC.status`:
- `PENDING` → `VERIFIED` (Transición permitida solo para Staff/Administradores)
- `PENDING` → `BLOCKED`
- `VERIFIED` → `BLOCKED`
- `VERIFIED` → `SELF_EXCLUDED` (El propio usuario, sin reversión manual)
- `SELF_EXCLUDED` → `VERIFIED` (Automático, solo si expiró el plazo)
- `BLOCKED` → (Irreversible)

### Controles de Juego Responsable

Se implementan los límites en `PerfilKYC`:
- **Disminución de límites:** Inmediata.
- **Aumento de límites:** Sujeto a un cooldown obligatorio de 24 horas (`limits_last_raised_at`) para proteger al jugador de decisiones impulsivas.
- **Autoexclusión:** Configurable a 7, 30, 90 días o de forma indefinida, bloqueando completamente las operaciones de apuestas y depósitos.

### Idempotencia

Para prevenir operaciones duplicadas (doble registro, doble depósito), se implementa un modelo `RegistroIdempotencia` y un `IdempotencyMixin`:
- Guarda el hash SHA-256 del cuerpo del request y la respuesta HTTP.
- Si se recibe la misma `Idempotency-Key` para el mismo usuario, se devuelve la respuesta cachead sin procesar la lógica de negocio nuevamente.

## Consecuencias

- **Seguridad:** El sistema es mucho más resiliente a comportamientos compulsivos y errores de red.
- **Trazabilidad:** Todas las validaciones de identidad quedan centralizadas en la tabla `perfil_kyc`.
- **Complejidad:** La separación del usuario y KYC requiere dos operaciones de guardado al crear una cuenta, manejadas atómicamente en el `RegistroSerializer`.

## Fecha y Autor
- **Fecha:** 27 de Mayo de 2026
- **Autor:** Walter Llatas
