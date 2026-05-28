# Ensayo de Arquitectura: Integridad, Juego Responsable y Ley 31557

En el presente documento se exponen los pilares arquitectónicos que respaldan la Casa de Apuestas y cómo estas decisiones abordan la integridad financiera, la protección al jugador, y el cumplimiento normativo exigido por la Ley N° 31557 de Perú.

## 1. Garantizando la Integridad Financiera

La integridad de los saldos de los usuarios es la columna vertebral de cualquier sistema transaccional de juegos de azar. Para evitar fallos catastróficos, inconsistencias o la posibilidad de que se "cree dinero de la nada", hemos implementado un modelo contable de **Partida Doble (Double-Entry Ledger)**.

### Modelo de Partida Doble
A diferencia de un sistema tradicional donde el balance del usuario es simplemente un campo numérico que se suma o se resta, nuestro sistema **no almacena balances estáticos como fuente de verdad**. En cambio:
- Todas las operaciones financieras (depósitos, apuestas, pagos, retiros) se registran como transacciones inmutables.
- Cada transacción tiene al menos dos asientos (Ledger Entries): un crédito en una cuenta y un débito equivalente en otra.
- El balance de la billetera de un usuario (`USER_WALLET`) se calcula dinámicamente sumando todos los créditos y restando todos los débitos.
- Si una operación de apuesta (débito al usuario) no se balancea exactamente con un crédito en el pasivo de la casa de apuestas (`HOUSE_LIABILITY`), la transacción entera es rechazada por restricciones a nivel de base de datos.

### Concurrencia y Bloqueos (select_for_update)
Para lidiar con el problema de "double-spending" (cuando un usuario intenta hacer dos apuestas simultáneas con su último dólar disponible), hemos integrado **`select_for_update`** a nivel de base de datos. Cuando un endpoint procesa una apuesta, bloquea la fila del usuario en la base de datos de manera pesimista hasta que la transacción se completa. Esto garantiza que dos peticiones simultáneas se procesen secuencialmente, asegurando que el balance siempre se evalúe con precisión de milisegundos. Además, el uso de claves de idempotencia previene que caídas de red resulten en apuestas duplicadas accidentalmente.

## 2. Decisiones de Juego Responsable

Proteger a los usuarios vulnerables no es solo un requisito legal, sino un deber ético. Se han introducido varios controles a nivel arquitectónico y de negocio:
- **Límites de Depósito y Apuesta Diarios**: Se ha establecido lógica que monitorea el volumen transaccional de un usuario en una ventana de 24 horas. Si el usuario intenta sobrepasar un límite predefinido, el sistema rechaza automáticamente la operación, instando al usuario a un período de enfriamiento.
- **Monitoreo de Comportamiento Sospechoso (DEP_WD)**: A través de tareas asíncronas de Celery, el sistema detecta patrones como depósitos seguidos inmediatamente por retiros sin un volumen razonable de juego. Estos perfiles son congelados temporalmente (estado PENDIENTE) y marcados en el panel de cumplimiento para revisión humana.
- **Detección de IPs Compartidas**: La plataforma alerta cuando múltiples cuentas inician sesión desde una misma dirección IP en un lapso corto, limitando las oportunidades para sindicatos de apostadores o suplantación de identidad de menores de edad.

## 3. Autocrítica Normativa: Cumplimiento de la Ley 31557

La Ley N° 31557 (y sus modificatorias) regula la explotación de los juegos y apuestas deportivas a distancia en el Perú. Si bien nuestro sistema avanza en gran parte de las exigencias tecnológicas, debemos ser honestos en lo que actualmente se cubre y lo que aún representa una deuda técnica.

### Requisitos Cubiertos
- **Trazabilidad Absoluta**: La ley exige que la plataforma tecnológica pueda ser auditada por MINCETUR. Gracias al modelo de Partida Doble y el registro inmutable de transacciones, cada centavo apostado y pagado tiene un rastro criptográfico rastreable hasta su origen. El panel de Compliance expone estos datos en un formato fácilmente exportable.
- **Prevención de Lavado de Activos (SPLAFT)**: Las lógicas de alertas de depósitos rápidos sin juego (DEP_WD) y los bloqueos preventivos por actividad sospechosa cumplen con las exigencias de "Conoce a tu Cliente" (KYC) y alertas de operaciones inusuales.

### Requisitos No Cubiertos (Deuda Técnica / Autocrítica)
- **Integración Homologada (Homologación de Software)**: La ley estipula que el sistema debe estar conectado en tiempo real o mediante reportes automatizados encriptados directamente a los servidores del MINCETUR y SUNAT. Actualmente, si bien tenemos un botón de "reporte-mincetur" en el backoffice, esto es solo una simulación. Falta la integración real mediante los estándares (XSD/XML) oficiales del gobierno.
- **Laboratorios de Certificación**: El software aún no cuenta con un certificado de laboratorio autorizado internacional (como GLI, BMM Testlabs) exigido por el Artículo 15 de la ley. La certificación del RNG (Generador de Números Aleatorios, si aplicara) y del código fuente es un proceso legal y técnico complejo que excede el scope de este MVP.
- **Bloqueo a Registros de Ludópatas Oficiales**: No hemos integrado aún una conexión a la base de datos nacional del Registro de Personas Prohibidas de Acceder a Establecimientos de Juegos de Casino (Ludopatía) del MINCETUR. Es decir, actualmente un usuario baneado a nivel nacional podría intentar registrarse en el sistema.

### Conclusión
El diseño subyacente es sumamente resiliente y soporta transaccionalidad bancaria. Las fundaciones están puestas para cumplir a cabalidad con la Ley 31557, pero se requerirán puentes de integración externa con entidades del Estado y laboratorios privados antes de un lanzamiento a producción en suelo peruano.
