from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction as db_transaction
from django.utils import timezone

from apps.compliance.services import append_audit_event
from apps.wallet.models import (
    BonusCampaign,
    BonusType,
    LedgerAccount,
    LedgerDirection,
    LedgerEntry,
    Transaction,
    TransactionKind,
    UserBonus,
    UserBonusStatus,
)
from apps.wallet.selectors import get_account_balance
from apps.wallet.services import (
    _create_entry,
    _lock_users_in_order,
    _validate_transaction_is_balanced,
)
from core.money import normalize_money


BONUS_REDEEMED_EVENT = "WALLET_BONUS_REDEEMED"
BONUS_TRANSACTION_DESCRIPTION_PREFIX = "BONUS_PROMO:"
FIRST_DEPOSIT_MINIMUM = Decimal("100.0000")

DEFAULT_BONUS_CAMPAIGNS = (
    {
        "code": "BIENVENIDA",
        "name": "Bono de bienvenida",
        "bonus_type": BonusType.WELCOME,
        "amount": Decimal("50.0000"),
        "required_bets_count": 5,
    },
    {
        "code": "PRIMERA_RECARGA",
        "name": "Bono de primera recarga",
        "bonus_type": BonusType.FIRST_DEPOSIT,
        "amount": Decimal("30.0000"),
        "required_bets_count": 5,
    },
    {
        "code": "JUEGO_RESPONSABLE",
        "name": "Bono de juego responsable",
        "bonus_type": BonusType.RESPONSIBLE_GAMING,
        "amount": Decimal("20.0000"),
        "required_bets_count": 5,
    },
)


class BonusError(ValueError):
    code = "bonus_error"


class BonusNotFound(BonusError):
    code = "invalid_code"


class BonusInactive(BonusError):
    code = "inactive_bonus"


class BonusAlreadyRedeemed(BonusError):
    code = "already_used"


class BonusNotEligible(BonusError):
    code = "not_eligible"


class BonusWithdrawalBlocked(BonusError):
    code = "bonus_not_withdrawable"


def seed_default_bonus_campaigns():
    campaigns = []
    for campaign_data in DEFAULT_BONUS_CAMPAIGNS:
        code = campaign_data["code"]
        defaults = {
            "name": campaign_data["name"],
            "bonus_type": campaign_data["bonus_type"],
            "amount": normalize_money(campaign_data["amount"]),
            "is_active": True,
            "required_bets_count": campaign_data["required_bets_count"],
        }
        campaign, _created = BonusCampaign.objects.update_or_create(
            code=code,
            defaults=defaults,
        )
        campaigns.append(campaign)
    return campaigns


def get_bonus_balance(user):
    return get_account_balance(user, LedgerAccount.BONUS)


def get_available_bonuses(user):
    seed_default_bonus_campaigns()
    campaigns = BonusCampaign.objects.order_by("id")
    redemptions = {
        redemption.campaign_id: redemption
        for redemption in UserBonus.objects.filter(user=user).select_related("campaign")
    }

    bonuses = []
    for campaign in campaigns:
        redemption = redemptions.get(campaign.id)
        status = "available"
        reason = ""
        if not campaign.is_active:
            status = "inactive"
            reason = "Bono no disponible."
        elif redemption is not None:
            status = "already_used"
            reason = "Bono ya utilizado."
        else:
            try:
                _validate_campaign_eligibility(user=user, campaign=campaign)
            except BonusNotEligible as exc:
                status = "not_eligible"
                reason = str(exc)

        bonuses.append(_serialize_campaign(campaign, status, reason, redemption))
    return bonuses


def redeem_bonus_code(user, code):
    normalized_code = _normalize_code(code)
    seed_default_bonus_campaigns()

    with db_transaction.atomic():
        locked_user = _lock_users_in_order(user)[user.pk]
        campaign = (
            BonusCampaign.objects.select_for_update()
            .filter(code=normalized_code)
            .first()
        )
        if campaign is None:
            raise BonusNotFound("Codigo promocional invalido.")
        if not campaign.is_active:
            raise BonusInactive("Bono no disponible.")
        if UserBonus.objects.select_for_update().filter(
            user=locked_user,
            campaign=campaign,
        ).exists():
            raise BonusAlreadyRedeemed("Bono ya utilizado.")

        _validate_campaign_eligibility(user=locked_user, campaign=campaign)
        amount = normalize_money(campaign.amount)
        wallet_transaction = Transaction.objects.create(
            kind=TransactionKind.INTERNAL_TRANSFER,
            description=f"{BONUS_TRANSACTION_DESCRIPTION_PREFIX}{campaign.code}",
            created_by=locked_user,
        )
        entries = [
            _create_entry(
                transaction=wallet_transaction,
                account=LedgerAccount.HOUSE,
                account_owner=None,
                direction=LedgerDirection.DEBIT,
                amount=amount,
            ),
            _create_entry(
                transaction=wallet_transaction,
                account=LedgerAccount.BONUS,
                account_owner=locked_user,
                direction=LedgerDirection.CREDIT,
                amount=amount,
            ),
        ]
        _validate_transaction_is_balanced(entries)

        try:
            user_bonus = UserBonus.objects.create(
                user=locked_user,
                campaign=campaign,
                transaction=wallet_transaction,
                amount=amount,
                status=UserBonusStatus.ACTIVE,
                required_bets_count=campaign.required_bets_count,
                completed_bets_count=0,
                is_withdrawable=False,
            )
        except IntegrityError as exc:
            raise BonusAlreadyRedeemed("Bono ya utilizado.") from exc

        _emit_bonus_audit_event(
            transaction=wallet_transaction,
            user=locked_user,
            amount=amount,
            campaign=campaign,
        )
        return _serialize_redeemed_bonus(user_bonus)


def validate_bonus_withdrawal(user, amount):
    normalize_money(amount)
    active_locked_bonus = UserBonus.objects.filter(
        user=user,
        status=UserBonusStatus.ACTIVE,
        is_withdrawable=False,
    ).exists()
    if not active_locked_bonus:
        return

    # Los bonos y sus ganancias asociadas no son retirables hasta que el usuario complete al menos 5 apuestas validas.
    raise BonusWithdrawalBlocked(
        "Los bonos y sus ganancias asociadas no son retirables hasta completar 5 apuestas validas."
    )


def _normalize_code(code):
    normalized = str(code or "").strip().upper()
    if not normalized:
        raise BonusNotFound("Codigo promocional invalido.")
    return normalized


def _validate_campaign_eligibility(*, user, campaign):
    if not getattr(user, "is_authenticated", False):
        raise BonusNotEligible("Usuario no autenticado.")
    if not user.is_active:
        raise BonusNotEligible("Usuario no elegible para bonos.")

    if campaign.bonus_type == BonusType.WELCOME:
        _validate_kyc_not_blocked(user)
        return
    if campaign.bonus_type == BonusType.FIRST_DEPOSIT:
        _validate_first_deposit_bonus(user)
        return
    if campaign.bonus_type == BonusType.RESPONSIBLE_GAMING:
        _validate_responsible_gaming_bonus(user)
        return

    raise BonusNotEligible("Bono no elegible.")


def _validate_kyc_not_blocked(user):
    profile = _get_kyc_profile(user)
    if profile is None:
        return
    status = getattr(profile, "status", "")
    if status == "BLOCKED" or getattr(profile, "is_autoexcluido", False):
        raise BonusNotEligible("Usuario bloqueado o autoexcluido.")


def _validate_first_deposit_bonus(user):
    first_deposit = (
        LedgerEntry.objects.filter(
            account=LedgerAccount.USER_WALLET,
            account_owner=user,
            direction=LedgerDirection.CREDIT,
            transaction__kind=TransactionKind.DEPOSIT,
        )
        .order_by("transaction__created_at", "created_at", "id")
        .first()
    )
    if first_deposit is None or first_deposit.amount < FIRST_DEPOSIT_MINIMUM:
        raise BonusNotEligible(
            "Requiere una primera recarga simulada de al menos 100.0000 fichas."
        )


def _validate_responsible_gaming_bonus(user):
    profile = _get_kyc_profile(user)
    if profile is None:
        raise BonusNotEligible("Configura un perfil KYC con limites de deposito.")
    _validate_kyc_not_blocked(user)
    has_limit = any(
        getattr(profile, field) is not None
        for field in (
            "daily_deposit_limit",
            "weekly_deposit_limit",
            "monthly_deposit_limit",
        )
    )
    if not has_limit:
        raise BonusNotEligible("Configura al menos un limite de deposito.")


def _get_kyc_profile(user):
    try:
        return user.perfil_kyc
    except ObjectDoesNotExist:
        return None


def _serialize_campaign(campaign, status, reason, redemption=None):
    return {
        "code": campaign.code,
        "name": campaign.name,
        "bonus_type": campaign.bonus_type,
        "amount": f"{campaign.amount:.4f}",
        "status": status,
        "reason": reason,
        "required_bets_count": (
            redemption.required_bets_count if redemption else campaign.required_bets_count
        ),
        "completed_bets_count": redemption.completed_bets_count if redemption else 0,
        "is_withdrawable": redemption.is_withdrawable if redemption else False,
    }


def _serialize_redeemed_bonus(user_bonus):
    return {
        "status": "applied",
        "code": user_bonus.campaign.code,
        "name": user_bonus.campaign.name,
        "bonus_type": user_bonus.campaign.bonus_type,
        "amount": f"{user_bonus.amount:.4f}",
        "bonus_balance": f"{get_bonus_balance(user_bonus.user):.4f}",
        "transaction_id": str(user_bonus.transaction_id),
        "required_bets_count": user_bonus.required_bets_count,
        "completed_bets_count": user_bonus.completed_bets_count,
        "is_withdrawable": user_bonus.is_withdrawable,
        "message": (
            "Bono aplicado. No es retirable hasta completar 5 apuestas validas."
        ),
    }


def _emit_bonus_audit_event(*, transaction, user, amount, campaign):
    append_audit_event(
        event_type=BONUS_REDEEMED_EVENT,
        payload={
            "transaction_id": str(transaction.id),
            "user_id": str(user.pk),
            "amount": str(amount),
            "kind": "BONUS_REDEEM",
            "bonus_code": campaign.code,
            "bonus_type": campaign.bonus_type,
            "timestamp": transaction.created_at.isoformat(),
        },
    )


__all__ = [
    "BONUS_REDEEMED_EVENT",
    "BonusAlreadyRedeemed",
    "BonusError",
    "BonusInactive",
    "BonusNotEligible",
    "BonusNotFound",
    "BonusWithdrawalBlocked",
    "get_available_bonuses",
    "get_bonus_balance",
    "redeem_bonus_code",
    "seed_default_bonus_campaigns",
    "validate_bonus_withdrawal",
]
