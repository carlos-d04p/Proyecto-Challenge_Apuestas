from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import PerfilKYC
from apps.wallet.bonus_services import (
    BonusAlreadyRedeemed,
    BonusNotEligible,
    BonusNotFound,
    BonusWithdrawalBlocked,
    get_bonus_balance,
    redeem_bonus_code,
    seed_default_bonus_campaigns,
)
from apps.wallet.models import BonusCampaign, LedgerEntry, Transaction, UserBonus
from apps.wallet.services import deposit_simulated, withdraw_simulated


def create_user(username):
    return get_user_model().objects.create_user(username=username)


def assert_transaction_is_balanced(transaction):
    balance = Decimal("0.0000")
    for entry in transaction.entries.all():
        if entry.direction == "CREDIT":
            balance += entry.amount
        elif entry.direction == "DEBIT":
            balance -= entry.amount

    assert balance == Decimal("0.0000")


def create_kyc_profile(user, **overrides):
    data = {
        "user": user,
        "dni": str(abs(hash(user.username)))[:8].zfill(8),
        "birth_date": date(2000, 1, 1),
        "status": PerfilKYC.Status.VERIFIED,
    }
    data.update(overrides)
    return PerfilKYC.objects.create(**data)


@pytest.mark.django_db
def test_seed_default_bonus_campaigns_creates_three_campaigns():
    seed_default_bonus_campaigns()
    seed_default_bonus_campaigns()

    assert BonusCampaign.objects.count() == 3
    assert set(BonusCampaign.objects.values_list("code", flat=True)) == {
        "BIENVENIDA",
        "PRIMERA_RECARGA",
        "JUEGO_RESPONSABLE",
    }


@pytest.mark.django_db
def test_redeem_welcome_bonus_once_and_credit_bonus_balance():
    user = create_user("bonus-welcome")

    result = redeem_bonus_code(user, "bienvenida")

    assert result["status"] == "applied"
    assert result["amount"] == "50.0000"
    assert get_bonus_balance(user) == Decimal("50.0000")
    assert UserBonus.objects.filter(user=user, campaign__code="BIENVENIDA").count() == 1
    assert LedgerEntry.objects.filter(
        account="BONUS",
        account_owner=user,
        direction="CREDIT",
        amount=Decimal("50.0000"),
    ).exists()


@pytest.mark.django_db
def test_welcome_bonus_double_redemption_fails():
    user = create_user("bonus-welcome-duplicate")
    redeem_bonus_code(user, "BIENVENIDA")

    with pytest.raises(BonusAlreadyRedeemed):
        redeem_bonus_code(user, "BIENVENIDA")

    assert UserBonus.objects.filter(user=user, campaign__code="BIENVENIDA").count() == 1
    assert Transaction.objects.filter(description="BONUS_PROMO:BIENVENIDA").count() == 1


@pytest.mark.django_db
def test_first_deposit_bonus_fails_without_sufficient_first_deposit():
    user = create_user("bonus-first-no-deposit")

    with pytest.raises(BonusNotEligible):
        redeem_bonus_code(user, "PRIMERA_RECARGA")

    assert UserBonus.objects.count() == 0


@pytest.mark.django_db
def test_first_deposit_bonus_credits_thirty_when_condition_is_met():
    user = create_user("bonus-first-ok")
    deposit_simulated(user=user, amount="100.0000", created_by=user)

    result = redeem_bonus_code(user, "PRIMERA_RECARGA")

    assert result["amount"] == "30.0000"
    assert get_bonus_balance(user) == Decimal("30.0000")
    assert UserBonus.objects.filter(user=user, campaign__code="PRIMERA_RECARGA").exists()


@pytest.mark.django_db
def test_responsible_gaming_bonus_credits_twenty_when_limit_exists():
    user = create_user("bonus-rg-ok")
    create_kyc_profile(user, daily_deposit_limit=Decimal("150.0000"))

    result = redeem_bonus_code(user, "JUEGO_RESPONSABLE")

    assert result["amount"] == "20.0000"
    assert get_bonus_balance(user) == Decimal("20.0000")
    assert UserBonus.objects.filter(user=user, campaign__code="JUEGO_RESPONSABLE").exists()


@pytest.mark.django_db
def test_unknown_bonus_code_raises_controlled_error():
    user = create_user("bonus-invalid")

    with pytest.raises(BonusNotFound):
        redeem_bonus_code(user, "NO_EXISTE")

    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0


@pytest.mark.django_db
def test_bonus_transaction_is_balanced():
    user = create_user("bonus-balanced")

    redeem_bonus_code(user, "BIENVENIDA")
    transaction = Transaction.objects.get(description="BONUS_PROMO:BIENVENIDA")

    assert_transaction_is_balanced(transaction)
    assert transaction.entries.count() == 2


@pytest.mark.django_db
def test_bonus_balance_is_derived_from_ledger_entries():
    user = create_user("bonus-derived")
    redeem_bonus_code(user, "BIENVENIDA")

    user_bonus = UserBonus.objects.get(user=user, campaign__code="BIENVENIDA")
    user_bonus.amount = Decimal("1.0000")
    user_bonus.save(update_fields=["amount"])

    assert get_bonus_balance(user) == Decimal("50.0000")


@pytest.mark.django_db
def test_withdrawal_is_blocked_until_bonus_bets_are_completed():
    user = create_user("bonus-withdraw-blocked")
    deposit_simulated(user=user, amount="100.0000", created_by=user)
    redeem_bonus_code(user, "BIENVENIDA")

    with pytest.raises(BonusWithdrawalBlocked):
        withdraw_simulated(user=user, amount="10.0000", created_by=user)

    assert Transaction.objects.filter(kind="WITHDRAWAL").count() == 0
