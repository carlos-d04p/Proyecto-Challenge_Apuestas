import uuid
from django.shortcuts import render, redirect, get_object_or_404
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import IntegrityError, DataError
from apps.betting.models import Bet
from apps.betting.services import place_simple_bet, place_acca_bet, cash_out_bet


@login_required
def mis_apuestas(request):
    apuestas = Bet.objects.filter(user=request.user).prefetch_related(
        "selections__selection__market__event"
    ).order_by("-created_at")
    return render(request, "betting/mis_apuestas.html", {"apuestas": apuestas})


@login_required
@require_POST
def colocar_apuesta(request):
    selection_ids = request.POST.getlist("selection_id")
    stake_str = request.POST.get("stake", "0")
    expected_odds_str = request.POST.get("expected_odds", "0")
    bet_type = request.POST.get("bet_type", "SINGLE")
    use_bonus = request.POST.get("use_bonus") == "true"
    idempotency_key = str(uuid.uuid4())

    try:
        if not selection_ids:
            raise ValidationError("No se han enviado selecciones en el boleto.")

        stake = Decimal(stake_str.strip().replace(",", "."))
        expected_odds = Decimal(expected_odds_str.strip().replace(",", "."))

        if bet_type == "ACCA":
            if len(selection_ids) < 2:
                raise ValidationError("Una apuesta combinada requiere mínimo 2 selecciones.")
            if len(selection_ids) > 5:
                raise ValidationError("Una apuesta combinada admite un máximo de 5 selecciones.")
            
            place_acca_bet(
                user=request.user,
                selection_ids=selection_ids,
                stake=stake,
                expected_odds=expected_odds,
                idempotency_key=idempotency_key,
                use_bonus=use_bonus,
            )
            messages.success(request, "¡Apuesta combinada colocada con éxito!")
        else:
            # Procesar múltiples apuestas simples independientes
            stakes = request.POST.getlist("stake")
            expected_odds_list = request.POST.getlist("expected_odds")
            
            # Si solo envían 1 stake (como antes), lo usamos para todos (por retrocompatibilidad si fuese necesario)
            if len(stakes) == 1 and len(selection_ids) > 1:
                stakes = stakes * len(selection_ids)
                expected_odds_list = expected_odds_list * len(selection_ids)
            elif not stakes:
                # Fallback al viejo método de obtener un string
                stakes = [stake_str] * len(selection_ids)
                expected_odds_list = [expected_odds_str] * len(selection_ids)
            
            if len(stakes) != len(selection_ids) or len(expected_odds_list) != len(selection_ids):
                raise ValidationError("Datos de apuesta simple incompletos o malformados.")
            
            success_count = 0
            for i in range(len(selection_ids)):
                sel_id = selection_ids[i]
                stake_val = Decimal(stakes[i].strip().replace(",", "."))
                odds_val = Decimal(expected_odds_list[i].strip().replace(",", "."))
                
                try:
                    place_simple_bet(
                        user=request.user,
                        selection_id=sel_id,
                        stake=stake_val,
                        expected_odds=odds_val,
                        idempotency_key=f"{idempotency_key}_{i}",
                        use_bonus=use_bonus,
                    )
                    success_count += 1
                except ValidationError as e:
                    messages.warning(request, f"No se pudo colocar una selección: {getattr(e, 'message', str(e))}")
                except ValueError as e:
                    from apps.wallet.selectors import get_wallet_balance
                    if str(e) == "Saldo insuficiente.":
                        balance = get_wallet_balance(request.user)
                        messages.warning(request, f"Saldo insuficiente para una selección. Balance: {balance:.2f} fichas.")
                    else:
                        messages.warning(request, f"Error en una selección: {str(e)}")
            
            if success_count > 0:
                messages.success(request, f"¡{success_count} apuesta(s) simple(s) colocada(s) con éxito!")

    except ValidationError as e:
        messages.error(request, f"Error: {getattr(e, 'message', str(e))}")
    except ValueError as e:
        # Check if the ValueError is due to insufficient balance
        from apps.wallet.selectors import get_wallet_balance
        if str(e) == "Saldo insuficiente.":
            balance = get_wallet_balance(request.user)
            messages.error(request, f"Saldo insuficiente. Tu balance actual es: {balance:.2f} fichas.")
        else:
            messages.error(request, f"Error: {str(e)}")
    except InvalidOperation:
        messages.error(request, "La cuota o el monto tienen un formato inválido.")
    except IntegrityError:
        messages.info(request, "Esta apuesta ya fue procesada (doble clic detectado).")
    except DataError as e:
        messages.error(request, f"Error de datos: {e}")

    # Si redirigimos al referer, mostramos la alerta. Redirigimos a Mis Apuestas o se queda en la página?
    # Para la experiencia, redirigiremos a "Mis Apuestas" para que el usuario vea su boleto.
    return redirect("betting:mis_apuestas")


@login_required
@require_POST
def ejecutar_cashout(request, bet_id):
    bet = get_object_or_404(Bet, id=bet_id, user=request.user)
    current_odds_str = request.POST.get("current_odds")

    try:
        if not current_odds_str:
            raise ValidationError("No se especificó la cuota actual para el cálculo.")

        current_odds = Decimal(current_odds_str.strip().replace(",", "."))

        cash_out_bet(bet=bet, current_odds=current_odds, house_factor=Decimal("0.9000"))
        messages.success(request, "Cash-out procesado y fondos transferidos.")
    except (ValidationError, ValueError) as e:
        messages.error(request, f"No se pudo ejecutar el Cash-out: {getattr(e, 'message', str(e))}")
    except InvalidOperation:
        messages.error(request, "Formato de cuota inválido al procesar el Cash-out.")

    return redirect("betting:mis_apuestas")