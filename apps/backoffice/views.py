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

from apps.accounts.models import CustomUser, PerfilKYC
from apps.betting.models import Bet
from apps.wallet.models import Transaction, TransactionKind, LedgerEntry, LedgerDirection, LedgerAccount
from apps.wallet.selectors import get_wallet_balance
from apps.compliance.models import SuspiciousActivity, AuditLog
from apps.compliance.services import verify_audit_chain


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

    # 0. Eventos en vivo para el Dashboard unificado
    live_events = (
        Event.objects.filter(status=Event.Status.LIVE)
        .order_by("live_started_at")[:10]
    )

    # 1. KPIs de Usuarios (adicionales a kpis)
    blocked_users = PerfilKYC.objects.filter(status=PerfilKYC.Status.BLOCKED).count()

    # 2. KPIs de Apuestas
    total_bets_count = Bet.objects.exclude(status=Bet.Status.PENDING).count()
    total_wagered = Bet.objects.exclude(status=Bet.Status.PENDING).aggregate(total=Sum('stake'))['total'] or Decimal("0.0000")
    total_payout = Bet.objects.filter(status=Bet.Status.WON).aggregate(total=Sum('payout'))['total'] or Decimal("0.0000")
    house_margin = total_wagered - total_payout

    # 3. KPIs de Billetera (Totales)
    total_deposits = LedgerEntry.objects.filter(
        account=LedgerAccount.USER_WALLET,
        direction=LedgerDirection.CREDIT,
        transaction__kind=TransactionKind.DEPOSIT
    ).aggregate(total=Sum('amount'))['total'] or Decimal("0.0000")

    total_withdrawals = LedgerEntry.objects.filter(
        account=LedgerAccount.USER_WALLET,
        direction=LedgerDirection.DEBIT,
        transaction__kind=TransactionKind.WITHDRAWAL
    ).aggregate(total=Sum('amount'))['total'] or Decimal("0.0000")

    # 4. Alertas de Actividad Sospechosa
    pending_alerts_count = SuspiciousActivity.objects.filter(status=SuspiciousActivity.Status.PENDIENTE).count()
    pending_alerts = SuspiciousActivity.objects.filter(status=SuspiciousActivity.Status.PENDIENTE).order_by("-detected_at")[:10]

    # 5. Estado de Verificación de Cadena de Hashes
    chain_status = verify_audit_chain()
    last_audit_logs = AuditLog.objects.all().order_by("-sequence")[:100]

    # 6. Lista de perfiles de usuario y KYC
    usuarios_kyc = PerfilKYC.objects.select_related("user").all()
    
    autoexcluded_count = sum(1 for p in usuarios_kyc if p.is_autoexcluido)
    net_caja = total_deposits - total_withdrawals

    # 7. Resumen de apuestas para gráfico simulado dinámico
    bets_won_count = Bet.objects.filter(status=Bet.Status.WON).count()
    bets_lost_count = Bet.objects.filter(status=Bet.Status.LOST).count()
    bets_cashout_count = Bet.objects.filter(status=Bet.Status.CASHED_OUT).count()

    max_count = max(bets_won_count + bets_lost_count + bets_cashout_count, 1)
    
    chart_data = {
        "won_height": int((bets_won_count / max_count) * 150) if bets_won_count else 110,
        "lost_height": int((bets_lost_count / max_count) * 150) if bets_lost_count else 70,
        "cashout_height": int((bets_cashout_count / max_count) * 150) if bets_cashout_count else 30,
        "won": bets_won_count,
        "lost": bets_lost_count,
        "cashout": bets_cashout_count,
    }

    context = {
        "kpis": kpis,
        "top_bettors": list(top_bettors),
        "live_events": live_events,
        # Variables de compliance integradas
        "blocked_users": blocked_users,
        "autoexcluded_count": autoexcluded_count,
        "total_bets_count": total_bets_count,
        "total_wagered": total_wagered,
        "total_payout": total_payout,
        "house_margin": house_margin,
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "net_caja": net_caja,
        "pending_alerts_count": pending_alerts_count,
        "pending_alerts": pending_alerts,
        "chain_status": chain_status,
        "last_audit_logs": last_audit_logs,
        "usuarios_kyc": usuarios_kyc,
        "chart_data": chart_data,
        "current_time": now,
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
import csv
from decimal import Decimal
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum

from apps.accounts.models import CustomUser, PerfilKYC
from apps.betting.models import Bet
from apps.wallet.models import LedgerEntry, LedgerAccount, LedgerDirection, Transaction, TransactionKind
from apps.compliance.models import SuspiciousActivity, AuditLog
from apps.compliance.services import verify_audit_chain


@staff_member_required
def compliance_view(request):
    # 1. KPIs de Usuarios
    total_users = CustomUser.objects.count()
    active_users = CustomUser.objects.filter(is_active=True).count()
    blocked_users = PerfilKYC.objects.filter(status=PerfilKYC.Status.BLOCKED).count()

    # 2. KPIs de Apuestas
    total_bets_count = Bet.objects.exclude(status=Bet.Status.PENDING).count()
    total_wagered = Bet.objects.exclude(status=Bet.Status.PENDING).aggregate(total=Sum('stake'))['total'] or Decimal("0.0000")
    total_payout = Bet.objects.filter(status=Bet.Status.WON).aggregate(total=Sum('payout'))['total'] or Decimal("0.0000")
    house_margin = total_wagered - total_payout

    # 3. KPIs de Billetera (Depositos y Retiros)
    total_deposits = LedgerEntry.objects.filter(
        account=LedgerAccount.USER_WALLET,
        direction=LedgerDirection.CREDIT,
        transaction__kind=TransactionKind.DEPOSIT
    ).aggregate(total=Sum('amount'))['total'] or Decimal("0.0000")

    total_withdrawals = LedgerEntry.objects.filter(
        account=LedgerAccount.USER_WALLET,
        direction=LedgerDirection.DEBIT,
        transaction__kind=TransactionKind.WITHDRAWAL
    ).aggregate(total=Sum('amount'))['total'] or Decimal("0.0000")

    # 4. Alertas de Actividad Sospechosa
    pending_alerts_count = SuspiciousActivity.objects.filter(status=SuspiciousActivity.Status.PENDIENTE).count()
    pending_alerts = SuspiciousActivity.objects.filter(status=SuspiciousActivity.Status.PENDIENTE).order_by("-detected_at")[:10]

    # 5. Estado de Verificación de Cadena de Hashes
    chain_status = verify_audit_chain()
    last_audit_logs = AuditLog.objects.all().order_by("-sequence")[:100]  # Exponer hasta 100 en la pestaña de auditoría

    # 6. Lista de perfiles de usuario y KYC para backoffice
    usuarios_kyc = PerfilKYC.objects.select_related("user").all()
    
    # Calcular autoexcluidos reales
    autoexcluded_count = 0
    for p in usuarios_kyc:
        if p.is_autoexcluido:
            autoexcluded_count += 1

    net_caja = total_deposits - total_withdrawals

    # 7. Resumen de apuestas para gráfico simulado dinámico (Ganadas, Perdidas, Cash-out)
    bets_won_count = Bet.objects.filter(status=Bet.Status.WON).count()
    bets_lost_count = Bet.objects.filter(status=Bet.Status.LOST).count()
    bets_cashout_count = Bet.objects.filter(status=Bet.Status.CASHED_OUT).count()

    # Si no hay datos, inicializamos con valores estéticos por defecto para que no se vea vacío
    max_count = max(bets_won_count + bets_lost_count + bets_cashout_count, 1)
    
    chart_data = {
        "won_height": int((bets_won_count / max_count) * 150) if bets_won_count else 110,
        "lost_height": int((bets_lost_count / max_count) * 150) if bets_lost_count else 70,
        "cashout_height": int((bets_cashout_count / max_count) * 150) if bets_cashout_count else 30,
        "won": bets_won_count,
        "lost": bets_lost_count,
        "cashout": bets_cashout_count,
    }

    context = {
        "total_users": total_users,
        "active_users": active_users,
        "blocked_users": blocked_users,
        "autoexcluded_count": autoexcluded_count,
        "total_bets_count": total_bets_count,
        "total_wagered": total_wagered,
        "total_payout": total_payout,
        "house_margin": house_margin,
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "net_caja": net_caja,
        "pending_alerts_count": pending_alerts_count,
        "pending_alerts": pending_alerts,
        "chain_status": chain_status,
        "last_audit_logs": last_audit_logs,
        "usuarios_kyc": usuarios_kyc,
        "chart_data": chart_data,
        "current_time": timezone.now(),
    }

    return render(request, "backoffice/compliance.html", context)


@staff_member_required
def resolver_alerta_view(request, alerta_id):
    if request.method == "POST":
        alerta = SuspiciousActivity.objects.filter(id=alerta_id).first()
        if alerta:
            nuevo_status = request.POST.get("status")
            nota = request.POST.get("reviewer_note")
            
            if nuevo_status in [SuspiciousActivity.Status.REVISADO, SuspiciousActivity.Status.FALSO_POSITIVO]:
                alerta.status = nuevo_status
                alerta.reviewer_note = nota
                alerta.reviewed_at = timezone.now()
                alerta.save()
                
    return redirect("backoffice:dashboard")


@staff_member_required
def reporte_mincetur_view(request):
    # Generar respuesta con cabeceras de descarga de CSV
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="reporte_mincetur_audit.csv"'

    writer = csv.writer(response)
    # Cabecera según estándares regulados
    writer.writerow([
        "Fecha (UTC)",
        "ID Operación / Apuesta",
        "Categoría",
        "Tipo / Detalle",
        "Usuario ID",
        "Nombre Usuario",
        "DNI",
        "Monto (Fichas)",
        "Estado / Resultado"
    ])

    # 1. Obtener Transacciones Financieras (Depósitos y Retiros)
    txs = Transaction.objects.all().select_related("created_by").order_by("created_at")
    for tx in txs:
        # Buscar el monto de la transacción para el balance del usuario
        entry = LedgerEntry.objects.filter(
            transaction=tx,
            account=LedgerAccount.USER_WALLET
        ).first()
        
        monto = entry.amount if entry else Decimal("0.0000")
        username = tx.created_by.username if tx.created_by else "Sistema"
        dni = ""
        if tx.created_by and hasattr(tx.created_by, "perfil_kyc"):
            dni = tx.created_by.perfil_kyc.dni
            
        writer.writerow([
            tx.created_at.isoformat(),
            str(tx.id),
            "FINANCIERA",
            tx.kind,
            str(tx.created_by_id) if tx.created_by_id else "N/A",
            username,
            dni,
            f"{monto:.4f}",
            "COMPLETADA"
        ])

    # 2. Obtener Apuestas
    bets = Bet.objects.all().select_related("user").order_by("created_at")
    for bet in bets:
        username = bet.user.username if bet.user else "N/A"
        dni = ""
        if bet.user and hasattr(bet.user, "perfil_kyc"):
            dni = bet.user.perfil_kyc.dni
            
        # Fila para la colocación de la apuesta
        writer.writerow([
            bet.created_at.isoformat(),
            str(bet.id),
            "APUESTA_COLOCACION",
            bet.bet_type,
            str(bet.user_id) if bet.user_id else "N/A",
            username,
            dni,
            f"{bet.stake:.4f}",
            bet.status
        ])
        
        # Fila adicional si ya está liquidada y tuvo ganancia (payout)
        if bet.status in [Bet.Status.WON, Bet.Status.LOST, Bet.Status.VOID, Bet.Status.CASHED_OUT] and bet.payout is not None:
            payout_val = bet.payout
            writer.writerow([
                bet.updated_at.isoformat(),
                f"PAYOUT-{bet.id}",
                "APUESTA_LIQUIDACION",
                f"Retorno de apuesta {bet.status}",
                str(bet.user_id) if bet.user_id else "N/A",
                username,
                dni,
                f"{payout_val:.4f}",
                bet.status
            ])

    return response
