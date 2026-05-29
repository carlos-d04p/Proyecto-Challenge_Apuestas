import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from decimal import Decimal
from apps.markets.models import Event, Market, Selection
from datetime import timedelta

events_data = [
    {
        "name": "Arsenal vs Manchester City",
        "sport": Event.Sport.FOOTBALL,
        "starts_at": timezone.now() + timedelta(days=2),
        "status": Event.Status.SCHEDULED,
        "home_score": 0,
        "away_score": 0,
        "markets": [
            {
                "name": "Ganador del Partido",
                "type": Market.Kind.MATCH_RESULT,
                "selections": [
                    {"name": "Arsenal", "odds": Decimal("2.80")},
                    {"name": "Empate", "odds": Decimal("3.20")},
                    {"name": "Manchester City", "odds": Decimal("2.10")}
                ]
            },
            {
                "name": "Más de 2.5 Goles",
                "type": Market.Kind.OVER_UNDER,
                "selections": [
                    {"name": "Más 2.5", "odds": Decimal("1.70")},
                    {"name": "Menos 2.5", "odds": Decimal("2.10")}
                ]
            }
        ]
    },
    {
        "name": "Nadal vs Djokovic",
        "sport": Event.Sport.TENNIS,
        "starts_at": timezone.now() - timedelta(minutes=45),
        "status": Event.Status.LIVE,
        "home_score": 2,
        "away_score": 1,
        "markets": [
            {
                "name": "Ganador del Partido",
                "type": Market.Kind.MATCH_RESULT,
                "selections": [
                    {"name": "Nadal", "odds": Decimal("1.40")},
                    {"name": "Djokovic", "odds": Decimal("2.90")}
                ]
            }
        ]
    },
    {
        "name": "Boston Celtics vs Miami Heat",
        "sport": Event.Sport.BASKETBALL,
        "starts_at": timezone.now() - timedelta(minutes=90),
        "status": Event.Status.LIVE,
        "home_score": 105,
        "away_score": 98,
        "markets": [
            {
                "name": "Ganador del Partido",
                "type": Market.Kind.MATCH_RESULT,
                "selections": [
                    {"name": "Boston Celtics", "odds": Decimal("1.10")},
                    {"name": "Miami Heat", "odds": Decimal("6.50")}
                ]
            }
        ]
    },
    {
        "name": "Perú vs Colombia",
        "sport": Event.Sport.FOOTBALL,
        "starts_at": timezone.now() + timedelta(days=5),
        "status": Event.Status.SCHEDULED,
        "home_score": 0,
        "away_score": 0,
        "markets": [
            {
                "name": "Ganador del Partido",
                "type": Market.Kind.MATCH_RESULT,
                "selections": [
                    {"name": "Perú", "odds": Decimal("3.50")},
                    {"name": "Empate", "odds": Decimal("3.00")},
                    {"name": "Colombia", "odds": Decimal("2.00")}
                ]
            },
            {
                "name": "Ambos Equipos Anotan",
                "type": Market.Kind.BOTH_TEAMS_SCORE,
                "selections": [
                    {"name": "Sí", "odds": Decimal("1.85")},
                    {"name": "No", "odds": Decimal("1.90")}
                ]
            }
        ]
    },
    {
        "name": "Italia vs Brasil",
        "sport": Event.Sport.VOLLEYBALL,
        "starts_at": timezone.now() + timedelta(hours=3),
        "status": Event.Status.SCHEDULED,
        "home_score": 0,
        "away_score": 0,
        "markets": [
            {
                "name": "Ganador del Partido",
                "type": Market.Kind.MATCH_RESULT,
                "selections": [
                    {"name": "Italia", "odds": Decimal("1.95")},
                    {"name": "Brasil", "odds": Decimal("1.85")}
                ]
            }
        ]
    },
    {
        "name": "Yankees vs Red Sox",
        "sport": Event.Sport.BASEBALL,
        "starts_at": timezone.now() - timedelta(minutes=120),
        "status": Event.Status.LIVE,
        "home_score": 4,
        "away_score": 7,
        "markets": [
            {
                "name": "Ganador del Partido",
                "type": Market.Kind.MATCH_RESULT,
                "selections": [
                    {"name": "Yankees", "odds": Decimal("3.20")},
                    {"name": "Red Sox", "odds": Decimal("1.35")}
                ]
            }
        ]
    }
]

for edata in events_data:
    event = Event.objects.create(
        name=edata["name"],
        sport=edata["sport"],
        starts_at=edata["starts_at"],
        status=edata["status"],
        home_score=edata["home_score"],
        away_score=edata["away_score"]
    )
    if edata["status"] == Event.Status.LIVE:
        event.live_started_at = timezone.now() - timedelta(minutes=60)
        event.save()
        
    for mdata in edata["markets"]:
        market = Market.objects.create(
            event=event,
            name=mdata["name"],
            kind=mdata["type"]
        )
        for sdata in mdata["selections"]:
            Selection.objects.create(
                market=market,
                name=sdata["name"],
                odds=sdata["odds"]
            )
            
print("Events seeded successfully!")
