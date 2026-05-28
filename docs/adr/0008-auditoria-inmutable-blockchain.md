# ADR 0008: Auditoría Inmutable (Blockchain simulado)

## Contexto
Las regulaciones modernas para plataformas de apuestas exigen que el historial de transacciones, resultados deportivos, y el propio sistema sean auditables en caso de reclamos de usuarios o del Estado, sin posibilidad de ser alterados subrepticiamente por un administrador o hacker (Write-Once-Read-Many).

## Decisión
Hemos implementado una cadena de hashes criptográficos sobre el registro de auditoría (`AuditLog`), emulando el funcionamiento de un libro mayor de blockchain.
Cada nuevo evento crítico (login de usuario, retiro, resultado de evento) se empaqueta en JSON, se combina con el hash del evento inmediatamente anterior, y se calcula su hash SHA-256. 

## Consecuencias
- **Positivas**: Si la base de datos es comprometida y alguien intenta alterar el monto de una transacción antigua, el hash de los eventos subsiguientes se romperá, activando una alerta de intrusión (corrupción en la cadena).
- **Negativas**: Mayor costo de escritura (calcular el hash requiere consultas al evento previo). Complica drásticamente el proceso legítimo de borrado de datos (Data Pruning) o las purgas dictadas por la ley europea GDPR, ya que no se pueden borrar eventos sin invalidar la cadena completa.
