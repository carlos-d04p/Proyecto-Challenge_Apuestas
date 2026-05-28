"""
Vistas web (HTML) para el catálogo de eventos y mercados.
Separadas de las vistas de la API REST.
"""
from django.shortcuts import render, get_object_or_404
from .models import Event, Market


def event_list(request):
    """Página principal: listado de eventos con filtro por estado."""
    status_filter = request.GET.get("status", "")
    qs = Event.objects.prefetch_related("markets__selections").order_by("starts_at")

    if status_filter:
        qs = qs.filter(status=status_filter)

    all_events = Event.objects.all()
    counts = {
        "total":     all_events.count(),
        "live":      all_events.filter(status="LIVE").count(),
        "scheduled": all_events.filter(status="SCHEDULED").count(),
        "finished":  all_events.filter(status="FINISHED").count(),
    }

    return render(request, "markets/event_list.html", {
        "events": qs,
        "status_filter": status_filter,
        "counts": counts,
    })



def event_detail(request, pk):
    """Detalle de un evento: muestra todos sus mercados y selecciones."""
    event = get_object_or_404(
        Event.objects.prefetch_related("markets__selections"),
        pk=pk,
    )
    markets = event.markets.filter(is_active=True).prefetch_related("selections")

    return render(request, "markets/event_detail.html", {
        "event": event,
        "markets": markets,
    })
