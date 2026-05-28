from rest_framework import serializers

from core.money import normalize_money


class MoneyAmountField(serializers.DecimalField):
    def to_internal_value(self, data):
        if isinstance(data, float):
            raise serializers.ValidationError("Money amounts must not be floats.")
        return normalize_money(data)


class WalletAmountSerializer(serializers.Serializer):
    amount = MoneyAmountField(max_digits=18, decimal_places=4)


class BonusRedeemSerializer(serializers.Serializer):
    code = serializers.RegexField(
        regex=r"^[A-Za-z0-9_-]{3,32}$",
        max_length=32,
        trim_whitespace=True,
        error_messages={"invalid": "Codigo promocional invalido."},
    )
