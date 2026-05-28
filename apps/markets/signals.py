"""
Signals para broadcasting WebSocket de cambios en Markets y Events.

RB-RT-03: Todo payload incluye timestamp ISO 8601.
RB-RT-04: Suspensión/finalización de evento emite broadcast inmediato.
"""
from datetime import datetime, timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.markets.models import Event, Market, Selection


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ── Market: suspensión de mercado individual ─────────────────────────────────

@receiver(post_save, sender=Market)
def broadcast_market_update(sender, instance, **kwargs):
    """Emite MARKET_SUSPEND cuando un mercado se desactiva."""
    if not instance.is_active:
        channel_layer = get_channel_layer()
        group_name = f"event_{instance.event_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "market_message",
                "action": "MARKET_SUSPEND",
                "market_id": str(instance.id),
                "message": "🔒 Mercado Suspendido",
                "timestamp": _now_iso(),
            }
        )


# ── Selection: actualización de cuotas ───────────────────────────────────────

@receiver(post_save, sender=Selection)
def broadcast_odds_update(sender, instance, **kwargs):
    """Emite ODDS_UPDATE cuando cambia la cuota de una selección activa."""
    channel_layer = get_channel_layer()
    group_name = f"event_{instance.market.event_id}"

    if instance.is_active and instance.market.is_active:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "market_message",
                "action": "ODDS_UPDATE",
                "market_id": str(instance.market_id),
                "selection_id": str(instance.id),
                "odds": f"{instance.odds:.4f}",
                "timestamp": _now_iso(),
            }
        )


# ── Event: cambio de estado (suspensión, finalización, cancelación) ──────────

# Usamos pre_save para detectar si el estado CAMBIÓ
_EVENT_STATUS_ACTIONS = {
    Event.Status.SUSPENDED: "EVENT_SUSPENDED",
    Event.Status.FINISHED: "EVENT_FINISHED",
    Event.Status.CANCELLED: "EVENT_CANCELLED",
    Event.Status.LIVE: "EVENT_LIVE",
}

_EVENT_STATUS_MESSAGES = {
    Event.Status.SUSPENDED: "🔒 Evento suspendido por el administrador",
    Event.Status.FINISHED: "🏁 Evento finalizado",
    Event.Status.CANCELLED: "❌ Evento cancelado",
    Event.Status.LIVE: "🔴 Evento en vivo",
}


@receiver(pre_save, sender=Event)
def track_event_status_change(sender, instance, **kwargs):
    """Guarda el estado anterior para comparar en post_save."""
    if instance.pk:
        try:
            instance._previous_status = Event.objects.get(pk=instance.pk).status
        except Event.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Event)
def broadcast_event_status_change(sender, instance, created, **kwargs):
    """
    RB-RT-04: Emite broadcast inmediato cuando el estado del evento cambia.
    Si el evento se suspende/cancela/finaliza, también desactiva todos sus mercados.
    """
    if created:
        return

    previous_status = getattr(instance, '_previous_status', None)
    if previous_status == instance.status:
        return  # No cambió el estado

    action = _EVENT_STATUS_ACTIONS.get(instance.status)
    if not action:
        return

    channel_layer = get_channel_layer()
    group_name = f"event_{instance.id}"

    # Broadcast del cambio de estado del evento
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "event_message",
            "action": action,
            "event_id": str(instance.id),
            "message": _EVENT_STATUS_MESSAGES.get(instance.status, ""),
            "timestamp": _now_iso(),
        }
    )

    # Si el evento se suspendió/finalizó/canceló, desactivar todos los mercados
    if instance.status in (Event.Status.SUSPENDED, Event.Status.FINISHED, Event.Status.CANCELLED):
        instance.markets.filter(is_active=True).update(is_active=False)