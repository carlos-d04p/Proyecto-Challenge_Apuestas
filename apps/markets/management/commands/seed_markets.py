"""
Comando para poblar la base de datos con eventos y mercados de ejemplo.
Uso: python manage.py seed_markets
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.markets.models import Event, Market, Selection


# Margen del operador (5%). Afecta los odds: odds_reales / (1 + margen)
OPERATOR_MARGIN = Decimal("0.05")


def apply_margin(raw_odds: Decimal) -> Decimal:
    """Aplica el margen del operador a una cuota bruta."""
    return (raw_odds / (1 + OPERATOR_MARGIN)).quantize(Decimal("0.0001"))


class Command(BaseCommand):
    help = "Carga eventos deportivos y mercados de ejemplo para desarrollo"

    def handle(self, *args, **options):
        self.stdout.write("Limpiando datos anteriores...")
        Selection.objects.all().delete()
        Market.objects.all().delete()
        Event.objects.all().delete()

        now = timezone.now()

        events_data = [
            {
                "name": "Perú vs Argentina",
                "sport": "Fútbol",
                "starts_at": now + timedelta(hours=2),
                "status": Event.Status.SCHEDULED,
            },
            {
                "name": "Real Madrid vs Barcelona",
                "sport": "Fútbol",
                "starts_at": now + timedelta(days=1),
                "status": Event.Status.SCHEDULED,
            },
            {
                "name": "Lakers vs Warriors",
                "sport": "Baloncesto",
                "starts_at": now + timedelta(hours=5),
                "status": Event.Status.LIVE,
            },
            {
                "name": "Djokovic vs Alcaraz",
                "sport": "Tenis",
                "starts_at": now - timedelta(hours=3),
                "status": Event.Status.FINISHED,
            },
        ]

        for edata in events_data:
            event = Event.objects.create(**edata)
            self._create_markets(event)
            self.stdout.write(f"  [OK] {event.name} ({event.status})")

        self.stdout.write(self.style.SUCCESS(
            f"\n{Event.objects.count()} eventos, "
            f"{Market.objects.count()} mercados, "
            f"{Selection.objects.count()} selecciones creados."
        ))

    def _create_markets(self, event: Event):
        # ── Mercado 1X2 ──────────────────────────────────────────────────────
        m1x2 = Market.objects.create(
            event=event,
            kind=Market.Kind.MATCH_RESULT,
            name="Resultado Final",
        )
        for name, raw in [("Gana Local", "2.10"), ("Empate", "3.40"), ("Gana Visitante", "3.20")]:
            Selection.objects.create(
                market=m1x2,
                name=name,
                odds=apply_margin(Decimal(raw)),
            )

        # ── Over / Under 2.5 ─────────────────────────────────────────────────
        if event.sport == "Fútbol":
            mou = Market.objects.create(
                event=event,
                kind=Market.Kind.OVER_UNDER,
                name="Más / Menos 2.5 Goles",
            )
            for name, raw in [("Más de 2.5", "1.90"), ("Menos de 2.5", "1.95")]:
                Selection.objects.create(
                    market=mou,
                    name=name,
                    odds=apply_margin(Decimal(raw)),
                )

            # ── BTTS ─────────────────────────────────────────────────────────
            mbtts = Market.objects.create(
                event=event,
                kind=Market.Kind.BOTH_TEAMS_SCORE,
                name="Ambos Equipos Anotan",
            )
            for name, raw in [("Sí", "1.80"), ("No", "2.05")]:
                Selection.objects.create(
                    market=mbtts,
                    name=name,
                    odds=apply_margin(Decimal(raw)),
                )

            # ── Handicap asiático ─────────────────────────────────────────────
            mhcap = Market.objects.create(
                event=event,
                kind=Market.Kind.HANDICAP,
                name="Handicap Asiático -1",
            )
            for name, raw in [("Local -1", "2.20"), ("Visitante +1", "1.70")]:
                Selection.objects.create(
                    market=mhcap,
                    name=name,
                    odds=apply_margin(Decimal(raw)),
                )
