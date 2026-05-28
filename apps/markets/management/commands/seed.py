from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import uuid

from apps.wallet.models import LedgerAccount, LedgerDirection, LedgerEntry, Transaction, TransactionKind
from apps.markets.models import Event, EventStatus, Market, MarketType, Selection, SelectionStatus

User = get_user_model()

class Command(BaseCommand):
    help = "Pobla la base de datos con usuarios y eventos de prueba"

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando seedeo de la base de datos...")

        # 1. Crear usuarios
        users_data = [
            {"username": "arnold", "email": "arnold@example.com", "password": "password123", "balance": 100.00},
            {"username": "sleyter", "email": "sleyter@example.com", "password": "password123", "balance": 500.00},
            {"username": "walter", "email": "walter@example.com", "password": "password123", "balance": 1000.00},
        ]
        
        users = []
        for u_data in users_data:
            user, created = User.objects.get_or_create(username=u_data["username"], defaults={"email": u_data["email"]})
            if created:
                user.set_password(u_data["password"])
                user.is_staff = True
                user.save()
                
                # Crear depósito
                tx = Transaction.objects.create(
                    created_by=user,
                    kind=TransactionKind.DEPOSIT,
                    reference=f"seed_deposit_{user.id}",
                )
                LedgerEntry.objects.create(
                    transaction=tx,
                    account=LedgerAccount.USER_WALLET,
                    direction=LedgerDirection.CREDIT,
                    amount=Decimal(u_data["balance"])
                )
                self.stdout.write(self.style.SUCCESS(f"Usuario {user.username} creado con balance {u_data['balance']}"))
            users.append(user)

        # 2. Crear Eventos
        if not Event.objects.filter(name="Real Madrid vs Barcelona").exists():
            event1 = Event.objects.create(
                name="Real Madrid vs Barcelona",
                category="Fútbol",
                scheduled_start=timezone.now() + timezone.timedelta(days=1),
                status=EventStatus.SCHEDULED
            )
            
            market1 = Market.objects.create(
                event=event1,
                market_type=MarketType.MATCH_WINNER,
                name="Ganador del Partido"
            )
            
            Selection.objects.create(market=market1, name="Real Madrid", odds=Decimal("1.80"))
            Selection.objects.create(market=market1, name="Empate", odds=Decimal("3.50"))
            Selection.objects.create(market=market1, name="Barcelona", odds=Decimal("2.90"))

            self.stdout.write(self.style.SUCCESS(f"Evento {event1.name} creado con éxito"))

        if not Event.objects.filter(name="Lakers vs Bulls").exists():
            event2 = Event.objects.create(
                name="Lakers vs Bulls",
                category="Baloncesto",
                scheduled_start=timezone.now() - timezone.timedelta(hours=1),
                status=EventStatus.LIVE
            )
            
            market2 = Market.objects.create(
                event=event2,
                market_type=MarketType.MATCH_WINNER,
                name="Ganador del Partido"
            )
            
            Selection.objects.create(market=market2, name="Lakers", odds=Decimal("1.50"))
            Selection.objects.create(market=market2, name="Bulls", odds=Decimal("2.60"))
            self.stdout.write(self.style.SUCCESS(f"Evento {event2.name} creado con éxito"))

        self.stdout.write(self.style.SUCCESS("¡Seedeo completado con éxito!"))
