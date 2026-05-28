from django.shortcuts import render
from decimal import Decimal
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from apps.betting.models import Bet
from apps.betting.services import place_simple_bet, cash_out_bet

@login_required
def mis_apuestas(request):
    apuestas = Bet.objects.filter(user=request.user).prefetch_related("selections__selection__market__event")
    return render(request, "betting/mis_apuestas.html", {"apuestas": apuestas})

@login_required
@require_POST
def colocar_apuesta(request):
    selection_id = request.POST.get("selection_id")
    stake_str = request.POST.get("stake", "0")
    expected_odds_str = request.POST.get("expected_odds", "0")
    idempotency_key = request.POST.get("idempotency_key")

    try:
        stake = Decimal(stake_str)
        expected_odds = Decimal(expected_odds_str)
        
        # Invocación de la lógica transaccional aislada
        place_simple_bet(
            user=request.user,
            selection_id=selection_id,
            stake=stake,
            expected_odds=expected_odds,
            idempotency_key=idempotency_key
        )
        messages.success(request, "¡Apuesta colocada con éxito!")
    except (ValidationError, ValueError) as e:
        messages.error(request, f"Error al procesar la apuesta: {getattr(e, 'message', str(e))}")
    
    # Redirige de vuelta al detalle del evento o al historial
    return redirect(request.META.get("HTTP_REFERER", "markets:event_list"))

@login_required
@require_POST
def ejecutar_cashout(request, bet_id):
    bet = get_object_or_404(Bet, id=bet_id, user=request.user)
    current_odds_str = request.POST.get("current_odds")

    try:
        if not current_odds_str:
            raise ValidationError("No se especificó la cuota actual de mercado para el cálculo.")
        
        current_odds = Decimal(current_odds_str)
        
        # Invocación de la fórmula del requerimiento con factor de la casa (90%)
        cash_out_bet(bet=bet, current_odds=current_odds, house_factor=Decimal("0.9000"))
        messages.success(request, "Cash-out procesado y fondos transferidos a la cuenta.")
    except (ValidationError, ValueError) as e:
        messages.error(request, f"No se pudo ejecutar el Cash-out: {getattr(e, 'message', str(e))}")

    return redirect("betting:mis_apuestas")