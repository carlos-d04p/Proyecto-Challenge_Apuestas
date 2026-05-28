import logging
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from celery import shared_task

from apps.compliance.models import AuditLog, SuspiciousActivity
from apps.compliance.services import append_audit_event, verify_audit_chain
from apps.wallet.models import Transaction, TransactionKind, LedgerEntry, LedgerAccount, LedgerDirection

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def check_shared_ip_task(user_id, ip_address):
    """
    Celery task that checks if other users logged in from the same IP address
    in the last 24 hours.
    """
    limit_time = timezone.now() - timedelta(hours=24)
    # Buscamos eventos USER_LOGIN con la misma IP pero diferente usuario
    # En Django, filtramos usando payload__ip_address ya que es un JSONField
    coincident_events = AuditLog.objects.filter(
        event_type="USER_LOGIN",
        created_at__gte=limit_time,
        payload__ip_address=ip_address
    ).exclude(payload__user_id=user_id)

    other_user_ids = set()
    other_usernames = set()
    for event in coincident_events:
        other_user_ids.add(event.payload.get("user_id"))
        other_usernames.add(event.payload.get("username"))

    if other_usernames:
        user = User.objects.filter(id=user_id).first()
        username = user.username if user else "Desconocido"
        
        evidence = {
            "ip": ip_address,
            "user_id": user_id,
            "username": username,
            "coincidencias": list(other_usernames)
        }

        # Evitar crear duplicados idénticos en estado PENDIENTE en un corto lapso
        exists = SuspiciousActivity.objects.filter(
            user_id=user_id,
            reason=SuspiciousActivity.Reason.SHARED_IP,
            evidence__ip=ip_address,
            status=SuspiciousActivity.Status.PENDIENTE
        ).exists()

        if not exists:
            activity = SuspiciousActivity.objects.create(
                user_id=user_id,
                reason=SuspiciousActivity.Reason.SHARED_IP,
                evidence=evidence,
                status=SuspiciousActivity.Status.PENDIENTE
            )
            append_audit_event(
                event_type="SUSPICIOUS_ACTIVITY_DETECTED",
                payload={
                    "activity_id": activity.id,
                    "reason": activity.reason,
                    "user_id": user_id,
                    "username": username,
                    "evidence": evidence
                }
            )
            logger.warning(f"Actividad sospechosa de IP compartida detectada para {username}: {ip_address}")


@shared_task
def check_suspicious_activity_on_transaction_task(transaction_id):
    """
    Celery task analyzing if a withdrawal constitutes a quick withdrawal
    without significant wagering (DEP_WD).
    """
    tx = Transaction.objects.filter(id=transaction_id).first()
    if not tx or tx.kind != TransactionKind.WITHDRAWAL:
        return

    user = tx.created_by
    if not user:
        return

    # Obtener el monto de este retiro
    withdrawal_entry = LedgerEntry.objects.filter(
        transaction=tx,
        account=LedgerAccount.USER_WALLET,
        direction=LedgerDirection.DEBIT
    ).first()
    if not withdrawal_entry:
        return
    withdrawal_amount = withdrawal_entry.amount

    # Buscar depósitos y apuestas del usuario en las últimas 24 horas
    time_limit = timezone.now() - timedelta(hours=24)
    
    # Sumar depósitos en las últimas 24 horas
    deposit_txs = Transaction.objects.filter(
        created_by=user,
        kind=TransactionKind.DEPOSIT,
        created_at__gte=time_limit
    )
    total_deposited = Decimal("0.0000")
    for d_tx in deposit_txs:
        d_entry = LedgerEntry.objects.filter(
            transaction=d_tx,
            account=LedgerAccount.USER_WALLET,
            direction=LedgerDirection.CREDIT
        ).first()
        if d_entry:
            total_deposited += d_entry.amount

    # Sumar volumen de apuestas (BET_PLACEMENT) en las últimas 24 horas
    bet_txs = Transaction.objects.filter(
        created_by=user,
        kind=TransactionKind.BET_PLACEMENT,
        created_at__gte=time_limit
    )
    total_wagered = Decimal("0.0000")
    for b_tx in bet_txs:
        b_entry = LedgerEntry.objects.filter(
            transaction=b_tx,
            account=LedgerAccount.USER_WALLET,
            direction=LedgerDirection.DEBIT
        ).first()
        if b_entry:
            total_wagered += b_entry.amount

    # Si depositó más de 0 y su apuesta total es menor al 80% de su depósito,
    # y el retiro es considerable, alertar
    if total_deposited > 0 and total_wagered < (total_deposited * Decimal("0.8000")):
        evidence = {
            "transaction_id": str(tx.id),
            "monto_retiro": str(withdrawal_amount),
            "total_depositado_24h": str(total_deposited),
            "total_apostado_24h": str(total_wagered),
            "ratio_juego_vs_deposito": f"{(total_wagered / total_deposited) * 100:.2f}%"
        }
        
        activity = SuspiciousActivity.objects.create(
            user=user,
            reason=SuspiciousActivity.Reason.DEP_WD,
            evidence=evidence,
            status=SuspiciousActivity.Status.PENDIENTE
        )
        append_audit_event(
            event_type="SUSPICIOUS_ACTIVITY_DETECTED",
            payload={
                "activity_id": activity.id,
                "reason": activity.reason,
                "user_id": str(user.id),
                "username": user.username,
                "evidence": evidence
            }
        )
        logger.warning(f"Depósito-retiro rápido sospechoso detectado para usuario {user.username}: {evidence}")


@shared_task
def verify_compliance_chain_periodic_task():
    """
    Verifica la cadena de hashes periódicamente y registra cualquier
    anomalía en la cadena como actividad sospechosa (PATTERN).
    """
    res = verify_audit_chain()
    if not res["valid"]:
        # Crear actividad sospechosa sobre la alteración del log de auditoría
        evidence = {"error_message": res["message"], "error_sequence": res["error_sequence"]}
        activity = SuspiciousActivity.objects.create(
            user=None,
            reason=SuspiciousActivity.Reason.PATTERN,
            evidence=evidence,
            status=SuspiciousActivity.Status.PENDIENTE
        )
        append_audit_event(
            event_type="AUDIT_CHAIN_CORRUPTION_DETECTED",
            payload=evidence
        )
        logger.error(f"CORRUPCIÓN DE CADENA DE AUDITORÍA DETECTADA: {res['message']}")
        return False
    return True


# ── RECEIVERS / SEÑALES DE DJANGO ────────────────────────────────────────────

@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    Registra el evento de login en la cadena de auditoría e inicia
    la tarea en background para verificar IPs compartidas.
    """
    if not request:
        return
        
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')

    if not ip:
        ip = "127.0.0.1"

    # Registrar en AuditLog
    append_audit_event(
        event_type="USER_LOGIN",
        payload={
            "user_id": str(user.id),
            "username": user.username,
            "ip_address": ip,
            "timestamp": timezone.now().isoformat()
        }
    )

    # Lanzar Celery task
    check_shared_ip_task.delay(str(user.id), ip)


@receiver(post_save, sender=Transaction)
def on_transaction_saved(sender, instance, created, **kwargs):
    """
    Cuando se crea una transacción, disparamos el análisis de retiros rápidos (DEP_WD)
    si la transacción es de tipo retiro.
    """
    if created and instance.kind == TransactionKind.WITHDRAWAL:
        check_suspicious_activity_on_transaction_task.delay(str(instance.id))
