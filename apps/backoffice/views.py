"""
Backoffice views para control de eventos en vivo.
Solo accesible por usuarios staff (is_staff=True).
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.markets.models import Event, Market, Selection


@staff_member_required
@require_http_methods(["GET", "POST"])
def event_control_view(request, event_id):
    """
    Panel de control para que el admin gestione un evento en vivo.
    Permite: cambiar estado, suspender/reactivar mercados, modificar cuotas.
    Los signals de markets se encargan del broadcast WebSocket automáticamente.
    """
    event = get_object_or_404(
        Event.objects.prefetch_related("markets__selections"),
        pk=event_id,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Cambio de estado del evento ──────────────────────────────────
        if action == "change_event_status":
            new_status = request.POST.get("new_status")
            valid_statuses = [s.value for s in Event.Status]

            if new_status not in valid_statuses:
                messages.error(request, f"Estado '{new_status}' no es válido.")
            elif new_status == event.status:
                messages.info(request, f"El evento ya está en estado '{new_status}'.")
            else:
                old_status = event.get_status_display()
                event.status = new_status
                event.save(update_fields=["status", "updated_at"])
                messages.success(
                    request,
                    f"Estado cambiado de '{old_status}' a '{event.get_status_display()}'."
                    " Los WebSockets notificarán a los clientes conectados."
                )

        # ── Toggle de mercado (activar/suspender) ────────────────────────
        elif action == "toggle_market":
            market_id = request.POST.get("market_id")
            market = get_object_or_404(Market, pk=market_id, event=event)
            market.is_active = not market.is_active
            market.save(update_fields=["is_active"])
            state = "activado" if market.is_active else "suspendido"
            messages.success(request, f"Mercado '{market.name}' {state}.")

        # ── Actualización de cuota de una selección ──────────────────────
        elif action == "update_odds":
            selection_id = request.POST.get("selection_id")
            new_odds_str = request.POST.get("new_odds", "")
            selection = get_object_or_404(
                Selection, pk=selection_id, market__event=event
            )
            try:
                new_odds = Decimal(new_odds_str.strip().replace(",", "."))
                if new_odds < Decimal("1.0100"):
                    raise ValueError("La cuota mínima es 1.01")
                selection.odds = new_odds.quantize(Decimal("0.0001"))
                selection.save(update_fields=["odds", "updated_at"])
                messages.success(
                    request,
                    f"Cuota de '{selection.name}' actualizada a {selection.odds}"
                )
            except (InvalidOperation, ValueError) as e:
                messages.error(request, f"Error al actualizar cuota: {e}")

        else:
            messages.error(request, "Acción no reconocida.")

        return redirect("backoffice:event_control", event_id=event.pk)

    # ── GET: Renderizar panel ────────────────────────────────────────────
    markets_data = []
    for market in event.markets.all():
        markets_data.append({
            "market": market,
            "selections": list(market.selections.all()),
        })

    # Transiciones de estado válidas
    status_transitions = _get_valid_transitions(event.status)

    context = {
        "event": event,
        "markets_data": markets_data,
        "status_transitions": status_transitions,
        "all_statuses": Event.Status.choices,
    }
    return render(request, "backoffice/event_control.html", context)


def _get_valid_transitions(current_status):
    """Define las transiciones de estado permitidas para un evento."""
    transitions = {
        Event.Status.SCHEDULED: [
            (Event.Status.LIVE, "🔴 Iniciar En Vivo", "success"),
            (Event.Status.CANCELLED, "❌ Cancelar", "danger"),
        ],
        Event.Status.LIVE: [
            (Event.Status.SUSPENDED, "⏸️ Suspender", "warning"),
            (Event.Status.FINISHED, "🏁 Finalizar", "info"),
            (Event.Status.CANCELLED, "❌ Cancelar", "danger"),
        ],
        Event.Status.SUSPENDED: [
            (Event.Status.LIVE, "🔴 Reanudar En Vivo", "success"),
            (Event.Status.FINISHED, "🏁 Finalizar", "info"),
            (Event.Status.CANCELLED, "❌ Cancelar", "danger"),
        ],
        Event.Status.FINISHED: [],
        Event.Status.CANCELLED: [],
    }
    return transitions.get(current_status, [])
