# ADR 0004: Manejo de Decimal y Precisión

## Contexto
En un sistema financiero y de apuestas, el cálculo de las cuotas (odds) y los pagos (payouts) involucra multiplicaciones fraccionarias. El uso de tipos numéricos de punto flotante (`float`) introduce errores de redondeo inherentes a la representación binaria (ej. 0.1 + 0.2 = 0.30000000000000004), lo cual es inaceptable para el dinero de los usuarios y las ganancias de la casa de apuestas.

## Decisión
Se ha decidido estandarizar el uso del tipo de dato `Decimal` (proporcionado por la librería estándar `decimal` de Python) para **todos** los cálculos financieros, montos de transacciones y cuotas en la aplicación. La precisión de almacenamiento en PostgreSQL se fija en `Decimal(18, 4)`.

## Consecuencias
- **Positivas**: Evita por completo la pérdida de centavos debido a errores de redondeo de punto flotante. Cumple con los estándares contables y de auditoría.
- **Negativas**: El rendimiento de las operaciones aritméticas con `Decimal` es ligeramente inferior al de `float` (aunque despreciable en este contexto). Requiere conversiones cuidadosas en las fronteras de la aplicación (ej. validadores DRF y serializadores JSON).
