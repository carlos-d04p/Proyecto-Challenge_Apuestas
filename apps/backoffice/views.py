"""
Backoffice views para control de eventos en vivo.
Solo accesible por usuarios staff (is_staff=True).
"""
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods


def staff_only(view_func):
    """
    Bloquea el acceso a usuarios no staff.
    - Anónimo → redirige al login con `?next=`.
    - Autenticado pero no staff → 403 directo (sin filtrar que la URL existe
      como hace `staff_member_required`, que manda al login de admin).
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect(f"/accounts/login/?next={request.path}")
        if not user.is_staff:
            raise PermissionDenied("Solo el personal autorizado puede acceder al panel de control.")
        return view_func(request, *args, **kwargs)
    return _wrapped

from apps.markets.models import Event, Market, Selection
from apps.markets.services import (
    CRITICAL_EVENT_KINDS,
    DEFAULT_SUSPENSION_SECONDS,
    suspend_event_markets,
)


@staff_only
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
                update_fields = ["status", "updated_at"]
                # Al pasar manualmente a LIVE, fijar el reloj del partido.
                if new_status == Event.Status.LIVE and event.live_started_at is None:
                    from django.utils import timezone as _tz
                    event.live_started_at = _tz.now()
                    update_fields.append("live_started_at")
                event.save(update_fields=update_fields)
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

        # ── Evento crítico: gol/expulsión → suspensión automática N seg ──
        elif action == "critical_event":
            reason = request.POST.get("reason", "GOAL")
            try:
                seconds = int(request.POST.get("seconds") or DEFAULT_SUSPENSION_SECONDS)
            except ValueError:
                seconds = DEFAULT_SUSPENSION_SECONDS
            seconds = max(5, min(seconds, 300))  # rango sano: 5..300s
            try:
                until, market_ids = suspend_event_markets(
                    event=event, seconds=seconds, reason=reason,
                )
            except ValueError as e:
                messages.error(request, str(e))
            else:
                label = CRITICAL_EVENT_KINDS.get(reason, reason)
                messages.success(
                    request,
                    f"{label}: {len(market_ids)} mercados suspendidos por {seconds}s. "
                    "Reapertura automática vía Celery."
                )

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
        "critical_event_kinds": CRITICAL_EVENT_KINDS,
        "default_suspension_seconds": DEFAULT_SUSPENSION_SECONDS,
    }
    return render(request, "backoffice/event_control.html", context)


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard de monitoreo: el operador ve la actividad de los clientes sin
# que estos perciban nada. Todas las URLs están bajo /backoffice/ y gateadas
# con @staff_only — el cliente nunca recibe links a esta sección.
# ═══════════════════════════════════════════════════════════════════════════

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.utils import timezone

from apps.betting.models import Bet
from apps.wallet.models import Transaction, TransactionKind, LedgerEntry, LedgerDirection
from apps.wallet.selectors import get_wallet_balance


def _serialize_bet(bet):
    return {
        "id": str(bet.id),
        "user": bet.user.username,
        "user_id": bet.user_id,
        "stake": f"{bet.stake:.4f}",
        "odds": f"{bet.total_odds:.4f}",
        "status": bet.status,
        "type": bet.bet_type,
        "created_at": bet.created_at.isoformat(),
    }


def _serialize_tx(tx, user_id=None):
    entry = None
    for e in tx.entries.all():
        if user_id is None and e.direction == LedgerDirection.CREDIT:
            entry = e
            break
        if user_id is not None and e.account_owner_id == user_id:
            entry = e
            break
    amount = entry.amount if entry else 0
    sign = -1 if entry and entry.direction == LedgerDirection.DEBIT else 1
    return {
        "id": str(tx.id),
        "kind": tx.kind,
        "user": entry.account_owner.username if entry and entry.account_owner else "—",
        "amount": f"{amount * sign:.4f}",
        "created_at": tx.created_at.isoformat(),
    }


@staff_only
def dashboard_view(request):
    """Vista principal: KPIs + actividad reciente."""
    User = get_user_model()
    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    kpis = {
        "events_live": Event.objects.filter(status=Event.Status.LIVE).count(),
        "bets_24h": Bet.objects.filter(created_at__gte=last_24h).count(),
        "deposits_24h": Transaction.objects.filter(
            kind=TransactionKind.DEPOSIT, created_at__gte=last_24h
        ).count(),
        "withdrawals_24h": Transaction.objects.filter(
            kind=TransactionKind.WITHDRAWAL, created_at__gte=last_24h
        ).count(),
        "users_total": User.objects.count(),
        "users_active_24h": User.objects.filter(
            Q(wallet_transactions__created_at__gte=last_24h)
            | Q(bets__created_at__gte=last_24h)
        ).distinct().count(),
    }

    # Top apostadores por stake en últimas 24h
    top_bettors = (
        Bet.objects.filter(created_at__gte=last_24h)
        .values("user_id", "user__username")
        .annotate(total_stake=Sum("stake"), n_bets=Count("id"))
        .order_by("-total_stake")[:10]
    )

    live_events = (
        Event.objects.filter(status=Event.Status.LIVE)
        .order_by("live_started_at")[:10]
    )

    context = {
        "kpis": kpis,
        "top_bettors": list(top_bettors),
        "live_events": live_events,
    }
    return render(request, "backoffice/dashboard.html", context)


@staff_only
def dashboard_feed(request):
    """JSON endpoint para refresco silencioso (polling cada 10s)."""
    limit = 25
    recent_bets = (
        Bet.objects.select_related("user").order_by("-created_at")[:limit]
    )
    recent_txs = (
        Transaction.objects.filter(
            kind__in=[TransactionKind.DEPOSIT, TransactionKind.WITHDRAWAL]
        )
        .prefetch_related("entries__account_owner")
        .order_by("-created_at")[:limit]
    )
    return JsonResponse({
        "bets": [_serialize_bet(b) for b in recent_bets],
        "transactions": [_serialize_tx(t) for t in recent_txs],
        "timestamp": timezone.now().isoformat(),
    })


@staff_only
def user_detail_view(request, user_id):
    """Drill-down por cliente: saldo, apuestas, movimientos."""
    User = get_user_model()
    target = get_object_or_404(User, pk=user_id)

    balance = get_wallet_balance(target)
    bets = (
        Bet.objects.filter(user=target)
        .select_related()
        .order_by("-created_at")[:100]
    )

    txs = (
        Transaction.objects.filter(entries__account_owner=target)
        .distinct()
        .prefetch_related("entries__account_owner")
        .order_by("-created_at")[:100]
    )

    context = {
        "target": target,
        "balance": f"{balance:.4f}",
        "bets": bets,
        "transactions": [_serialize_tx(t, user_id=target.id) for t in txs],
    }
    return render(request, "backoffice/user_detail.html", context)


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


from apps.backoffice.forms import EventCreateForm
from apps.markets.services import create_default_markets_for_event

@staff_only
def event_create_view(request):
    """Vista para crear un nuevo evento desde el panel de backoffice."""
    if request.method == "POST":
        form = EventCreateForm(request.POST)
        if form.is_valid():
            event = form.save()
            create_default_markets_for_event(event)
            messages.success(request, f"Evento '{event.name}' creado correctamente con sus mercados base.")
            return redirect("backoffice:event_control", event_id=event.pk)
        else:
            for error_list in form.errors.values():
                for error in error_list:
                    messages.error(request, error)
    else:
        form = EventCreateForm()

    return render(request, "backoffice/event_create.html", {"form": form})


from apps.betting.services import settle_event_markets

@staff_only
def event_settle_view(request, event_id):
    """Vista para ingresar el marcador final y liquidar los mercados del evento."""
    event = get_object_or_404(Event.objects.prefetch_related("markets"), pk=event_id)
    
    if event.status == Event.Status.FINISHED:
        messages.info(request, "Este evento ya se encuentra finalizado.")
        return redirect("backoffice:event_control", event_id=event.pk)
        
    if request.method == "POST":
        # Checkbox confirmation is enforced by HTML5 'required' attribute, but we can double check
        if not request.POST.get("confirm"):
            messages.error(request, "Debes confirmar que el resultado es correcto marcando la casilla de verificación.")
            return redirect("backoffice:event_settle", event_id=event.pk)

        try:
            home_score = int(request.POST.get("home_score", 0))
            away_score = int(request.POST.get("away_score", 0))
        except ValueError:
            messages.error(request, "Los marcadores deben ser números enteros válidos.")
            return redirect("backoffice:event_settle", event_id=event.pk)
            
        settle_event_markets(event, home_score, away_score)
        
        messages.success(request, f"El evento '{event.name}' ha sido cerrado con resultado {home_score}-{away_score} y todas las apuestas han sido liquidadas automáticamente.")
        return redirect("backoffice:event_control", event_id=event.pk)

    return render(request, "backoffice/event_settle.html", {"event": event})

@staff_only
def event_list_view(request):
    """Vista para listar todos los eventos en el backoffice."""
    status_filter = request.GET.get("status")
    events = Event.objects.all().order_by("-starts_at")
    
    if status_filter:
        events = events.filter(status=status_filter)
        
    context = {
        "events": events,
        "current_status": status_filter,
        "all_statuses": Event.Status.choices,
    }
    return render(request, "backoffice/event_list.html", context)
