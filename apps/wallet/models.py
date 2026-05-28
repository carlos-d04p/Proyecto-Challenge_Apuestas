import uuid
from decimal import Decimal
from inspect import signature

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


def check_constraint(*, condition, name):
    constraint_kwargs = {"name": name}
    if "condition" in signature(models.CheckConstraint).parameters:
        constraint_kwargs["condition"] = condition
    else:
        constraint_kwargs["check"] = condition
    return models.CheckConstraint(**constraint_kwargs)


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


class BonusType(models.TextChoices):
    WELCOME = "WELCOME", "Welcome"
    FIRST_DEPOSIT = "FIRST_DEPOSIT", "First deposit"
    RESPONSIBLE_GAMING = "RESPONSIBLE_GAMING", "Responsible gaming"


class UserBonusStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    EXPIRED = "EXPIRED", "Expired"


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
            models.Index(
                fields=["account", "account_owner"],
                name="ledger_account_owner_idx",
            ),
            models.Index(fields=["created_at"], name="ledger_created_at_idx"),
        ]
        constraints = [
            check_constraint(
                condition=models.Q(amount__gt=Decimal("0.0000")),
                name="ledger_amount_gt_zero",
            ),
            check_constraint(
                condition=(
                    models.Q(
                        account=LedgerAccount.HOUSE,
                        account_owner__isnull=True,
                    )
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


class BonusCampaign(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    bonus_type = models.CharField(max_length=32, choices=BonusType.choices)
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    is_active = models.BooleanField(default=True)
    required_bets_count = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"], name="bonus_campaign_code_idx"),
            models.Index(fields=["bonus_type"], name="bonus_campaign_type_idx"),
            models.Index(fields=["is_active"], name="bonus_campaign_active_idx"),
        ]
        constraints = [
            check_constraint(
                condition=models.Q(amount__gt=Decimal("0.0000")),
                name="bonus_campaign_amount_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class UserBonus(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallet_bonuses",
    )
    campaign = models.ForeignKey(
        BonusCampaign,
        on_delete=models.PROTECT,
        related_name="redemptions",
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name="bonus_redemptions",
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    status = models.CharField(
        max_length=16,
        choices=UserBonusStatus.choices,
        default=UserBonusStatus.ACTIVE,
    )
    required_bets_count = models.PositiveIntegerField(default=5)
    completed_bets_count = models.PositiveIntegerField(default=0)
    is_withdrawable = models.BooleanField(default=False)
    redeemed_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "campaign"],
                name="user_bonus_user_campaign_uniq",
            ),
            check_constraint(
                condition=models.Q(amount__gt=Decimal("0.0000")),
                name="user_bonus_amount_gt_zero",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="user_bonus_user_status_idx"),
            models.Index(fields=["campaign"], name="user_bonus_campaign_idx"),
            models.Index(fields=["redeemed_at"], name="user_bonus_redeemed_idx"),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.campaign.code}"
