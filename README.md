# OPS Console & Casa de Apuestas

Este proyecto es una plataforma completa de apuestas deportivas que cuenta con una **Billetera de Partida Doble (Double-Entry Ledger)** para integridad financiera, un **Motor de Apuestas en Tiempo Real** vía WebSockets, y un módulo de **Backoffice (OPS Console)** para la gestión y liquidación automática de eventos.

## Tecnologías Principales
- **Backend**: Django 5.0, Django REST Framework, Channels (WebSockets)
- **Base de Datos**: PostgreSQL
- **Caché / Brokers**: Redis
- **Background Tasks**: Celery
- **Testing**: Pytest, Coverage, Hypothesis
- **Contenedores**: Docker & Docker Compose

## Inicialización del Proyecto

Para levantar todo el entorno, utiliza `docker-compose`:

```bash
docker-compose up -d --build
```

Esto levantará los siguientes servicios:
- Base de datos (PostgreSQL)
- Redis (Broker para Channels y Celery)
- Backend (Django / Daphne / Celery worker)

### Poblado de la Base de Datos (Seed)

Se ha creado un comando customizado para poblar usuarios con fondos de prueba y eventos deportivos:

```bash
docker-compose exec web python manage.py seed
```

## Entregables y Documentación

Toda la documentación técnica exigida se encuentra en la carpeta `docs/`.

### 1. Diagramas
En la carpeta `docs/sketches/` se encuentran los bocetos y diagramas (renderizados con Mermaid):
- [Diagrama ER de Billetera](docs/sketches/ER_wallet.md)
- [Máquina de Estados de Apuestas](docs/sketches/Bet_StateMachine.md)
- [Secuencia: Apuesta a Liquidación](docs/sketches/Secuencia_Apuesta_Liquidacion.md)
- [Secuencia: Cash-Out](docs/sketches/Secuencia_CashOut.md)

### 2. Decisiones de Arquitectura (ADRs)
Contamos con 10 ADRs detallando las decisiones técnicas más críticas en la carpeta `docs/adr/`. Entre ellos se incluyen el modelo de partida doble, concurrencia, idempotencia, y políticas de juego responsable.

### 3. API y Cobertura
- [Documentación OpenAPI (Swagger)](openapi.yaml)
- [Reporte de Cobertura (Coverage)](coverage_report.txt)

### 4. Ensayos y Lecciones
- [Ensayo sobre Integridad y Ley 31557](docs/ensayo_arquitectura.md)
- [Lecciones Aprendidas e Intentos Fallidos](docs/lecciones.md)
- [Bitácoras Individuales](docs/)
- [Declaraciones de Uso de IA](docs/)

## Metodología y Commits
El historial del proyecto ha sido gestionado con **Conventional Commits**. Para el desarrollo de los módulos core (`wallet`, `betting`), se utilizó TDD (Test-Driven Development), con commits de pruebas (test) precediendo a la implementación funcional (feat).
