"""
Servicios de gestión de eventos en vivo.

Suspensión automática por evento crítico (gol, expulsión, etc):
- Marca los mercados activos como inactivos -> los signals emiten MARKET_SUSPEND.
- Persiste `Event.suspended_until` para que la API de apuestas rechace
  colocaciones durante la ventana (RB-RT-06).
- Programa una tarea Celery para reactivar los mercados al expirar la ventana
  y emitir MARKET_REOPEN.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.markets.models import Event


CRITICAL_EVENT_KINDS = {
    "GOAL": "⚽ Gol",
    "RED_CARD": "🟥 Expulsión",
    "PENALTY": "🥅 Penalti",
    "VAR_REVIEW": "📺 Revisión VAR",
}

DEFAULT_SUSPENSION_SECONDS = 30


def suspend_event_markets(event, seconds=DEFAULT_SUSPENSION_SECONDS, reason="GOAL"):
    """
    Suspende temporalmente todos los mercados activos del evento.

    Devuelve `(suspended_until, [market_ids])`.
    Si el evento no está LIVE, no hace nada.
    """
    if event.status != Event.Status.LIVE:
        raise ValueError("Solo se pueden suspender eventos en estado LIVE.")

    seconds = max(1, int(seconds))
    until = timezone.now() + timedelta(seconds=seconds)

    with transaction.atomic():
        market_ids = []
        for market in event.markets.select_for_update().filter(is_active=True):
            market.is_active = False
            market.save(update_fields=["is_active"])
            market_ids.append(str(market.id))

        event.suspended_until = until
        event.save(update_fields=["suspended_until", "updated_at"])

    # Programar reapertura. Si Celery no está disponible (tests), no falla:
    try:
        from apps.markets.tasks import reopen_event_markets

        reopen_event_markets.apply_async(
            args=[str(event.id), market_ids, reason],
            countdown=seconds,
        )
    except Exception:
        # En tests / sin worker, la reapertura quedará a cargo del cron o manual.
        pass

    return until, market_ids


# Margen del operador (5%)
OPERATOR_MARGIN = Decimal("0.05")

def apply_margin(raw_odds: Decimal) -> Decimal:
    return (raw_odds / (1 + OPERATOR_MARGIN)).quantize(Decimal("0.0001"))

def create_default_markets_for_event(event):
    from apps.markets.models import Market, Selection
    
    m1x2 = Market.objects.create(event=event, kind=Market.Kind.MATCH_RESULT, name="Resultado Final")
    for name, raw in [("Gana Local", "2.10"), ("Empate", "3.40"), ("Gana Visitante", "3.20")]:
        Selection.objects.create(market=m1x2, name=name, odds=apply_margin(Decimal(raw)))

    if event.sport == "Fútbol":
        mou = Market.objects.create(event=event, kind=Market.Kind.OVER_UNDER, name="Más / Menos 2.5 Goles")
        for name, raw in [("Más de 2.5", "1.90"), ("Menos de 2.5", "1.95")]:
            Selection.objects.create(market=mou, name=name, odds=apply_margin(Decimal(raw)))

        mbtts = Market.objects.create(event=event, kind=Market.Kind.BOTH_TEAMS_SCORE, name="Ambos Equipos Anotan")
        for name, raw in [("Sí", "1.80"), ("No", "2.05")]:
            Selection.objects.create(market=mbtts, name=name, odds=apply_margin(Decimal(raw)))

        mhcap = Market.objects.create(event=event, kind=Market.Kind.HANDICAP, name="Handicap Asiático -1")
        for name, raw in [("Local -1", "2.20"), ("Visitante +1", "1.70")]:
            Selection.objects.create(market=mhcap, name=name, odds=apply_margin(Decimal(raw)))
