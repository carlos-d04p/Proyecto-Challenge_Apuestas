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
def dashboard_view(request):
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

    return render(request, "backoffice/dashboard.html", context)


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
