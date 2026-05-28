import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from apps.markets.models import Event, Market, Selection
from django.utils import timezone
from datetime import timedelta
import copy
from django.template import context

# Patch Django's BaseContext.__copy__ to support Python 3.14
def _base_context_copy(self):
    cls = self.__class__
    duplicate = cls.__new__(cls)
    duplicate.__dict__.update(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate

context.BaseContext.__copy__ = _base_context_copy


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def event(db):
    return Event.objects.create(
        name="Real Madrid vs Barcelona",
        sport="Fútbol",
        starts_at=timezone.now() + timedelta(days=1),
        status=Event.Status.SCHEDULED,
    )


@pytest.fixture
def market(db, event):
    return Market.objects.create(
        event=event,
        kind=Market.Kind.MATCH_RESULT,
        name="Resultado Final",
        is_active=True,
    )


@pytest.fixture
def selections(db, market):
    Selection.objects.create(market=market, name="Gana Local", odds="2.5000")
    Selection.objects.create(market=market, name="Empate", odds="3.2000")
    Selection.objects.create(market=market, name="Gana Visitante", odds="2.8000")


# ── Eventos ──────────────────────────────────────────────────────────────────

class TestEventList:
    def test_listar_eventos(self, api_client, event):
        url = reverse("markets_api:event-list")
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Real Madrid vs Barcelona"

    def test_filtrar_por_deporte(self, api_client, event):
        url = reverse("markets_api:event-list") + "?sport=Fútbol"
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_filtrar_por_estado(self, api_client, event):
        url = reverse("markets_api:event-list") + "?status=SCHEDULED"
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_buscar_por_nombre(self, api_client, event):
        url = reverse("markets_api:event-list") + "?search=Madrid"
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) == 1


class TestEventDetail:
    def test_detalle_evento(self, api_client, event):
        url = reverse("markets_api:event-detail", kwargs={"pk": event.pk})
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["id"] == str(event.id)
        assert response.data["sport"] == "Fútbol"

    def test_evento_inexistente(self, api_client, db):
        import uuid
        url = reverse("markets_api:event-detail", kwargs={"pk": uuid.uuid4()})
        response = api_client.get(url)
        assert response.status_code == 404


class TestEventMarkets:
    def test_mercados_de_evento(self, api_client, event, market, selections):
        url = reverse("markets_api:event-markets", kwargs={"pk": event.pk})
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["kind"] == "1X2"


# ── Mercados ──────────────────────────────────────────────────────────────────

class TestMarketSelections:
    def test_selecciones_de_mercado(self, api_client, market, selections):
        url = reverse("markets_api:market-selections", kwargs={"pk": market.pk})
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 3

    def test_odds_son_decimal(self, api_client, market, selections):
        url = reverse("markets_api:market-selections", kwargs={"pk": market.pk})
        response = api_client.get(url)
        assert response.status_code == 200
        for sel in response.data:
            odds = float(sel["odds"])
            assert odds > 1.0, "Los odds siempre deben ser mayores a 1"


# ── Modelos ───────────────────────────────────────────────────────────────────

class TestEventModel:
    def test_estado_inicial_es_scheduled(self, db):
        event = Event.objects.create(
            name="Test Event",
            sport="Baloncesto",
            starts_at=timezone.now() + timedelta(hours=2),
        )
        assert event.status == Event.Status.SCHEDULED

    def test_str_evento(self, event):
        assert "Real Madrid vs Barcelona" in str(event)
        assert "Fútbol" in str(event)


class TestMarketModel:
    def test_mercado_activo_por_defecto(self, market):
        assert market.is_active is True

    def test_str_mercado(self, market):
        assert "Resultado Final" in str(market)


class TestSelectionModel:
    def test_seleccion_str(self, db, market):
        sel = Selection.objects.create(market=market, name="Gana Local", odds="2.5000")
        assert "Gana Local" in str(sel)
        assert "2.5000" in str(sel)
