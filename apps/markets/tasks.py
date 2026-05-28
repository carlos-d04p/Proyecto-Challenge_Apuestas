"""
Tareas Celery del módulo Markets.
"""

import random
from datetime import timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.markets.models import Event, Market, Selection
from apps.realtime.constants import WSAction


@shared_task
def reopen_event_markets(event_id, market_ids, reason="GOAL"):
    """
    Reactiva los mercados suspendidos temporalmente y emite MARKET_REOPEN.
    Si el evento ya no está LIVE (finalizó/canceló), no reabre nada.
    """
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        return

    if event.status != Event.Status.LIVE:
        return

    with transaction.atomic():
        markets = list(Market.objects.select_for_update().filter(id__in=market_ids))
        for m in markets:
            m.is_active = True
            # `save()` activa el signal `broadcast_market_update` que envía
            # MARKET_REOPEN al canal del evento — no replicar aquí.
            m.save(update_fields=["is_active"])

        event.suspended_until = None
        event.save(update_fields=["suspended_until", "updated_at"])


@shared_task
def auto_transition_events():
    """
    Reloj del partido.
    - SCHEDULED con starts_at <= now  -> LIVE
    - LIVE con starts_at + duración < now  -> FINISHED
    Los signals (post_save Event) se encargan del broadcast por WebSocket.
    """
    now = timezone.now()
    auto_finish_minutes = int(
        getattr(settings, "EVENT_AUTO_FINISH_AFTER_MINUTES", 110)
    )
    finish_threshold = now - timedelta(minutes=auto_finish_minutes)

    transitions = {"to_live": 0, "to_finished": 0}

    with transaction.atomic():
        scheduled_due = (
            Event.objects.select_for_update(skip_locked=True)
            .filter(status=Event.Status.SCHEDULED, starts_at__lte=now)
        )
        for ev in scheduled_due:
            ev.status = Event.Status.LIVE
            ev.live_started_at = now
            ev.save(update_fields=["status", "live_started_at", "updated_at"])
            transitions["to_live"] += 1

    with transaction.atomic():
        live_done = (
            Event.objects.select_for_update(skip_locked=True)
            .filter(status=Event.Status.LIVE, starts_at__lte=finish_threshold)
        )
        for ev in live_done:
            ev.status = Event.Status.FINISHED
            ev.save(update_fields=["status", "updated_at"])
            transitions["to_finished"] += 1

    return transitions


# ── Simulador de partido (in-play) ────────────────────────────────────────
ODDS_MIN = Decimal("1.0100")
ODDS_MAX = Decimal("50.0000")
GOAL_SUSPEND_SECONDS = 5            # ventana de bloqueo tras tanto/gol/set
HOUSE_MARGIN = Decimal("1.05")      # overround del 5% sobre la probabilidad pura
ODDS_NOISE_PCT = 0.015              # ±1.5% de ruido por tick para simular liquidez


# Cada deporte tiene su mecánica:
#  - duration:    minutos totales del partido (informativo + tope del reloj).
#  - score_prob:  probabilidad por tick de que ALGUIEN anote.
#  - points:      tupla de valores posibles a sumar y sus pesos (1=básquet libre,
#                 2=básquet de cancha, 3=triple; en fútbol/tenis siempre 1).
#  - has_draw:    si el deporte admite empate como resultado final.
#  - score_label: cómo llamar al "tanto" en mensajes de UI (gol/canasta/punto…).
#  - emoji:       emoji para el toast.
SPORT_PROFILES = {
    "Fútbol": {
        "duration": 90,
        "score_prob": 0.003,           # ~3 goles esperados en 90 min con tick de 5s
        "points": ((1, 1.0),),
        "has_draw": True,
        "score_label": "GOL",
        "emoji": "⚽",
        # Promedio esperado de puntos por equipo por minuto (para el modelo Poisson de odds).
        "rate_per_min": 0.018,         # ~1.6 goles por equipo en 90 min
    },
    "Baloncesto": {
        "duration": 48,
        "score_prob": 0.175,           # ~220 pts totales en 48 min
        "points": ((2, 0.62), (3, 0.28), (1, 0.10)),
        "has_draw": False,
        "score_label": "CANASTA",
        "emoji": "🏀",
        "rate_per_min": 1.10,          # ~53 pts/equipo en 48 min (NBA real)
    },
    "Tenis": {
        "duration": 120,
        "score_prob": 0.004,           # ~5 sets en 120 min
        "points": ((1, 1.0),),
        "has_draw": False,
        "score_label": "SET",
        "emoji": "🎾",
        "rate_per_min": 0.025,         # ~3 sets por jugador típico
    },
    "Vóley": {
        "duration": 90,
        "score_prob": 0.004,           # ~4 sets en 90 min
        "points": ((1, 1.0),),
        "has_draw": False,
        "score_label": "SET",
        "emoji": "🏐",
        "rate_per_min": 0.033,
    },
    "Béisbol": {
        "duration": 180,
        "score_prob": 0.005,           # ~10 carreras en 180 min
        "points": ((1, 0.75), (2, 0.18), (3, 0.05), (4, 0.02)),
        "has_draw": False,
        "score_label": "CARRERA",
        "emoji": "⚾",
        "rate_per_min": 0.035,         # ~6 carreras/equipo en 180 min
    },
}

DEFAULT_PROFILE = SPORT_PROFILES["Fútbol"]


def _profile(event: Event) -> dict:
    return SPORT_PROFILES.get(event.sport, DEFAULT_PROFILE)


def _elapsed_minute(event: Event, now) -> int:
    """
    Minuto en curso del partido, acotado por la duración del deporte.
    Usa `live_started_at` si existe (refleja el inicio REAL del partido,
    que puede diferir de `starts_at` si se forzó LIVE antes/después de hora).
    """
    duration = _profile(event)["duration"]
    reference = event.live_started_at or event.starts_at
    if not reference or reference >= now:
        return 0
    minutes = int((now - reference).total_seconds() // 60)
    return min(max(minutes, 0), duration)


def _weighted_choice(items):
    """items=[(value, weight), ...] -> uno de los `value` según peso."""
    r = random.random() * sum(w for _, w in items)
    upto = 0.0
    for value, weight in items:
        upto += weight
        if r <= upto:
            return value
    return items[-1][0]


def _clamp_odds(odds: Decimal) -> Decimal:
    if odds < ODDS_MIN:
        return ODDS_MIN
    if odds > ODDS_MAX:
        return ODDS_MAX
    return odds.quantize(Decimal("0.0001"))


def _compute_1x2_odds(event: Event, minute: int):
    """
    Modelo Poisson aproximado.

    Cada equipo seguirá anotando a `rate_per_min` puntos/minuto durante el tiempo
    restante. El marcador final esperado de cada equipo es:
        expected_final = score_actual + rate * remaining_minutes
    La diferencia final D = H_final - A_final se aproxima como Normal con:
        E[D] = current_diff           (los esperados de aquí al final son iguales)
        Var[D] = expected_remaining_home + expected_remaining_away
    P(home gana) = P(D > 0) ~ logístico(diff / sd)

    Cuanto MENOS tiempo queda, menor `sd` → la ventaja actual pesa más.
    Cuanto MÁS marcador acumulado (básquet), mayor `sd` → la ventaja relativa
    cuenta, no la absoluta. Esto es exactamente lo que queremos.
    """
    import math

    profile = _profile(event)
    duration = profile["duration"]
    has_draw = profile["has_draw"]
    rate = profile["rate_per_min"]

    home_score, away_score = event.home_score, event.away_score
    diff = home_score - away_score
    remaining = max(duration - minute, 0.5)

    # Varianza Poisson de la diferencia residual + ya anotado (smoothing 1.0
    # para evitar dividir por 0 al inicio).
    expected_remaining_each = rate * remaining
    variance = 2 * expected_remaining_each + (home_score + away_score) * 0.05 + 1.0
    sd = math.sqrt(variance)

    # Pasa a probabilidad vía logística (parámetro k calibra agudeza).
    k = 1.6
    z = diff / sd
    p_home = 1.0 / (1.0 + math.exp(-k * z))
    p_away = 1.0 / (1.0 + math.exp(k * z))

    if has_draw:
        # Empate ≈ densidad de la diferencia residual en 0.
        # PDF Normal(diff, sd) en 0 = (1/sd√2π) · exp(-diff²/2sd²).
        # Esto da empate alto cuando: marcador parejo + poco tiempo + sd bajo.
        pdf0 = math.exp(-(diff ** 2) / (2 * variance)) / (sd * math.sqrt(2 * math.pi))
        p_draw = min(max(pdf0, 0.05), 0.65)
    else:
        p_draw = 0.005   # casi imposible (cuota ~ 50.00)

    # Normaliza y aplica overround de casa.
    raws = [max(p_home, 0.01), max(p_draw, 0.005), max(p_away, 0.01)]
    total = sum(raws)
    probs = [r / total for r in raws]

    odds = [Decimal(str(1.0 / p)) / HOUSE_MARGIN for p in probs]
    return tuple(_clamp_odds(o) for o in odds)


def _noisy(odds: Decimal) -> Decimal:
    """
    Aplica un pequeño jitter ±ODDS_NOISE_PCT sobre la odd determinista para
    simular el movimiento natural del mercado (liquidez) entre eventos clave.
    """
    factor = 1.0 + random.uniform(-ODDS_NOISE_PCT, ODDS_NOISE_PCT)
    return _clamp_odds(odds * Decimal(str(factor)))


def _apply_1x2_odds(event: Event):
    """Recalcula y guarda las odds 1X2 para el evento, si tiene ese mercado."""
    market = event.markets.filter(kind="1X2", is_active=True).first()
    if market is None:
        return 0
    selections = list(market.selections.filter(is_active=True).order_by("name"))
    if len(selections) < 3:
        return 0

    home_odds, draw_odds, away_odds = _compute_1x2_odds(
        event, _elapsed_minute(event, timezone.now()),
    )

    mutated = 0
    for sel in selections:
        name = sel.name.lower()
        if "local" in name:
            new = _noisy(home_odds)
        elif "empate" in name or "draw" in name or name.strip() == "x":
            new = _noisy(draw_odds)
        elif "visit" in name or "away" in name:
            new = _noisy(away_odds)
        else:
            continue
        if new != sel.odds:
            sel.odds = new
            sel.save(update_fields=["odds", "updated_at"])
            mutated += 1
    return mutated


def _broadcast_score(
    event: Event,
    action: WSAction,
    minute: int,
    scorer: str | None = None,
    points: int = 0,
):
    """Emite SCORE_UPDATE / GOAL al canal del evento y al lobby global."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    profile = _profile(event)
    payload = {
        "type": "event_message",
        "action": action.value,
        "event_id": str(event.id),
        "home_score": event.home_score,
        "away_score": event.away_score,
        "minute": minute,
        "sport": event.sport,
        "timestamp": timezone.now().isoformat(),
    }
    if scorer:
        label = profile["score_label"]
        emoji = profile["emoji"]
        extra = f" (+{points})" if points > 1 else ""
        payload["scorer"] = scorer
        payload["points"] = points
        payload["message"] = (
            f"{emoji} ¡{label} de {scorer}!{extra} "
            f"({event.home_score}-{event.away_score})"
        )
    async_to_sync(channel_layer.group_send)(f"event_{event.id}", payload)
    async_to_sync(channel_layer.group_send)("events_lobby", payload)


@shared_task
def simulate_match_progress():
    """
    Simulador realista de partidos LIVE.
    - Calcula el minuto desde starts_at.
    - Con probabilidad GOAL_PROB_PER_TICK genera un gol; si ocurre,
      dispara suspensión crítica vía `suspend_event_markets`.
    - Recalcula y guarda las odds 1X2 según marcador y minuto.
    - Emite SCORE_UPDATE (o GOAL) por WebSocket.
    Solo aplica a eventos no suspendidos.
    """
    from apps.markets.services import suspend_event_markets

    now = timezone.now()
    events = (
        Event.objects.filter(status=Event.Status.LIVE)
        .exclude(suspended_until__gt=now)
    )
    summary = {"events": 0, "goals": 0, "odds_changes": 0}

    for event in events:
        summary["events"] += 1
        profile = _profile(event)

        # Fallback: si un evento se forzó a LIVE sin pasar por la auto-transición
        # (admin, shell, seed), inicializa su reloj ahora mismo y resetea el
        # marcador — el partido empieza en 0-0 cuando arranca el cronómetro.
        if event.live_started_at is None:
            event.live_started_at = now
            event.home_score = 0
            event.away_score = 0
            event.save(update_fields=[
                "live_started_at", "home_score", "away_score", "updated_at",
            ])

        minute = _elapsed_minute(event, now)
        duration = profile["duration"]

        # Sortea anotación según probabilidad del deporte
        scorer = None
        points = 0
        if random.random() < profile["score_prob"] and minute < duration:
            points = _weighted_choice(profile["points"])
            if random.random() < 0.5:
                event.home_score += points
                scorer = "Local"
            else:
                event.away_score += points
                scorer = "Visitante"
            event.save(update_fields=["home_score", "away_score", "updated_at"])
            summary["goals"] += 1

        # Recalcula odds según estado actual
        summary["odds_changes"] += _apply_1x2_odds(event)

        # Broadcast del marcador / anotación
        if scorer:
            _broadcast_score(event, WSAction.GOAL, minute, scorer, points)
            # En deportes de muchos puntos (básquet, béisbol) no tiene sentido
            # suspender cada canasta — solo congelamos mercados cuando el tanto
            # cambia el equilibrio drásticamente (fútbol, tenis, vóley).
            if profile["score_label"] in ("GOL", "SET"):
                try:
                    suspend_event_markets(event, seconds=GOAL_SUSPEND_SECONDS, reason="GOAL")
                except ValueError:
                    pass
        else:
            _broadcast_score(event, WSAction.SCORE_UPDATE, minute)

    return summary
