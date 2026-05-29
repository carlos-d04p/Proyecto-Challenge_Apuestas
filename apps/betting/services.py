from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from apps.betting.models import Bet, BetSelection
from apps.markets.models import Selection, Event
from apps.wallet.services import (
    record_bet_placement,
    record_bet_settlement_won,
    record_bet_settlement_lost,
    record_bet_settlement_void,
    record_bet_cashout,
)

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


def place_simple_bet(user, selection_id, stake, expected_odds, idempotency_key=None, use_bonus=False):
    # GUARD: correo no verificado
    if not getattr(user, 'is_email_verified', False):
        raise PermissionError(
            "Debes verificar tu correo electrónico antes de realizar apuestas. "
            "Revisa tu bandeja de entrada."
        )

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

        # In-play betting: permitir SCHEDULED y LIVE. Bloquear el resto.
        if event.status not in (Event.Status.SCHEDULED, Event.Status.LIVE):
            raise ValidationError("El evento no está disponible para nuevas apuestas.")

        # RB-RT-06: ventana de suspensión automática (gol/expulsión).
        if event.suspended_until and event.suspended_until > timezone.now():
            raise ValidationError(
                "El mercado está temporalmente suspendido por un evento crítico. "
                "Intenta de nuevo en unos segundos."
            )

        if not market.is_active or not selection.is_active:
            raise ValidationError("El mercado o selección se encuentran inactivos.")

        expected_odds_norm = expected_odds.quantize(Decimal("0.0001"))
        # Para mejorar la experiencia en partidos EN VIVO, aceptamos la cuota actual automáticamente
        # en lugar de bloquear la apuesta por cambios de milisegundos.
        # if selection.odds != expected_odds_norm:
        #     raise ValidationError(
        #         f"La cuota ha cambiado. Actual: {selection.odds}, "
        #         f"Esperada: {expected_odds_norm}. Por favor reconfirme."
        #     )

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
        
        # Integración con Wallet
        record_bet_placement(user, stake, bet.id, use_bonus=use_bonus)
        
        return bet


def place_acca_bet(user, selection_ids, stake, expected_odds, idempotency_key=None, use_bonus=False):
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

        market_ids = [sel.market_id for sel in selections]
        if len(market_ids) != len(set(market_ids)):
            raise ValidationError(
                "No se pueden combinar selecciones del mismo mercado (exclusión mutua)."
            )

        total_odds = Decimal("1.0000")
        now = timezone.now()
        for sel in selections:
            ev = sel.market.event
            if ev.status not in (Event.Status.SCHEDULED, Event.Status.LIVE):
                raise ValidationError("Uno o más eventos ya no están disponibles.")
            if ev.suspended_until and ev.suspended_until > now:
                raise ValidationError(
                    "Uno de los mercados está temporalmente suspendido por un evento crítico."
                )
            if not sel.market.is_active or not sel.is_active:
                raise ValidationError("Una de las selecciones no está activa.")
            total_odds *= sel.odds

        total_odds = total_odds.quantize(Decimal("0.0001"))

        expected_odds_norm = expected_odds.quantize(Decimal("0.0001"))
        # Para mejorar la experiencia en partidos EN VIVO, aceptamos la cuota actual automáticamente
        # if total_odds != expected_odds_norm:
        #     raise ValidationError(
        #         f"Las cuotas cambiaron. Actual: {total_odds}, Esperada: {expected_odds_norm}."
        #     )

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
        
        # Integración con Wallet
        record_bet_placement(user, stake, bet.id, use_bonus=use_bonus)
        
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
        
        # Integración con Wallet
        if final_status == Bet.Status.WON:
            record_bet_settlement_won(bet_lock.user, bet_lock.stake, bet_lock.payout, bet_lock.id)
        elif final_status == Bet.Status.LOST:
            record_bet_settlement_lost(bet_lock.user, bet_lock.stake, bet_lock.id)
        elif final_status == Bet.Status.VOID:
            record_bet_settlement_void(bet_lock.user, bet_lock.stake, bet_lock.id)
            
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
        
        # Integración con Wallet
        if final_status == Bet.Status.WON:
            record_bet_settlement_won(bet_lock.user, bet_lock.stake, bet_lock.payout, bet_lock.id)
        elif final_status == Bet.Status.LOST:
            record_bet_settlement_lost(bet_lock.user, bet_lock.stake, bet_lock.id)
        # Note: ACCA bets do not settle as entirely VOID in this logic, they either win or lose.
        # If all selections were void, it would evaluate as WON with odds 1.0.
        
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
        
        # Integración con Wallet
        record_bet_cashout(bet_lock.user, bet_lock.stake, bet_lock.payout, bet_lock.id)
        
        return bet_lock


def settle_event_markets(event, home_score: int, away_score: int):
    """
    Finaliza un evento y liquida automáticamente todos los mercados y apuestas
    basándose en el marcador final.
    """
    from apps.markets.models import Market
    
    with transaction.atomic():
        event.home_score = home_score
        event.away_score = away_score
        event.status = Event.Status.FINISHED
        event.save(update_fields=["home_score", "away_score", "status", "updated_at"])
        
        # Recolectar todas las apuestas ACCA que toquemos para evaluarlas al final
        affected_acca_bets = set()

        for market in event.markets.filter(is_active=True):
            market.is_active = False
            market.save(update_fields=["is_active"])
            
            # Determinar qué selecciones ganaron
            winning_selections = []
            if market.kind == Market.Kind.MATCH_RESULT:
                if home_score > away_score:
                    winning_selections.append("Gana Local")
                elif away_score > home_score:
                    winning_selections.append("Gana Visitante")
                else:
                    winning_selections.append("Empate")
            elif market.kind == Market.Kind.OVER_UNDER:
                if (home_score + away_score) > 2.5:
                    winning_selections.append("Más de 2.5")
                else:
                    winning_selections.append("Menos de 2.5")
            elif market.kind == Market.Kind.BOTH_TEAMS_SCORE:
                if home_score > 0 and away_score > 0:
                    winning_selections.append("Sí")
                else:
                    winning_selections.append("No")
            elif market.kind == Market.Kind.HANDICAP:
                if (home_score - 1) > away_score:
                    winning_selections.append("Local -1")
                else:
                    winning_selections.append("Visitante +1")

            for sel in market.selections.all():
                is_winner = sel.name in winning_selections
                final_result = BetSelection.Result.WON if is_winner else BetSelection.Result.LOST
                
                for bs in BetSelection.objects.filter(
                    selection=sel, 
                    result=BetSelection.Result.PENDING,
                    bet__status=Bet.Status.PLACED
                ).select_related('bet'):
                    
                    bs.result = final_result
                    bs.save(update_fields=["result"])
                    
                    if bs.bet.bet_type == Bet.Type.SINGLE:
                        settle_bet(bs.bet, Bet.Status.WON if is_winner else Bet.Status.LOST)
                    else:
                        affected_acca_bets.add(bs.bet)

        # Evaluar apuestas ACCA afectadas
        for acca_bet in affected_acca_bets:
            all_bs = list(acca_bet.selections.all())
            has_lost = any(b.result == BetSelection.Result.LOST for b in all_bs)
            is_pending = any(b.result == BetSelection.Result.PENDING for b in all_bs)
            
            if has_lost:
                # Perdió una selección, la combinada entera se pierde
                res_dict = {str(b.id): b.result for b in all_bs}
                # Asegurar que settle_acca_bet no sobreescriba los previos que sí ganaron
                settle_acca_bet(acca_bet, res_dict)
            elif not is_pending:
                # Todas ganaron (o void), la combinada gana
                res_dict = {str(b.id): b.result for b in all_bs}
                settle_acca_bet(acca_bet, res_dict)