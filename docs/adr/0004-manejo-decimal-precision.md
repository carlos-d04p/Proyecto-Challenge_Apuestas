# ADR 0004: Manejo de Tipos Decimal y Precisión para Datos Financieros

## Estado
Aceptado

## Contexto
Las apuestas y los cálculos de pagos, comisiones o cuotas (odds) involucran matemáticas financieras. Utilizar tipos de datos de punto flotante (`float`, `double`) puede introducir errores de redondeo que, acumulados a lo largo de miles de transacciones, provocan pérdidas o descuadres financieros.

## Decisión
Utilizar el tipo `Decimal` de la biblioteca estándar (o tipos equivalentes como `numeric`/`decimal` en la base de datos PostgreSQL) para todos los campos que representen dinero, cuotas, o balances, en las aplicaciones `wallet`, `betting` y `payments`.

Se establece el estándar de almacenamiento:
- **Dinero:** 4 decimales de precisión interna para evitar errores de arrastre en divisiones, aunque a nivel de presentación en la UI se redondee a 2 decimales (ej. `max_digits=12, decimal_places=4`).
- **Cuotas (Odds):** 3 decimales de precisión (ej. `max_digits=8, decimal_places=3`).
- **Contexto Decimal:** El redondeo por defecto será `ROUND_HALF_EVEN` (Banker's rounding).

## Consecuencias
### Positivas:
- **Precisión matemática absoluta:** Se eliminan los errores de representación binaria de fracciones de coma flotante.
- **Conformidad contable:** Operaciones financieras fiables.

### Negativas:
- **Mayor espacio de almacenamiento:** Los tipos numéricos exactos ocupan más espacio en base de datos.
- **Rendimiento computacional:** Las operaciones con `Decimal` son ligeramente más lentas que con floats nativos (aunque marginal e imperceptible para los casos de uso del proyecto).

## Fecha y Autor
* **Fecha:** 27 de Mayo de 2026
* **Autor:** Arnold Quiroz
