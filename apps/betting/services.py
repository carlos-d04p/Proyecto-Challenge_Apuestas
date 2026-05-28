from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from apps.betting.models import Bet, BetSelection
from apps.markets.models import Selection, Event

MAX_PAYOUT = Decimal("20000.0000")
MIN_STAKE = Decimal("10.0000")
HOUSE_FACTOR = Decimal("0.9000")
CASHOUT_BLOCK_MINUTES = 10


def _validate_stake(stake, expected_odds):
    if stake < MIN_STAKE:
        raise ValidationError(f"El monto mínimo de apuesta es {MIN_STAKE} fichas.")
    stake_max = (MAX_PAYOUT / expected_odds).quantize(Decimal("0.0001"))
    if stake > stake_max:
        raise ValidationError(
            f"El stake máximo para esta cuota es {stake_max} fichas "
            f"(límite de retorno: {MAX_PAYOUT} fichas)."
        )


def place_simple_bet(user, selection_id, stake, expected_odds, idempotency_key=None):
    if idempotency_key:
        existing_bet = Bet.objects.filter(idempotency_key=idempotency_key).first()
        if existing_bet:
            return existing_bet

    _validate_stake(stake, expected_odds)

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

        expected_odds_norm = expected_odds.quantize(Decimal("0.0001"))
        if selection.odds != expected_odds_norm:
            raise ValidationError(
                f"La cuota ha cambiado. Actual: {selection.odds}, "
                f"Esperada: {expected_odds_norm}. Por favor reconfirme."
            )

        bet = Bet.objects.create(
            user=user,
            stake=stake,
            total_odds=selection.odds,
            status=Bet.Status.PENDING,
            bet_type=Bet.Type.SINGLE,
            idempotency_key=idempotency_key,
        )

        BetSelection.objects.create(
            bet=bet,
            selection=selection,
            odds_at_placement=selection.odds,
        )

        bet.status = Bet.Status.PLACED
        bet.save(update_fields=["status"])
        return bet


def place_acca_bet(user, selection_ids, stake, expected_odds, idempotency_key=None):
    if idempotency_key:
        existing_bet = Bet.objects.filter(idempotency_key=idempotency_key).first()
        if existing_bet:
            return existing_bet

    if len(selection_ids) < 2:
        raise ValidationError("Una apuesta combinada requiere mínimo 2 selecciones.")

    if len(selection_ids) > 5:
        raise ValidationError("Una apuesta combinada admite un máximo de 5 selecciones.")

    _validate_stake(stake, expected_odds)

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
            raise ValidationError(
                "No se pueden combinar selecciones del mismo evento (exclusión mutua)."
            )

        total_odds = Decimal("1.0000")
        for sel in selections:
            if sel.market.event.status != Event.Status.SCHEDULED:
                raise ValidationError("Uno o más eventos ya no están disponibles.")
            if not sel.market.is_active or not sel.is_active:
                raise ValidationError("Una de las selecciones no está activa.")
            total_odds *= sel.odds

        total_odds = total_odds.quantize(Decimal("0.0001"))

        expected_odds_norm = expected_odds.quantize(Decimal("0.0001"))
        if total_odds != expected_odds_norm:
            raise ValidationError(
                f"Las cuotas cambiaron. Actual: {total_odds}, Esperada: {expected_odds_norm}."
            )

        bet = Bet.objects.create(
            user=user,
            stake=stake,
            total_odds=total_odds,
            status=Bet.Status.PENDING,
            bet_type=Bet.Type.ACCA,
            idempotency_key=idempotency_key,
        )

        for sel in selections:
            BetSelection.objects.create(
                bet=bet,
                selection=sel,
                odds_at_placement=sel.odds,
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
            raise ValidationError(
                f"Solo se pueden liquidar apuestas en estado PLACED. "
                f"Estado actual: {bet_lock.status}"
            )

        if final_status == Bet.Status.WON:
            bet_lock.payout = (bet_lock.stake * bet_lock.total_odds).quantize(
                Decimal("0.0001")
            )
        elif final_status == Bet.Status.LOST:
            bet_lock.payout = Decimal("0.0000")
        elif final_status == Bet.Status.VOID:
            bet_lock.payout = bet_lock.stake

        bet_lock.status = final_status
        bet_lock.save(update_fields=["status", "payout", "updated_at"])
        return bet_lock


def settle_acca_bet(bet, selection_results: dict):
    """
    RB-BET-15: Liquida una apuesta combinada aplicando resultados por selección.
    selection_results: {bet_selection_id: 'WON'|'LOST'|'VOID'}
    Las selecciones VOID contribuyen con cuota 1.0000 al multiplicador final.
    """
    with transaction.atomic():
        bet_lock = Bet.objects.select_for_update().get(id=bet.id)

        if bet_lock.status != Bet.Status.PLACED:
            raise ValidationError(
                f"Solo se pueden liquidar apuestas en estado PLACED. "
                f"Estado actual: {bet_lock.status}"
            )

        bet_selections = list(
            BetSelection.objects.select_for_update().filter(bet=bet_lock)
        )

        has_lost = False
        effective_odds = Decimal("1.0000")

        for bs in bet_selections:
            result = selection_results.get(str(bs.id), BetSelection.Result.PENDING)
            bs.result = result
            if result == BetSelection.Result.LOST:
                has_lost = True
            elif result == BetSelection.Result.VOID:
                pass
            else:
                effective_odds *= bs.odds_at_placement

        BetSelection.objects.bulk_update(bet_selections, ["result"])

        if has_lost:
            final_status = Bet.Status.LOST
            payout = Decimal("0.0000")
        else:
            effective_odds = effective_odds.quantize(Decimal("0.0001"))
            final_status = Bet.Status.WON
            payout = (bet_lock.stake * effective_odds).quantize(Decimal("0.0001"))

        bet_lock.total_odds = effective_odds if not has_lost else bet_lock.total_odds
        bet_lock.payout = payout
        bet_lock.status = final_status
        bet_lock.save(update_fields=["status", "payout", "total_odds", "updated_at"])
        return bet_lock


def cash_out_bet(bet, current_odds, house_factor=HOUSE_FACTOR):
    if current_odds < Decimal("1.0000"):
        raise ValidationError(
            "El cash-out no está disponible: la cuota actual es menor a 1.0000."
        )

    if bet.status != Bet.Status.PLACED:
        raise ValidationError("Solo se puede realizar cash-out en apuestas activas.")

    with transaction.atomic():
        bet_lock = Bet.objects.select_for_update().get(id=bet.id)

        if bet_lock.status != Bet.Status.PLACED:
            raise ValidationError("Solo se puede realizar cash-out en apuestas activas.")

        if bet_lock.selections.filter(result=BetSelection.Result.LOST).exists():
            raise ValidationError(
                "El cash-out no está disponible: una o más selecciones ya resultaron perdedoras."
            )

        now = timezone.now()
        block_threshold = now + timedelta(minutes=CASHOUT_BLOCK_MINUTES)
        for bs in bet_lock.selections.select_related("selection__market__event"):
            event = bs.selection.market.event
            if event.status == Event.Status.SCHEDULED and event.starts_at <= block_threshold:
                raise ValidationError(
                    f"El cash-out está bloqueado: el evento '{event.name}' "
                    f"comienza en menos de {CASHOUT_BLOCK_MINUTES} minutos."
                )

        payout = (
            bet_lock.stake * (bet_lock.total_odds / current_odds) * house_factor
        ).quantize(Decimal("0.0001"))
        bet_lock.payout = payout
        bet_lock.status = Bet.Status.CASHED_OUT
        bet_lock.save(update_fields=["status", "payout", "updated_at"])
        return bet_lock