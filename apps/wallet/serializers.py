from rest_framework import serializers

from core.money import normalize_money


class MoneyAmountField(serializers.DecimalField):
    def to_internal_value(self, data):
        if isinstance(data, float):
            raise serializers.ValidationError("Money amounts must not be floats.")
        return normalize_money(data)


class WalletAmountSerializer(serializers.Serializer):
    amount = MoneyAmountField(max_digits=18, decimal_places=4)
