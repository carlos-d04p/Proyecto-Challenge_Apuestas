from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Event, Market, Selection
from .serializers import (
    EventSerializer,
    EventListSerializer,
    MarketSerializer,
    SelectionSerializer,
)


class EventViewSet(viewsets.ModelViewSet):
    """
    Endpoints para eventos deportivos.

    list:   GET  /api/markets/events/
    detail: GET  /api/markets/events/{id}/
    create: POST /api/markets/events/         (solo staff)
    update: PUT  /api/markets/events/{id}/    (solo staff)
    delete: DEL  /api/markets/events/{id}/    (solo staff)

    Filtros disponibles: ?sport=Fútbol  ?status=LIVE
    Búsqueda:            ?search=Real Madrid
    """

    queryset = Event.objects.all().prefetch_related("markets__selections")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["sport", "status"]
    search_fields = ["name", "sport"]
    ordering_fields = ["starts_at", "status"]
    ordering = ["starts_at"]

    def get_serializer_class(self):
        # En el listado usamos el serializer ligero (sin mercados anidados)
        if self.action == "list":
            return EventListSerializer
        return EventSerializer

    @action(detail=True, methods=["get"], url_path="markets")
    def markets(self, request, pk=None):
        """GET /api/markets/events/{id}/markets/ — mercados de un evento."""
        event = self.get_object()
        markets = event.markets.filter(is_active=True).prefetch_related("selections")
        serializer = MarketSerializer(markets, many=True)
        return Response(serializer.data)


class MarketViewSet(viewsets.ModelViewSet):
    """
    Endpoints para mercados.

    GET /api/markets/markets/
    GET /api/markets/markets/{id}/
    GET /api/markets/markets/{id}/selections/
    """

    queryset = Market.objects.all().select_related("event")
    serializer_class = MarketSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["event", "kind", "is_active"]

    @action(detail=True, methods=["get"], url_path="selections")
    def selections(self, request, pk=None):
        """GET /api/markets/markets/{id}/selections/ — selecciones con cuotas."""
        market = self.get_object()
        selections = market.selections.filter(is_active=True)
        serializer = SelectionSerializer(selections, many=True)
        return Response(serializer.data)


class SelectionViewSet(viewsets.ModelViewSet):
    """
    Endpoints para selecciones (opciones apostables con cuota).

    GET /api/markets/selections/
    GET /api/markets/selections/{id}/
    """

    queryset = Selection.objects.all().select_related("market__event")
    serializer_class = SelectionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["market", "is_active"]
