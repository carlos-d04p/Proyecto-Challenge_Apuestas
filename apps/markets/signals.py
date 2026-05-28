"""
Signals para broadcasting WebSocket de cambios en Markets y Events.

RB-RT-03: Todo payload incluye timestamp ISO 8601.
RB-RT-04: Suspensión/finalización de evento emite broadcast inmediato.
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.markets.models import Event, Market, Selection
from apps.realtime.constants import WSAction


def _now_iso():
    return timezone.now().isoformat()


LOBBY_GROUP = "events_lobby"


def _broadcast(group_name, payload):
    """
    Envía el payload al grupo del evento y al grupo lobby (para la lista).
    No-op si Channels no está configurado (p. ej. tests sin channel layer).
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(group_name, payload)
    if group_name != LOBBY_GROUP:
        async_to_sync(channel_layer.group_send)(LOBBY_GROUP, payload)


# ── Market: suspensión / reapertura ──────────────────────────────────────────

@receiver(pre_save, sender=Market)
def track_market_active_change(sender, instance, **kwargs):
    """Guarda el `is_active` anterior para detectar transiciones reales."""
    if instance.pk:
        instance._previous_is_active = (
            Market.objects.filter(pk=instance.pk)
            .values_list("is_active", flat=True)
            .first()
        )
    else:
        instance._previous_is_active = None


@receiver(post_save, sender=Market)
def broadcast_market_update(sender, instance, created, **kwargs):
    """Emite MARKET_SUSPEND / MARKET_REOPEN solo cuando is_active cambió."""
    if created:
        return
    previous = getattr(instance, "_previous_is_active", None)
    if previous is None or previous == instance.is_active:
        return

    action = WSAction.MARKET_REOPEN if instance.is_active else WSAction.MARKET_SUSPEND
    message = "🟢 Mercado reabierto" if instance.is_active else "🔒 Mercado suspendido"

    _broadcast(
        f"event_{instance.event_id}",
        {
            "type": "market_message",
            "action": action.value,
            "market_id": str(instance.id),
            "message": message,
            "timestamp": _now_iso(),
        },
    )


# ── Selection: actualización de cuotas ───────────────────────────────────────

@receiver(pre_save, sender=Selection)
def track_selection_odds_change(sender, instance, **kwargs):
    """Captura odds anteriores para evitar broadcasts ruidosos."""
    if instance.pk:
        instance._previous_odds = (
            Selection.objects.filter(pk=instance.pk)
            .values_list("odds", flat=True)
            .first()
        )
    else:
        instance._previous_odds = None


@receiver(post_save, sender=Selection)
def broadcast_odds_update(sender, instance, created, **kwargs):
    """Emite ODDS_UPDATE solo si la cuota realmente cambió y todo está activo."""
    if created:
        return
    previous = getattr(instance, "_previous_odds", None)
    if previous is None or previous == instance.odds:
        return
    if not instance.is_active:
        return

    # Evitar el N+1 de leer `instance.market.event_id` / `instance.market.is_active`:
    # una sola query trae los dos campos necesarios.
    market_row = (
        Market.objects.filter(pk=instance.market_id)
        .values("event_id", "is_active")
        .first()
    )
    if not market_row or not market_row["is_active"]:
        return

    _broadcast(
        f"event_{market_row['event_id']}",
        {
            "type": "market_message",
            "action": WSAction.ODDS_UPDATE.value,
            "market_id": str(instance.market_id),
            "selection_id": str(instance.id),
            "odds": f"{instance.odds:.4f}",
            "previous_odds": f"{previous:.4f}",
            "timestamp": _now_iso(),
        },
    )


# ── Event: cambio de estado ──────────────────────────────────────────────────

_EVENT_STATUS_ACTIONS = {
    Event.Status.SUSPENDED: WSAction.EVENT_SUSPENDED,
    Event.Status.FINISHED: WSAction.EVENT_FINISHED,
    Event.Status.CANCELLED: WSAction.EVENT_CANCELLED,
    Event.Status.LIVE: WSAction.EVENT_LIVE,
}

_EVENT_STATUS_MESSAGES = {
    Event.Status.SUSPENDED: "🔒 Evento suspendido por el administrador",
    Event.Status.FINISHED: "🏁 Evento finalizado",
    Event.Status.CANCELLED: "❌ Evento cancelado",
    Event.Status.LIVE: "🔴 Evento en vivo",
}


@receiver(pre_save, sender=Event)
def track_event_status_change(sender, instance, **kwargs):
    """Captura el estado anterior para detectar cambios reales."""
    if instance.pk:
        instance._previous_status = (
            Event.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )
    else:
        instance._previous_status = None


@receiver(post_save, sender=Event)
def broadcast_event_status_change(sender, instance, created, **kwargs):
    """
    RB-RT-04: emite broadcast inmediato cuando el estado del evento cambia.
    Si el evento pasa a SUSPENDED/FINISHED/CANCELLED también desactiva sus mercados.
    """
    if created:
        _broadcast(
            f"event_{instance.id}",
            {
                "type": "event_message",
                "action": WSAction.EVENT_CREATED.value,
                "event_id": str(instance.id),
                "message": "Nuevos eventos disponibles",
                "timestamp": _now_iso(),
            },
        )
        return

    previous_status = getattr(instance, "_previous_status", None)
    if previous_status == instance.status:
        return

    action = _EVENT_STATUS_ACTIONS.get(instance.status)
    if action is None:
        return

    _broadcast(
        f"event_{instance.id}",
        {
            "type": "event_message",
            "action": action.value,
            "event_id": str(instance.id),
            "message": _EVENT_STATUS_MESSAGES.get(instance.status, ""),
            "timestamp": _now_iso(),
        },
    )

    if instance.status in (
        Event.Status.SUSPENDED,
        Event.Status.FINISHED,
        Event.Status.CANCELLED,
    ):
        # `.update()` evita disparar el signal `broadcast_market_update` por cada
        # market: queremos un solo broadcast de evento, no N de mercados. Si se
        # quisiera notificar mercado por mercado, iterar con .save() en su lugar.
        instance.markets.filter(is_active=True).update(is_active=False)
