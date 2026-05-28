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