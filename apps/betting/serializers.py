from rest_framework import serializers
from .models import Bet, BetSelection
from apps.markets.serializers import SelectionSerializer

class BetSelectionSerializer(serializers.ModelSerializer):
    selection = SelectionSerializer(read_only=True)
    
    class Meta:
        model = BetSelection
        fields = ['id', 'selection', 'odds_at_placement']

class BetSerializer(serializers.ModelSerializer):
    selections = BetSelectionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Bet
        fields = [
            'id', 'user', 'stake', 'payout', 'total_odds', 
            'status', 'bet_type', 'created_at', 'selections'
        ]
        read_only_fields = ['id', 'user', 'payout', 'status', 'created_at']