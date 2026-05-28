from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apps.markets.models import Market, Selection

@receiver(post_save, sender=Market)
def broadcast_market_update(sender, instance, **kwargs):
    """Escucha si un mercado es suspendido (is_active=False)"""
    if not instance.is_active:
        channel_layer = get_channel_layer()
        group_name = f"event_{instance.event_id}"
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "market_message", # Llama a la función del Consumer
                "action": "SUSPEND",
                "market_id": str(instance.id),
                "message": "🔒 Suspendido"
            }
        )

@receiver(post_save, sender=Selection)
def broadcast_odds_update(sender, instance, **kwargs):
    """Escucha si cambia la cuota de una selección específica"""
    channel_layer = get_channel_layer()
    group_name = f"event_{instance.market.event_id}"
    
    # Solo enviamos la actualización si el mercado y la selección están activos
    if instance.is_active and instance.market.is_active:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "market_message",
                "action": "ODDS_UPDATE",
                "market_id": str(instance.market_id),
                "selection_id": str(instance.id), # Enviamos qué selección exacta cambió
                "odds": f"{instance.odds:.2f}"
            }
        )