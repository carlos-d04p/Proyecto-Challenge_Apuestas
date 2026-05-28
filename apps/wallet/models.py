import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class TransactionKind(models.TextChoices):
    DEPOSIT = "DEPOSIT", "Deposit"
    WITHDRAWAL = "WITHDRAWAL", "Withdrawal"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER", "Internal transfer"
    BET_PLACEMENT = "BET_PLACEMENT", "Bet placement"
    BET_PAYOUT = "BET_PAYOUT", "Bet payout"
    BET_LOSS = "BET_LOSS", "Bet loss"
    BET_REFUND = "BET_REFUND", "Bet refund"
    CASHOUT = "CASHOUT", "Cashout"


class LedgerAccount(models.TextChoices):
    USER_WALLET = "USER_WALLET", "User wallet"
    HOUSE = "HOUSE", "House"
    PENDING_BETS = "PENDING_BETS", "Pending bets"
    BONUS = "BONUS", "Bonus"


class LedgerDirection(models.TextChoices):
    DEBIT = "DEBIT", "Debit"
    CREDIT = "CREDIT", "Credit"


class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=TransactionKind.choices)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallet_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"], name="wallet_tx_created_at_idx"),
        ]

    def __str__(self):
        return f"{self.kind} {self.id}"


class LedgerEntry(models.Model):
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    account = models.CharField(max_length=32, choices=LedgerAccount.choices)
    account_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    direction = models.CharField(max_length=6, choices=LedgerDirection.choices)
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["transaction"], name="ledger_tx_idx"),
            models.Index(fields=["account", "account_owner"], name="ledger_account_owner_idx"),
            models.Index(fields=["created_at"], name="ledger_created_at_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=Decimal("0.0000")),
                name="ledger_amount_gt_zero",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(account=LedgerAccount.HOUSE, account_owner__isnull=True)
                    | models.Q(
                        account__in=[
                            LedgerAccount.USER_WALLET,
                            LedgerAccount.PENDING_BETS,
                            LedgerAccount.BONUS,
                        ],
                        account_owner__isnull=False,
                    )
                ),
                name="ledger_account_owner_required",
            ),
        ]

    def __str__(self):
        return f"{self.direction} {self.account} {self.amount}"


class WalletIdempotencyRecord(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallet_idempotency_records",
    )
    key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name="idempotency_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key"],
                name="wallet_idempotency_user_key_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "key"], name="wallet_idem_user_key_idx"),
            models.Index(fields=["created_at"], name="wallet_idem_created_at_idx"),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.key}"
