from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.betting.models import Bet, BetSelection
from apps.markets.models import Selection, Event


def place_simple_bet(user, selection_id, stake, expected_odds, idempotency_key=None):
    
    if idempotency_key:
        existing_bet = Bet.objects.filter(idempotency_key=idempotency_key).first()
        if existing_bet:
            return existing_bet

    if stake < Decimal("1.0000"):
        raise ValidationError("El monto mínimo de apuesta es 1.0000 ficha.")

    with transaction.atomic():
        try:
            selection = Selection.objects.select_for_update().get(id=selection_id)
        except Selection.DoesNotExist:
            raise ValidationError("La selección no existe.")

        market = selection.market
        event = market.event

        if event.status != Event.Status.SCHEDULED:
            raise ValidationError("El evento no está disponible para nuevas apuestas.")
        
        if not market.is_active or not selection.is_active:
            raise ValidationError("El mercado o selección se encuentran inactivos.")

        
        if selection.odds != expected_odds:
            raise ValidationError(f"La cuota ha cambiado. Actual: {selection.odds}, Esperada: {expected_odds}. Por favor reconfirme.")

        bet = Bet.objects.create(
            user=user,
            stake=stake,
            total_odds=selection.odds,
            status=Bet.Status.PENDING, # Queda pendiente hasta que Wallet descuente
            bet_type=Bet.Type.SINGLE,
            idempotency_key=idempotency_key
        )

        BetSelection.objects.create(
            bet=bet,
            selection=selection,
            odds_at_placement=selection.odds
        )

        bet.status = Bet.Status.PLACED
        bet.save(update_fields=["status"])

        return bet
    
def settle_bet(bet, final_status):
    if final_status not in [Bet.Status.WON, Bet.Status.LOST, Bet.Status.VOID]:
        raise ValidationError("Estado de liquidación no válido.")

    from django.db import transaction
    with transaction.atomic():
        # select_for_update() bloquea la fila de la apuesta de manera pesimista
        bet_lock = Bet.objects.select_for_update().get(id=bet.id)

        # La validación se hace con el objeto bloqueado en la base de datos
        if bet_lock.status != Bet.Status.PLACED:
            raise ValidationError(f"Solo se pueden liquidar apuestas en estado PLACED. Estado actual: {bet_lock.status}")

        if final_status == Bet.Status.WON:
            bet_lock.payout = (bet_lock.stake * bet_lock.total_odds).quantize(Decimal("0.0001"))
        elif final_status == Bet.Status.LOST:
            bet_lock.payout = Decimal("0.0000")
        elif final_status == Bet.Status.VOID:
            bet_lock.payout = bet_lock.stake

        bet_lock.status = final_status
        bet_lock.save(update_fields=["status", "payout", "updated_at"])
        
        return bet_lock