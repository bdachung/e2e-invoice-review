"""Lookup helpers for the fixed fictional Northstar GL catalog."""

from app.accounting.models import (
    GENERAL_LEDGER_CATALOG,
    GeneralLedgerAccount,
)


def get_gl_account(code: str) -> GeneralLedgerAccount | None:
    return next(
        (account for account in GENERAL_LEDGER_CATALOG if account.code.value == code),
        None,
    )


def list_gl_accounts() -> tuple[GeneralLedgerAccount, ...]:
    return GENERAL_LEDGER_CATALOG
