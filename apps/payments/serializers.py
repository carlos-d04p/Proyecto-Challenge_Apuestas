from decimal import Decimal

from rest_framework import serializers


class PaymentAmountSerializer(serializers.Serializer):
    """
    RB-PAY-01: amount manejado como Decimal(18,4), nunca float.
    Los límites concretos (min/max depósito y mínimo retiro) los aplica
    `apps.wallet.services` para mantener una sola fuente de verdad.
    """

    amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        coerce_to_string=False,
        min_value=Decimal("0.0001"),
    )
