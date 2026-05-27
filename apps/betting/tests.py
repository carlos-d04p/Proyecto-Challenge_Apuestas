from django.test import TestCase
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

# pyrefly: ignore [missing-import]
from apps.markets.models import Event, Market, Selection
# pyrefly: ignore [missing-import]
from apps.betting.models import Bet
# pyrefly: ignore [missing-import]
from apps.betting.services import place_simple_bet

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
        # Simulamos que el usuario intenta apostar creyendo que la cuota es 2.5000, 
        # pero en la base de datos es 2.1000. Debe ser rechazado.
        with pytest.raises(ValidationError, match="La cuota ha cambiado"):
            place_simple_bet(
                user=test_user, 
                selection_id=active_selection.id, 
                stake=Decimal("10.0000"), 
                expected_odds=Decimal("2.5000")
            )

    def test_idempotencia_evita_doble_ticket(self, test_user, active_selection):
        key = "req-12345"
        
        # Primera solicitud
        bet1 = place_simple_bet(test_user, active_selection.id, Decimal("10.0000"), Decimal("2.1000"), key)
        # Segunda solicitud (ej. el usuario hace doble click)
        bet2 = place_simple_bet(test_user, active_selection.id, Decimal("10.0000"), Decimal("2.1000"), key)
        
        assert bet1.id == bet2.id
        assert Bet.objects.count() == 1  # Solo se creó un ticket en BD