from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections

from apps.wallet.models import Transaction
from apps.wallet.selectors import get_wallet_balance
from apps.wallet.services import deposit_simulated, withdraw_simulated


def ledger_balance_for(transaction):
    balance = Decimal("0.0000")

    for entry in transaction.entries.all():
        if entry.direction == "CREDIT":
            balance += entry.amount
        elif entry.direction == "DEBIT":
            balance -= entry.amount

    return balance


@pytest.mark.django_db(transaction=True)
def test_concurrent_withdrawals_do_not_overspend_wallet():
    user = get_user_model().objects.create_user(username="concurrent-withdraw")
    deposit_simulated(user=user, amount="100.0000", created_by=user)

    attempts = 5
    withdraw_amount = Decimal("30.0000")
    start = Barrier(attempts)

    def run_withdrawal():
        close_old_connections()
        try:
            start.wait()
            transaction = withdraw_simulated(
                user=user,
                amount=withdraw_amount,
                created_by=user,
            )
            return ("success", transaction.pk)
        except ValueError:
            return ("insufficient_balance", None)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=attempts) as executor:
        results = list(executor.map(lambda _index: run_withdrawal(), range(attempts)))

    successes = [transaction_id for status, transaction_id in results if status == "success"]
    failures = [status for status, _transaction_id in results if status != "success"]

    assert successes
    assert failures
    assert len(successes) <= 3
    assert len(failures) == attempts - len(successes)

    final_balance = get_wallet_balance(user)
    assert final_balance == Decimal("100.0000") - (withdraw_amount * len(successes))
    assert final_balance >= Decimal("0.0000")

    assert Transaction.objects.filter(kind="WITHDRAWAL").count() == len(successes)

    for transaction in Transaction.objects.all():
        assert transaction.entries.count() >= 2
        assert ledger_balance_for(transaction) == Decimal("0.0000")
