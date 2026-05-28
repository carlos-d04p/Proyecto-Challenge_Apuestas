# Bitácora — Carlos Cancino

## Semana 1 (26/05/2026)

Esta semana arranqué con el proyecto enfocado en la parte core del negocio: la app `betting`. Lo primero fue definir un manifiesto claro de reglas de negocio para asegurar que el simulador funcione como una casa de apuestas real, contemplando la gestión de riesgo (liability), reglas anti-arbitraje y los límites de las combinadas para no "quebrar" la banca virtual de FairBet Lab.

Me tocó construir todo el motor transaccional de las apuestas, la máquina de estados y la integración crítica con la billetera. Era un módulo de alto riesgo lógico, así que me enfoqué en que los cálculos matemáticos y las transacciones de base de datos fueran a prueba de fallos.

Lo que hice:
- Creé la capa de servicios (`services.py`) para procesar la creación de tickets de apuestas simples y combinadas (ACCA), limitando estas últimas a un máximo de 5 eventos según las reglas de negocio.
- Implementé una Máquina de Estados Finita (FSM) estricta. Las apuestas nacen en `PLACED` y transicionan a estados terminales (`WON`, `LOST`, `VOID` o `CASHED_OUT`). Aseguré por código que un estado terminal sea inmutable.
- Logré la integración financiera con la app `wallet` usando partida doble. Al apostar, el dinero se mueve de `USER_WALLET` a `PENDING_BETS` (Fichas en apuestas pendientes). Validé el control de saldo insuficiente interceptando los errores.
- Escribí la lógica matemática para el cierre anticipado (Cash-out), aplicando el factor de retención (margen de la casa) y usando el tipo de dato `Decimal` (4 dígitos en backend, 2 en frontend) para evitar fugas de dinero por redondeos.
- Construí y ajusté los templates (HTML/CSS) del apartado de apuestas para que el usuario vea cómo su saldo se actualiza en tiempo real al intentar jugar.

Lo que no salió bien:
- Tuve una batalla campal con Git y Docker al intentar sincronizar mi rama con la de mis compañeros (`Main-de-prueba` y `hector_montenegro`). Me quedé bloqueado con un `MERGE_HEAD`, archivos temporales de Vim (`.swp`) y carpetas "basura" que se colaban en mi entorno.
- Al hacer limpiezas profundas con `git reset --hard` y `git clean -fd`, el contenedor de mi base de datos colapsó arrojando errores de autenticación de contraseña (`psycopg2.OperationalError`). Resultó ser un problema con el archivo `.env`, pero me obligó a destruir y reconstruir los contenedores varias veces.

Coordiné la integración de mis cambios, subiendo mis commits formales (con Conventional Commits) a mi rama `Carlos_Cancino` y combinando con éxito el flujo de apuestas y liquidación con el saldo de la billetera.

Para la próxima semana tocaría afinar detalles visuales de los tickets en el frontend, o hacer pruebas de estrés para asegurar que las transacciones atómicas (`transaction.atomic`) no generen cuellos de botella si el evaluador lanza muchas apuestas a la vez.