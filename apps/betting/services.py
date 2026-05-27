from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
# pyrefly: ignore [missing-import]
from apps.betting.models import Bet, BetSelection
# pyrefly: ignore [missing-import]
from apps.markets.models import Selection, Event


def place_simple_bet(user, selection_id, stake, expected_odds, idempotency_key=None):
    # 1. Control de Idempotencia (Evitar doble procesamiento por clicks repetidos)
    if idempotency_key:
        existing_bet = Bet.objects.filter(idempotency_key=idempotency_key).first()
        if existing_bet:
            return existing_bet

    # 2. Restricción de montos
    if stake < Decimal("1.0000"):
        raise ValidationError("El monto mínimo de apuesta es 1.0000 ficha.")

    # 3. Transacción atómica con bloqueo de fila (concurrencia)
    with transaction.atomic():
        try:
            # select_for_update() bloquea la fila para evitar que otro proceso cambie la cuota mientras validamos
            selection = Selection.objects.select_for_update().get(id=selection_id)
        except Selection.DoesNotExist:
            raise ValidationError("La selección no existe.")

        market = selection.market
        event = market.event

        # 4. Validaciones de estado
        if event.status != Event.Status.SCHEDULED:
            raise ValidationError("El evento no está disponible para nuevas apuestas.")
        
        if not market.is_active or not selection.is_active:
            raise ValidationError("El mercado o selección se encuentran inactivos.")

        # 5. Política de re-cotización (Exigencia de la rúbrica)
        if selection.odds != expected_odds:
            raise ValidationError(f"La cuota ha cambiado. Actual: {selection.odds}, Esperada: {expected_odds}. Por favor reconfirme.")

        # 6. Creación del Ticket de Apuesta
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

        # TODO: Integrar llamada a la app Wallet (Partida doble) para descontar el `stake`.
        # Como aún no hacemos el Wallet, simulamos la aceptación pasándolo a PLACED.
        bet.status = Bet.Status.PLACED
        bet.save(update_fields=["status"])

        return bet