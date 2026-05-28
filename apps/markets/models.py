import uuid
from django.db import models


class Event(models.Model):
    """
    Evento deportivo con su ciclo de vida completo.
    Estado inicial siempre SCHEDULED.
    """

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Programado"
        LIVE = "LIVE", "En vivo"
        FINISHED = "FINISHED", "Finalizado"
        SUSPENDED = "SUSPENDED", "Suspendido"
        CANCELLED = "CANCELLED", "Cancelado"

    class Sport(models.TextChoices):
        FOOTBALL = "Fútbol", "Fútbol"
        BASKETBALL = "Baloncesto", "Baloncesto"
        TENNIS = "Tenis", "Tenis"
        VOLLEYBALL = "Vóley", "Vóley"
        BASEBALL = "Béisbol", "Béisbol"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    sport = models.CharField(max_length=50, choices=Sport.choices, default=Sport.FOOTBALL)

    starts_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    suspended_until = models.DateTimeField(null=True, blank=True)

    # Marcador en vivo (in-play state).
    home_score = models.PositiveSmallIntegerField(default=0)
    away_score = models.PositiveSmallIntegerField(default=0)
    # Momento real en que el partido pasó a LIVE (puede diferir de starts_at).
    live_started_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "evento"
        ordering = ["starts_at"]

    def __str__(self):
        return f"{self.name} ({self.sport}) — {self.status}"


class Market(models.Model):
    """
    Mercado de apuesta dentro de un evento.
    Ejemplo: 1X2 (resultado final), Over/Under 2.5 goles.
    """

    class Kind(models.TextChoices):
        MATCH_RESULT = "1X2", "Resultado (1X2)"
        OVER_UNDER = "OU", "Más/Menos (Over/Under)"
        BOTH_TEAMS_SCORE = "BTTS", "Ambos equipos anotan"
        HANDICAP = "HCAP", "Handicap asiático"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="markets")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "mercado"

    def __str__(self):
        return f"{self.name} [{self.kind}] — {'Activo' if self.is_active else 'Inactivo'}"

    @property
    def sorted_selections(self):
        """Devuelve las selecciones ordenadas lógicamente (Local, Empate, Visitante)."""
        selections = list(self.selections.all())
        def sort_key(sel):
            name = sel.name.lower()
            if "local" in name: return 1
            if "empate" in name or "draw" in name or name.strip() == "x": return 2
            if "visit" in name or "away" in name: return 3
            return 4
        return sorted(selections, key=sort_key)


class Selection(models.Model):
    """
    Opción apostable dentro de un mercado con su cuota (odds).
    Ejemplo: 'Gana Local' con odds 2.50
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    market = models.ForeignKey(
        Market, on_delete=models.CASCADE, related_name="selections"
    )
    name = models.CharField(max_length=100)
    odds = models.DecimalField(max_digits=10, decimal_places=4)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "seleccion"

    def __str__(self):
        return f"{self.name} @ {self.odds}"
