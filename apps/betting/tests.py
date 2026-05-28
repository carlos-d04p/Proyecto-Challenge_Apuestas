import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.markets.models import Event, Market, Selection
from apps.betting.models import Bet
from apps.betting.services import place_simple_bet, settle_bet, place_acca_bet

User = get_user_model()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="apostador", password="123")

@pytest.fixture
def active_selection(db):
    event = Event.objects.create(
        name="Liverpool vs Chelsea", sport="Fútbol", 
        starts_at=timezone.now() + timedelta(days=1), 
        status=Event.Status.SCHEDULED
    )
    market = Market.objects.create(event=event, kind=Market.Kind.MATCH_RESULT, name="1X2")
    return Selection.objects.create(market=market, name="Gana Local", odds=Decimal("2.1000"))

@pytest.fixture
def placed_bet(test_user, active_selection):
    return Bet.objects.create(
        user=test_user,
        stake=Decimal("10.0000"),
        total_odds=Decimal("2.5000"),
        status=Bet.Status.PLACED,
        bet_type=Bet.Type.SINGLE
    )

@pytest.fixture
def second_selection(db):
    event2 = Event.objects.create(
        name="Real Madrid vs Barcelona", sport="Fútbol", 
        starts_at=timezone.now() + timedelta(days=1), 
        status=Event.Status.SCHEDULED
    )
    market2 = Market.objects.create(event=event2, kind=Market.Kind.MATCH_RESULT, name="1X2")
    return Selection.objects.create(market=market2, name="Gana Local", odds=Decimal("2.0000"))

class TestPlaceSimpleBet:
    def test_exito_apuesta_simple(self, test_user, active_selection):
        bet = place_simple_bet(
            user=test_user, 
            selection_id=active_selection.id, 
            stake=Decimal("50.0000"), 
            expected_odds=Decimal("2.1000")
        )
        assert bet.status == Bet.Status.PLACED
        assert bet.stake == Decimal("50.0000")
        assert bet.selections.count() == 1
        assert bet.selections.first().odds_at_placement == Decimal("2.1000")

    def test_politica_recotizacion_bloquea_cambios(self, test_user, active_selection):
        with pytest.raises(ValidationError, match="La cuota ha cambiado"):
            place_simple_bet(
                user=test_user, 
                selection_id=active_selection.id, 
                stake=Decimal("10.0000"), 
                expected_odds=Decimal("2.5000")
            )

    def test_idempotencia_evita_doble_ticket(self, test_user, active_selection):
        key = "req-12345"
        bet1 = place_simple_bet(test_user, active_selection.id, Decimal("10.0000"), Decimal("2.1000"), key)
        bet2 = place_simple_bet(test_user, active_selection.id, Decimal("10.0000"), Decimal("2.1000"), key)
        assert bet1.id == bet2.id
        assert Bet.objects.count() == 1

class TestSettleBet:
    def test_liquidar_apuesta_ganadora(self, placed_bet):
        bet = settle_bet(placed_bet, Bet.Status.WON)
        assert bet.status == Bet.Status.WON
        assert bet.payout == Decimal("25.0000")

    def test_liquidar_apuesta_perdedora(self, placed_bet):
        bet = settle_bet(placed_bet, Bet.Status.LOST)
        assert bet.status == Bet.Status.LOST
        assert bet.payout == Decimal("0.0000")

    def test_liquidar_apuesta_anulada(self, placed_bet):
        bet = settle_bet(placed_bet, Bet.Status.VOID)
        assert bet.status == Bet.Status.VOID
        assert bet.payout == Decimal("10.0000")

    def test_evitar_doble_liquidacion(self, placed_bet):
        settle_bet(placed_bet, Bet.Status.WON)
        with pytest.raises(ValidationError, match="Solo se pueden liquidar apuestas en estado PLACED"):
            settle_bet(placed_bet, Bet.Status.LOST)

class TestPlaceAccaBet:
    def test_exito_apuesta_combinada(self, test_user, active_selection, second_selection):
        selection_ids = [active_selection.id, second_selection.id]
        bet = place_acca_bet(
            user=test_user,
            selection_ids=selection_ids,
            stake=Decimal("10.0000"),
            expected_odds=Decimal("4.2000")
        )
        assert bet.bet_type == Bet.Type.ACCA
        assert bet.status == Bet.Status.PLACED
        assert bet.total_odds == Decimal("4.2000")
        assert bet.selections.count() == 2

    def test_bloqueo_seleccion_mutuamente_excluyente(self, test_user, active_selection):
        empate_selection = Selection.objects.create(
            market=active_selection.market, 
            name="Empate", 
            odds=Decimal("3.0000")
        )
        selection_ids = [active_selection.id, empate_selection.id]
        with pytest.raises(ValidationError, match="No se pueden combinar selecciones del mismo evento"):
            place_acca_bet(
                user=test_user,
                selection_ids=selection_ids,
                stake=Decimal("10.0000"),
                expected_odds=Decimal("6.3000")
            )


class TestCashOutBet:
    def test_exito_cash_out_calculo_exacto(self, placed_bet):
        from apps.betting.services import cash_out_bet
        # placed_bet tiene stake=10.0000 y total_odds=2.5000
        # Fórmula: 10 * (2.5000 / 2.0000) * 0.9000 = 11.2500
        bet = cash_out_bet(
            bet=placed_bet, 
            current_odds=Decimal("2.0000"), 
            house_factor=Decimal("0.9000")
        )
        assert bet.status == Bet.Status.CASHED_OUT
        assert bet.payout == Decimal("11.2500")

    def test_bloqueo_cash_out_apuesta_no_activa(self, placed_bet):
        from apps.betting.services import cash_out_bet, settle_bet
        # Primero liquidamos la apuesta como ganada
        settle_bet(placed_bet, Bet.Status.WON)
        
        # Intentar cobrar cash-out de una apuesta ya resuelta debe fallar
        with pytest.raises(ValidationError, match="Solo se puede realizar cash-out en apuestas activas"):
            cash_out_bet(placed_bet, current_odds=Decimal("2.0000"))