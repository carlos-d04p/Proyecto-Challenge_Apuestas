"""
Constantes de acciones WebSocket.

Centralizamos los strings de `action` que viajan en los payloads para evitar
typos y mantener una sola fuente de verdad entre signals, tasks y consumers.
"""

from django.db import models


class WSAction(models.TextChoices):
    # Mercado
    ODDS_UPDATE = "ODDS_UPDATE", "Actualización de cuota"
    MARKET_SUSPEND = "MARKET_SUSPEND", "Mercado suspendido"
    MARKET_REOPEN = "MARKET_REOPEN", "Mercado reabierto"

    # Evento
    EVENT_LIVE = "EVENT_LIVE", "Evento en vivo"
    EVENT_SUSPENDED = "EVENT_SUSPENDED", "Evento suspendido"
    EVENT_FINISHED = "EVENT_FINISHED", "Evento finalizado"
    EVENT_CANCELLED = "EVENT_CANCELLED", "Evento cancelado"

    # Marcador in-play
    SCORE_UPDATE = "SCORE_UPDATE", "Actualización de marcador"
    GOAL = "GOAL", "Gol"
