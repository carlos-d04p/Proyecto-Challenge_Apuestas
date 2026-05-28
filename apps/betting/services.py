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
            status=Bet.Status.PENDING,
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

    with transaction.atomic():
        bet_lock = Bet.objects.select_for_update().get(id=bet.id)

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

def place_acca_bet(user, selection_ids, stake, expected_odds, idempotency_key=None):
    if idempotency_key:
        existing_bet = Bet.objects.filter(idempotency_key=idempotency_key).first()
        if existing_bet:
            return existing_bet

    if stake < Decimal("1.0000"):
        raise ValidationError("El monto mínimo de apuesta es 1.0000 ficha.")

    if len(selection_ids) < 2:
        raise ValidationError("Una apuesta combinada requiere mínimo 2 selecciones.")

    with transaction.atomic():
        selections = list(
            Selection.objects.select_for_update()
            .filter(id__in=selection_ids)
            .order_by("id")
        )

        if len(selections) != len(selection_ids):
            raise ValidationError("Una o más selecciones no existen.")

        event_ids = [sel.market.event_id for sel in selections]
        if len(event_ids) != len(set(event_ids)):
            raise ValidationError("No se pueden combinar selecciones del mismo evento (exclusión mutua).")

        total_odds = Decimal("1.0000")
        for selection in selections:
            if selection.market.event.status != Event.Status.SCHEDULED:
                raise ValidationError("Uno o más eventos ya no están disponibles.")
            if not selection.market.is_active or not selection.is_active:
                raise ValidationError("Una de las selecciones no está activa.")
            total_odds *= selection.odds

        total_odds = total_odds.quantize(Decimal("0.0001"))

        if total_odds != expected_odds:
            raise ValidationError(f"Las cuotas cambiaron. Actual: {total_odds}, Esperada: {expected_odds}.")

        bet = Bet.objects.create(
            user=user,
            stake=stake,
            total_odds=total_odds,
            status=Bet.Status.PENDING,
            bet_type=Bet.Type.ACCA,
            idempotency_key=idempotency_key
        )

        for selection in selections:
            BetSelection.objects.create(
                bet=bet,
                selection=selection,
                odds_at_placement=selection.odds
            )

        bet.status = Bet.Status.PLACED
        bet.save(update_fields=["status"])
        return bet

def cash_out_bet(bet, current_odds, house_factor=Decimal("0.9000")):
    if bet.status != Bet.Status.PLACED:
        raise ValidationError("Solo se puede realizar cash-out en apuestas activas.")
    
    with transaction.atomic():
        bet_lock = Bet.objects.select_for_update().get(id=bet.id)
        
        if bet_lock.status != Bet.Status.PLACED:
            raise ValidationError("Solo se puede realizar cash-out en apuestas activas.")
            
        payout = (bet_lock.stake * (bet_lock.total_odds / current_odds) * house_factor).quantize(Decimal("0.0001"))
        bet_lock.payout = payout
        bet_lock.status = Bet.Status.CASHED_OUT
        bet_lock.save(update_fields=["status", "payout", "updated_at"])
        return bet_lock