from django.db import models
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
# pyrefly: ignore [missing-import]
from apps.markets.models import Selection

class Bet(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"      # Creada pero sin descontar saldo (temporal)
        PLACED = "PLACED", "Colocada"         # Aceptada y saldo descontado
        WON = "WON", "Ganada"                 
        LOST = "LOST", "Perdida"
        VOID = "VOID", "Anulada"
        CASHED_OUT = "CASHED_OUT", "Retirada (Cash-out)"

    class Type(models.TextChoices):
        SINGLE = "SINGLE", "Simple"
        ACCA = "ACCA", "Combinada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bets")
    
    stake = models.DecimalField(max_digits=18, decimal_places=4)
    payout = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    
    total_odds = models.DecimalField(max_digits=10, decimal_places=4)
    
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    bet_type = models.CharField(max_length=10, choices=Type.choices, default=Type.SINGLE)

    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "apuesta"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.id} - {self.user} - {self.status}"

    @property
    def current_odds(self):
        if self.status != self.Status.PLACED:
            return self.total_odds
        current_odds = Decimal("1.0000")
        for sel in self.selections.all():
            selection = sel.selection
            market = selection.market
            event = market.event
            name = selection.name.lower()
            
            # Evaluación in-play: si está matemáticamente perdida, la cuota cae a 0.
            if market.kind == "OU":
                try:
                    # Extraer el límite, ej. "Menos de 2.5" -> 2.5
                    limit_str = [word for word in name.split() if word.replace(".","").isdigit()][0]
                    limit = float(limit_str)
                    total_score = event.home_score + event.away_score
                    
                    if "menos" in name or "under" in name:
                        if total_score > limit:
                            return Decimal("0.0000")
                except:
                    pass
            elif market.kind == "BTTS":
                if ("no" in name) and (event.home_score > 0 and event.away_score > 0):
                    return Decimal("0.0000")
                    
            current_odds *= selection.odds
            
        return current_odds

    @property
    def current_cashout_value(self):
        if self.status != self.Status.PLACED:
            return None
        current = self.current_odds
        house_factor = Decimal("0.90")
        if current == Decimal("0.0000"):
            return Decimal("0.0000")
        payout = (self.stake * (self.total_odds / current) * house_factor).quantize(Decimal("0.0001"))
        return payout


class BetSelection(models.Model):
    class Result(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        WON = "WON", "Ganada"
        LOST = "LOST", "Perdida"
        VOID = "VOID", "Anulada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bet = models.ForeignKey(Bet, on_delete=models.CASCADE, related_name="selections")
    selection = models.ForeignKey(Selection, on_delete=models.PROTECT)

    odds_at_placement = models.DecimalField(max_digits=10, decimal_places=4)
    result = models.CharField(
        max_length=10,
        choices=Result.choices,
        default=Result.PENDING,
    )

    class Meta:
        db_table = "apuesta_seleccion"
        unique_together = ("bet", "selection")

    def __str__(self):
        return f"{self.bet_id} -> {self.selection.name} @ {self.odds_at_placement}"