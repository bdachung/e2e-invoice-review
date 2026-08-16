"""HTTP access to the fixed GL catalog."""

from fastapi import APIRouter

from app.accounting.catalog import list_gl_accounts
from app.accounting.models import GeneralLedgerAccount

router = APIRouter(prefix="/api/accounting", tags=["accounting"])


@router.get("/gl-accounts", response_model=list[GeneralLedgerAccount])
def get_gl_accounts() -> tuple[GeneralLedgerAccount, ...]:
    return list_gl_accounts()
