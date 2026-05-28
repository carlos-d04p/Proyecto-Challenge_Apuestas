from rest_framework import serializers
from .models import Event, Market, Selection


class SelectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Selection
        fields = ["id", "name", "odds", "is_active", "updated_at"]


class MarketSerializer(serializers.ModelSerializer):
    selections = SelectionSerializer(many=True, read_only=True)

    class Meta:
        model = Market
        fields = ["id", "event", "kind", "name", "is_active", "selections"]


class EventSerializer(serializers.ModelSerializer):
    markets = MarketSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "sport",
            "starts_at",
            "status",
            "suspended_until",
            "created_at",
            "updated_at",
            "markets",
        ]


class EventListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados (sin mercados anidados)."""

    class Meta:
        model = Event
        fields = ["id", "name", "sport", "starts_at", "status"]
